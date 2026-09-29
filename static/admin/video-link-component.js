// Registers the MDX <VideoLink id=".." title=".." /> component (see
// scripts/convert_gitbook_to_mdx.py's render_embed_link()) as a custom
// editor component, so editors get an "Add YouTube video" toolbar button
// with a URL/title form and a preview - not raw JSX in the markdown
// editor. The markdown widget only understands plain markdown; this
// pattern/fromBlock/toBlock trio is how it round-trips a custom MDX
// component through that widget without corrupting it on save.
// CMS.registerEditorComponent() is API-identical between Decap CMS (used
// originally) and Sveltia CMS (switched to after Decap's beta `nested`
// folder-collection support broke on this repo's real folder tree), so
// this file needed no changes for that switch - only admin/index.html's
// script tag did. Loaded as a plain <script> tag after the CMS bundle,
// which auto-initializes itself on DOMContentLoaded -
// registerEditorComponent() just needs to run before that fires, which a
// synchronous script tag guarantees. Deliberately does NOT call CMS.init()
// itself: doing so alongside the bundle's own auto-init created a second
// React root on the same container (React's createRoot() called twice),
// which is what caused every /admin page load to crash with
// "NotFoundError: Failed to execute 'removeChild' on 'Node'" under Decap -
// a known class of bug (decaporg/decap-cms#7445 and similar) usually
// caused by exactly this double-init pattern.
//
// The YouTube-ID regex here intentionally mirrors
// scripts/convert_gitbook_to_mdx.py's YOUTUBE_ID_PATTERN - this file runs
// in the browser (plain JS), the conversion script runs at build time
// (Python), so the logic can't be shared directly between them.

const YOUTUBE_ID_PATTERN =
  /(?:youtu\.be\/|youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/))([A-Za-z0-9_-]{11})/;

function extractYouTubeId(url) {
  const match = YOUTUBE_ID_PATTERN.exec(url || '');
  return match ? match[1] : null;
}

CMS.registerEditorComponent({
  id: 'video-link',
  label: 'YouTube Video',
  fields: [
    { name: 'url', label: 'YouTube URL', widget: 'string' },
    { name: 'title', label: 'Video Title', widget: 'string' },
  ],
  // Matches the exact tag shape render_embed_link() emits. The `m` flag is
  // required: Sveltia's live-preview pane matches `pattern` against the
  // WHOLE field value in one go (not block-by-block like the editor's own
  // parser does), so bare ^/$ only ever match a field containing nothing
  // but this one tag - never true on a real page with surrounding text.
  // With `m`, ^/$ bind to line boundaries instead, so the component is
  // found wherever this line occurs. Without it, the preview pane silently
  // drops the whole element - no thumbnail, no title, nothing - even
  // though editing/saving still worked fine via the editor's own DOM-based
  // import path.
  pattern: /^<VideoLink id="([^"]*)" title="([^"]*)" \/>$/m,
  fromBlock: function (match) {
    return {
      url: `https://youtu.be/${match[1]}`,
      title: match[2].replace(/&quot;/g, '"'),
    };
  },
  toBlock: function (obj) {
    const id = extractYouTubeId(obj.url) || (obj.url || '').trim();
    const title = (obj.title || '').replace(/"/g, '&quot;');
    return `<VideoLink id="${id}" title="${title}" />`;
  },
  // A plain DOM element rather than a string, so the editor's live preview
  // pane shows the actual YouTube thumbnail - matching what editors see on
  // the real site (src/components/VideoLink/index.tsx) - instead of a bare
  // "📺 title" text line.
  toPreview: function (obj) {
    const id = extractYouTubeId(obj.url);
    const title = obj.title || obj.url || 'YouTube video';

    const link = document.createElement('a');
    link.href = id ? `https://youtu.be/${id}` : obj.url || '#';
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.style.cssText =
      'display:flex;align-items:center;gap:12px;text-decoration:none;' +
      'color:inherit;border:1px solid rgba(128,128,128,0.3);' +
      'border-radius:8px;padding:8px;max-width:480px;';

    if (id) {
      const img = document.createElement('img');
      img.src = `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
      img.alt = title;
      img.loading = 'lazy';
      img.style.cssText = 'width:120px;height:auto;border-radius:4px;flex-shrink:0;';
      link.appendChild(img);
    }

    const label = document.createElement('span');
    label.textContent = `📺 ${title}`;
    link.appendChild(label);

    return link;
  },
});
