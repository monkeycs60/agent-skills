# Technical pitfalls of rendering

Visual composition defects (icon on the wrong side, cursor on the label, set under the caption,
overflowing text...) are listed in `critique.md`.

| Pitfall | Reality |
|---|---|
| Washed-out colors after encoding in the browser | `encoder.html` converts to I420 BT.709 video range itself and adds the `colr` box. Do not touch it. |
| Film in the reference film's colors | `brand.css` not replaced, or a hard-coded color in an added set. Search `film.html` for `#` hex values: only neutral elements (phone, browser bar) keep some. |
| Two `style` attributes on a tag | The second one is ignored without an error, the element loses its position. One `style` per tag. |
| Dull or wrong color transition | `trA` needs `color('--x')`, not a CSS string. `color()` cannot read a transparent color: give it the solid color and pass the alpha as the second argument. |
| Fallback font in the render | Missing weight or file: check `@font-face`, `display=block`, and look at a full-size frame. |
| "Chrome or Chromium not found" | Install one of the two, or `CHROME_PATH=/path/to/binary` (`tools.md`). |
| "the browser stopped" at launch | The last lines of its log follow the message. As root without `--no-sandbox`: run as a normal user or in Docker (added automatically as root). Snap Chromium: `CHROME_PATH` to a non-snap Chrome if the pipe does not go through. |
| `/dev/shm` too small (Docker) | Already worked around by `--disable-dev-shm-usage`. |
| "no H.264 encoder in this browser" | Chromium without proprietary codecs: install ffmpeg, or use Google Chrome. |
| Slow render | `WORKERS` sets the parallel tabs; beyond 4, the gain is small. Do not encode during a capture: ffmpeg takes the same cores. |
| MP4 colors slightly off | Encoding goes through ffmpeg's `colorspace` filter (full-range BT.601 JPEG to video-range BT.709). A default `scale` shifts flat areas by 2 to 3; its exact options are 9 times slower. |
| File not found reported by `render.js` | Path relative to the film folder, exact name (case included); real capture: `capture.js`. |
| The verification shows the same frame everywhere | Playback by the browser: wait for `requestVideoFrameCallback` after `seeked` (already done in `verify.html`). |
| Difference of 6 or more on blue flat areas, while the video is right | Frame compared with color management: an ffmpeg PNG carries BT.709 tags that Chrome converts. `verify.html` loads the images with `colorSpaceConversion: 'none'`. |
| `window.seek` calling itself | A global function named `seek` gets overwritten: the film names its own `paint`. |
| 403 error from the local server | Paths with mixed slashes: always `path.resolve`. |
| Two renders of the same film differ slightly | Chrome noise on the blur of large shadows. Does not matter. |
