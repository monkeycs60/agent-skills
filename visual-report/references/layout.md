# Writing the report

The reader opens the file to decide something. Everything serves that: the answer first, the proof next, the detail last.

## Order of a report

1. **Header**: a kicker (type of report and date), a title that states the outcome ("The Save button now enables as soon as the form is valid", not "Profile form"), one lead sentence with what remains to decide.
2. **Verdict** (`<section class="verdict ok|warn|ko">`): two or three sentences, readable without the rest.
3. **Proof**: before/after videos, key screenshots, numbers.
4. **What was checked**: a table, one line per check, result in `class="ok|warn|ko"`.
5. **Decision**, when the user has one: a table option, strength, weakness, confidence /10, the recommended option first.
6. **Detail** in `<details>`: method, raw data, logs. Collapsed, so it never hides the answer.

## Components of the stylesheet

| Markup | Renders as |
|---|---|
| `<main class="report">` | centered column, 1100 px max |
| `<p class="kicker">`, `<p class="lead">` | small colored label, larger grey intro |
| `<section>` | card |
| `<section class="verdict ok">` (`warn`, `ko`) | card with a colored edge and background |
| `<figure class="pair">` with two `<figure>` and a last `<figcaption>` | before on the left, after on the right, shared caption below; one slide in the viewer |
| `<div class="grid">` of `<figure>` | responsive grid of screenshots |
| `class="ok"`, `"warn"`, `"ko"` on any text | green, amber, red |
| `<details><summary>` | collapsed block |
| `data-no-zoom` on an image or a container | excluded from the viewer |

Plain HTML (tables, lists, `<pre><code>`, headings) is styled too. Light and dark follow the reader's system. Add a `<style>` block of your own when the content needs it; keep it in the file.

## Media

- Screenshots: crop to the part that matters. Text in a screenshot must stay readable at half the column width (about 500 px). PNG for interface text, JPEG or WebP for photos and large captures.
- Before and after: same flow, same data, same window size, the "before" always on the left.
- Captions say what to look at ("watch the Save button at 0:04"), not what the file is.
- `alt` on every image, `title` on every video: the viewer and screen readers use them.
- Never put secrets, tokens in URLs, personal emails or someone else's data in a capture: crop or blur before embedding.

## Size

The file carries its media, so its size is the sum of the media plus about 30 %.

| Item | Typical size |
|---|---|
| UI screenshot, PNG, 1280 px | 100 to 300 KB |
| Same as JPEG quality 80 | 60 to 150 KB |
| 15 s video, 1280 px, 15 fps, `to-mp4.sh` | 0.2 to 1 MB, more when the whole screen moves (scrolling) |

Pupitre accepts 2 MiB per HTML document: two videos and four screenshots fit. Over budget, in this order: shorten the videos to the moment that matters, downscale them (`to-mp4.sh in out 960 12`), switch screenshots to JPEG or WebP, crop.

## Writing

- Absolute dates, measured numbers with their unit, no "fast" or "much better" without a figure.
- One idea per section; a section title says its conclusion.
- Write in the language of the user's request.
- Do not repeat the report in the chat: the chat gives the verdict and what the user must decide.
