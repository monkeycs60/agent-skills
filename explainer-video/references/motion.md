# Motion: how a film is built

## The engine (`template/engine.js`, do not modify)

- Brand: `color('--brand')` turns a `brand.css` variable into `[r, g, b, a]` for `trA`;
  `alpha(c, a)` makes it an `rgba` string; `logos()` fills the `<img data-logo="light|dark">`;
  `brandFonts()` lists the fonts to wait for. **No hard-coded color** in the film: in CSS,
  `var(--brand)` and `color-mix(in srgb, var(--brand) 20%, transparent)` for transparency.
  In an SVG attribute (`fill`, `stroke`), `var()` does not work: use `style="fill:var(--brand)"`.

- `sp(t, t0, 'spring')`: 0 to 1 progress of a spring started at `t0`.
- `tr(t, v0, [[time, value, spring], ...])`: a value that changes target **several times**. One
  spring per change, never a restart: the motion stays continuous, and any frame is computed on
  its own, without simulating the previous ones.
- `trA`: the same for a color `[r, g, b, a]`.
- `io(t, in, out)`: visibility of an element.
- `enter(t, in, out, options)`: standard entrance and exit of a set (rises, sharpens, fades out
  in a blur).
- `imp(t, t0, amplitude)`: damped jolt. Negative for a click (the shape sinks in), positive for a
  success pulse.
- `put(el, {x, y, s, r, o, blur})`, `words(el)` (title split into words), `startFilm({...})`.

Springs: `snap` (buttons, icons), `ui` (interface, default), `def` (cards, the shape), `heavy`
(full screen, no bounce), `play` (chips, visible bounce), `cam` (camera, slow), `soft` (fades).
**Slight bounce on the interface, none on large texts.** Never a classic easing curve
(ease-in-out): that is what gives the "slideshow" effect.

## The single shape

1. **List its states** in `ST`: position, size, radius, one per step.
   Template example: `FULL` (full screen), `CHIP` (Join button, then chip), `MENU`, `INPUT`,
   `LINK`, `STICKER` (link line in the messaging app), `RING`.
2. **Chain the states** in `GEO`: `[time, 'STATE', spring]`. Background color in `BG_KEYS`,
   border, glow and shadow in their own key sequences.
3. **Each state has its content**: one layer per state (`#cChip`, `#cMenu`...), of fixed size
   equal to the state's, which appears **after** the shape arrives and disappears **before** it
   leaves (`snap` spring on the way out).
4. **Handover**: when the shape leaves an element that must stay on screen (the URL field stays
   while the link appears), an identical **fixed copy** appears on the same frame (`#inputS`), and
   the shape leaves again. The viewer sees no cut.
5. **Transition colors**: going from `--brand` to `--success-bg` often passes through a dull grey.
   Land the shape in a set that is **already there**, and change the color during the landing.
6. Ending: the shape settles as a **frame** on the real capture (`captureFrames()` reads the
   capture JSON, see `capture.md`), then widens into full screen `--brand`.

## Rhythm

- 0.5 s grid (120 beats per minute): changes land on the grid, so music can be added later
  without re-editing the film.
- Hook: 3 s at most, three one-word-ish phrases rising on the beats, one highlighted word.
- One step: 3 to 5 s. One idea per step, one caption per step (title + one line).
- A step can change subtitle midway (`SUBS`) when the action changes meaning.
- Ending: about 2.5 s of full screen `--brand` with logo, title and a "Full docs" pill.
- Total: about 7 s per step, pauses included. The reference film lasts 36.7 s for 5 steps.

## Leaving time to read (pauses)

Rule, checked on the reference film: **every text stays on screen, whole and still, for at least
0.4 s + 0.3 s per word**. An 8-word subtitle needs 2.8 s. Count from the moment the text has
**fully** appeared until its exit starts.

To keep the rule without slowing the motion down (which would lose its liveliness), the template
**pauses the film** at the moments when everything has settled:

```js
const HOLDS = [[2.0, 1.0], [3.6, .5], ...];   // [time in the film without pauses, pause length]
function hold(T) { let acc = 0; for (const [a, d] of HOLDS) { if (T < a + acc) return T - acc; if (T < a + acc + d) return a; acc += d; } return T - acc; }
function paint(T) { const t = hold(T); const u = warp(t); paintBase(u, T); scene1(t, u); }
```

- During a pause, everything that tells the story freezes; **the background keeps going** (halos,
  dot grid, camera breathing), as does everything that oscillates constantly (floating
  illustration, text caret, pulses): these elements use the ambient time `tReal`, never `t`.
- Place a pause **after** short effects end: a click ripple frozen mid-expansion makes a
  suspended circle.
- Place the pause **before** the caption exits, once the shape and the set have arrived.
- Check with a contact sheet taken in the middle of each pause: every frame must be complete and
  still.

## Lengthening a scene without shifting everything (edit)

A film carries about a hundred time marks. To lengthen a scene, do not shift them by hand: insert
time with `warp()`, as in the template, where scene 1 (Join, Pending, Member) got 1.2 s more than
the rest of the film.

```js
const INS_A = 4.3, INS_D = 1.2;   // at 4.3 s, insert 1.2 s
const warp = (t) => t <= INS_A ? t : (t <= INS_A + INS_D ? INS_A : t - INS_D);
function paint(t) { const u = warp(t); paintBase(u, t); scene1(t, u); }
```

- `paintBase(u, tReal)`: the whole film, on the shifted time. The background (halos, dot grid,
  camera breathing) uses `tReal`, otherwise it freezes during the insertion.
- `scene1(t, u)`: the lengthened scene, told in real time. It **overwrites** what the base draws
  during the insertion, and must **converge to the base's state** at `INS_A + INS_D`, when the
  base takes over again. Choose `INS_A` at a moment when the base is still.
- Layers created for the lengthened scene must be hidden outside its window.

## Camera

- `camFx`, `camFy`, `camZ` with the `cam` spring, plus an imperceptible breathing
  (`0.012 * sin(t * 0.35)`).
- Zoom (1.15 to 1.2) **only** on the key moment. Before zooming, clear what would slide under the
  caption band.
- The cursor lives in the world, but is counter-scaled (`/ camZ`) to keep the same size.

## Cursor and clicks

- Visible segments (`CUR`): it appears, moves with `def`, clicks, then disappears. It is never
  there when it serves no purpose.
- Each click: the cursor sinks in (negative `imp`), a ripple in the `--brand` color spreads, and
  the clicked element reacts on the same frame (color, `imp` on the shape).
- Aim next to the label, never on it.

## Texts

- Titles: masked words rising one by one (`words`, 0.045 s offset).
- Typed text: reveal by characters with a curve that slows down at the end, blinking text caret.
  Pasted text: left-to-right wipe in 0.25 s (more accurate than typing).
- A long text in a box: fit its size at initialization (loop in `init()`).
