# Prouver un parcours en vidéo

Une vidéo montre ce qu'une capture ne montre pas : l'enchaînement, les transitions, l'état qui change après un clic. Pour un changement de comportement, livrer deux vidéos du même parcours, avant et après.

## Prérequis

`ab record` exige ffmpeg avec les encodeurs libvpx et libx264 : `brew install ffmpeg` sur macOS, `sudo apt install ffmpeg` sur Debian ou Ubuntu. `install.sh` signale leur absence ; `AB_ISOLATED=1 ab doctor` le vérifie aussi.

## Tourner l'avant et l'après

- L'« avant » se tourne sur la branche de base (worktree ou checkout de la branche principale), si possible avant de toucher au code.
- Même parcours, même compte, même taille de fenêtre (`ab set viewport 1440 900`) : c'est la comparaison qui parle.
- Le mode isolé convient à tout parcours sans connexion. En vrai Chrome, l'onglet de l'agent doit rester au premier plan pendant toute la prise : un onglet caché ralentit chaque clic d'environ 5 s.

## Pendant la prise

- `ab record start <fichier.webm> [url] --fps 15` démarre la prise ; avec une URL, l'onglet y navigue d'abord.
- Le wrapper ajoute `--cursor` : un pointeur et une onde à chaque clic apparaissent à l'image. Sans lui, on voit l'écran changer sans savoir où l'agent a agi.
- Chaque geste passe par la souris : `ab click`, `ab find text "…" click`, `ab mouse`, `ab scroll`. Un `ab eval "….click()"` agit sans déplacer le pointeur.
- Laisser une pause courte entre deux étapes (`ab wait 800`) pour qu'un humain suive.
- `ab record stop` termine la prise. S'il affiche `✗`, refaire la prise.

## Vérifier la prise sans la regarder

`--contact-sheet` sur `record start` produit, à côté de la vidéo, une planche des images où l'écran change (`<nom>.contact-sheet.png`). La lire suffit pour vérifier que la prise montre bien chaque étape.

## Convertir

Enregistrer en `.webm`, puis convertir en MP4 H.264 :

```bash
ffmpeg -loglevel error -y -i /tmp/preuve/apres.webm -c:v libx264 -pix_fmt yuv420p \
  -crf 28 -preset veryfast -movflags +faststart -an /tmp/preuve/apres.mp4
```

Sur une machine chargée, l'enregistrement direct en `.mp4` peut échouer (`Recording encoder fell more than 500 ms behind capture`) et laisser un fichier illisible : le `.webm` puis la conversion évitent ce cas. Le MP4 H.264 se lit dans tous les navigateurs courants.

## Intégrer dans un rapport HTML

```html
<video controls muted playsinline preload="metadata" title="Après · ajout d'un profil"
  src="data:video/mp4;base64,…"></video>
```

Poser chaque « avant » à gauche de son « après », sur la même ligne, avec une légende (`title` ou `<figcaption>`) qui dit ce que montre la vidéo.
