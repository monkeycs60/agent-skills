# Direction artistique et brief Codex

## Questionnaire quand la DA manque

Poser toutes les questions en une fois (AskUserQuestion si disponible, sinon une liste courte), chacune avec une réponse par défaut proposée.

- **Nature** : scène plein cadre, objet isolé, icône, portrait, texture, fond ?
- **Usage et taille d'affichage** : où l'image apparaît, taille minimale à l'écran, recadrage imposé par l'interface (bandeau, cercle, carré) ?
- **Ratio et format** : ratio source et ratio affiché, dimensions et format servis (WebP, PNG, SVG), qualité ?
- **Fond** : transparent ou plein cadre, couleur de fond de l'interface pour les bords ?
- **Style** : réalisme ou illustration, références, exclusions (texte, logos, cartoon…) ?
- **Palette et lumière** : hex de la charte, moment de la journée, ambiance ?
- **Cohérence** : série existante à égaler ou nouvelle série ?

Ensuite, proposer d'ajouter ou de compléter la section « Direction artistique » du README du projet avec un tableau des familles (dossier servi, source, format, fond, usage) : les générations suivantes n'auront plus à reposer les questions.

## DA commune d'un lot

Style, palette en hex, lumière, cadrage, format, fond (plein cadre ou transparent), usages et tailles d'affichage. La lisibilité se juge à la plus petite taille d'affichage.

## Modèle de brief

Fichier `/tmp/<slug>-prompt.md`, en anglais :

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
