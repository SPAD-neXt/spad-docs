"""
GitBook -> Docusaurus MDX converter, adapted for the SPAD.neXt documentation.

Forked from (and originally written for a different, unrelated project):
  https://github.com/obx-vivien/migrate-from-gitbook-to-docusaurus-starter-script/blob/main/convert_gitbook_to_mdx3.py

Adaptations made for SPAD.neXt (public/spad-docs):
  - Source/output paths reconfigured for this repo's layout (source is a
    sibling repo, ../SPAD.next-docs, output is this repo's docs/ and
    static/img/assets/ - see main() below), instead of a website/docs
    subfolder of the source tree.
  - GitBook `{% embed %}` blocks are rendered as a plain markdown link using
    the embed's caption instead of being silently dropped.
  - `.gitbook/assets/...` image/file references are rewritten more robustly
    (handles filenames containing parentheses/underscore-escapes) and, new
    in this fork, asset filenames containing whitespace or other characters
    that are unsafe for a URL/webpack asset path are sanitized on copy, with
    every reference to them rewritten to match.
  - The narrow arrow/comparison-glyph whitelist (`<-`, `<->`, `<-->`, `<<`)
    was replaced with a general "escape any `<` that can't start a real
    tag/comment" rule, which also removes a double-escaping bug in the old
    glyph-specific regexes.
  - The JSX-open-tag heuristic used while escaping curly braces no longer
    misfires on GitBook's `<PlaceholderName>` documentation convention
    (e.g. `<Guid>`, `<AppVersion>`) - it now only tracks the two real JSX
    components this pipeline emits (`<Tabs>` / `<TabItem>`).
  - Frontmatter `description:` is promoted into the page body before the
    escaping passes run (previously it happened after, so special
    characters in the description leaked into the body unescaped).
  - Dead code copied from the original, unrelated project (vector-search /
    Data Sync / getting-started special-casing in the embed-link-text
    fallback) has been removed.
  - Several additional, narrowly-scoped defects found only after the above
    were fixed and the build got far enough to reach MDX/SSG rendering and
    the broken-link checker: stray mis-encoded control characters in one
    source file are stripped; an HTML `style="..."` string attribute
    (invalid as a React/JSX prop) is converted to the `style={{...}}`
    object form MDX/React requires; internal links to a folder's
    `README.md` (GitBook's own convention, used throughout SUMMARY.md) now
    strip the `README` segment to match the route Docusaurus actually
    generates for a folder's index page; and GitBook's own "I couldn't
    resolve this link" placeholder destinations (`/broken/pages/<id>`, 20
    of them across 3 files - dead links already in the GitBook source,
    with no real URL to recover) are rendered as plain text instead of a
    link to a meaningless target.

No internal SPAD.neXt secrets, IDs, or credentials belong in this file -
it is a public, generic GitBook -> MDX text transform and must stay that way.
"""

import re
import glob
import json
import os
import shutil
import sys
import unicodedata

print("Script starting...")

# ---------------------------------------------------------------------------
# Path configuration
#
# Intended invocation (from public/spad-docs):
#   python3 scripts/convert_gitbook_to_mdx.py [../SPAD.next-docs]
#
# SOURCE_ROOT: the read-only GitBook export to convert (defaults to the
#              sibling ../SPAD.next-docs checkout).
# OUTPUT_ROOT: this repo's docs/ folder (regenerated in place).
# ASSET_SRC_DIR / ASSET_DST_DIR: GitBook's flat asset dump -> this repo's
#              static/img/assets/, sanitizing filenames along the way.
# ---------------------------------------------------------------------------

SOURCE_ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '../SPAD.next-docs')
OUTPUT_ROOT = os.path.abspath('docs')
ASSET_SRC_DIR = os.path.join(SOURCE_ROOT, '.gitbook', 'assets')
ASSET_DST_DIR = os.path.abspath(os.path.join('static', 'img', 'assets'))
SUMMARY_PATH = os.path.join(SOURCE_ROOT, 'SUMMARY.md')


def ensure_valid_frontmatter(content):
    """Ensure the file has valid frontmatter."""
    if content.startswith('---\n'):
        return content
    # Otherwise, try to extract a description
    match = re.search(r'^(.*?)\n\n', content, re.DOTALL)
    if match:
        description = match.group(1).strip()
        if not description.startswith('#'):
            frontmatter = f'---\ndescription: >\n  {description}\n---\n\n'
            content = content[len(match.group(0)):]
            return frontmatter + content
    return content


def find_docs_files_recursive(directory):
    """Find all .md and .mdx files recursively in the given source directory."""
    print(f"[DEBUG] Searching recursively in directory: {directory}")
    all_files = []
    for ext in ['*.md', '*.mdx']:
        pattern = os.path.join(directory, '**', ext)
        files = glob.glob(pattern, recursive=True)
        print(f"[DEBUG] Found {len(files)} {ext} files with pattern {pattern}")
        all_files.extend(files)

    # SUMMARY.md is GitBook's own table of contents (parsed separately by
    # parse_summary_positions() to drive the Docusaurus sidebar order) -
    # it's not a real content page and shouldn't become one.
    before = len(all_files)
    all_files = [f for f in all_files if os.path.basename(f) != 'SUMMARY.md']
    if len(all_files) != before:
        print("[DEBUG] Excluded SUMMARY.md from conversion (table of contents, not a content page)")

    print(f"[DEBUG] Total files found: {len(all_files)}")
    return all_files


def get_output_path(input_file, source_dir, output_dir):
    """Generate output path maintaining folder structure."""
    rel_path = os.path.relpath(input_file, source_dir)

    if rel_path.endswith('.md'):
        rel_path = rel_path[:-3] + '.mdx'

    output_path = os.path.join(output_dir, rel_path)
    print(f"[DEBUG] Input: {input_file} -> Output: {output_path}")
    return output_path


def extract_yaml_frontmatter(lines):
    if lines and lines[0].strip() == '---':
        fm = []
        for i, line in enumerate(lines):
            fm.append(line)
            if line.strip() == '---' and i > 0:
                return fm, lines[i + 1:]
    return [], lines


def strip_stray_control_characters(content):
    """
    Strip stray Unicode C1/C0 control characters (category 'Cc', excluding
    tab/newline/CR) from the source text.

    Found in the wild: hardware-specific/saitek-fip/README.md contains a
    mis-encoded smart-quote (the UTF-8 bytes for U+201C LEFT DOUBLE
    QUOTATION MARK, E2 80 9C, got reinterpreted a byte at a time as
    Latin-1/cp1252 at some point in GitBook's export/import history,
    leaving the literal control codepoints U+0080/U+009C behind instead of
    the intended character). Such bytes are invalid in the rendered HTML
    output and fail Docusaurus's HTML minifier ("Control character in
    input stream"). This is a one-off source data glitch (2 characters,
    1 file, as of this writing) but stripping any stray control character
    generally is a safe, low-risk pass that also protects future
    GitBook re-syncs from the same class of encoding mishap.
    """
    return ''.join(ch for ch in content if not (unicodedata.category(ch) == 'Cc' and ch not in '\t\n\r'))


def fix_inline_style_string_attributes(content):
    """
    Convert HTML `style="css; declarations"` string attributes into the
    JSX object form MDX/React requires (`style={{cssProp: 'value'}}`).

    Found in the wild: extending-and-apis/gauges-and-extensions/README.md
    uses `<mark style="color:red;">...</mark>`. Plain HTML allows a CSS
    string here, but MDX compiles HTML elements to JSX createElement calls,
    and React's `style` prop must be a JS object, not a string - passing a
    string made the page fail server-side rendering with "The `style` prop
    expects a mapping from style properties to values, not a string."

    Runs *after* improved_escape_curly_braces() (see convert_file) so the
    curly braces this introduces aren't themselves escaped to entities.
    """
    def convert(match):
        css = match.group(1)
        declarations = [d.strip() for d in css.split(';') if d.strip()]
        props = []
        for decl in declarations:
            if ':' not in decl:
                continue
            prop, _, val = decl.partition(':')
            prop = prop.strip()
            val = val.strip().replace("'", "\\'")
            camel_prop = re.sub(r'-([a-zA-Z])', lambda m: m.group(1).upper(), prop)
            if camel_prop:
                props.append(f"{camel_prop}: '{val}'")
        return 'style={{' + ', '.join(props) + '}}'

    return re.sub(r'style="([^"]*)"', convert, content)


def collapse_multiline_tables(content):
    """
    One-off structural fix: some GitBook HTML tables have their trailing
    <tr>...</tr> rows split across separate physical lines instead of
    staying on one line like every other table in the corpus. MDX's JSX
    tag-balance tracking loses the open <tbody> across that line break.

    Scoped narrowly to <table>...</table> blocks: collapse any internal
    newlines (and surrounding whitespace) to single spaces so the whole
    table is one physical line/paragraph, matching the rest of the corpus.
    Blocks that are already single-line are left unchanged (no-op).
    """
    def collapse(match):
        block = match.group(0)
        return re.sub(r'\s*\n\s*', ' ', block)

    return re.sub(r'<table\b.*?</table>', collapse, content, flags=re.DOTALL | re.IGNORECASE)


def fix_html_and_escape(content):
    """
    Comprehensive HTML fixing for MDX compatibility.
    """
    print("[DEBUG] fix_html_and_escape called")

    # 1) Normalize <options>...</options>
    def opt(m):
        return f'```txt\n{m.group(1).strip()}\n```'
    content = re.sub(r'<options\b[^>]*>([\s\S]*?)</options>', opt, content, flags=re.IGNORECASE)

    # 2) Convert <pre><code> to code blocks
    def pre(m):
        attrs, code_attrs, code = m.group(1), m.group(2), m.group(3)
        lang = (re.search(r'language-(\w+)', attrs + code_attrs) or [None, None])[1] or ''
        txt = re.sub(r'<[^>]+>', '', code).strip()
        return f'```{lang}\n{txt}\n```'
    content = re.sub(r'<pre([^>]*)><code([^>]*)>([\s\S]*?)</code></pre>', pre, content, flags=re.IGNORECASE)

    # 3) Fix unclosed HTML void-element tags so they self-close.
    # <br>: previously `<br(?!/>)` -> `<br/>` left the *original* trailing
    # '>' behind (e.g. "<br>" -> "<br/>>"). Match the whole tag (with or
    # without an existing trailing slash) and replace it wholesale instead.
    content = re.sub(r'<br\s*/?>', '<br/>', content)
    content = re.sub(r'<img([^>]*?)(?<!/)>', r'<img\1/>', content)
    content = re.sub(r'<hr(?!\s*/>)(?![^>]*>)', '<hr/>', content)
    content = re.sub(r'<input([^>]*?)(?<!/)>', r'<input\1/>', content)

    # 4) GitBook asset path rewriting: `.gitbook/assets/NAME` -> `/img/assets/NAME`.
    #
    # GitBook wraps a link destination in <...> precisely when the filename
    # contains characters (spaces, parentheses, ...) that plain markdown
    # link syntax can't hold, per CommonMark's pointy-bracket destination
    # form - so for wrapped links the filename may legitimately contain ')'
    # and we must capture up to the matching '>', not the first ')'. For
    # unwrapped links/HTML attributes there's no such need. GitBook also
    # backslash-escapes underscores in unwrapped filenames (e.g.
    # "Serial\_Display\_1.png") to avoid triggering markdown italics -
    # strip those backslashes so the captured name matches the real file.
    def strip_md_escapes(name):
        return name.replace('\\', '')

    # Markdown images, wrapped in <...>: `![alt](<../.gitbook/assets/NAME>)`
    content = re.sub(
        r'!\[([^\]]*)\]\(\s*<(?:\.\./)*\.gitbook/assets/([^>]+)>\s*\)',
        lambda m: f'![{m.group(1)}](/img/assets/{strip_md_escapes(m.group(2))})',
        content,
    )
    # Markdown images, unwrapped: `![alt](../.gitbook/assets/NAME)` (optionally `docs/` prefixed)
    content = re.sub(
        r'!\[([^\]]*)\]\(\s*(?:docs/)?(?:\.\./)*\.gitbook/assets/([^)]+)\)',
        lambda m: f'![{m.group(1)}](/img/assets/{strip_md_escapes(m.group(2))})',
        content,
    )
    # HTML <img src="..."> (optionally wrapped in <...> too, GitBook does both)
    content = re.sub(
        r'<img([^>]*?)src="<?(?:docs/)?(?:\.\./)*\.gitbook/assets/([^">]+)>?"([^>]*?)/?>',
        lambda m: f'<img{m.group(1)}src="/img/assets/{strip_md_escapes(m.group(2))}"{m.group(3)}/>',
        content,
    )

    print("[DEBUG] Fixed .gitbook/assets image paths")

    # 5) Convert figure+img to markdown
    def fig(m):
        img_tag = m.group(1)
        src_match = re.search(r'src="([^"]+)"', img_tag)
        alt_match = re.search(r'alt="([^"]*)"', img_tag)
        src = src_match.group(1) if src_match else ''
        alt = alt_match.group(1) if alt_match else ''

        if '.gitbook/assets' in src:
            src = f'/img/assets/{strip_md_escapes(src.split("/")[-1])}'
        elif 'gitbook/assets' in src:
            src = re.sub(r'(?:docs/|\.\./)?\.gitbook/assets/', '/img/assets/', src)
            src = strip_md_escapes(src)

        return f'![{alt}]({src})'

    content = re.sub(r'<figure>\s*(<img[^>]+>)\s*(?:<figcaption>.*?</figcaption>)?\s*</figure>', fig, content, flags=re.IGNORECASE | re.DOTALL)

    # 6) Remove leftover HTML tags
    content = re.sub(r'</?(?:figure|figcaption)>', '', content)

    # 7) Fix any remaining problematic HTML in tables
    content = re.sub(
        r'<span data-gb-custom-inline[^>]*>([^<]*)</span>',
        r'\1',
        content
    )
    content = re.sub(r'<figcaption[^>]*>(.*?)</figcaption>', r'*\1*', content, flags=re.DOTALL)

    print("[DEBUG] fix_html_and_escape completed")
    return content


def fix_gitbook_content_ref_to_cards(content):
    """
    Fix GitBook content-ref blocks by converting them to styled Docusaurus cards.
    """
    print("[DEBUG] fix_gitbook_content_ref_to_cards called")

    content_ref_pattern = r'{% content-ref url="([^"]*)" %}\s*\[([^\]]*)\]\([^)]*\)\s*{% endcontent-ref %}'

    def content_ref_to_card(match):
        url = match.group(1)
        link_text = match.group(2)

        if url.endswith('.md'):
            clean_url = url[:-3]
        elif url.endswith('.mdx'):
            clean_url = url[:-4]
        else:
            clean_url = url

        card_title = link_text.replace('.md', '').replace('-', ' ').title()
        card_description = f'Learn more about {card_title.lower()}'

        card_html = f'''<div className="custom-nav-card">
  <a href="/{clean_url}" className="custom-nav-card-link">
    <div className="custom-nav-card-content">
      <h3 className="custom-nav-card-title">{card_title}</h3>
      <p className="custom-nav-card-description">{card_description}</p>
    </div>
    <div className="custom-nav-card-arrow">›</div>
  </a>
</div>'''
        return card_html

    result = re.sub(content_ref_pattern, content_ref_to_card, content, flags=re.DOTALL)
    return result


def enhanced_convert_gitbook_code_blocks_simple(content):
    """
    Handles GitBook {% code %} block patterns.
    """
    def code_block_replace(match):
        try:
            groups = match.groups()
            if len(groups) == 2:
                title = groups[0]
                language = ""
                code_content = groups[1]
            elif len(groups) == 3:
                title = groups[0]
                language = groups[1] if groups[1] else ""
                code_content = groups[2]
            else:
                return match.group(0)
        except Exception:
            return match.group(0)

        if not language:
            language = "text"
            if title:
                if title.endswith('.fbs'):
                    language = "fbs"
                elif title.endswith('.cpp') or title.endswith('.hpp'):
                    language = "cpp"
                elif title.endswith('.c') or title.endswith('.h'):
                    language = "c"
                elif title.endswith('.cmake') or 'CMake' in title:
                    language = "cmake"
                elif title.endswith('.sh') or title.endswith('.bash'):
                    language = "sh"
                elif title.endswith('.py'):
                    language = "python"
                elif title.endswith('.js'):
                    language = "javascript"
                elif title.endswith('.go'):
                    language = "go"

        if title:
            clean_title = title.replace('"', '')
            result = f'```{language} title="{clean_title}"\n{code_content}\n```'
        else:
            result = f'```{language}\n{code_content}\n```'
        return result

    pattern1 = r'{% code title="(.*?)" %}\s*```([a-zA-Z]*)\s*\n(.*?)\n```\s*{% endcode %}'
    content = re.sub(pattern1, lambda m: code_block_replace(m), content, flags=re.DOTALL)

    pattern2 = r'{% code title="(.*?)" %}\s*```\s*\n(.*?)\n```\s*{% endcode %}'
    content = re.sub(pattern2, lambda m: code_block_replace(m), content, flags=re.DOTALL)

    pattern3 = r'{% code %}\s*```([a-zA-Z]*)\s*\n(.*?)\n```\s*{% endcode %}'
    content = re.sub(pattern3, lambda m: code_block_replace(m), content, flags=re.DOTALL)

    return content


def fix_all_remaining_gitbook_blocks(content):
    """
    Final cleanup function to catch any remaining GitBook patterns that weren't converted.
    """
    remaining_code_blocks = re.findall(r'{% code[^}]*%}.*?{% endcode %}', content, flags=re.DOTALL)
    remaining_hints = re.findall(r'{% hint[^}]*%}.*?{% endhint %}', content, flags=re.DOTALL)
    remaining_content_refs = re.findall(r'{% content-ref[^}]*%}.*?{% endcontent-ref %}', content, flags=re.DOTALL)
    remaining_page_refs = re.findall(r'{% page-ref[^}]*%}', content, flags=re.DOTALL)

    if remaining_code_blocks:
        pattern = r'{% code title="([^"]*)" %}\s*```?\s*\n?(.*?)\n?```?\s*{% endcode %}'
        def simple_code_replace(match):
            title = match.group(1)
            code_content = match.group(2).strip()
            clean_title = title.replace('"', '')
            return f'```text title="{clean_title}"\n{code_content}\n```'
        content = re.sub(pattern, simple_code_replace, content, flags=re.DOTALL)

        pattern2 = r'{% code %}\s*```?\s*\n?(.*?)\n?```?\s*{% endcode %}'
        def simple_code_replace2(match):
            code_content = match.group(1).strip()
            return f'```text\n{code_content}\n```'
        content = re.sub(pattern2, simple_code_replace2, content, flags=re.DOTALL)

    if remaining_hints:
        pattern = r'{% hint style="([^"]*)" %}\s*(.*?)\s*{% endhint %}'
        def hint_replace(match):
            style = match.group(1)
            hint_content = match.group(2).strip()
            style_map = {'info': 'info', 'warning': 'warning', 'danger': 'danger', 'success': 'tip', 'tip': 'tip'}
            admonition_type = style_map.get(style, 'info')
            return f'''<div className="admonition admonition-{admonition_type}">
<div className="admonition-content">

{hint_content}

</div>
</div>'''
        content = re.sub(pattern, hint_replace, content, flags=re.DOTALL)

    if remaining_content_refs:
        content_ref_pattern = r'{% content-ref url="([^"]*)" %}\s*\[([^\]]*)\]\([^)]*\)\s*{% endcontent-ref %}'
        def content_ref_replace(match):
            url = match.group(1)
            link_text = match.group(2)
            if url.endswith('.md'):
                clean_url = url[:-3]
            elif url.endswith('.mdx'):
                clean_url = url[:-4]
            else:
                clean_url = url
            return f'[{link_text}]({clean_url})'
        content = re.sub(content_ref_pattern, content_ref_replace, content, flags=re.DOTALL)

    if remaining_page_refs:
        page_ref_pattern = r'{% page-ref page="([^"]*)" %}'
        def page_ref_replace(match):
            page_url = match.group(1)
            clean_url = page_url[:-3] if page_url.endswith('.md') else page_url
            link_text = clean_url.replace('-', ' ').title()
            return f'[{link_text}]({clean_url})'
        content = re.sub(page_ref_pattern, page_ref_replace, content, flags=re.DOTALL)

    final_remaining = re.findall(r'{% [^}]*%}', content)
    if final_remaining:
        print(f"[DEBUG] WARNING: Still have {len(final_remaining)} GitBook patterns after cleanup, stripping them")
        content = re.sub(r'{% [^}]*%}', '', content)

    return content


YOUTUBE_ID_PATTERN = re.compile(
    r'(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/))'
    r'([A-Za-z0-9_-]{11})'
)


def extract_youtube_id(url):
    """Return the 11-char YouTube video ID for a youtu.be/youtube.com URL, or None."""
    match = YOUTUBE_ID_PATTERN.search(url)
    return match.group(1) if match else None


def render_embed_link(url, caption):
    """
    Render one converted embed as MDX. YouTube URLs (the overwhelming
    majority - 199 of 199 in the SPAD.neXt source) render as a <VideoLink>
    card (thumbnail + play button + caption, globally available via
    src/theme/MDXComponents.tsx - no per-file import needed) instead of a
    bare text link, which was flagged as "extrem unschoen" (plain stacked
    text links, no visual distinction) once seen in the real site. Any
    non-YouTube embed (none currently exist, but kept as a safety net)
    falls back to a plain markdown link.
    """
    video_id = extract_youtube_id(url)
    if video_id:
        safe_title = caption.replace('"', '&quot;') if caption else url
        return f'<VideoLink id="{video_id}" title="{safe_title}" />'
    link_text = caption if caption else url
    return f'[{link_text}]({url})'


def fix_gitbook_embed_blocks(content):
    """
    Convert GitBook embed blocks to a <VideoLink> card for YouTube URLs
    (plain markdown link otherwise), using the embed's own caption text as
    the title/link text (falling back to the URL if there is no caption).

    GitBook embed syntax:
        {% embed url="https://youtu.be/ID" %}
        Some caption text
        {% endembed %}

    The previous implementation matched `{% embed url="..." %}` and
    `{% endembed %}` as two *separate* regexes, so the caption between them
    (and, for practical purposes, the whole point of the block) was dropped
    on the floor and only survived as an orphaned paragraph with no link.
    That was compounded by pipeline ordering: fix_all_remaining_gitbook_blocks()
    runs a generic `{% [^}]*%}` catch-all that strips any GitBook marker it
    doesn't otherwise recognize - if it ran before this function, it would
    delete the `{% embed %}` / `{% endembed %}` markers first and leave this
    function nothing to match at all, which is why this function must run
    before that catch-all (see the call order in convert_file()).
    It also special-cased link text for URLs containing "vector-search" /
    "sync" / "getting-started" - dead code copied from the unrelated
    project this script originated in; SPAD.neXt has no such URLs, and now
    that the real caption is used as link text this fallback logic is
    unnecessary regardless.

    A separate, real quirk in the SPAD.neXt source: 199 `{% embed %}` opens
    exist but only 177 `{% endembed %}` closes do - some embeds (typically
    the last one in a section) are simply never closed by the GitBook
    export. A naive single `open ... non-greedy ... close` regex applied
    with re.sub would, for an unclosed open followed later by an unrelated
    closed embed, incorrectly pair the unclosed open with that *later*
    block's close tag - swallowing the intervening block's own open tag
    into the first block's "caption" and losing its URL entirely. To avoid
    that, each open tag is only allowed to pair with a close tag that
    appears before the *next* open tag; an open with no close in that
    window is treated as a caption-less embed and rendered as `[url](url)`.
    """
    print("[DEBUG] fix_gitbook_embed_blocks called")

    open_pattern = re.compile(r'{% embed url="([^"]*)" %}')
    close_pattern = re.compile(r'{% endembed %}')

    opens = list(open_pattern.finditer(content))
    if not opens:
        return content

    pieces = []
    cursor = 0
    for i, open_match in enumerate(opens):
        pieces.append(content[cursor:open_match.start()])
        url = open_match.group(1)

        next_open_start = opens[i + 1].start() if i + 1 < len(opens) else len(content)
        search_region = content[open_match.end():next_open_start]
        close_match = close_pattern.search(search_region)

        if close_match:
            caption = re.sub(r'\s+', ' ', search_region[:close_match.start()]).strip()
            pieces.append(render_embed_link(url, caption))
            cursor = open_match.end() + close_match.end()
            print(f"[DEBUG] Converted embed block: {url!r} (caption: {caption!r})")
        else:
            # No matching {% endembed %} before the next embed (or EOF):
            # a caption-less embed. Render the URL itself as the title/link text.
            pieces.append(render_embed_link(url, ''))
            cursor = open_match.end()
            print(f"[DEBUG] Converted caption-less/unclosed embed block: {url!r}")

    pieces.append(content[cursor:])
    result = ''.join(pieces)

    remaining = re.findall(r'{% embed|{% endembed', result)
    if remaining:
        print(f"[DEBUG] WARNING: Found {len(remaining)} unconverted embed markers")

    return result


def extract_description_from_frontmatter(content):
    """
    Extract description from frontmatter and add it as page content AFTER the main heading.
    """
    lines = content.split('\n')

    frontmatter_start = -1
    frontmatter_end = -1
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if frontmatter_start == -1:
                frontmatter_start = i
            elif frontmatter_end == -1:
                frontmatter_end = i
                break

    if frontmatter_start == -1 or frontmatter_end == -1:
        return content

    frontmatter_lines = lines[frontmatter_start + 1:frontmatter_end]
    description_text = None
    in_description = False
    description_lines = []

    for line in frontmatter_lines:
        if line.strip().startswith('description:'):
            if ':' in line and not line.strip().endswith('>-'):
                description_text = line.split(':', 1)[1].strip().strip('"\'')
                break
            else:
                in_description = True
                continue
        elif in_description:
            if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                break
            else:
                description_lines.append(line.strip())

    if description_lines:
        description_text = ' '.join(description_lines).strip()

    if not description_text:
        return content

    main_heading_line = -1
    content_lines = lines[frontmatter_end + 1:]

    for i, line in enumerate(content_lines):
        if line.strip().startswith('# ') and not line.strip().startswith('## '):
            main_heading_line = frontmatter_end + 1 + i
            break

    if main_heading_line == -1:
        insert_line = frontmatter_end + 1
        for i in range(frontmatter_end + 1, len(lines)):
            if lines[i].strip() and not lines[i].strip().startswith('import '):
                insert_line = i
                break
    else:
        insert_line = main_heading_line + 1

    lines.insert(insert_line, '')
    lines.insert(insert_line + 1, description_text)
    lines.insert(insert_line + 2, '')

    return '\n'.join(lines)


def fix_admonition_syntax(content):
    """Convert HTML admonition divs to proper Docusaurus admonition syntax."""
    html_admonition_pattern = r'<div className="admonition admonition-(\w+)">\s*<div className="admonition-content">\s*(.*?)\s*</div>\s*</div>'

    def replace_admonition(match):
        admonition_type = match.group(1)
        content_text = match.group(2).strip()
        type_mapping = {'info': 'info', 'tip': 'tip', 'success': 'tip', 'warning': 'warning', 'danger': 'danger'}
        docusaurus_type = type_mapping.get(admonition_type, 'info')
        return f':::{docusaurus_type}\n{content_text}\n:::'

    return re.sub(html_admonition_pattern, replace_admonition, content, flags=re.DOTALL)


def fix_malformed_code_blocks(content):
    """Fix malformed code blocks that have duplicate markers or empty content."""
    content = re.sub(r'```(\w+)(\s+title="[^"]*")?\s*\n\s*\n\s*```(\w+)', r'```\1\2', content)
    content = re.sub(r'```\w*\s*\n\s*\n```\s*\n', '', content)
    content = re.sub(r'```(\w+)(\s+title="[^"]*")?\s*\n\s+\n```', '', content)
    return content


def fix_html_entities(content):
    """Fix common HTML entity issues."""
    content = re.sub(r'&amp;', '&', content)
    return content


def fix_mdx_list_dash(content):
    """Fix list formatting issues in MDX."""
    lines = content.split('\n')
    result = []
    for line in lines:
        if re.match(r'^\s*[•·‣⁃]\s', line):
            line = re.sub(r'^(\s*)[•·‣⁃]\s', r'\1- ', line)
        result.append(line)
    return '\n'.join(result)


def escape_bare_angle_brackets(content):
    """
    Escape any literal '<' in prose that cannot start a real JSX/HTML tag or
    comment, using the &lt; HTML entity.

    Replaces the previous narrow whitelist approach (which only handled
    `<-`, `<->`, `<-->`, `<<` via backtick-wrapping) that still let bare
    `<=`, `<,` etc. through to break MDX parsing, and which had a
    double-escaping bug where the `<-->` and `<-` regexes both fired on the
    same text and produced mismatched/unbalanced backtick counts. Entity
    substitution sidesteps both problems - it never needs to balance
    anything, and is safe inside table cells.

    A '<' is left alone (and thus still eligible to be parsed as JSX/HTML)
    only when immediately followed by a letter, '/', or '!' - i.e. it could
    plausibly start an opening tag, a closing tag, or a comment.
    Frontmatter, fenced code blocks, and inline code spans are left
    untouched.
    """
    lines = content.split('\n')

    frontmatter_start = -1
    frontmatter_end = -1
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if frontmatter_start == -1:
                frontmatter_start = i
            elif frontmatter_end == -1:
                frontmatter_end = i
                break

    in_code_block = False
    result = []
    lines_fixed = 0

    for i, line in enumerate(lines):
        if frontmatter_start != -1 and frontmatter_end != -1 and frontmatter_start <= i <= frontmatter_end:
            result.append(line)
            continue

        stripped = line.strip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            result.append(line)
            continue
        if in_code_block:
            result.append(line)
            continue

        # Preserve inline code spans; only escape the prose parts of the line.
        parts = re.split(r'(`[^`]*`)', line)
        new_parts = []
        changed = False
        for part in parts:
            if len(part) >= 2 and part.startswith('`') and part.endswith('`'):
                new_parts.append(part)
            else:
                escaped = re.sub(r'<(?![A-Za-z/!])', '&lt;', part)
                if escaped != part:
                    changed = True
                new_parts.append(escaped)
        if changed:
            lines_fixed += 1
        result.append(''.join(new_parts))

    if lines_fixed:
        print(f"[DEBUG] escape_bare_angle_brackets: escaped bare '<' on {lines_fixed} lines")

    return '\n'.join(result)


def convert_gitbook_hints(content):
    """Convert GitBook hint blocks to Docusaurus admonitions."""
    hint_pattern = r'{% hint style="([^"]*)" %}\s*(.*?)\s*{% endhint %}'

    def hint_replace(match):
        style = match.group(1)
        hint_content = match.group(2).strip()
        style_map = {'info': 'info', 'warning': 'warning', 'danger': 'danger', 'success': 'tip', 'tip': 'tip'}
        admonition_type = style_map.get(style, 'info')
        return f'''<div className="admonition admonition-{admonition_type}">
<div className="admonition-content">

{hint_content}

</div>
</div>'''

    return re.sub(hint_pattern, hint_replace, content, flags=re.DOTALL)


def convert_gitbook_tabs(content):
    """
    Convert GitBook tabs to Docusaurus Tabs/TabItem components, propagating
    language context from tab titles to empty code blocks within tabs.
    """
    tabs_pattern = r'{% tabs %}\s*(.*?)\s*{% endtabs %}'
    tab_pattern = r'{% tab title="([^"]*)" %}\s*(.*?)\s*{% endtab %}'

    def extract_language_from_title(title):
        title_lower = title.lower().strip()
        if title_lower in ['c++', 'cpp']:
            return 'cpp'
        elif title_lower == 'c' or 'c without' in title_lower:
            return 'c'
        elif 'cmake' in title_lower:
            return 'cmake'
        elif 'bash' in title_lower or 'shell' in title_lower:
            return 'bash'
        elif 'python' in title_lower:
            return 'python'
        elif 'java' in title_lower:
            return 'java'
        elif 'swift' in title_lower:
            return 'swift'
        elif 'kotlin' in title_lower:
            return 'kotlin'
        elif 'dart' in title_lower:
            return 'dart'
        elif 'go' in title_lower or 'golang' in title_lower:
            return 'go'
        else:
            return None

    def fix_code_blocks_in_tab_content(tab_content, language_context):
        if not language_context:
            return tab_content
        empty_code_pattern = r'```\s*\n([^`]+?)\n```'
        def replace_empty_code_block(match):
            return f'```{language_context}\n{match.group(1)}\n```'
        return re.sub(empty_code_pattern, replace_empty_code_block, tab_content, flags=re.DOTALL)

    def tabs_replace(match):
        tabs_content = match.group(1)
        tabs = re.findall(tab_pattern, tabs_content, flags=re.DOTALL)
        if not tabs:
            return match.group(0)

        tab_items = []
        used_values = []

        for i, (title, tab_content) in enumerate(tabs):
            language_context = extract_language_from_title(title)
            if language_context:
                tab_content = fix_code_blocks_in_tab_content(tab_content, language_context)

            title_lower = title.lower().strip()
            if title_lower in ['c++', 'cpp']:
                value = 'cpp'
            elif title_lower == 'c' or 'c without' in title_lower:
                value = 'c'
            elif 'cmake' in title_lower and ('cpp' in title_lower or 'c++' in title_lower):
                value = 'cmakecpp'
            elif 'cmake' in title_lower:
                value = 'cmake'
            else:
                value = re.sub(r'[^a-zA-Z0-9]', '', title_lower)
                if not value:
                    value = f'tab{i+1}'

            original_value = value
            counter = 1
            while value in used_values:
                value = f"{original_value}{counter}"
                counter += 1
            used_values.append(value)

            tab_content = tab_content.strip()
            tab_item = f'<TabItem value="{value}" label="{title}">\n\n{tab_content}\n\n</TabItem>'
            tab_items.append(tab_item)

        tabs_jsx = f'<Tabs>\n' + '\n'.join(tab_items) + '\n</Tabs>'
        return tabs_jsx

    result = re.sub(tabs_pattern, tabs_replace, content, flags=re.DOTALL)
    return result


def fix_text_code_blocks(content):
    """
    Fix code blocks that were converted to 'text' language by detecting the
    actual language. Only touches ```text blocks.
    """
    text_block_pattern = r'^```text\s*\n(.*?)\n```'

    def detect_language_and_replace(match):
        code_content = match.group(1).strip()
        if any(keyword in code_content.lower() for keyword in [
            'cmake_minimum_required', 'project(', 'target_link_libraries',
            'add_executable', 'find_package', 'fetchcontent'
        ]):
            language = 'cmake'
        elif any(keyword in code_content for keyword in ['#include', 'int main(', 'printf(', 'return 0']):
            language = 'c'
        elif any(keyword in code_content for keyword in ['#include', 'std::', 'namespace', 'class ', 'cout']):
            language = 'cpp'
        elif any(keyword in code_content.lower() for keyword in ['npm install', 'yarn add', 'package.json']):
            language = 'bash'
        elif any(keyword in code_content for keyword in ['curl ', 'wget ', 'sudo ', './configure']):
            language = 'bash'
        elif code_content.startswith('$') or code_content.startswith('./'):
            language = 'bash'
        else:
            language = ''

        if language:
            return f'```{language}\n{code_content}\n```'
        return f'```\n{code_content}\n```'

    return re.sub(text_block_pattern, detect_language_and_replace, content, flags=re.DOTALL | re.MULTILINE)


def improved_escape_curly_braces(content):
    """
    Escape curly braces outside of code blocks/inline code so MDX doesn't
    try to parse them as JS expressions.

    JSX-block tracking is intentionally narrow: it only recognizes the two
    real JSX components this pipeline ever emits, <Tabs> and <TabItem>
    (see convert_gitbook_tabs above). The original heuristic matched *any*
    `<Uppercase...>` as an opening JSX tag expecting a later `</Name>`
    close - which also matches GitBook's own `<PlaceholderName>`
    documentation convention (`<Guid>`, `<AppVersion>`, `<SerialVersion>`,
    ...). Those placeholders are never "closed", so `in_jsx_block` got
    stuck true for the remainder of the file, silently disabling brace
    escaping for everything after the first such placeholder. Restricting
    the tracked tag names to the real components removes that false
    trigger while still protecting braces inside genuine <Tabs>/<TabItem>
    blocks.
    """
    lines = content.splitlines()
    result = []
    in_code_block = False
    in_jsx_block = False
    jsx_stack = []

    JSX_TAG_RE = re.compile(r'<(Tabs|TabItem)\b')
    JSX_CLOSE_RE = re.compile(r'</(Tabs|TabItem)>')

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('```'):
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        jsx_open_matches = JSX_TAG_RE.findall(line)
        for tag in jsx_open_matches:
            jsx_stack.append(tag)
            in_jsx_block = True

        jsx_close_matches = JSX_CLOSE_RE.findall(line)
        for tag in jsx_close_matches:
            if jsx_stack and jsx_stack[-1] == tag:
                jsx_stack.pop()
            if not jsx_stack:
                in_jsx_block = False

        should_skip = (
            in_jsx_block or
            stripped.startswith(('import ', 'export ')) or
            '{% ' in stripped or
            stripped.startswith(':::') or
            stripped.startswith('@tab ') or
            re.match(r'^<(Tabs|TabItem)\b', stripped) is not None
        )

        if should_skip:
            result.append(line)
        else:
            parts = re.split(r'(`[^`]*`)', line)
            escaped_parts = []
            for part in parts:
                if part.startswith('`') and part.endswith('`'):
                    escaped_parts.append(part)
                else:
                    escaped_parts.append(part.replace('{', '&#123;').replace('}', '&#125;'))
            result.append(''.join(escaped_parts))

    return '\n'.join(result)


def fix_gitbook_unresolved_page_links(content):
    """
    GitBook itself sometimes can't resolve an internal link (e.g. the
    target page was later deleted or moved) and exports it with a literal
    placeholder destination, `/broken/pages/<id>` (optionally with a
    `#anchor`), instead of a real URL. Found in 3 source files (20 links
    total: SUMMARY.md, old-docs/old-getting-started-guide.md, and
    getting-started/common-tasks-and-issues/spad/spad.next-discord-community.md).

    There is no real URL to recover here - GitBook itself never had one -
    so linking to this placeholder in the new site would just be a dead
    link with a meaningless target. Drop the link and keep its label as
    plain text, which is strictly better than shipping a broken href.
    """
    return re.sub(r'\[([^\]]*)\]\(/broken/pages/[^)]*\)', r'\1', content)


def fix_internal_links(content):
    """
    Fix internal links that still point to .md files.

    Also strips a trailing `README` path segment (e.g. `folder/README` ->
    `folder`): Docusaurus routes a folder's README.md as that folder's own
    index page, with the `README` segment stripped from the route. GitBook's
    own links (most visibly in SUMMARY.md, its table of contents) are
    written the other way, as `folder/README.md`, which without this fix
    never matches the real generated route and shows up as a broken link.
    """
    md_link_pattern = r'\[([^\]]*)\]\(([^)]*\.md[^)]*)\)'

    def fix_link(match):
        link_text = match.group(1)
        link_url = match.group(2)

        if link_url.startswith('http://') or link_url.startswith('https://'):
            return match.group(0)

        if '.md' in link_url:
            parts = link_url.split('.md', 1)
            if len(parts) == 2:
                clean_url = parts[0] + parts[1]
            else:
                clean_url = link_url
        else:
            clean_url = link_url

        path_part, hash_sep, anchor_part = clean_url.partition('#')
        if path_part == 'README':
            # This repo's docs/README.mdx carries `slug: /`, making it the
            # site root - so a bare (no anchor) top-level "README" link
            # means "the site root". Route there explicitly rather than
            # leaving an empty href (which Docusaurus warns about, and
            # which is technically an invalid <a href>).
            path_part = '/'
        elif path_part.endswith('/README'):
            path_part = path_part[:-len('/README')]
        clean_url = path_part + hash_sep + anchor_part

        return f'[{link_text}]({clean_url})'

    return re.sub(md_link_pattern, fix_link, content)


def fix_frontmatter_structure(content):
    """
    Move ALL imports after frontmatter, regardless of current structure.
    """
    lines = content.split('\n')

    jsx_imports = []
    frontmatter_lines = []
    content_lines = []

    for line in lines:
        if line.strip().startswith('import ') and ' from ' in line:
            jsx_imports.append(line)

    frontmatter_start = -1
    frontmatter_end = -1
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if frontmatter_start == -1:
                frontmatter_start = i
            elif frontmatter_end == -1:
                frontmatter_end = i
                break

    if frontmatter_start != -1 and frontmatter_end != -1:
        frontmatter_lines = lines[frontmatter_start:frontmatter_end + 1]
        for i, line in enumerate(lines):
            if frontmatter_start <= i <= frontmatter_end:
                continue
            if line.strip().startswith('import ') and ' from ' in line:
                continue
            content_lines.append(line)
    else:
        for line in lines:
            if not (line.strip().startswith('import ') and ' from ' in line):
                content_lines.append(line)

    result_lines = []
    if frontmatter_lines:
        result_lines.extend(frontmatter_lines)
        result_lines.append('')
    if jsx_imports:
        result_lines.extend(jsx_imports)
        result_lines.append('')
    result_lines.extend(content_lines)

    return '\n'.join(result_lines)


def predict_docusaurus_anchor_id(heading_text):
    """Predict what anchor ID Docusaurus will generate for a heading."""
    clean_text = re.sub(r'[*_`~]', '', heading_text)
    anchor_id = clean_text.lower()
    anchor_id = re.sub(r'[\s\.\(\)\[\]\{\}\/\\:;,\'"!@#$%^&*+=<>?|]', '-', anchor_id)
    anchor_id = re.sub(r'-+', '-', anchor_id)
    anchor_id = anchor_id.strip('-')
    return anchor_id


def extract_headings_from_content(content, file_path):
    """Extract headings from MDX content and their predicted anchor IDs."""
    headings = {}
    heading_pattern = r'^(#{1,6})\s+(.+)$'
    for line in content.split('\n'):
        line = line.strip()
        match = re.match(heading_pattern, line)
        if match:
            heading_text = match.group(2).strip()
            anchor_id = predict_docusaurus_anchor_id(heading_text)
            if anchor_id:
                headings[heading_text] = anchor_id
    return headings


def fix_anchors_with_real_headings(content, all_headings, current_file):
    """Fix anchor links using real heading data from converted files (2nd pass)."""
    anchor_link_pattern = r'\[([^\]]*)\]\(([^)]*#[^)]*)\)'

    def fix_anchor_link(match):
        link_text = match.group(1)
        link_url = match.group(2)

        if link_url.startswith(('http://', 'https://', 'mailto:')):
            return match.group(0)
        if '#' not in link_url:
            return match.group(0)

        if link_url.startswith('#'):
            file_part = ''
            anchor_part = link_url[1:]
        else:
            file_part, anchor_part = link_url.split('#', 1)
            if ' ' in anchor_part:
                anchor_part = anchor_part.split(' ')[0]
            if '"' in anchor_part:
                anchor_part = anchor_part.split('"')[0]
            target_file = file_part + '.mdx' if not file_part.endswith('.mdx') else file_part

        target_headings = None
        for file_path, headings in all_headings.items():
            target_file_name = (file_part + '.mdx' if file_part and not file_part.endswith('.mdx') else file_part) or current_file
            if file_path.endswith(target_file_name) or os.path.basename(file_path) == os.path.basename(target_file_name):
                target_headings = headings
                break
            if target_file_name.replace('/', os.sep) in file_path.replace('/', os.sep):
                target_headings = headings
                break

        if not target_headings:
            return match.group(0)

        original_anchor = anchor_part
        if original_anchor in target_headings.values():
            return match.group(0)

        best_match_anchor = None
        best_score = 0
        for heading_text, correct_anchor in target_headings.items():
            heading_words = set(heading_text.lower().split())
            anchor_words = set(original_anchor.replace('-', ' ').split())
            if heading_words and anchor_words:
                common_words = heading_words.intersection(anchor_words)
                score = len(common_words) / max(len(heading_words), len(anchor_words))
                if score > best_score and score > 0.3:
                    best_match_anchor = correct_anchor
                    best_score = score

        if best_match_anchor and best_match_anchor != original_anchor:
            if file_part:
                fixed_url = f"{file_part}#{best_match_anchor}"
            else:
                fixed_url = f"#{best_match_anchor}"
            return f"[{link_text}]({fixed_url})"

        return match.group(0)

    return re.sub(anchor_link_pattern, fix_anchor_link, content)


# ---------------------------------------------------------------------------
# Asset sanitization (whitespace/unsafe characters in GitBook asset filenames)
# ---------------------------------------------------------------------------

def sanitize_asset_filename(name):
    """
    Produce a URL/webpack-safe filename: only alnum, '-', '_', '.'; runs of
    whitespace become '-'; any other unsafe character also becomes '-';
    repeated '-' are collapsed.
    """
    base, ext = os.path.splitext(name)

    def clean(part):
        part = re.sub(r'\s+', '-', part)
        part = re.sub(r'[^A-Za-z0-9._-]', '-', part)
        part = re.sub(r'-+', '-', part)
        return part.strip('-')

    base = clean(base)
    ext = clean(ext)
    if not base:
        base = 'asset'
    if ext and not ext.startswith('.'):
        ext = '.' + ext
    return base + ext.lower()


def build_asset_rename_map(asset_src_dir):
    """
    Build an old-filename -> new-filename map for every file directly under
    asset_src_dir, sanitizing names and resolving collisions by appending a
    numeric suffix.
    """
    mapping = {}
    used_names = set()

    if not os.path.isdir(asset_src_dir):
        print(f"[WARN] Asset source directory not found: {asset_src_dir}")
        return mapping

    for name in sorted(os.listdir(asset_src_dir)):
        path = os.path.join(asset_src_dir, name)
        if not os.path.isfile(path):
            continue

        new_name = sanitize_asset_filename(name)
        final_name = new_name
        counter = 2
        while final_name in used_names:
            base, ext = os.path.splitext(new_name)
            final_name = f"{base}-{counter}{ext}"
            counter += 1

        used_names.add(final_name)
        mapping[name] = final_name

    renamed = sum(1 for old, new in mapping.items() if old != new)
    print(f"[INFO] Asset rename map: {len(mapping)} assets, {renamed} renamed for URL-safety")
    return mapping


def copy_assets(asset_src_dir, asset_dst_dir, rename_map):
    """Copy every source asset into asset_dst_dir under its sanitized name."""
    if os.path.isdir(asset_dst_dir):
        shutil.rmtree(asset_dst_dir)
    os.makedirs(asset_dst_dir, exist_ok=True)

    for old_name, new_name in rename_map.items():
        src = os.path.join(asset_src_dir, old_name)
        dst = os.path.join(asset_dst_dir, new_name)
        shutil.copy2(src, dst)

    print(f"[INFO] Copied {len(rename_map)} assets to {asset_dst_dir}")


def rewrite_asset_references(output_root, rename_map):
    """
    Rewrite every `/img/assets/OLDNAME` reference in the generated .mdx
    tree to use the sanitized NEWNAME. Longest old names are replaced first
    so no name is accidentally matched as a prefix of another.
    """
    items = sorted(
        ((old, new) for old, new in rename_map.items() if old != new),
        key=lambda kv: -len(kv[0]),
    )
    if not items:
        return

    files_changed = 0
    for dirpath, _dirnames, filenames in os.walk(output_root):
        for filename in filenames:
            if not filename.endswith('.mdx'):
                continue
            file_path = os.path.join(dirpath, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original = content
            for old_name, new_name in items:
                old_ref = f'/img/assets/{old_name}'
                if old_ref in content:
                    content = content.replace(old_ref, f'/img/assets/{new_name}')

            if content != original:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                files_changed += 1

    print(f"[INFO] Rewrote sanitized asset references in {files_changed} files")


def set_frontmatter_field(content, key, value):
    """
    Insert or update a single scalar `key: value` line in a file's YAML
    frontmatter block, leaving every other key untouched. Assumes
    ensure_valid_frontmatter() has already guaranteed a `---`-delimited
    block exists (falls back to wrapping the whole file in one if not).
    """
    lines = content.split('\n')
    if not lines or lines[0].strip() != '---':
        return f'---\n{key}: {value}\n---\n' + content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end_idx = i
            break
    if end_idx is None:
        return content

    field_re = re.compile(rf'^{re.escape(key)}:\s*.*$')
    for i in range(1, end_idx):
        if field_re.match(lines[i]):
            lines[i] = f'{key}: {value}'
            return '\n'.join(lines)

    lines.insert(end_idx, f'{key}: {value}')
    return '\n'.join(lines)


def ensure_site_root_frontmatter(content, output_path):
    """
    docs/README.mdx is this site's home page (docusaurus.config.ts sets
    `docs.routeBasePath` to '/'), which needs some frontmatter a normal doc
    doesn't:
      - `slug: /` to actually serve at the site root.
      - `pagination_prev: null` / `pagination_next: null` to suppress the
        auto-generated "Previous/Next" footer links. Without an explicit
        sidebar_position, README sorts last in the sidebar (see
        apply_sidebar_order()), so Docusaurus was showing a "Previous:
        Old-Getting-Started-Guide" link at the bottom of the home page -
        a reading-order artifact that makes no sense on a landing page.
    Previously these were one-off manual edits made directly to the
    generated file, which a full re-run of this script would silently
    overwrite - so they're asserted here instead, making a re-run
    idempotent.
    """
    if os.path.abspath(output_path) != os.path.join(OUTPUT_ROOT, 'README.mdx'):
        return content
    if not re.search(r'^slug:\s*/\s*$', content, re.MULTILINE):
        content = set_frontmatter_field(content, 'slug', '/')
    if not re.search(r'^pagination_prev:\s*null\s*$', content, re.MULTILINE):
        content = set_frontmatter_field(content, 'pagination_prev', 'null')
    if not re.search(r'^pagination_next:\s*null\s*$', content, re.MULTILINE):
        content = set_frontmatter_field(content, 'pagination_next', 'null')
    return content


def parse_summary_positions(summary_path):
    """
    Parse GitBook's SUMMARY.md - its own hand-curated table of contents -
    into sidebar ordering data for Docusaurus.

    Without this, Docusaurus's autogenerated sidebar (sidebars.ts uses
    `{type: 'autogenerated', dirName: '.'}`) falls back to plain
    alphabetical order, which throws away SUMMARY.md's curated structure
    entirely (e.g. "Getting Started" no longer comes before "FAQ").

    SUMMARY.md is a nested bullet list of `[Title](path/to/page.md)`
    links; `##` headings introduce top-level sections that have no doc of
    their own (no `section/README.md` bullet - they're pure headings), and
    `folder/README.md` bullets represent a subfolder's own index/category
    page (Docusaurus's autogenerated sidebar already treats a folder's
    `README.md`/`index.md` as that category's link, same as this script's
    fix_internal_links() already assumes).

    Returns (folder_positions, file_positions):
      - folder_positions: {'a/b': {'position': N, 'label': str_or_None}}
        for every folder that should get a generated `_category_.json`
        (position always; label only for top-level sections, which have
        no README of their own for Docusaurus to derive a label from -
        nested folders keep their existing README-derived label).
      - file_positions: {'a/b/c': N} for every non-index doc, to be
        written as that file's `sidebar_position` frontmatter.
    Both keyed by slash-joined path relative to the docs/ output root,
    matching get_output_path()'s layout (folders and files interleave in
    one shared position sequence per parent, exactly like Docusaurus
    sorts a real sidebar).
    """
    with open(summary_path, 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()

    counters = {}       # parent_tuple -> next position to hand out
    folder_pos = {}     # folder_tuple -> position
    file_pos = {}       # file_tuple -> position
    heading_label = {}  # (top_level_segment,) -> heading text
    pending_heading = None

    link_re = re.compile(r'^\s*[*+-]\s*\[([^\]]*)\]\(([^)]*)\)')
    heading_re = re.compile(r'^#{1,6}\s+(.*\S)\s*$')

    def ensure_folder(folder_tuple):
        if not folder_tuple or folder_tuple in folder_pos:
            return
        parent = folder_tuple[:-1]
        ensure_folder(parent)
        counters[parent] = counters.get(parent, 0) + 1
        folder_pos[folder_tuple] = counters[parent]

    for raw_line in raw_lines:
        heading_match = heading_re.match(raw_line)
        if heading_match:
            pending_heading = heading_match.group(1).strip()
            continue

        link_match = link_re.match(raw_line)
        if not link_match:
            continue

        _title, target = link_match.groups()
        target = target.split('#', 1)[0].strip()
        # Skip external links and GitBook's own dead cross-references
        # (e.g. "/broken/pages/<id>") - neither corresponds to a real
        # converted file under docs/.
        if not target.endswith('.md'):
            continue

        segments = tuple(seg for seg in target[:-3].split('/') if seg and seg != '.')
        if not segments:
            continue

        if pending_heading:
            top_tuple = (segments[0],)
            heading_label.setdefault(top_tuple, pending_heading)
            pending_heading = None

        if segments[-1].upper() == 'README':
            folder_tuple = segments[:-1]
            if folder_tuple:
                ensure_folder(folder_tuple)
        else:
            parent = segments[:-1]
            ensure_folder(parent)
            counters[parent] = counters.get(parent, 0) + 1
            file_pos[segments] = counters[parent]

    folder_positions = {
        '/'.join(k): {'position': v, 'label': heading_label.get(k)}
        for k, v in folder_pos.items()
    }
    file_positions = {'/'.join(k): v for k, v in file_pos.items()}
    return folder_positions, file_positions


def apply_sidebar_order(output_root, summary_path):
    """
    Apply parse_summary_positions() to the already-converted docs/ tree:
    write a `_category_.json` (position, and label where there's no
    README to supply one) for every folder, and a `sidebar_position`
    frontmatter field on every non-index doc.
    """
    if not os.path.exists(summary_path):
        print(f"[WARN] SUMMARY.md not found at {summary_path} - skipping sidebar ordering")
        return

    folder_positions, file_positions = parse_summary_positions(summary_path)

    categories_written = 0
    for rel_folder, info in folder_positions.items():
        folder_abs = os.path.join(output_root, *rel_folder.split('/'))
        if not os.path.isdir(folder_abs):
            print(f"[WARN] SUMMARY.md references folder '{rel_folder}' with no matching docs/ directory - skipping")
            continue
        data = {'position': info['position']}
        if info['label']:
            data['label'] = info['label']
        with open(os.path.join(folder_abs, '_category_.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        categories_written += 1

    docs_updated = 0
    for rel_file, position in file_positions.items():
        file_abs = os.path.join(output_root, *rel_file.split('/')) + '.mdx'
        if not os.path.isfile(file_abs):
            print(f"[WARN] SUMMARY.md references doc '{rel_file}' with no matching .mdx file - skipping")
            continue
        with open(file_abs, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content = set_frontmatter_field(content, 'sidebar_position', str(position))
        if new_content != content:
            with open(file_abs, 'w', encoding='utf-8') as f:
                f.write(new_content)
            docs_updated += 1

    print(f"[INFO] Sidebar ordering: wrote {categories_written} _category_.json files, "
          f"set sidebar_position on {docs_updated} docs")


def convert_file(input_file):
    """Convert a single file from GitBook MD to Docusaurus MDX."""
    output_path = get_output_path(input_file, SOURCE_ROOT, OUTPUT_ROOT)
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    print(f'Converting {input_file} to {output_path}')

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    content = strip_stray_control_characters(content)

    content = ensure_valid_frontmatter(content)

    # One-off structural fix (scoped to <table> blocks only) before anything
    # else touches the HTML, so later passes see a normal single-line table.
    content = collapse_multiline_tables(content)

    print("[DEBUG] Step 1: HTML fixes")
    content = fix_html_and_escape(content)

    print("[DEBUG] Step 2: Code block conversion")
    content = enhanced_convert_gitbook_code_blocks_simple(content)

    print("[DEBUG] Step 3: Hints conversion")
    content = convert_gitbook_hints(content)

    print("[DEBUG] Step 4: Tabs conversion")
    content = convert_gitbook_tabs(content)

    print("[DEBUG] Step 5: HTML entities")
    content = fix_html_entities(content)

    # Promote frontmatter `description:` into the body BEFORE the escaping
    # passes below run, so any special characters it contains (e.g. "<-->")
    # get escaped along with the rest of the body instead of leaking through
    # unescaped. The frontmatter's own YAML copy is untouched either way.
    print("[DEBUG] Step 6: Extract description from frontmatter (before escaping)")
    content = extract_description_from_frontmatter(content)

    print("[DEBUG] Step 7: Convert content-ref to cards")
    content = fix_gitbook_content_ref_to_cards(content)

    print("[DEBUG] Step 8: List fixes")
    content = fix_mdx_list_dash(content)

    # IMPORTANT: embed blocks must be converted before the generic
    # fix_all_remaining_gitbook_blocks() catch-all below, which strips any
    # leftover `{% ... %}` marker it doesn't otherwise recognize (including
    # `{% embed url="..." %}` / `{% endembed %}`). If that catch-all ran
    # first, it would delete the embed markers while leaving the caption
    # text behind as an orphaned paragraph with no link - silently dropping
    # every video link in the corpus (this was the original defect).
    print("[DEBUG] Step 9: Fix GitBook embed blocks")
    content = fix_gitbook_embed_blocks(content)

    print("[DEBUG] Step 10: Fix remaining GitBook blocks")
    content = fix_all_remaining_gitbook_blocks(content)

    print("[DEBUG] Step 11: Escape bare '<' in prose")
    content = escape_bare_angle_brackets(content)

    print("[DEBUG] Step 12: Fix internal links")
    content = fix_internal_links(content)

    print("[DEBUG] Step 12.5: Fix GitBook's own unresolved page links")
    content = fix_gitbook_unresolved_page_links(content)

    print("[DEBUG] Step 13: Brace escaping")
    content = improved_escape_curly_braces(content)

    # Runs after brace escaping so the `{{ }}` this introduces isn't itself
    # escaped to entities by improved_escape_curly_braces() above.
    print("[DEBUG] Step 13.5: Fix inline style string attributes")
    content = fix_inline_style_string_attributes(content)

    has_jsx = '<Tabs>' in content or '<TabItem' in content or 'className="admonition"' in content
    content = 'import Tabs from "@theme/Tabs"\nimport TabItem from "@theme/TabItem"\n\n' + content

    print("[DEBUG] Step 14: Fix frontmatter structure (final)")
    content = fix_frontmatter_structure(content)

    content = ensure_site_root_frontmatter(content, output_path)

    print(f"[DEBUG] Output: {output_path} (JSX detected: {has_jsx})")

    print("[DEBUG] Step 15: Fix admonition syntax")
    content = fix_admonition_syntax(content)

    print("[DEBUG] Step 16: Fix malformed code blocks")
    content = fix_malformed_code_blocks(content)

    print("[DEBUG] Step 17: Fix text code blocks")
    content = fix_text_code_blocks(content)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return output_path
    except Exception as e:
        print(f"[ERROR] writing file {output_path}: {e}")
        return None


def main():
    """Main function to process all markdown files with two-pass anchor fixing."""
    print("Starting GitBook to MDX conversion...")
    print(f"[INFO] Source: {SOURCE_ROOT}")
    print(f"[INFO] Docs output: {OUTPUT_ROOT}")
    print(f"[INFO] Asset source: {ASSET_SRC_DIR}")
    print(f"[INFO] Asset output: {ASSET_DST_DIR}")

    md_files = find_docs_files_recursive(SOURCE_ROOT)

    if not md_files:
        print("No .md files found in source directory")
        return

    print(f"Found {len(md_files)} files to process")

    print("\n=== PASS 1: Converting files and extracting headings ===")

    converted_files = []
    all_headings = {}

    for input_file in md_files:
        try:
            output_file = convert_file(input_file)
            if output_file and os.path.exists(output_file):
                converted_files.append(output_file)
                with open(output_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                headings = extract_headings_from_content(content, output_file)
                if headings:
                    all_headings[output_file] = headings
        except Exception as e:
            print(f"Error processing {input_file}: {e}")
            continue

    print(f"\n=== PASS 2: Fixing anchor links with real heading data ===")

    for output_file in converted_files:
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            fixed_content = fix_anchors_with_real_headings(content, all_headings, os.path.basename(output_file))
            if fixed_content != content:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
        except Exception as e:
            print(f"Error fixing anchors in {output_file}: {e}")
            continue

    print("\n=== PASS 3: Asset sanitization (rename, copy, rewrite references) ===")
    rename_map = build_asset_rename_map(ASSET_SRC_DIR)
    copy_assets(ASSET_SRC_DIR, ASSET_DST_DIR, rename_map)
    rewrite_asset_references(OUTPUT_ROOT, rename_map)

    print("\n=== PASS 4: Sidebar ordering from SUMMARY.md ===")
    apply_sidebar_order(OUTPUT_ROOT, SUMMARY_PATH)

    print("\n=== Conversion complete! ===")
    print(f"Processed {len(converted_files)} files with anchor prediction")


if __name__ == "__main__":
    main()
