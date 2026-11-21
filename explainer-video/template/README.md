# Video "TITLE" (YYYY-MM-DD)

Project: PROJECT NAME. DURATION s, 1920 x 1080, 60 frames per second, silent. Project brand in
`brand.css` (colors, fonts, logos, each with its source in the code).

Made with the `explainer-video` skill.

## What the folder contains

| File | Role |
|---|---|
| `film.html` | The film. Opened in a browser, it plays with a scrub bar. `?t=12.5` opens it frozen at a given time, `&lang=fr` in another language. |
| `brand.css` | The project brand: single source of the colors, fonts and logos of the film, the thumbnail and the kit. |
| `engine.js` | The animation engine, identical for every film. Do not modify. |
| `thumbnail.html`, `youtube-<lang>.json` | The thumbnail and the texts of the YouTube kit. |
| `assets/` | Real app screenshot and its JSON (element frames), project fonts and logos (do not distribute them if their license forbids it). |
| `out/` | The MP4, the poster, the key-frame contact sheets, the verification, the YouTube kit. |

## Render the video again

From the skill's `scripts/` folder:

```
node render.js "<this folder>" contact-sheet 2,6,10,14,18,22 en
node render.js "<this folder>" video en
node render.js "<this folder>" verify en
node render.js "<this folder>" poster 14 en
```

## Notes from preparing the video

- (gaps between the written docs and the app, changed labels, uncertain brand values, elements hidden in the capture...)
