---
name: explainer-video
description: Builds a short motion-design explainer video in code (1080p, 60 fps, silent MP4) for a feature or doc of any project, in the project's own visual identity, with a YouTube kit, or edits one. Use for "make a video of X", "animate this tutorial", or /explainer-video.
---

# Vidéo explicative en motion design, pour n'importe quel projet

Une vidéo est une **page HTML animée** : `peindre(t)` dessine chaque instant, Chrome la photographie
image par image, puis ffmpeg (ou Chrome lui-même) l'encode en MP4 H.264. Format : **1920 x 1080,
60 i/s, muet, environ 7 s par étape, pauses comprises** ; la lisibilité passe avant la brièveté.
Modèle de référence à lire avant tout : `modele/film.html` (produit fictif « Coche » : inviter son
équipe sur une liste partagée).

Principe qui fait la qualité : **une seule forme traverse tout le film sans jamais couper** (plein
écran `--brand`, bouton, pastille, champ, résultat, cadre sur l'écran réel, plein écran). Toute
l'identité visuelle vient d'un seul fichier, `charte.css`, relevé dans le projet.

## Avant de commencer

- `S` = dossier `scripts/` de ce skill (en général `~/.claude/skills/explainer-video/scripts`).
- **Outils** : `node $S/outils.js` vérifie Node 20+, trouve Chrome ou Chromium (sinon `CHROME_PATH`)
  et ffmpeg (facultatif, recommandé), et dit quoi installer. Aucun paquet npm. Détail, variables et
  temps de rendu : `references/outils.md`.
- **Première fois sur une machine** : `node $S/exemple.js` fabrique le film d'exemple de bout en bout
  (2 à 4 min) dans `~/explainer-videos/coche/inviter-equipe/`. C'est le test de la chaîne.
- Entrées : URL de doc, Markdown, README, ticket, description ou parcours dans l'app. Sujet flou :
  demander **quoi montrer et à qui**, le reste se déduit du code.
- Le dépôt du projet et, idéalement, l'app qui tourne sur des données fictives.
- Dossiers : film dans `$EXPLAINER_VIDEO_DIR/<projet>/<slug>/` (défaut `~/explainer-videos/`,
  **hors du dépôt**) ; charte partagée `.../<projet>/charte.css` ; images intermédiaires dans
  `FRAMES_DIR` (dossier temporaire par défaut, environ 200 Mo par film).

## Workflow

0. **Charte**, si `<projet>/charte.css` n'existe pas : `node $S/inventaire-charte.js <racine-du-dépôt>`,
   lire les sources, mesurer sur l'app (`capturer.js`, clé `styles`), remplir depuis
   `modele/charte.css` avec une source par valeur. Montrer un tableau variable / valeur / source.
   Méthode : `references/charte.md` ; exemple rempli : `exemple/charte.css`.
1. **Sujet** : en tirer **4 à 6 étapes au plus** et le moment « waouh » (l'app fait quelque chose
   seule). Le reste reste dans la doc écrite.
2. **Libellés** vérifiés dans le code puis vus sur l'app (navigateur de l'agent si une session est
   nécessaire, sinon `capturer.js`). Relever les états intermédiaires (« Recherche en cours... »).
3. **Liste d'états** montrée en tableau (état, ce que devient la forme, ce que le spectateur
   comprend, instant). Enchaîner sans attendre, sauf si l'utilisateur veut valider.
4. **Capture réelle** de la scène finale : `node $S/capturer.js recette.json` ; le JSON donne le
   cadre exact des éléments, que le film lit tout seul. Recette et usage : `references/capture.md`.
5. **Montage** : copier `modele/` dans le dossier du film, y mettre la charte du projet, ses polices
   et logos dans `assets/`. `moteur.js` reste intact ; réécrire dans `film.html` `TXT`, `ST`, `GEO`,
   `BG_KEYS`, décors, `CAPS`, `CUR` et caméra. Méthode : `references/mouvement.md` ; rôles des
   couleurs, grille et composants : `references/direction-artistique.md`.
6. **Autocritique obligatoire** : planches d'images clés et de transitions, note sur 10, trois pires
   défauts corrigés, jusqu'à 8 partout, signature complète. Grille : `references/critique.md`.
7. **Temps de lecture** : chaque texte reste affiché, entier et immobile, au moins **0,4 s + 0,3 s
   par mot** ; sinon ajouter une pause dans `HOLDS`.
8. **Rendu et vérification** : `video` en arrière-plan, puis `verifier`, qui sort en erreur au
   moindre écart (taille, cadence, durée, couleurs, image vide). Regarder ensuite une image décodée
   en pleine résolution.
9. **Kit YouTube** si la vidéo y va : `miniature.html` → `render.js miniature`, `youtube-<lang>.json`
   (avec `chaine` et `duree`), puis `kit.js`. Regarder la miniature à 168 x 94, ne livrer que tout
   au vert. Règles : `references/youtube.md`.
10. **Livrer** : le MP4 (et le kit), le chemin de `film.html` (`?t=14.9` l'ouvre figé), le
    `LISEZ-MOI.md` du dossier rempli, et les écarts relevés entre la doc écrite et l'app.

```
node $S/render.js <dossier-film> planche 1.9,7.4,13.9,22.5 fr
node $S/render.js <dossier-film> video fr
node $S/render.js <dossier-film> verifier fr
node $S/render.js <dossier-film> affiche 22 fr
node $S/render.js <dossier-film> miniature fr
node $S/kit.js <dossier-film> fr
```

`render.js` refuse de rendre tant que `charte.css` est le gabarit, et signale tout fichier que le
film demande sans le trouver.

## Règles

- **La charte vient du projet**, jamais du film de référence ni d'un goût personnel ; aucune couleur
  de marque en dur dans le film, la miniature ou le kit.
- **Captures sur données fictives uniquement**, jamais un compte réel ni une base de production.
- **Ne jamais inventer un retour d'interface** (toast, « Copié ») ; une annotation reste permise si
  elle se lit comme une annotation, hors de l'interface.
- Argent, sécurité, délais, quotas : **prouvé dans le code ou pas écrit**. Chaque annotation doit
  rester vraie dans tous les cas, pas seulement sur la démo ; sinon nommer l'objet sans
  l'interpréter (« Votre lien »).
- Scènes dessinées avec des données fictives génériques (« Équipe Produit », `example.com`) ; la
  vraie capture n'est jamais retouchée. **Aucun visuel enfantin.**
- Ne parler que du sujet : pas d'option avancée dans une prise en main.
- Texte à l'écran : jamais de tiret cadratin ni demi-cadratin ; en français, espace insécable avant
  les deux-points et les points d'interrogation, aucune en anglais.
- **Ne rien installer** (ffmpeg, navigateur, paquets) sans l'accord de l'utilisateur : `outils.js`
  dit quoi installer et comment.
- Polices du projet : copiées pour le rendu, jamais publiées si la licence l'interdit.
- Écrire les fichiers longs avec l'outil d'écriture, pas avec un heredoc.

## Retouches, autre langue, intégration

- **Retouche** : planche autour de l'instant touché (avant, pendant, après), puis rendu complet.
  Allonger une scène sans tout décaler : `warp()` (`references/mouvement.md`).
- **Nouvelle charte** : mettre à jour `charte.css`, refaire une planche, relancer le rendu.
- **Autre langue** : `TXT.<lang>` avec les traductions du projet, capture dans cette langue
  (`"lang"` de la recette, sortie `ecran-reel-<lang>.png`), rendu avec `<lang>`, vérifier les
  largeurs. Le modèle a `fr` et `en` : `node $S/exemple.js <dossier> en`.
- **Intégration** : téléverser le MP4 et l'affiche, puis
  `<video src="URL_MP4" poster="URL_AFFICHE" controls muted playsinline preload="metadata" style="width:100%;height:auto;display:block;border-radius:14px;"></video>`.
  GitHub : 10 Mo au plus sur un compte gratuit (raccourcir, ou rendre en 30 i/s).

## Références (à lire seulement si l'étape l'exige)

- `references/outils.md` : prérequis, recherche du navigateur, variables, scripts, contrôles de `verifier`, temps mesurés (avant de commencer, en cas de panne d'outil).
- `references/charte.md` : relever la charte, table des sources par design system, polices, logos (étape 0).
- `references/capture.md` : recette de `capturer.js`, session, du JSON au cadre du film (étapes 0, 4).
- `references/mouvement.md` : moteur, forme unique, rythme, pauses, `warp()`, caméra, curseur (étapes 5, 7).
- `references/direction-artistique.md` : rôles des couleurs, typographie, grille, composants du modèle (étape 5).
- `references/critique.md` : signature à vérifier, grille de notation, défauts connus, lecture de `verifier` (étapes 6, 8).
- `references/youtube.md` : miniature, titre, description, tags, contrôles du kit (étape 9).
- `references/pieges.md` : pannes techniques du rendu et de l'encodage (quand un rendu sort faux).
- `modele/` : film, moteur, charte gabarit, miniature, JSON YouTube (`fr`, `en`), Inter (OFL) et `LISEZ-MOI.md` à copier.
- `exemple/` : charte remplie et maquette HTML de l'app fictive, capturée par `exemple.js`.
