# Pièges techniques du rendu

Les défauts visuels de composition (icône du mauvais côté, curseur sur le libellé, décor sous la
légende, texte qui déborde...) sont listés dans `critique.md`.

| Piège | Réalité |
|---|---|
| Couleurs délavées après encodage dans le navigateur | `encoder.html` convertit lui-même en I420 BT.709 plage vidéo et ajoute la boîte `colr`. Ne pas y toucher. |
| Film aux couleurs du film de référence | `charte.css` non remplacée, ou une couleur en dur dans un décor ajouté. Chercher les `#` hexadécimaux dans `film.html` : seuls les éléments neutres (téléphone, barre de navigateur) en gardent. |
| Deux attributs `style` sur une balise | Le second est ignoré sans erreur, l'élément perd sa position. Un seul `style` par balise. |
| Transition de couleur terne ou fausse | `trA` a besoin de `couleur('--x')`, pas d'une chaîne CSS. `couleur()` ne lit pas une couleur transparente : lui donner la couleur pleine et passer l'alpha en second argument. |
| Police de repli dans le rendu | Graisse ou fichier manquant : vérifier `@font-face`, `display=block`, et regarder une image en pleine taille. |
| « Chrome ou Chromium introuvable » | Installer l'un des deux, ou `CHROME_PATH=/chemin/du/binaire` (`outils.md`). |
| « le navigateur s'est arrêté » au lancement | Les dernières lignes de son journal suivent le message. En root sans `--no-sandbox` : lancer en utilisateur normal ou dans Docker (ajouté tout seul en root). Chromium en snap : `CHROME_PATH` vers un Chrome hors snap si le tube ne passe pas. |
| `/dev/shm` trop petit (Docker) | Déjà contourné par `--disable-dev-shm-usage`. |
| « aucun encodeur H.264 dans ce navigateur » | Chromium sans codec propriétaire : installer ffmpeg, ou prendre Google Chrome. |
| Rendu lent | `WORKERS` règle les onglets en parallèle ; au-delà de 4, le gain est faible. Ne pas encoder pendant la capture : ffmpeg prend les mêmes cœurs. |
| Couleurs du MP4 légèrement décalées | L'encodage passe par le filtre `colorspace` de ffmpeg (JPEG BT.601 plage pleine vers BT.709 plage vidéo). Un `scale` par défaut décale les aplats de 2 à 3 ; ses options exactes sont 9 fois plus lentes. |
| Fichier introuvable signalé par `render.js` | Chemin relatif au dossier du film, nom exact (casse comprise) ; capture réelle : `capturer.js`. |
| La vérification montre la même image partout | Lecture par le navigateur : attendre `requestVideoFrameCallback` après `seeked` (déjà fait dans `verifier.html`). |
| Écart de 6 ou plus sur les aplats bleus, alors que la vidéo est juste | Image comparée avec gestion des couleurs : un PNG de ffmpeg porte des balises BT.709 que Chrome convertit. `verifier.html` charge les images avec `colorSpaceConversion: 'none'`. |
| `window.seek` qui s'appelle lui-même | Une fonction globale nommée `seek` est écrasée : le film nomme la sienne `paint`. |
| Erreur 403 du serveur local | Chemins à barres mixtes : toujours `path.resolve`. |
| Deux rendus du même film diffèrent légèrement | Bruit de Chrome sur le flou des grandes ombres. Sans importance. |
