#!/usr/bin/env node
// Generates a single downloadable PDF export of the whole docs site.
//
// NOT wired into any build/deploy step yet and `docs-to-pdf` is NOT a
// project dependency yet - both are intentionally deferred to when this
// runs on its actual home (one of the maintenance VMs set up for jobs like
// this, not the pve3-web production VM serving the site itself). Before
// running this for real:
//   npm install --save-dev docs-to-pdf
//   npx puppeteer browsers install chrome
// (plus the headless-Chrome system libraries - libatk1.0-0, libatk-bridge2.0-0,
// libcups2, libdrm2, libxkbcommon0, libxcomposite1, libxdamage1, libxfixes3,
// libxrandr2, libgbm1, libasound2t64, libpango-1.0-0, libcairo2, libnss3,
// libnspr4 - on whatever VM ends up running it).
//
// Usage:
//   node scripts/generate-manual-pdf.mjs --docsDir=./build --out=./build/spad-next-manual.pdf
//   node scripts/generate-manual-pdf.mjs --baseUrl=https://docs.spadnext.net --out=./spad-next-manual.pdf
//
// Why a custom script instead of just the `docs-to-pdf` CLI:
//
// 1. Crawl start: the CLI's docusaurus mode walks a single pagination chain
//    from one starting URL. This site's landing page (docs/README.mdx) has
//    `pagination_next: null` (set deliberately, see ensure_site_root_frontmatter()
//    in convert_gitbook_to_mdx.py, to drop a stray "Previous" footer link) - so
//    a crawl starting there stops after one page. Confirmed live: `/about` is
//    the actual first entry in the site's real (alphabetical-by-top-category)
//    reading order, and its pagination chain covers all other pages in one
//    pass, looping back to `/` at the very end. Seeding with `['/', '/about']`
//    picks up the landing page's own content first, then that one complete
//    chain, with no gaps or reordering.
// 2. TOC shape: the CLI always builds one front-page TOC entry per HEADING
//    (h1-h4) across the whole site, which is hundreds of entries for this
//    site's ~160 pages - confirmed unusable in practice. This script keeps
//    the exact same per-heading id-assignment/cross-link-rewriting pipeler
//    (so in-content links between pages and the PDF's native bookmark pane,
//    which independently re-scans the rendered DOM for every heading, are
//    unaffected), but prints only one entry per PAGE (h1) on the front TOC.
//    The bookmark pane already gives a complete per-heading index, so this
//    intentionally does not add a second, redundant detailed index anywhere
//    else in the document.
//
// Everything below the seed list and the TOC-filtering line is otherwise the
// same page-crawl -> cover+TOC+content assembly -> PDF pipeline as
// `docs-to-pdf docusaurus`, reusing its own exported building blocks rather
// than reimplementing them, so it stays in sync with that package's actual
// behavior (heading-id scheme, link sanitization, outline/bookmark
// generation, etc.) instead of drifting from it over time.

import { parseArgs } from 'node:util';
import * as puppeteer from 'puppeteer-core';
import { chromeExecPath } from 'docs-to-pdf/lib/browser.js';
import * as utils from 'docs-to-pdf/lib/utils.js';
import * as links from 'docs-to-pdf/lib/links.js';
import { PDF } from 'docs-to-pdf/lib/pdf/generate.js';
import {
  checkBuildDir,
  startDocusaurusServer,
  stopDocusaurusServer,
} from 'docs-to-pdf/lib/provider/docusaurus.js';

const { values: args } = parseArgs({
  options: {
    docsDir: { type: 'string' },
    baseUrl: { type: 'string' },
    out: { type: 'string', default: 'spad-next-manual.pdf' },
    coverTitle: { type: 'string', default: 'SPAD.neXt Documentation' },
    noSandbox: { type: 'boolean', default: true },
  },
});

if (!args.docsDir && !args.baseUrl) {
  console.error('Usage: generate-manual-pdf.mjs (--docsDir=<path> | --baseUrl=<url>) [--out=<file>] [--coverTitle=<title>]');
  process.exit(1);
}
if (args.docsDir && args.baseUrl) {
  console.error('Pass either --docsDir or --baseUrl, not both.');
  process.exit(1);
}

// Docusaurus v3's default theme selectors (see docs-to-pdf's own
// provider/docusaurus.ts for the version-1/2/3 variants this mirrors).
const CONTENT_SELECTOR = 'main';
const PAGINATION_SELECTOR = 'a.pagination-nav__link.pagination-nav__link--next';
const EXCLUDE_SELECTORS = [
  '.margin-vert--xl a',
  "[class^='tocCollapsible']",
  '.breadcrumbs',
  '.theme-edit-this-page',
];

// See the file header: '/' alone (pagination_next: null) plus '/about' (the
// real first page in reading order, whose pagination chain covers the rest).
const SEED_PATHS = ['/', '/about'];

/**
 * Same shape as docs-to-pdf's own `generateTocFromChunks` (utils.ts), except
 * the printed front-page TOC list is filtered down to level-1 (one per page)
 * headings. Heading id assignment and cross-page link rewriting - which the
 * PDF's native bookmark pane and in-content page links both depend on - are
 * untouched, so only what's *printed* on the TOC page changes.
 */
function buildOnePerPageToc(chunks, { tocTitle }) {
  const maxLevel = 4;
  const headers = [];
  const anchorMap = {};
  const re = new RegExp('<h[1-' + maxLevel + '](.+?)</h[1-' + maxLevel + ']( )*>', 'gs');

  const staged = chunks.map(({ url, html }) => {
    const pageKey = links.normalizePageKey(url, url) ?? '/';
    const pageSlug = links.buildPageSlug(pageKey);
    const pageTopId = `page-top-${pageSlug}`;
    const entry = { pageTopId, headings: {} };

    const modified = html.replace(re, (matchedStr) => {
      const { headerText, headerId, level, originalId } = utils.generateHeader(
        headers,
        matchedStr,
        pageSlug,
      );
      headers.push({ header: headerText, level, id: headerId });
      if (originalId) {
        entry.headings[originalId] = headerId;
      }
      return utils.replaceHeader(matchedStr, headerId, maxLevel);
    });

    anchorMap[pageKey] = entry;
    return { url, html: `<a id="${pageTopId}"></a>${modified}` };
  });

  const modifiedContentHTML = staged
    .map((chunk) => links.rewriteContentLinks(chunk.html, anchorMap, chunk.url))
    .join('');

  const onePerPage = headers.filter((h) => h.level === 1);
  const tocHTML = utils.generateTocHtml(onePerPage, tocTitle);

  return { modifiedContentHTML, tocHTML };
}

async function crawl(page, seedUrls) {
  const contentChunks = [];
  const visitedURLs = new Set();

  for (const seedUrl of seedUrls) {
    let nextPageURL = seedUrl;

    while (nextPageURL) {
      if (visitedURLs.has(nextPageURL)) {
        console.log(`Skipping already-visited URL (pagination loop closed): ${nextPageURL}`);
        break;
      }
      visitedURLs.add(nextPageURL);

      console.log(`Retrieving ${nextPageURL}`);
      await page.goto(nextPageURL, { waitUntil: 'networkidle0', timeout: 0 });

      await utils.openDetails(page);
      contentChunks.push({
        url: nextPageURL,
        html: await utils.getHtmlContent(page, CONTENT_SELECTOR),
      });

      nextPageURL = await utils.findNextUrl(page, PAGINATION_SELECTOR);
    }
  }

  return contentChunks;
}

async function generate({ originUrl, outputPDFFilename, coverTitle, puppeteerArgs }) {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: chromeExecPath(),
    args: puppeteerArgs,
    protocolTimeout: 600_000,
  });

  try {
    const page = await browser.newPage();
    const seedUrls = SEED_PATHS.map((path) => new URL(path, originUrl).toString());

    const contentChunks = await crawl(page, seedUrls);
    console.log(`Crawled ${contentChunks.length} pages.`);

    const coverHTML = utils.generateCoverHtml(coverTitle, '', '');
    const { modifiedContentHTML, tocHTML } = buildOnePerPageToc(contentChunks, {
      tocTitle: 'Table of contents',
    });

    await page.goto(seedUrls[0], { waitUntil: 'networkidle0' });
    await page.evaluate(
      utils.concatHtml,
      coverHTML,
      tocHTML,
      modifiedContentHTML,
      false,
      false,
      originUrl,
    );
    await utils.removeExcludeSelector(page, EXCLUDE_SELECTORS);
    await page.addStyleTag({ content: utils.DEFAULT_PDF_STYLESHEET });

    const { scrollPageToBottom } = await import('puppeteer-autoscroll-down');
    await scrollPageToBottom(page, {});

    const pdf = new PDF({
      outputPDFFilename,
      paperFormat: 'A4',
      pdfMargin: { top: 32, right: 32, bottom: 32, left: 32 },
    });
    await pdf.generate(page, coverHTML);
  } finally {
    await browser.close();
  }
}

async function main() {
  const puppeteerArgs = args.noSandbox ? ['--no-sandbox', '--disable-setuid-sandbox'] : [];

  if (args.baseUrl) {
    await generate({
      originUrl: args.baseUrl,
      outputPDFFilename: args.out,
      coverTitle: args.coverTitle,
      puppeteerArgs,
    });
    return;
  }

  await checkBuildDir(args.docsDir);
  const server = await startDocusaurusServer(args.docsDir);
  try {
    await generate({
      originUrl: `http://127.0.0.1:${server.port}`,
      outputPDFFilename: args.out,
      coverTitle: args.coverTitle,
      puppeteerArgs,
    });
  } finally {
    await stopDocusaurusServer(server);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
