# Art direction and Codex brief

## Questionnaire when the art direction is missing

Ask every question at once (AskUserQuestion if available, otherwise a short list), each with a suggested default answer.

- **Kind**: full-bleed scene, isolated object, icon, portrait, texture, background?
- **Use and display size**: where the image appears, minimum on-screen size, crop imposed by the UI (banner, circle, square)?
- **Ratio and format**: source ratio and displayed ratio, served dimensions and format (WebP, PNG, SVG), quality?
- **Background**: transparent or full-bleed, UI background color for the edges?
- **Style**: realism or illustration, references, exclusions (text, logos, cartoon…)?
- **Palette and lighting**: brand hex colors, time of day, mood?
- **Consistency**: an existing series to match or a new series?

Then offer to add or complete the "Art direction" section of the project's README with a table of asset families (served folder, source, format, background, use): later generations won't need to ask the questions again.

## Shared art direction of a batch

Style, palette in hex, lighting, framing, format, background (full-bleed or transparent), uses and display sizes. Legibility is judged at the smallest display size.

## Brief template

File `/tmp/<slug>-prompt.md`, in English:

```markdown
Use your imagegen skill (built-in image_gen tool, one call per image) to generate <N> <type> for <project, context>.

## Art direction (applies to every image)
- <style: realistic / illustration / etc., what to avoid explicitly>
- <format: "Full-bleed square scene (1024x1024), no text, no logos, no UI" or "transparent background">
- <shared palette, lighting, setting>
- <framing, legibility at the smallest display size>

## Subjects (file name = id)
1. <id>: <description>
...

## Output
- After each generation, copy the chosen file from $CODEX_HOME/generated_images/... to `<folder>/<id>.png`. Keep exactly one file per id.
- Keep the set visually consistent. If an image is off-brief (style, text, clutter), regenerate it.
- At the end, write `<folder>/README.md` listing each id with the final prompt used, and report which files exist.
```
