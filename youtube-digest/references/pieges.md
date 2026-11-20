# Pièges

## yt-dlp
- Binaire autonome dans `~/.local/bin/yt-dlp`. YouTube change souvent : au premier échec d'extraction (`Sign in to confirm you're not a bot`, `nsig`, formats vides), lancer `yt-dlp -U` puis réessayer.
- `HTTP Error 429` : YouTube limite le débit. Il frappe surtout les traductions automatiques de sous-titres, que le script ne demande jamais. S'il frappe la piste choisie, le script bascule seul sur l'audio.
- Vidéo privée, réservée aux membres ou limitée par l'âge : relancer avec `--cookies` (session YouTube de Chrome).
- `--download-sections` est à éviter : il passe par ffmpeg en flux, des minutes pour un extrait de 10 min, contre environ 1 s par minute de vidéo pour un téléchargement complet de l'audio.
- Le message `no impersonate target is available` est sans effet sur YouTube.
- YouTube exige un moteur JavaScript pour certaines vidéos : sans deno, le script active node ou bun auprès de yt-dlp (`--js-runtimes`). Sans aucun des trois, la plupart des sous-titres passent encore, mais pas toujours.

## Moteur local
- Le venv `.venv/` du skill est hors Git. Sur une machine neuve, le script le crée au premier besoin avec `uv`, sinon avec `python -m venv`, et onnx-asr télécharge le modèle (environ 670 Mo, dans `~/.cache/huggingface`) au premier lancement. Compter une minute de plus la première fois.
- La mémoire grimpe avec la longueur d'un segment : `asr.py` limite les segments à 25 s. Ne pas monter cette limite.
- Le calcul occupe tous les cœurs. Sous forte charge (autres agents, builds), la vitesse peut chuter de moitié.

## Rapport HTML
- Mermaid est téléchargé une fois depuis jsdelivr dans `~/.cache/youtube-skill/mermaid.min.js`. Le rendu passe par Chrome, Chromium ou Edge en headless avec un profil temporaire (Linux : `google-chrome`, `chromium` ; macOS : `/Applications/…app`) ; `CHROME_PATH` impose un exécutable. Sans navigateur, les schémas restent en source dans le rapport.
- La miniature est intégrée en base64 : l'aperçu de Pupitre bloque les images chargées depuis une URL.
- `--deliver downloads` ouvre le rapport avec Chrome s'il est trouvé, sinon `open` (macOS) ou `xdg-open` (Linux).

## Lecture des liens
- `yt links` cherche agent-browser (`AGENT_BROWSER_BIN`, PATH, nvm, `~/.local/opt/pupitre-browser`, Homebrew) et l'appelle dans une session headless dédiée, sans les variables `AGENT_BROWSER_*` du shell : aucune connexion au Chrome de l'utilisateur, aucun vol de focus. Sans agent-browser, ou si la page échoue, repli HTTP sans JavaScript ; une page vide signale un site rendu en JavaScript.
- `--http` force le repli sans navigateur.
- Un dépôt GitHub donne son README et la liste de ses fichiers ; une URL `/blob/` donne le fichier brut, `/tree/` le dossier et son README. `gh` doit être installé et connecté, sinon l'erreur est notée et la lecture continue.
