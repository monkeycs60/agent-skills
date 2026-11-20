# Kit de publication YouTube

Règle : pour **chaque** vidéo destinée à YouTube, une miniature parfaite, un titre et une
description optimisés pour la recherche YouTube, « épurés et quali », réunis dans un HTML. Le kit
se fabrique **après** la vidéo validée et ne la modifie jamais.

## Fichiers

| Fichier | Rôle |
|---|---|
| `miniature.html` (dossier du film, copié depuis `modele/`) | La miniature, 1280 x 720, dessinée en HTML comme le film |
| `youtube-<lang>.json` (dossier du film) | Titre, description, tags, réglages, `chaine` (nom affiché dans les aperçus, sinon `--nom` de la charte) |
| `out/<film>-<lang>-miniature.jpg` et `.png` | `render.js <film> miniature <lang>` |
| `out/kit-youtube-<lang>.html` | `kit.js <film> <lang>` : aperçus, boutons Copier, contrôles automatiques |

`kit.js` vérifie tout seul : titre de 100 caractères au plus (idéal 70), description de 5 000 au
plus, chapitres valides (premier à 00:00, trois au moins, 10 s chacun au moins), tags sous 500
caractères, 1 à 15 hashtags, aucun tiret cadratin, **liens de la description en HTTP 200**,
miniature JPG sous 2 Mo et en 1280 x 720. Ne livrer que si tout est vert.

## Miniature

Elle se juge à **168 x 94** (colonne « à suivre ») : le kit l'affiche à cette taille, la regarder.

- **3 à 5 mots**, dans la police de titre de la charte (graisse 900 ou la plus forte disponible), 120 px ou
  plus, blanc sur `--brand`. Un seul mot ou une promesse sur un bandeau `--accent`, texte `--ink`.
- **Un seul objet fort**, repris du film (le téléphone, la conversation et son aperçu de lien pour
  « Inviter son équipe »). Jamais de peluche ni de visuel enfantin (voir `direction-artistique.md`). Pas de capture d'écran de l'app : illisible en petit.
- Le **logo blanc** officiel en haut à gauche, et rien d'autre en plus du message et de l'objet :
  pas de badge « Tuto » ni de catégorie, qui encombre.
- **Coin bas droit libre** : YouTube y affiche la durée.
- Même lumière que le film : reflet en haut à gauche, profondeur en bas à droite, trame de points
  qui s'efface vers la droite.
- Rien de faux ni d'exagéré : une promesse de durée (« en 30 secondes ») n'est permise que si
  l'action prend vraiment ce temps une fois les prérequis remplis.

## Titre

- Le **mot-clé que les gens tapent** en premier. Exemple du film de référence : on tape « partager
  une liste de tâches » bien plus que « lien d'invitation », le terme de l'app : mettre le terme
  courant dans le titre, le terme de l'app dans la miniature et la description.
- La marque, puis une promesse vérifiable. 60 caractères au plus pour rester entier sur téléphone.
- Pas de majuscules criardes, pas d'emoji, pas de point d'exclamation, pas de « incroyable ».
- Exemple : « Partager une liste de tâches avec son équipe sur Coche » (54 caractères).
- Pour un projet perso sans audience, le nom du produit compte moins que le problème résolu :
  « Planifier ses séances de course en 2 minutes » plutôt que « Découvrez MonApp ».

## Description

1. **Deux premières lignes** (environ 150 caractères, visibles avant « plus ») : le mot-clé, le terme
   de l'app entre parenthèses, et ce qu'on apprend. Le kit les surligne.
2. **Chapitres** « Au programme » : `00:00`, puis une ligne par grande étape. Les instants se lisent
   dans le film **avec les pauses** (l'apparition des légendes, voir `CAPS` et `HOLDS`).
3. **En résumé** : les étapes numérotées, avec les **libellés exacts** de l'app, comme dans la doc.
4. Les **liens vers la doc** complète et une doc voisine utile, vérifiés en HTTP 200. Les domaines
   réservés aux exemples (`example.com`, `*.example`) ne sont pas vérifiés : le kit le signale.
5. **Trois hashtags** en dernière ligne (les trois s'affichent au-dessus du titre) :
   `#<Produit> #<domaine> #tutoriel` (film de référence : `#Coche #productivité #tutoriel`).

Mêmes règles que les docs : vouvoiement, pas de tiret cadratin, espace avant les deux-points en
français, aucune promesse sur l'argent ou les délais qui ne soit pas prouvée dans le code.

## Tags et réglages

- 10 à 15 tags : les synonymes du mot-clé (« partager une liste de tâches », « liste partagée »,
  « lien d'invitation »), la marque, le public visé (film de référence : « travail en équipe »).
- Réglages à indiquer dans le JSON : langue, catégorie Éducation, vidéo non destinée aux enfants,
  chapitres automatiques désactivés, écran de fin de 5 s au plus pour ne pas masquer le vrai écran.
