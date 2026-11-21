# Tools, variables and render times

## Prerequisites

| Tool | Status | Role | Install |
|---|---|---|---|
| Node 20 or later | required | Every script, without any npm package | https://nodejs.org |
| Google Chrome or Chromium (or Edge, Brave) | required | Draws and photographs each frame, captures the app | Linux: `google-chrome-stable` or `chromium` package; macOS: Google Chrome |
| ffmpeg with libx264 (and ffprobe) | optional, recommended | Encodes in about 15 s and checks the MP4 frame by frame | `apt install ffmpeg`, `brew install ffmpeg` |
| A fallback system font (DejaVu, Liberation...) | required on a minimal Linux | Glyphs missing from the film fonts (kit check marks) | `apt install fonts-dejavu-core` |

Without ffmpeg, the MP4 is encoded **in the browser** (WebCodecs): Google Chrome can always do
it, Chromium depending on the distribution. `node $S/tools.js` says which of the two will be used;
if neither is available, it says so too and exits with an error.

`install.sh` at the skill root only runs this diagnostic: nothing is downloaded.

## Browser

Looked up in this order: `CHROME_PATH`, then
- Linux: `google-chrome-stable`, `google-chrome`, `chromium`, `chromium-browser`, `microsoft-edge`,
  `brave-browser` in the `PATH`, then `/opt/google/chrome/chrome`, `/snap/bin/chromium`;
- macOS: `Google Chrome.app`, `Chromium.app`, `Microsoft Edge.app`, `Brave Browser.app` in
  `/Applications` or `~/Applications`.

The browser runs headless, with a temporary profile that is never shared, and is driven through a
pipe (`--remote-debugging-pipe`): **no port is opened**, two renders can run at the same time. As
root (Docker), `--no-sandbox` is added automatically.

## Environment variables

| Variable | Effect |
|---|---|
| `CHROME_PATH` | Browser binary to use |
| `CHROME_NO_SANDBOX` | `1`: launches the browser without a sandbox (container as a normal user); otherwise it relaunches on its own after a sandbox failure, with a warning |
| `FFMPEG_PATH`, `FFPROBE_PATH` | ffmpeg and ffprobe binaries, if they are not in the `PATH` |
| `ENCODER` | `ffmpeg` or `chrome` to force the encoder (default: ffmpeg if it has libx264) |
| `WORKERS` | Tabs photographing in parallel (default: half the cores, 4 at most) |
| `FRAMES_DIR` | Folder for intermediate frames (default: the system temporary folder) |
| `EXPLAINER_VIDEO_DIR` | Root of the films (default: `~/explainer-videos`) |

## Scripts

| Script | Usage |
|---|---|
| `tools.js` | Tool diagnostic, exit code 1 if no video is possible |
| `example.js [folder] [en\|fr] [--no-video]` | Full example film: capture, contact sheet, video, verification, poster, thumbnail, kit |
| `render.js <film> contact-sheet <t1,t2,...> [lang]` | Key frames -> `out/contact-sheet-<lang>.png` |
| `render.js <film> video [lang]` | All frames, then the MP4 -> `out/<film>-<lang>.mp4` |
| `render.js <film> encode [lang]` | Re-encodes from the frames already rendered |
| `render.js <film> verify [lang]` | Checks the MP4, exit code 1 at the slightest gap |
| `render.js <film> poster <t> [lang]` | Poster image -> `out/<film>-<lang>-poster.jpg` |
| `render.js <film> thumbnail [lang]` | YouTube thumbnail 1280 x 720 (JPG and PNG) |
| `capture.js <recipe.json>` | Capture of a real screen and frames of its elements (`capture.md`) |
| `kit.js <film> [lang]` | HTML YouTube kit, exit code 1 if a check fails |
| `brand-inventory.js <repo-root>` | Map of the brand sources (`brand.md`) |

`lang` defaults to `en`. `render.js` reports the files the film requests without finding them
(missing real capture, misnamed logo) and the fonts that failed, instead of rendering a film with
holes.

## What `verify` checks

With ffprobe: H.264 codec, 1920 x 1080, frame rate, frame count and duration equal to the film's.
Then six frames spread over the film, decoded from the MP4 (by ffmpeg, otherwise by the browser's
player) and compared with the same frame rendered again: mean difference below 3 with ffmpeg
(expected around 1), below 5 with the browser's player, which converts BT.709 colors on display
(up to 3 on saturated flat areas); no empty frame, no identical pair. It writes
`out/verification-<lang>.png` (the six decoded frames) and one full-size decoded frame, to look at.

## Measured times (example film of 36.7 s, 2,202 frames)

| Step | Linux desktop 16 cores, Chrome | Docker `node:22-bookworm-slim` + Chromium |
|---|---|---|
| Diagnostic (`install.sh`) | 0.5 s | 0.5 s |
| Photographing the frames, 4 tabs | 77 s (190 s with a single one) | 71 s |
| ffmpeg encoding (5.9 MB) | 14 s | 16 s |
| Encoding in the browser, without ffmpeg (18 MB, 6 Mbit/s) | | 59 s |
| Verification | 4 s | 2 to 4 s |
| Capture, contact sheet, poster, thumbnail, kit | 1 to 2 s each | 1 to 2 s each |
| Full `example.js` | | 95 s with ffmpeg, 136 s without |

Run `video` in the background and prepare the kit meanwhile. Without ffmpeg, the MP4 is three
times heavier: above 10 MB (GitHub's limit on a free account), go through ffmpeg.
