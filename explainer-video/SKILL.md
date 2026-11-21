---
name: explainer-video
description: Builds a short motion-design explainer video in code (1080p, 60 fps, silent MP4) for a feature or doc of any project, in the project's own visual identity, with a YouTube kit, or edits one. Use for "make a video of X", "animate this tutorial", or /explainer-video.
---

# Motion-design explainer video, for any project

Answer the user, and write every report or deliverable, in the language of the user's request,
whatever the language of this skill's files. On-screen text follows the language of the project
or the one the user asks for.

A video is an **animated HTML page**: `paint(t)` draws each instant, Chrome photographs it frame
by frame, then ffmpeg (or Chrome itself) encodes it to H.264 MP4. Format: **1920 x 1080, 60 fps,
silent, about 7 s per step, pauses included**; readability comes before brevity. Reference to read
before anything else: `template/film.html` (fictional product "Coche": invite your team to a shared
list).

What makes the quality: **a single shape runs through the whole film without ever cutting**
(full screen `--brand`, button, chip, field, result, frame on the real screen, full screen). The
whole visual identity comes from one file, `brand.css`, extracted from the project.

## Before you start

- `S` = this skill's `scripts/` folder (usually `~/.claude/skills/explainer-video/scripts`).
- **Tools**: `node $S/tools.js` checks Node 20+, finds Chrome or Chromium (otherwise `CHROME_PATH`)
  and ffmpeg (optional, recommended), and says what to install. No npm package. Details, variables
  and render times: `references/tools.md`.
- **First time on a machine**: `node $S/example.js` builds the example film end to end (2 to
  4 min) in `~/explainer-videos/coche/invite-team/`. It is the test of the whole pipeline.
- Inputs: docs URL, Markdown, README, ticket, description or a path through the app. Vague topic:
  ask **what to show and to whom**, the rest follows from the code.
- The project repository and, ideally, the app running on fictional data.
- Folders: film in `$EXPLAINER_VIDEO_DIR/<project>/<slug>/` (default `~/explainer-videos/`,
  **outside the repository**); shared brand in `.../<project>/brand.css`; intermediate frames in
  `FRAMES_DIR` (temporary folder by default, about 200 MB per film).

## Workflow

0. **Brand**, if `<project>/brand.css` does not exist: `node $S/brand-inventory.js <repo-root>`,
   read the sources, measure on the app (`capture.js`, `styles` key), fill it in from
   `template/brand.css` with one source per value. Show a variable / value / source table.
   Method: `references/brand.md`; filled-in example: `example/brand.css`.
1. **Topic**: draw **4 to 6 steps at most** from it, and the "wow" moment (the app does something
   on its own). Everything else stays in the written docs.
2. **Labels** checked in the code, then seen in the app (the agent's browser if a session is
   needed, otherwise `capture.js`). Note the intermediate states ("Searching...").
3. **List of states** shown as a table (state, what the shape becomes, what the viewer
   understands, time). Carry on without waiting, unless the user wants to approve.
4. **Real capture** of the final scene: `node $S/capture.js recipe.json`; the JSON gives the exact
   frame of the elements, which the film reads on its own. Recipe and usage: `references/capture.md`.
5. **Editing**: copy `template/` into the film folder, put the project brand, its fonts and logos
   in `assets/`. `engine.js` stays untouched; rewrite in `film.html` `TXT`, `ST`, `GEO`, `BG_KEYS`,
   sets, `CAPS`, `CUR` and camera. Method: `references/motion.md`; color roles, grid and
   components: `references/art-direction.md`.
6. **Mandatory self-review**: contact sheets of key frames and transitions, score out of 10, three
   worst defects fixed, until 8 everywhere, full signature. Grid: `references/critique.md`.
7. **Reading time**: every text stays on screen, whole and still, for at least **0.4 s + 0.3 s
   per word**; otherwise add a pause in `HOLDS`.
8. **Render and verification**: `video` in the background, then `verify`, which exits with an
   error at the slightest gap (size, frame rate, duration, colors, empty frame). Then look at one
   decoded frame at full resolution.
9. **YouTube kit** if the video goes there: `thumbnail.html` → `render.js thumbnail`,
   `youtube-<lang>.json` (with `channel` and `duration`), then `kit.js`. Look at the thumbnail at
   168 x 94, deliver only when everything is green. Rules: `references/youtube.md`.
10. **Deliver**: the MP4 (and the kit), the path of `film.html` (`?t=14.9` opens it frozen), the
    filled-in `README.md` of the folder, and the gaps found between the written docs and the app.

```
node $S/render.js <film-folder> contact-sheet 1.9,7.4,13.9,22.5 en
node $S/render.js <film-folder> video en
node $S/render.js <film-folder> verify en
node $S/render.js <film-folder> poster 22 en
node $S/render.js <film-folder> thumbnail en
node $S/kit.js <film-folder> en
```

`render.js` refuses to render while `brand.css` is still the template, and reports every file
the film requests without finding it.

## Rules

- **The brand comes from the project**, never from the reference film or personal taste; no brand
  color hard-coded in the film, the thumbnail or the kit.
- **Captures on fictional data only**, never a real account or a production database.
- **Never invent interface feedback** (toast, "Copied"); an annotation is allowed if it reads as an
  annotation, outside the interface.
- Money, security, delays, quotas: **proven in the code or not written**. Every annotation must
  stay true in every case, not only in the demo; otherwise name the object without interpreting it
  ("Your link").
- Scenes drawn with generic fictional data ("Product Team", `example.com`); the real capture is
  never retouched. **No childish visuals.**
- Talk only about the topic: no advanced option in a getting-started video.
- On-screen text: never an em dash or en dash; in French, a non-breaking space before colons and
  question marks, none in English.
- **Install nothing** (ffmpeg, browser, packages) without the user's consent: `tools.js` says what
  to install and how.
- Project fonts: copied for rendering, never published if the license forbids it.
- Write long files with the file-writing tool, not with a heredoc.

## Edits, other language, embedding

- **Edit**: contact sheet around the touched instant (before, during, after), then full render.
  Lengthen a scene without shifting everything: `warp()` (`references/motion.md`).
- **New brand**: update `brand.css`, make a contact sheet again, render again.
- **Other language**: `TXT.<lang>` with the project's translations, capture in that language
  (`"lang"` of the recipe, output `real-screen-<lang>.png`), render with `<lang>`, check the
  widths. The template has `en` and `fr`: `node $S/example.js <folder> fr`.
- **Embedding**: upload the MP4 and the poster, then
  `<video src="MP4_URL" poster="POSTER_URL" controls muted playsinline preload="metadata" style="width:100%;height:auto;display:block;border-radius:14px;"></video>`.
  GitHub: 10 MB at most on a free account (shorten, or render at 30 fps).

## References (read only when the step requires it)

- `references/tools.md`: prerequisites, browser lookup, variables, scripts, `verify` checks, measured times (before starting, when a tool breaks).
- `references/brand.md`: extracting the brand, source table per design system, fonts, logos (step 0).
- `references/capture.md`: `capture.js` recipe, session, from the JSON to the film frame (steps 0, 4).
- `references/motion.md`: engine, single shape, rhythm, pauses, `warp()`, camera, cursor (steps 5, 7).
- `references/art-direction.md`: color roles, typography, grid, template components (step 5).
- `references/critique.md`: signature to check, scoring grid, known defects, reading `verify` (steps 6, 8).
- `references/youtube.md`: thumbnail, title, description, tags, kit checks (step 9).
- `references/pitfalls.md`: technical failures of rendering and encoding (when a render comes out wrong).
- `template/`: film, engine, brand template, thumbnail, YouTube JSON (`en`, `fr`), Inter (OFL) and `README.md` to copy.
- `example/`: filled-in brand and HTML mockup of the fictional app, captured by `example.js`.
