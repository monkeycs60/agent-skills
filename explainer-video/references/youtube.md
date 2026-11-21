# YouTube publishing kit

Rule: for **every** video meant for YouTube, a perfect thumbnail, a title and a description
optimized for YouTube search, clean and high quality, gathered in one HTML page. The kit is made
**after** the video is approved and never changes it.

## Files

| File | Role |
|---|---|
| `thumbnail.html` (film folder, copied from `template/`) | The thumbnail, 1280 x 720, drawn in HTML like the film |
| `youtube-<lang>.json` (film folder) | Title, description, tags, settings, `channel` (name shown in the previews, otherwise the brand's `--name`) |
| `out/<film>-<lang>-thumbnail.jpg` and `.png` | `render.js <film> thumbnail <lang>` |
| `out/youtube-kit-<lang>.html` | `kit.js <film> <lang>`: previews, Copy buttons, automatic checks; page labels in French for `fr`, in English otherwise |

`kit.js` checks on its own: title of 100 characters at most (ideal 70), description of 5,000 at
most, valid chapters (first at 00:00, at least three, each at least 10 s long), tags under 500
characters, 1 to 15 hashtags, no em dash, **description links answering HTTP 200**, thumbnail JPG
under 2 MB and at 1280 x 720. Deliver only if everything is green.

## Thumbnail

It is judged at **168 x 94** (the "Up next" column): the kit shows it at that size, look at it.

- **3 to 5 words**, in the brand's title font (900 weight or the boldest available), 120 px or
  more, white on `--brand`. One word or a promise on an `--accent` band, `--ink` text.
- **A single strong object**, taken from the film (the phone, the conversation and its link
  preview for "Invite your team"). Never a plush toy or childish visual (see
  `art-direction.md`). No screenshot of the app: unreadable when small.
- The official **white logo** at the top left, and nothing else besides the message and the
  object: no "Tutorial" badge or category, which clutters.
- **Bottom right corner free**: YouTube shows the duration there.
- Same lighting as the film: sheen at the top left, depth at the bottom right, dot grid fading out
  to the right.
- Nothing false or exaggerated: a duration promise ("in 30 seconds") is allowed only if the action
  really takes that long once the prerequisites are met.

## Title

- The **keyword people type** first. Reference film example: people type "share a task list" far
  more than "invite link", the app's term: put the common term in the title, the app's term in
  the thumbnail and the description.
- The brand, then a verifiable promise. 60 characters at most to stay whole on phones.
- No shouty capitals, no emoji, no exclamation mark, no "amazing".
- Example: "Share a task list with your team on Coche" (41 characters).
- For a personal project without an audience, the product name matters less than the problem
  solved: "Plan your running sessions in 2 minutes" rather than "Discover MyApp".

## Description

1. **First two lines** (about 150 characters, visible before "more"): the keyword, the app's term
   in parentheses, and what you learn. The kit highlights them.
2. **Chapters**: `00:00`, then one line per major step. Times are read in the film **with the
   pauses** (when the captions appear, see `CAPS` and `HOLDS`).
3. **Summary**: the numbered steps, with the app's **exact labels**, as in the docs.
4. The **links to the full docs** and a useful neighboring doc, checked for HTTP 200. Domains
   reserved for examples (`example.com`, `*.example`) are not checked: the kit says so.
5. **Three hashtags** on the last line (all three show above the title):
   `#<Product> #<domain> #tutorial` (reference film: `#Coche #productivity #tutorial`).

Same rules as the docs: formal address where the language has one (vous in French), no em dash,
a space before colons in French, no promise about money or delays that is not proven in the code.

## Tags and settings

- 10 to 15 tags: synonyms of the keyword ("share a task list", "shared list", "invite link"), the
  brand, the target audience (reference film: "teamwork").
- Settings to give in the JSON (`settings`): language, Education category, video not made for
  kids, automatic chapters off, end screen of 5 s at most so it does not hide the real screen.
