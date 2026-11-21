# Art direction of doc films

Everything comes from the project's app, not from an interpretation: colors, fonts, radii and
logos are extracted from the code and measured on the app, then written into `brand.css` (method:
`brand.md`). This file describes what does not depend on the brand: color roles, sizes, grid,
components. The filled-in example is `example/brand.css`.

## Color roles

| Variable | Role in the film |
|---|---|
| `--brand` | Full screen of the hook and the ending, the single shape, numbered badges, text caret, progress bar |
| `--ink` | Titles, interface labels, mouse cursor |
| `--bg` | Film background between the hook and the ending |
| `--surface`, `--line` | Cards and fields, their borders |
| `--tint`, `--tint-2` | Active menu item, highlighted area (the result), hover |
| `--accent` | Highlighted word of the hook, thumbnail promise, sparks |
| `--success*`, `--warning*` | Status chips (approved, pending) |
| `--muted`, `--txt2` | Caption subtitles, secondary text |
| `--dots`, `--halo-*`, `--track` | Dot grid, background halos, progress bar track |

Film background: `--bg`, a `--dots` dot grid spaced 40 px apart at 55 % opacity, and three very
soft halos drifting slowly (`--halo-1` to `--halo-3`). The full screen `--brand` carries a sheen
(`#sheen`): light at the top left, `--brand-deep` shadow at the bottom right.

## Typography

- **Title font** (`--font-title`) for every title: 900 for captions and the hook, 800 for card
  titles, 700 for section titles. Tight letter spacing (-0.035 em on captions, -0.045 em on the
  hook); loosen it if the font is already narrow.
- **Body font** (`--font-body`) for everything else.
- Sizes on the 1920 x 1080 frame (the film is often watched 800 px wide, i.e. 0.42 times): hook
  124 px, caption 60 px, subtitle 30 px, interface text 28 to 32 px, labels 22 to 26 px. Below
  22 px, it is unreadable once the video is embedded in a page.

## Frame grid

- **Caption band** at the top left: `left:120px; top:70px`, 66 px numbered badge, title,
  subtitle. It reaches about y = 215: nothing important above y = 250.
- **Sets** between y = 250 and y = 1000. A narrow set (menu) goes on the right (x ≈ 1060), to
  balance the caption; a wide set (form) takes the full width.
- **Progress bar** at the bottom center (`left:810px; top:1034px`, 300 x 8 px), one segment per
  step.
- The camera can zoom, but the caption band never moves (it is outside the world).

## Components (exact markup in `template/film.html`)

| Component | Where to find it in the template |
|---|---|
| Card (`--surface`, `--radius-card` radius, soft shadow) | `.card` class |
| App sidebar, labels from the code | `#side`, `.row` lines, `.sect` sections |
| Form field, dropdown | `.field`, `#sel` |
| Result area (`--tint` background, bold `--brand` text, copy icon) | `#cLink` content of the shape |
| Status chip (`--success`, dot) | `#cChip` content, `#auto` |
| Keyboard keys (Ctrl + V) | `#keys`, `.kc` |
| Annotation bubble linked by a line ("Invite code" under the link's code) | `#call`, `#hl` highlight |
| Cursor, click ripple, burst of sparks | `#cursor`, `#ripple`, `#burst` |
| Browser window around a real capture | `#real` |
| Numbered caption, titles split into words | `.cap`, `.badge`, `.ttl`, `.sub` |
| Ending: `--logo-dark` logo, title, "Full docs" pill | `#outro` |

Logos: `<img data-logo="light">` and `<img data-logo="dark">`, filled by `logos()` from
`--logo-light` and `--logo-dark`. Never a redrawn logo.

Icons: inline SVG, 1.7 to 2 stroke, `currentColor`. Never Unicode glyphs. If the app uses an icon
library (Lucide, Material Symbols, Heroicons...), copy the SVG path of the same icon.

## Showing what happens outside the app

An app-like white card to "share the link" suggests everything happens **inside the app**. When
the action takes place elsewhere (social network, website, email), show it **on that medium**, in
a phone or a window that does not look like the app.

- The template contains a **suggested messaging app** (`#phone`): conversation header, bubbles,
  link preview, "Write a message" field, in neutral greys that do not recall the app. The invite
  link becomes the preview's **link line** there, which the shape comes to occupy.
- Show the action where it really works on that medium (a link pasted in an Instagram post
  caption is not clickable: story sticker or bio).
- Suggest a third party's interface, **never its logo** or its visual brand.
- A mobile gesture is shown with a **finger** (translucent grey circle with a white edge,
  `#touch`), not the cursor. It must be drawn **above** the shape (order in the HTML).

## Making a prerequisite readable

A status alone ("Approved") tells nothing. Show the sequence that leads to it, with the real
labels from the code: in the reference film, a **Join** button on a card tagged **Spaces**, a
click, a `--warning` **Pending** chip, then `--success` **Member**. The subtitle announces the
next step before it arrives.

Illustrations: simple, rounded shapes, in SVG. No downloaded image, no realistic character.

**No plush toy, toy or childish visual**, even when the demo data lends itself to it. Prefer a
**neutral object tied to the product's domain**, in the brand colors: the checklist of `#object`
(film) and of `template/thumbnail.html` is the reference for a task product; a shopping bag would
suit a store. For each illustration, ask yourself: how would someone ill-intentioned read it, out
of context?
