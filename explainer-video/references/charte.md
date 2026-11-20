# Relever la charte du projet

Le film doit ressembler à l'app **de ce projet**, pas au film de référence. Tout le visuel passe par
un seul fichier, `charte.css` : couleurs, polices, logos, rayons. Le film, la miniature et le kit le
lisent ; aucun d'eux ne contient de couleur de marque en dur.

La charte se relève **une fois par projet**, dans `$EXPLAINER_VIDEO_DIR/<projet>/charte.css`, puis se
copie dans chaque film. Exemple rempli : `exemple/charte.css` (produit fictif Coche, chaque valeur
renvoie à `exemple/maquette.html`). La relire seulement si l'app a changé d'identité.

## Méthode, dans cet ordre

1. **Inventaire** : `node $S/inventaire-charte.js <racine-du-dépôt>`. Dans un monorepo, le lancer à
   la **racine** : la charte vit souvent dans un paquet partagé (le script signale les variables
   employées mais définies ailleurs). Il liste la pile UI, les fichiers de thème, les variables CSS
   claires et sombres, les thèmes déclarés en code, les polices, les logos et les couleurs les plus
   employées.
2. **Lire les sources** que l'inventaire désigne. Le code prime : une couleur définie comme
   `primary` dans le thème l'emporte sur la couleur la plus fréquente.
3. **Mesurer sur l'app qui tourne** (serveur local, démo, préproduction à données fictives) avec
   `capturer.js` et sa clé `styles` (`capture.md`) : bouton principal, fond de page, carte, item de
   menu actif, champ, pastille de succès. Les styles calculés tranchent les ambiguïtés (thème
   surchargé, variable morte, mode sombre forcé).
4. **Remplir `charte.css`** à partir de `modele/charte.css`, **une source en commentaire par
   valeur** (fichier et variable, ou « mesuré sur /dashboard »). Retirer la ligne
   `CHARTE-NON-REMPLIE`, sans quoi `render.js` refuse de rendre.
5. **Vérifier** avec une planche (`render.js planche`) : accroche, une étape, la fin. Se demander
   si quelqu'un de l'équipe reconnaîtrait son produit au premier coup d'œil.

## Où trouver chaque valeur

| Variable | Tailwind v4 / shadcn | Tailwind v3 | MUI | Chakra, Mantine | CSS maison |
|---|---|---|---|---|---|
| `--brand` | `--primary`, `--color-primary`, `@theme` | `theme.extend.colors.primary` | `palette.primary.main` | `colors.brand.500`, `primaryColor` | variable du bouton principal |
| `--ink` | `--foreground` | `colors.gray.900`, `text-*` le plus employé | `palette.text.primary` | `colors.gray.800` | `color` de `body` |
| `--bg` | `--background` | `bg-*` du layout | `palette.background.default` | `bg` global | `background` de `body` ou du layout |
| `--surface` | `--card` | `bg-white` des cartes | `palette.background.paper` | `white` | fond des cartes |
| `--line` | `--border`, `--input` | `border-gray-200` | `palette.divider` | `gray.200` | bordure des champs |
| `--muted`, `--txt2` | `--muted-foreground` | `text-gray-500` / `600` | `palette.text.secondary` | `gray.500` / `600` | texte secondaire |
| `--accent` | `--accent` s'il est vif, sinon une couleur secondaire de la marque | `colors.accent` | `palette.secondary.main` | `colors.accent` | couleur d'appel |
| `--success*`, `--warning*` | `--success`, `--destructive` | `green-*`, `amber-*` | `palette.success`, `palette.warning` | `green`, `orange` | badges de statut |
| `--tint` | `--accent` pâle, item actif | `primary-50` / `100` | `alpha(primary, .08)` | `brand.50` | fond de l'item de menu actif |
| `--radius-*` | `--radius` | `borderRadius` | `shape.borderRadius` | `radii` | `border-radius` des cartes |
| `--font-*` | `--font-sans`, `next/font` | `fontFamily.sans` | `typography.fontFamily` | `fonts.heading` / `body` | `@font-face`, Google Fonts |

Valeurs du type `262 83% 58%` (shadcn) : écrire `hsl(262 83% 58%)`. Les formats `oklch()`,
`hsl()`, `color-mix()` sont acceptés tels quels : `couleur()` du moteur les convertit.

Les variables dérivées (`--brand-deep`, `--tint`, `--halo-*`...) se calculent seules à partir des
couleurs de base. Ne les surcharger que si le projet définit l'équivalent (item actif, survol).

## Polices

- **Google Fonts** : `@import` en tête de `charte.css`, avec toutes les graisses employées par le
  film (500 à 900) et `display=block`. Le rendu a alors besoin du réseau ; hors ligne, télécharger les
  fichiers de la police (licence OFL) dans `assets/` et passer par `@font-face`.
- **Police locale** (dans `public/fonts/`, `assets/`...) : la copier dans `<film>/assets/`, puis
  `@font-face` avec `font-display: block`. **Lire sa licence d'abord** : beaucoup (Fontshare,
  polices commerciales) autorisent l'usage mais interdisent la redistribution. La copie reste alors
  dans le dossier du film, jamais publiée ni versionnée.
- **Police système** (`system-ui`) : le rendu dépend de la machine. Préférer la police libre la plus
  proche (Inter, Geist, Manrope) et le signaler. Inter est fournie dans `modele/assets/polices/`
  (sous-ensemble latin, graisses 100 à 900, licence OFL jointe) : c'est le repli par défaut du gabarit.
- Si la police de titre n'a pas de graisse 900, le navigateur prend la plus forte : vérifier sur la
  planche que les titres ne paraissent ni maigres ni faussement grasses.
- Titres et texte peuvent partager la même police : c'est souvent le cas dans une app.

## Logos

- `--logo-clair` : logo pour fond clair (barre latérale, en-tête). `--logo-fonce` : logo **lisible
  sur `--brand`** (fin du film, miniature, en-tête du kit), souvent la version blanche.
- Prendre les fichiers **officiels** du projet (SVG de préférence), jamais un logo redessiné.
  Relatif au dossier du film (`url('assets/logo.svg')`) ou URL absolue.
- Aucun logo : laisser `none`, le film écrit `--nom` dans la police de titre.
- Un PNG coloré posé sur `--brand` disparaît souvent : regarder la fin du film et la miniature.

## Pièges

| Piège | Réalité |
|---|---|
| App uniquement en mode sombre | Mettre `--bg`, `--surface`, `--line` sombres et `--ink` clair, puis vérifier chaque décor : le film de référence suppose des cartes claires, certains textes blancs sur `--brand` restent justes, d'autres non. |
| Deux thèmes (clair et sombre) | Le clair par défaut : il se lit mieux une fois la vidéo réduite. Le sombre seulement si c'est l'identité du produit. |
| `--accent` trop proche de `--brand` | Le mot surligné de l'accroche ne se détache plus. Choisir une couleur secondaire contrastée (jaune, orange, vert vif) prise dans la marque. |
| Couleur la plus fréquente = gris ou blanc | Normal. La couleur de marque est celle du bouton principal et des liens actifs, pas la plus employée. |
| Variable CSS définie mais morte | Mesurer sur l'app (`styles` de `capturer.js`) avant de la retenir. |
| Rayons trop petits dans le film | Le film est vu réduit : doubler les rayons de l'app (`--radius-card`, `--radius-field`). |
| Aucun design system (projet naissant) | Partir du logo ou de la page d'accueil : `--brand` = couleur dominante du logo, gris neutres, Inter. L'écrire dans les points relevés du `LISEZ-MOI.md`. |
