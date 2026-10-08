import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'SPAD.neXt Documentation',
  tagline: 'Simulation Panel Advanced Drivers: neXt Generation',
  favicon: 'img/favicon.ico',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Go-live cutover happened 2026-10-08 (see SPAD-Migration/spad-docs/README.md).
  // docs.spadnext.net remains available as a staging domain, but this is the
  // canonical URL used for the sitemap, canonical link tags and social cards.
  url: 'https://docs.spadnext.com',
  baseUrl: '/',

  organizationName: 'SPAD-neXt',
  projectName: 'spad-docs',

  onBrokenLinks: 'throw',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  markdown: {
    // The CMS's `sidebar_position` field is optional (widget: number,
    // required: false); when an editor saves an entry without setting it,
    // Sveltia (like Decap before it) writes `sidebar_position: null` into
    // the frontmatter rather than omitting the key - confirmed live when
    // saving docs/README.mdx broke the build with "sidebar_position must
    // be a number". Docusaurus's own schema accepts a number or an absent
    // key, but not an explicit null (unlike pagination_prev/pagination_next,
    // where null is a valid, intentional value) - so strip it here rather
    // than trust every future CMS save to never reintroduce this.
    parseFrontMatter: async (params) => {
      const result = await params.defaultParseFrontMatter(params);
      if (result.frontMatter.sidebar_position === null) {
        delete result.frontMatter.sidebar_position;
      }
      return result;
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
          // No editUrl: the GitHub "Edit this page" link pointed readers at
          // raw markdown in the repo, bypassing the CMS entirely. Editors
          // should go through /admin instead - see EDITOR_GUIDE.md, linked
          // explicitly from the docs instead of this generated link.
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'SPAD.neXt Documentation',
      logo: {
        alt: 'SPAD.neXt Logo',
        src: 'img/logo.png',
      },
      items: [
        {
          href: 'https://github.com/SPAD-neXt/spad-docs/blob/main/EDITOR_GUIDE.md',
          label: 'Editor Guide',
          position: 'right',
        },
      ],
    },
    footer: {
      links: [],
      copyright: `Copyright © ${new Date().getFullYear()} SPAD.neXt. Built with <a href="https://github.com/facebook/docusaurus" target="_blank" rel="noopener noreferrer">Docusaurus</a>.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
