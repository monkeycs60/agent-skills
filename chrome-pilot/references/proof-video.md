# Prove a flow on video

A video shows what a screenshot can't: the sequence, the transitions, the state that changes after a click. For a behavior change, deliver two videos of the same flow, before and after.

## Requirements

`ab record` needs ffmpeg with the libvpx and libx264 encoders: `brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Debian or Ubuntu. `install.sh` reports when they are missing; `AB_ISOLATED=1 ab doctor` checks them too.

## Shooting the before and the after

- Shoot the "before" on the base branch (a worktree or a checkout of the main branch), ideally before touching the code.
- Same flow, same account, same window size (`ab set viewport 1440 900`): the comparison is what tells the story.
- Isolated mode fits any flow without a login. In real Chrome, the agent's tab must stay in the foreground for the whole take: a hidden tab slows every click by about 5 s.

## During the take

- `ab record start <file.webm> [url] --fps 15` starts the take; with a URL, the tab navigates there first.
- The wrapper adds `--cursor`: a pointer, and a ripple on each click, appear in the frame. Without it, the screen changes but you can't tell where the agent acted.
- Every gesture goes through the mouse: `ab click`, `ab find text "…" click`, `ab mouse`, `ab scroll`. An `ab eval "….click()"` acts without moving the pointer.
- Leave a short pause between two steps (`ab wait 800`) so a human can follow.
- `ab record stop` ends the take. If it prints `✗`, shoot it again.

## Check the take without watching it

`--contact-sheet` on `record start` writes, next to the video, a sheet of the frames where the screen changes (`<name>.contact-sheet.png`). Reading it is enough to check that the take shows every step.

## Convert

Record to `.webm`, then convert to H.264 MP4:

```bash
ffmpeg -loglevel error -y -i /tmp/proof/after.webm -c:v libx264 -pix_fmt yuv420p \
  -crf 28 -preset veryfast -movflags +faststart -an /tmp/proof/after.mp4
```

On a busy machine, recording straight to `.mp4` can fail (`Recording encoder fell more than 500 ms behind capture`) and leave an unreadable file: recording `.webm` and converting avoids that. H.264 MP4 plays in every mainstream browser.

## Embed in an HTML report

```html
<video controls muted playsinline preload="metadata" title="After · adding a profile"
  src="data:video/mp4;base64,…"></video>
```

Place each "before" to the left of its "after", on the same row, with a caption (`title` or `<figcaption>`) saying what the video shows.
