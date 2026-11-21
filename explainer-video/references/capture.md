# Capturing the app's real screen

`node $S/capture.js recipe.json` opens a page in a headless browser, prepares it, photographs it
(PNG, `dsf` times the viewport size) and writes a JSON next to it: frames of the chosen elements
(`boxes`) and computed styles of sample elements (`styles`, to fill in `brand.css`).

**Fictional data only**: local server, demo or staging, never a real account.

## Recipe

Only `url` and `output` are required. A relative path (local `url`, `output`) is read from the
recipe's folder.

```json
{
  "url": "http://localhost:5173/login",
  "viewport": [1440, 900], "dsf": 2, "lang": "en-US", "theme": "light",
  "output": "assets/real-screen-en.png",
  "wait": 1500,
  "cookies": [{ "name": "session", "value": "...", "domain": "localhost" }],
  "localStorage": { "onboardingSeen": "1" },
  "dismiss": "^(OK|Later|Accept all|Next|Close)$",
  "steps": [
    { "type": { "selector": "input[type=email]", "text": "demo@example.com" } },
    { "click": "Sign in" },
    { "waitFor": "/dashboard/.test(location.href)" },
    { "goto": "http://localhost:5173/invitations" },
    { "pause": 1500 },
    { "hide": ".cookie-banner" },
    { "js": "document.querySelector('input').focus()" }
  ],
  "boxes": { "linkArea": "document.querySelector('#link')", "menuItem": "minWidth(leaf(/^Invite$/), 120)" },
  "styles": { "primaryButton": "document.querySelector('button[type=submit]')", "activeItem": "leaf(/^Dashboard$/)" }
}
```

| Key | Effect |
|---|---|
| `url` | `http(s)://` or `file://` address, or a local path (with an optional `?lang=...`) |
| `wait` | Pause after loading, once fonts and images are ready (default 1,500 ms over http, 0 for a file) |
| `dismiss` | Regular expression of the buttons that close carousels, what's-new popups and banners; applied after each step |
| `click` | Exact text of a button or link, `/regular expression/`, or a CSS selector prefixed with `css:` |
| `waitFor` | JavaScript expression awaited until true (25 s at most) |
| `boxes`, `styles` | JavaScript expressions that return an element; helpers: `leaf(re)` (DOM leaf whose text matches), `ancestorWithBg(el, 'rgb(...)')`, `minWidth(el, px)` |

A session is needed and cookies are not enough: sign in with the agent's browser if it has one,
or through the `steps` (type, click, waitFor).

## From the JSON to the film

Frames are in CSS pixels of the viewport. The film shows the capture in `#real`, 1,120 px wide:
scale `1120 / viewport[0]`, origin (400, 306) in the world. `captureFrames()` in
`template/film.html` reads `assets/real-screen-<lang>.json` and places on its own:
- the shape's `RING` state (final frame) on `boxes.linkArea`, 7 px margin;
- the `#ring2` ring on `boxes.menuItem`, 5 px margin.

Keep these two box names, or adapt `captureFrames()`. The film opened from disk (`file://`) does
not read the JSON and keeps the frames written in `ST`: only the render by `render.js` counts.

One capture per language: the recipe's `"lang"` and the app's `?lang=` if it exists, output
`real-screen-<lang>.png`.
