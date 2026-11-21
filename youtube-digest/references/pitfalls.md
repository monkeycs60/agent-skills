# Pitfalls

## yt-dlp
- Standalone binary in `~/.local/bin/yt-dlp`. YouTube changes often: at the first extraction failure (`Sign in to confirm you're not a bot`, `nsig`, empty formats), run `yt-dlp -U` then retry.
- `HTTP Error 429`: YouTube is rate limiting. It mostly hits automatic caption translations, which the script never requests. If it hits the chosen track, the script switches to the audio on its own.
- Private, members-only or age-restricted video: rerun with `--cookies` (Chrome's YouTube session).
- Avoid `--download-sections`: it streams through ffmpeg, minutes for a 10-minute excerpt, against about 1 s per minute of video for a full audio download.
- The message `no impersonate target is available` has no effect on YouTube.
- YouTube requires a JavaScript runtime for some videos: without deno, the script enables node or bun for yt-dlp (`--js-runtimes`). Without any of the three, most captions still come through, but not always.

## Local engine
- The skill's `.venv/` is outside Git. On a fresh machine, the script creates it on first need with `uv`, otherwise with `python -m venv`, and onnx-asr downloads the model (about 670 MB, into `~/.cache/huggingface`) on the first run. Count one extra minute the first time.
- Memory grows with segment length: `asr.py` caps segments at 25 s. Do not raise this limit.
- The computation uses every core. Under heavy load (other agents, builds), speed can drop by half.

## HTML report
- Mermaid is downloaded once from jsdelivr into `~/.cache/youtube-skill/mermaid.min.js`. Rendering goes through Chrome, Chromium or Edge in headless mode with a temporary profile (Linux: `google-chrome`, `chromium`; macOS: `/Applications/…app`); `CHROME_PATH` forces an executable. Without a browser, diagrams stay as source in the report.
- The thumbnail is embedded in base64: Pupitre's preview blocks images loaded from a URL.
- `--deliver downloads` opens the report with Chrome when found, otherwise `open` (macOS) or `xdg-open` (Linux).

## Reading links
- `yt links` looks for agent-browser (`AGENT_BROWSER_BIN`, PATH, nvm, `~/.local/opt/pupitre-browser`, Homebrew) and calls it in a dedicated headless session, without the shell's `AGENT_BROWSER_*` variables: no connection to the user's Chrome, no focus stealing. Without agent-browser, or when the page fails, it falls back to plain HTTP without JavaScript; an empty page points to a site rendered with JavaScript.
- `--http` forces the browserless fallback.
- A GitHub repository gives its README and its file list; a `/blob/` URL gives the raw file, `/tree/` the folder and its README. `gh` must be installed and signed in, otherwise the error is recorded and reading continues.
