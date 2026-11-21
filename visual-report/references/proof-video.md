# Proving a UI change on video

A screenshot shows a state; a video shows the sequence, the transition and the state that changes after a click. For a behavior change, deliver two videos of the same flow, before and after. A pure visual tweak (color, spacing) only needs screenshots.

## Getting a "before"

- Best: shoot the before before touching the code.
- Otherwise run the base branch next to your work: `git worktree add ../app-before main`, start it on another port, and film both.
- Same account, same data, same window size for both takes: the comparison is what tells the story.

## Shooting with chrome-pilot

When the `chrome-pilot` skill is installed, use its isolated mode, which needs no login and never touches the user's browser:

```bash
export AB_ISOLATED=1
ab set viewport 1280 800
ab record start /tmp/report/media/after.webm http://localhost:3000/profile --fps 15
ab click @e3
ab wait 800
ab fill @e5 "ada@example.com"
ab wait 800
ab record stop
```

- The pointer and a ripple on each click are drawn into the frame (chrome-pilot adds `--cursor`).
- Every gesture goes through the pointer (`click`, `fill`, `scroll`, `find text … click`). A script that clicks through JavaScript changes the screen without showing who acted.
- Pause 600 to 800 ms between steps so a human can follow. Keep the take under 20 s; cut what is only waiting.
- `ab snapshot -i` before the take gives the element refs; refs expire after a navigation.

Other tools work the same way: Playwright's `recordVideo` context option, a screen recorder, or any browser automation that records. What matters is the same flow twice, with visible gestures.

## Convert and check

```bash
scripts/to-mp4.sh /tmp/report/media/after.webm /tmp/report/media/after.mp4        # 1280 px, 15 fps
scripts/to-mp4.sh /tmp/report/media/after.webm /tmp/report/media/after.mp4 960 12 # smaller
ffmpeg -loglevel error -y -i /tmp/report/media/after.mp4 \
  -vf "fps=1,scale=480:-1,tile=4x2" -frames:v 1 /tmp/report/after-sheet.png
```

H.264 MP4 plays in every mainstream browser and in Pupitre. Look at the contact sheet before embedding: every step of the flow must appear, with the pointer where the action happens. Shoot again rather than ship a take that skips a step.

## Embedding

```html
<figure class="pair">
  <figure><video src="media/before.mp4" controls muted playsinline preload="metadata" title="Before · adding a profile"></video><figcaption>Before</figcaption></figure>
  <figure><video src="media/after.mp4" controls muted playsinline preload="metadata" title="After · adding a profile"></video><figcaption>After</figcaption></figure>
  <figcaption>Same flow: watch the list after the click on Save.</figcaption>
</figure>
```

The viewer opens a pair as one slide and plays both videos together from the start, so the difference shows side by side.
