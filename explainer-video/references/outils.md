# Outils, variables et temps de rendu

## Prérequis

| Outil | Statut | Rôle | Installation |
|---|---|---|---|
| Node 20 ou plus | requis | Tous les scripts, sans aucun paquet npm | https://nodejs.org |
| Google Chrome ou Chromium (ou Edge, Brave) | requis | Dessine et photographie chaque image, capture l'app | Linux : paquet `google-chrome-stable` ou `chromium` ; macOS : Google Chrome |
| ffmpeg avec libx264 (et ffprobe) | facultatif, recommandé | Encode en 15 s environ et vérifie le MP4 image par image | `apt install ffmpeg`, `brew install ffmpeg` |
| Une police système de repli (DejaVu, Liberation...) | requis sur un Linux minimal | Glyphes absents des polices du film (coches du kit) | `apt install fonts-dejavu-core` |

Sans ffmpeg, le MP4 est encodé **dans le navigateur** (WebCodecs) : Google Chrome sait toujours le
faire, Chromium selon la distribution. `node $S/outils.js` dit lequel des deux servira ; s'il n'y en
a aucun, il le dit aussi et sort en erreur.

`install.sh` à la racine du skill ne fait que lancer ce diagnostic : rien n'est téléchargé.

## Navigateur

Cherché dans cet ordre : `CHROME_PATH`, puis
- Linux : `google-chrome-stable`, `google-chrome`, `chromium`, `chromium-browser`, `microsoft-edge`,
  `brave-browser` dans le `PATH`, puis `/opt/google/chrome/chrome`, `/snap/bin/chromium` ;
- macOS : `Google Chrome.app`, `Chromium.app`, `Microsoft Edge.app`, `Brave Browser.app` dans
  `/Applications` ou `~/Applications`.

Le navigateur tourne sans interface, avec un profil temporaire jamais partagé, et se pilote par un
tube (`--remote-debugging-pipe`) : **aucun port n'est ouvert**, deux rendus peuvent tourner en même
temps. En root (Docker), `--no-sandbox` est ajouté tout seul.

## Variables d'environnement

| Variable | Effet |
|---|---|
| `CHROME_PATH` | Binaire du navigateur à utiliser |
| `CHROME_NO_SANDBOX` | `1` : lance le navigateur sans bac à sable (conteneur en utilisateur normal) ; sinon il relance tout seul après un échec du bac à sable, avec un avertissement |
| `FFMPEG_PATH`, `FFPROBE_PATH` | Binaires ffmpeg et ffprobe, s'ils ne sont pas dans le `PATH` |
| `ENCODEUR` | `ffmpeg` ou `chrome` pour forcer l'encodeur (défaut : ffmpeg s'il a libx264) |
| `WORKERS` | Onglets qui photographient en parallèle (défaut : moitié des cœurs, 4 au plus) |
| `FRAMES_DIR` | Dossier des images intermédiaires (défaut : dossier temporaire du système) |
| `EXPLAINER_VIDEO_DIR` | Racine des films (défaut : `~/explainer-videos`) |

## Scripts

| Script | Usage |
|---|---|
| `outils.js` | Diagnostic des outils, code de sortie 1 si aucune vidéo n'est possible |
| `exemple.js [dossier] [fr\|en] [--sans-video]` | Film d'exemple complet : capture, planche, vidéo, vérification, affiche, miniature, kit |
| `render.js <film> planche <t1,t2,...> [lang]` | Images clés -> `out/planche-<lang>.png` |
| `render.js <film> video [lang]` | Toutes les images puis le MP4 -> `out/<film>-<lang>.mp4` |
| `render.js <film> encoder [lang]` | Réencode depuis les images déjà rendues |
| `render.js <film> verifier [lang]` | Contrôle du MP4, code de sortie 1 au moindre écart |
| `render.js <film> affiche <t> [lang]` | Image d'affiche -> `out/<film>-<lang>-affiche.jpg` |
| `render.js <film> miniature [lang]` | Miniature YouTube 1280 x 720 (JPG et PNG) |
| `capturer.js <recette.json>` | Capture d'un écran réel et cadre des éléments (`capture.md`) |
| `kit.js <film> [lang]` | Kit YouTube HTML, code de sortie 1 si un contrôle échoue |
| `inventaire-charte.js <racine-du-dépôt>` | Carte des sources de la charte (`charte.md`) |

`render.js` signale les fichiers que le film demande sans les trouver (capture réelle manquante,
logo mal nommé) et les polices en échec, au lieu de rendre un film à trous.

## Ce que `verifier` contrôle

Avec ffprobe : codec H.264, 1920 x 1080, cadence, nombre d'images et durée égaux à ceux du film.
Puis six images réparties sur le film, décodées du MP4 (par ffmpeg, sinon par le lecteur du
navigateur) et comparées à la même image rendue à nouveau : écart moyen sous 3 avec ffmpeg (attendu
autour de 1), sous 5 avec le lecteur du navigateur, qui convertit les couleurs BT.709 à l'affichage
(jusqu'à 3 sur les aplats saturés) ; aucune image vide, aucune paire identique. Il écrit `out/verification-<lang>.png` (les six images
décodées) et une image décodée en pleine taille, à regarder.

## Temps mesurés (film d'exemple de 36,7 s, 2 202 images)

| Étape | Bureau Linux 16 cœurs, Chrome | Docker `node:22-bookworm-slim` + Chromium |
|---|---|---|
| Diagnostic (`install.sh`) | 0,5 s | 0,5 s |
| Photographie des images, 4 onglets | 77 s (190 s avec un seul) | 71 s |
| Encodage ffmpeg (5,9 Mo) | 14 s | 16 s |
| Encodage dans le navigateur, sans ffmpeg (18 Mo, 6 Mbit/s) | | 59 s |
| Vérification | 4 s | 2 à 4 s |
| Capture, planche, affiche, miniature, kit | 1 à 2 s chacun | 1 à 2 s chacun |
| `exemple.js` complet | | 95 s avec ffmpeg, 136 s sans |

Lancer `video` en arrière-plan et préparer le kit pendant ce temps. Sans ffmpeg, le MP4 pèse trois
fois plus : au-delà de 10 Mo (limite de GitHub sur un compte gratuit), passer par ffmpeg.
