// Registers the MDX <VideoLink id=".." title=".." /> component (see
// scripts/convert_gitbook_to_mdx.py's render_embed_link()) as a Decap
// editor component, so editors get an "Add YouTube video" toolbar button
// with a URL/title form and a preview - not raw JSX in the markdown
// editor. Decap's markdown widget only understands plain markdown; this
// pattern/fromBlock/toBlock trio is how it round-trips a custom MDX
// component through that widget without corrupting it on save. Loaded by
// admin/index.html before CMS.init() runs.
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
  // Matches the exact tag shape render_embed_link() emits.
  pattern: /^<VideoLink id="([^"]*)" title="([^"]*)" \/>$/,
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
  toPreview: function (obj) {
    return `📺 ${obj.title || obj.url || 'YouTube video'}`;
  },
});

CMS.init();
