# Extracting the project brand

The film must look like the app **of this project**, not like the reference film. All visuals go
through a single file, `brand.css`: colors, fonts, logos, radii. The film, the thumbnail and the
kit read it; none of them contains a hard-coded brand color.

The brand is extracted **once per project**, in `$EXPLAINER_VIDEO_DIR/<project>/brand.css`, then
copied into each film. Filled-in example: `example/brand.css` (fictional product Coche, each value
points to `example/mockup.html`). Extract it again only if the app changed its identity.

## Method, in this order

1. **Inventory**: `node $S/brand-inventory.js <repo-root>`. In a monorepo, run it at the
   **root**: the brand often lives in a shared package (the script reports the variables used but
   defined elsewhere). It lists the UI stack, the theme files, the light and dark CSS variables,
   the themes declared in code, the fonts, the logos and the most used colors.
2. **Read the sources** the inventory points to. The code wins: a color defined as `primary` in
   the theme beats the most frequent color.
3. **Measure on the running app** (local server, demo, staging with fictional data) with
   `capture.js` and its `styles` key (`capture.md`): primary button, page background, card, active
   menu item, field, success badge. Computed styles settle ambiguities (overridden theme, dead
   variable, forced dark mode).
4. **Fill in `brand.css`** from `template/brand.css`, **one source comment per value** (file and
   variable, or "measured on /dashboard"). Remove the `BRAND-NOT-FILLED` line, otherwise
   `render.js` refuses to render.
5. **Check** with a contact sheet (`render.js contact-sheet`): hook, one step, the ending. Ask
   yourself whether someone on the team would recognize their product at first glance.

## Where to find each value

| Variable | Tailwind v4 / shadcn | Tailwind v3 | MUI | Chakra, Mantine | Custom CSS |
|---|---|---|---|---|---|
| `--brand` | `--primary`, `--color-primary`, `@theme` | `theme.extend.colors.primary` | `palette.primary.main` | `colors.brand.500`, `primaryColor` | primary button variable |
| `--ink` | `--foreground` | `colors.gray.900`, most used `text-*` | `palette.text.primary` | `colors.gray.800` | `color` of `body` |
| `--bg` | `--background` | layout `bg-*` | `palette.background.default` | global `bg` | `background` of `body` or the layout |
| `--surface` | `--card` | `bg-white` of the cards | `palette.background.paper` | `white` | card background |
| `--line` | `--border`, `--input` | `border-gray-200` | `palette.divider` | `gray.200` | field border |
| `--muted`, `--txt2` | `--muted-foreground` | `text-gray-500` / `600` | `palette.text.secondary` | `gray.500` / `600` | secondary text |
| `--accent` | `--accent` if it is vivid, otherwise a secondary brand color | `colors.accent` | `palette.secondary.main` | `colors.accent` | call-to-action color |
| `--success*`, `--warning*` | `--success`, `--destructive` | `green-*`, `amber-*` | `palette.success`, `palette.warning` | `green`, `orange` | status badges |
| `--tint` | pale `--accent`, active item | `primary-50` / `100` | `alpha(primary, .08)` | `brand.50` | active menu item background |
| `--radius-*` | `--radius` | `borderRadius` | `shape.borderRadius` | `radii` | `border-radius` of the cards |
| `--font-*` | `--font-sans`, `next/font` | `fontFamily.sans` | `typography.fontFamily` | `fonts.heading` / `body` | `@font-face`, Google Fonts |

Values like `262 83% 58%` (shadcn): write `hsl(262 83% 58%)`. The `oklch()`, `hsl()` and
`color-mix()` formats are accepted as they are: the engine's `color()` converts them.

Derived variables (`--brand-deep`, `--tint`, `--halo-*`...) are computed on their own from the
base colors. Override them only if the project defines the equivalent (active item, hover).

## Fonts

- **Google Fonts**: `@import` at the top of `brand.css`, with every weight the film uses (500 to
  900) and `display=block`. The render then needs the network; offline, download the font files
  (OFL license) into `assets/` and go through `@font-face`.
- **Local font** (in `public/fonts/`, `assets/`...): copy it into `<film>/assets/`, then
  `@font-face` with `font-display: block`. **Read its license first**: many (Fontshare,
  commercial fonts) allow use but forbid redistribution. The copy then stays in the film folder,
  never published or versioned.
- **System font** (`system-ui`): the render depends on the machine. Prefer the closest free font
  (Inter, Geist, Manrope) and say so. Inter ships in `template/assets/fonts/` (Latin subset,
  weights 100 to 900, OFL license included): it is the template's default fallback.
- If the title font has no 900 weight, the browser takes the boldest: check on the contact sheet
  that titles look neither thin nor fake bold.
- Titles and text can share the same font: it is often the case in an app.

## Logos

- `--logo-light`: logo for a light background (sidebar, header). `--logo-dark`: logo **readable
  on `--brand`** (end of the film, thumbnail, kit header), often the white version.
- Take the project's **official** files (SVG preferably), never a redrawn logo. Relative to the
  film folder (`url('assets/logo.svg')`) or an absolute URL.
- No logo: leave `none`, the film writes `--name` in the title font.
- A colored PNG placed on `--brand` often disappears: look at the end of the film and the
  thumbnail.

## Pitfalls

| Pitfall | Reality |
|---|---|
| Dark-mode-only app | Set `--bg`, `--surface`, `--line` dark and `--ink` light, then check every set: the reference film assumes light cards, some white texts on `--brand` stay right, others do not. |
| Two themes (light and dark) | Light by default: it reads better once the video is scaled down. Dark only if it is the product's identity. |
| `--accent` too close to `--brand` | The highlighted word of the hook no longer stands out. Pick a contrasting secondary color (yellow, orange, bright green) taken from the brand. |
| Most frequent color = grey or white | Normal. The brand color is the one of the primary button and active links, not the most used. |
| CSS variable defined but dead | Measure on the app (`styles` of `capture.js`) before keeping it. |
| Radii too small in the film | The film is watched scaled down: double the app's radii (`--radius-card`, `--radius-field`). |
| No design system (young project) | Start from the logo or the home page: `--brand` = dominant color of the logo, neutral greys, Inter. Write it in the notes of `README.md`. |
