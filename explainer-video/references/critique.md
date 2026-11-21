# Self-review loop

The first render is never the right one: show the video only after this loop.

## Signature: check that no element is missing, in this order

1. **Hook**: full screen `--brand` with sheen, three very short phrases in the 900 title font
   rising on the beats, one highlighted word on an `--accent` band, a line pictogram on the right.
2. **The shape shrinks** and becomes the first object of the story, then never leaves the screen.
3. **One step, one caption** at the top left (numbered badge, title, subtitle), progress bar at
   the bottom.
4. **Sets faithful to the app**: labels from the code, brand colors, a cursor that clicks next to
   the labels, a ripple on click, springs with a slight bounce.
5. **A prerequisite is told** (request, pending, approved).
6. **The "wow" moment**: soft camera zoom, text that writes itself.
7. **What happens outside the app** is shown on its real medium, without a third-party logo.
8. **The real capture** in a window, the shape settled as a frame on the key element.
9. **Ending**: full screen `--brand`, `--logo-dark` logo, title, pill pointing to the docs.
10. **Reading pauses** wherever a text must be read, the background staying alive.
11. **YouTube kit** if the video goes to YouTube (`youtube.md`).

## Which frames to look at

1. **Contact sheet of the key moments**: one frame in the middle of each step, plus the hook and
   the ending (12 to 16 frames, `render.js contact-sheet`).
2. **Contact sheet of the transitions**: one frame 0.1 to 0.3 s after **each** departure of the
   shape and **each** set change. Defects hide there.
3. **One full-size frame** at the key moment (in the frames folder, `still-XXXXX.jpg`) to judge
   sharpness and overlaps.

## Scoring grid, out of 10 per frame

| Criterion | Question |
|---|---|
| Readability | Does everything read at 800 px wide? Nothing below 22 px? |
| One idea | Is there a single important thing, or two competing? |
| Accuracy | Labels identical to the code? Nothing invented on the interface side? |
| Brand | Are the colors, fonts, radii and logo the app's? Would someone on the team recognize their product? |
| Composition | Balanced with the caption band? Nothing cut by the edge? |
| Continuity | Is the shape always identifiable? No element that pops up or floats? |

Write down the **three worst defects**, fix them, make a contact sheet again. Stop when every
frame scores 8 or more.

## Defects already met (look for them first)

- Icon placed on the wrong side (`left:0` forced by `.a`), while the cursor clicks on the other.
- Cursor placed on the label it clicks.
- Set too small to be read (an 800 x 210 card no longer reads: 900 x 240 at least).
- Leftover hairline when a title leaves its mask: fade it during the exit.
- Shape arriving before its set: bring the set in first.
- Shape content still visible during the next scene change.
- Dull color during a hue change (`--brand` to `--success-bg`).
- Set sliding under the caption during a zoom.
- Chip outliving its card: its content must disappear, and the shape leave, with the card.
- Element invisible because it is drawn **under** the shape (the finger under the white link
  line): check the order in the HTML before touching the colors.
- Action happening outside the app shown in a set that looks like the app.
- Text leaving before it could be read (rule: 0.4 s + 0.3 s per word, still).
- Text overflowing its container after a label change (a longer domain in the link line): after
  any text edit, look at the full-size frame.
- Pause placed during a short effect (click ripple, sparks): the effect freezes on screen.
- Annotation that interprets a URL parameter ("Your profile" under a parameter that does not
  always mean the profile) or mentions an option absent from the link shown. Reread each
  annotation asking: is it true for **every** account, not only in the demo?

## After encoding

`render.js verify` compares six frames decoded from the MP4 with the same frames rendered again
(`tools.md`). Expected: mean difference around 1, point difference of 1 to 3 on flat areas, up to
12 on the edge of a vivid-colored text (chroma subsampling, normal). A mean difference above the
threshold (3 with ffmpeg, 5 with the browser's player), or of 10 **on a flat area**, signals a
color matrix or range problem: the command then exits with an error. Also look at
`decoded-frame-*.png` at full size.
