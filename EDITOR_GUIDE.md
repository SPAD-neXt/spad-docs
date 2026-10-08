# Editing the SPAD.neXt documentation

*A guide for people who write and maintain the docs at docs.spadnext.com — no coding knowledge needed.*

This replaces the old GitBook editor. It works differently in a few ways
(explained below), but editing text, adding images and adding videos is
just as easy as before.

---

## 1. Logging in

1. Go to **[docs.spadnext.com/admin](https://docs.spadnext.com/admin/)**.
2. Click **Login with GitHub**.
3. A popup window opens asking you to sign in to GitHub (if you're not
   already) and approve access. Approve it.
4. The popup closes and you'll see the content editor — a list of
   folders and pages on the left, matching the structure of the manual.

You need a GitHub account to log in. If you don't have write access to the
`spad-docs` repository, you can still log in and make edits — see
[What happens when you save](#3-what-happens-when-you-save) below for what
changes for you.

---

## 2. Everyday editing

### Editing an existing page

1. Click through the folders on the left until you find the page.
2. Click it to open the editor.
3. You'll see a few fields at the top (**Title**, **Description**, **Sidebar
   Position** — more on that one below) and the page content itself
   (**Body**) underneath, in a rich text editor much like Word or Google
   Docs.
4. Make your changes.
5. Click **Save** in the top right, then see
   [What happens when you save](#3-what-happens-when-you-save).

### Creating a new page

1. Open the folder where the new page should live.
2. Click **New Doc page** (top right).
3. Fill in **Title** and the page content.
4. Set a **Sidebar Position** if you want it to appear in a specific spot
   (see below) — otherwise it'll show up last in that folder.
5. Save.

### Adding a YouTube video

Don't paste a raw YouTube link into the text. Instead:

1. Place your cursor where the video should go.
2. Look for a small toolbar icon above the text box for inserting a
   block/plugin (it sits alongside the bold/italic/link buttons) and choose
   **YouTube Video**.
3. Paste the YouTube URL and add a short title for it.
4. The preview pane on the right shows the real YouTube thumbnail right
   away — no need to publish first to check it looks right.

### Adding images

Use the image button in the toolbar as usual — uploaded images go into the
shared media library automatically.

---

## 3. What happens when you save

This is the part that's genuinely different from GitBook, so read it once.

GitBook saved your change immediately. Here, **Save** doesn't publish right
away — it proposes your change for a quick, mostly-automatic review:

1. Your change is submitted (behind the scenes, this creates a "pull
   request" — think of it as a labeled, reviewable version of your edit).
   It starts out as a **Draft**.
2. **Nothing else happens automatically while it's still a Draft** — not
   even the automatic build check. This is deliberate: it means you can
   save as many times as you like while you're still working on a page
   (e.g. a long edit, or trying something out) without triggering a check
   or a review request on every single save.
3. When you're done, move it out of Draft — either with the status control
   in the editor, or by dragging its card from "Draft" to "In Review" (or
   straight to "Ready") on the **Workflow** board (see below). *This* is
   what actually kicks things off.
4. Within a minute or two, an automatic check confirms the site still
   builds correctly with your change included.
5. **If you're a listed project collaborator:** once that check passes,
   your change is published automatically — usually within a couple of
   minutes of moving it out of Draft.
6. **If you're not a listed collaborator:** your change waits for a
   collaborator to look it over and approve it. You'll still see it on the
   Workflow board, just marked as pending review.

You can always see the status of your changes: in the content editor, click
the **Workflow** tab in the left sidebar (next to "Content"/"Media"). It
shows every pending change as a card you can drag between "Draft", "In
Review" and "Ready" — this is the editor's own status board, separate from
whether a human review is actually required for your specific account.

**Why the wait sometimes happens:** it's not about trust in what you wrote —
it's so at least one more person always looks over documentation changes
before they go live, the same way a second pair of eyes helps on anything
written collaboratively. If you're waiting on a review and it's urgent, ask
in the `#doc-discussion` Discord channel.

---

## 4. Changing where a page appears in the menu

In GitBook you dragged pages up and down in the sidebar. Here, each page has
a **Sidebar Position** number field instead:

- **Lower numbers show first.** A page with position `1` appears above a
  page with position `2`.
- This only orders pages **within the same folder** — it doesn't move a
  page into a different folder, and it doesn't reorder whole sections
  (folders) relative to each other (ask a developer for that one, for now).
- Leave it empty and the page sorts to the end of its folder.

**To insert a page between two existing ones without renumbering
everything else:** use a decimal. If you have pages at position `2` and
`3` and want a new one between them, give it position `2.5`. Done — no
need to touch the other pages at all.

If you ever do need to move several pages around, it's fine to just edit
each one's Sidebar Position field individually and save each — there's no
drag-and-drop, but nothing stops you from adjusting a handful of numbers to
get the order you want.

---

## 5. If something goes wrong

- **Your change doesn't show up on the live site after a while:** check
  the Workflow board (see above) — it might be waiting on a review, or the
  automatic check might have found a problem with the page (this usually
  means a formatting mistake, like an unclosed bit of markdown). Ask a
  developer to look at the specific page if you're not sure.
- **The editor shows an error page or won't load:** try refreshing, or
  logging out and back in. If it persists, report it — include a screenshot
  if you can.
- **You're not sure who has "collaborator" access:** ask in the
  `#doc-discussion` Discord channel; it's a small, explicit list, not
  everyone with a GitHub account.

---

## Quick reference

| I want to... | Do this |
|---|---|
| Edit a page | Click through folders on the left, click the page, edit, Save |
| Add a new page | Open the folder, **New Doc page**, fill in Title + content, Save |
| Add a YouTube video | Toolbar block/plugin icon → **YouTube Video** → paste URL + title |
| Actually publish my saved change | Move it out of **Draft** (status control, or drag its card on the **Workflow** board) |
| Move a page up/down in its folder | Lower **Sidebar Position** number = higher up |
| Insert a page between two others | Use a decimal, e.g. `2.5` between `2` and `3` |
| Check if my change is live yet | **Workflow** tab in the left sidebar |
| Reorder a whole section/folder | Not yet possible from the editor — ask a developer |
