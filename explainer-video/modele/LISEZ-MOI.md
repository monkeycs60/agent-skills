# Vidéo « TITRE » (JJ/MM/AAAA)

Projet : NOM DU PROJET. DURÉE s, 1920 x 1080, 60 images par seconde, muet. Charte du projet dans
`charte.css` (couleurs, polices, logos, chacun avec sa source dans le code).

Fabriquée avec le skill `explainer-video`.

## Ce que contient le dossier

| Fichier | Rôle |
|---|---|
| `film.html` | Le film. Ouvert dans un navigateur, il se joue avec une barre de lecture. `?t=12.5` l'ouvre figé à un instant, `&lang=en` dans une autre langue. |
| `charte.css` | La charte du projet : seule source des couleurs, polices et logos du film, de la miniature et du kit. |
| `moteur.js` | Le moteur d'animation, identique pour tous les films. Ne pas modifier. |
| `miniature.html`, `youtube-<lang>.json` | La miniature et les textes du kit YouTube. |
| `assets/` | Capture réelle de l'app et son JSON (cadre des éléments), polices et logos du projet (à ne pas diffuser si leur licence l'interdit). |
| `out/` | Le MP4, l'affiche, les planches d'images clés, la vérification, le kit YouTube. |

## Refaire la vidéo

Depuis le dossier `scripts/` du skill :

```
node render.js "<ce dossier>" planche 2,6,10,14,18,22 fr
node render.js "<ce dossier>" video fr
node render.js "<ce dossier>" verifier fr
node render.js "<ce dossier>" affiche 14 fr
```

## Points relevés en préparant la vidéo

- (écarts entre la doc écrite et l'app, libellés changés, valeurs de charte incertaines, éléments masqués sur la capture...)
