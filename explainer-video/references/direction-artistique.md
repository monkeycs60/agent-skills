# Direction artistique des films de doc

Tout vient de l'app du projet, pas d'une interprétation : les couleurs, polices, rayons et logos
sont relevés dans le code et mesurés sur l'app, puis écrits dans `charte.css` (méthode :
`charte.md`). Ce fichier décrit ce qui ne dépend pas de la marque : rôles des couleurs, tailles,
grille, composants. L'exemple rempli est `exemple/charte.css`.

## Rôles des couleurs

| Variable | Rôle dans le film |
|---|---|
| `--brand` | Plein écran de l'accroche et de la fin, la forme unique, pastilles numérotées, curseur texte, barre de progression |
| `--ink` | Titres, libellés d'interface, curseur de souris |
| `--bg` | Fond du film entre l'accroche et la fin |
| `--surface`, `--line` | Cartes et champs, leurs bordures |
| `--tint`, `--tint-2` | Item de menu actif, zone mise en valeur (le résultat), survol |
| `--accent` | Mot surligné de l'accroche, promesse de la miniature, étincelles |
| `--success*`, `--warning*` | Pastilles de statut (validé, en attente) |
| `--muted`, `--txt2` | Sous-titres des légendes, texte secondaire |
| `--dots`, `--halo-*`, `--track` | Trame de points, halos du fond, rail de la barre de progression |

Fond du film : `--bg`, trame de points `--dots` espacés de 40 px à 55 % d'opacité, et trois
halos très doux qui dérivent lentement (`--halo-1` à `--halo-3`). Le plein écran `--brand` porte un
reflet (`#sheen`) : lumière en haut à gauche, ombre `--brand-deep` en bas à droite.

## Typographie

- **Police de titre** (`--font-title`) pour tous les titres : 900 pour les légendes et l'accroche,
  800 pour les titres de carte, 700 pour les titres de section. Interlettrage serré
  (-0.035 em sur les légendes, -0.045 em sur l'accroche) ; le desserrer si la police est déjà étroite.
- **Police de texte** (`--font-body`) pour tout le reste.
- Tailles sur l'image 1920 x 1080 (le film est souvent vu à 800 px de large, soit 0,42 fois) :
  accroche 124 px, légende 60 px, sous-titre 30 px, texte d'interface 28 à 32 px, étiquettes 22 à 26 px.
  En dessous de 22 px, c'est illisible une fois la vidéo intégrée dans une page.

## Grille de l'image

- **Bande de légende** en haut à gauche : `left:120px; top:70px`, pastille numérotée de 66 px,
  titre, sous-titre. Elle occupe jusqu'à y = 215 environ : rien d'important au-dessus de y = 250.
- **Décors** entre y = 250 et y = 1000. Un décor étroit (menu) se place à droite
  (x ≈ 1060), pour équilibrer la légende ; un décor large (formulaire) occupe la largeur.
- **Barre de progression** en bas au centre (`left:810px; top:1034px`, 300 x 8 px), un segment
  par étape.
- La caméra peut zoomer, mais la bande de légende ne bouge jamais (elle est hors du monde).

## Composants (balisage exact dans `modele/film.html`)

| Composant | Où le trouver dans le modèle |
|---|---|
| Carte (`--surface`, rayon `--radius-card`, ombre douce) | classe `.card` |
| Barre latérale de l'app, libellés du code | `#side`, lignes `.row`, rubriques `.sect` |
| Champ de formulaire, liste déroulante | `.field`, `#sel` |
| Zone de résultat (fond `--tint`, texte `--brand` gras, icône de copie) | contenu `#cLink` de la forme |
| Pastille de statut (`--success`, point) | contenu `#cChip`, `#auto` |
| Touches de clavier (Ctrl + V) | `#keys`, `.kc` |
| Bulle d'annotation reliée par un trait (« Code d'invitation » sous le code du lien) | `#call`, surlignage `#hl` |
| Curseur, onde de clic, gerbe d'étincelles | `#cursor`, `#ripple`, `#burst` |
| Fenêtre de navigateur autour d'une vraie capture | `#real` |
| Légende numérotée, titres découpés en mots | `.cap`, `.badge`, `.ttl`, `.sub` |
| Fin : logo `--logo-fonce`, titre, pastille « La doc complète » | `#outro` |

Logos : `<img data-logo="clair">` et `<img data-logo="fonce">`, remplis par `logos()` depuis
`--logo-clair` et `--logo-fonce`. Jamais de logo redessiné.

Icônes : SVG en ligne, trait 1,7 à 2, `currentColor`. Jamais de glyphes Unicode. Si l'app emploie une
bibliothèque d'icônes (Lucide, Material Symbols, Heroicons...), recopier le tracé SVG de la même icône.

## Montrer ce qui se passe hors de l'app

Une carte blanche façon app pour « partager le lien » donne l'impression que tout se passe
**dans l'app**. Quand l'action a lieu ailleurs (réseau social,
site, e-mail), la montrer **sur ce support**, dans un téléphone ou une fenêtre qui ne ressemble pas
à l'app.

- Le modèle contient une **messagerie évoquée** (`#phone`) : en-tête de conversation, bulles,
  aperçu de lien, champ « Écrire un message », dans des gris neutres qui ne rappellent pas l'app. Le
  lien d'invitation y devient la **ligne de lien** de l'aperçu, que la forme vient occuper.
- Montrer l'action là où elle marche vraiment sur ce support (un lien collé dans la légende d'un post
  Instagram n'est pas cliquable : sticker de story ou bio).
- Évoquer l'interface d'un tiers, **jamais son logo** ni sa marque graphique.
- Un geste sur mobile se montre par un **doigt** (cercle gris translucide à bord blanc, `#touch`),
  pas par le curseur. Il doit être dessiné **au-dessus** de la forme (ordre dans le HTML).

## Rendre un prérequis lisible

Un statut seul (« Validé ») ne raconte rien. Montrer l'enchaînement qui y mène, avec les vrais
libellés du code : dans le film de référence, bouton **Rejoindre** sur une carte étiquetée
**Espaces**, clic, pastille `--warning` **En attente**, puis `--success` **Membre**. Le sous-titre annonce l'étape suivante avant qu'elle n'arrive.

Illustrations : formes simples et rondes, en SVG. Pas d'image téléchargée, pas de personnage réaliste.

**Pas de peluche, de jouet ni de visuel enfantin**, même quand les données de démo s'y prêtent. Préférer
un **objet neutre lié au domaine du produit**, aux couleurs de la charte : la liste à cocher de
`#objet` (film) et de `modele/miniature.html` est la référence pour un produit de tâches ; un sac
shopping irait à un commerce. Se demander, pour chaque illustration : comment la lirait quelqu'un de
mal intentionné, sorti de son contexte ?
