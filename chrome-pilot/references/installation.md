# Installation, réglages, désinstallation

## Ce que fait `install.sh`

Le script est idempotent : le relancer ne réinstalle que ce qui manque. Il ne demande jamais `sudo` et n'écrit que dans le dossier personnel.

1. Cherche agent-browser (ordre ci-dessous). Absent, ou plus ancien que la version minimale : installe la version épinglée avec `npm install --global --prefix ~/.local`. Node.js 22 ou plus récent est alors requis.
2. Vérifie qu'un navigateur est disponible (`agent-browser doctor`), sinon télécharge Chrome for Testing (environ 200 Mo, dans `~/.agent-browser/browsers`).
3. Lie le skill dans `~/.claude/skills`, et dans `~/.codex/skills` ou `~/.agents/skills` s'ils existent. Un dossier déjà présent sous ce nom est laissé tel quel.
4. Lie `ab` dans `~/.local/bin`, sans écraser un autre `ab`, et signale si ce dossier manque au `PATH` ou si un autre `ab` passe devant.
5. Signale l'absence de ffmpeg (utile seulement pour les vidéos).
6. Teste le mode isolé pour de vrai : ouverture d'une page, titre, snapshot, capture, fermeture.

Sous Linux, Chrome a besoin de bibliothèques système. Lancé en root (conteneur), le script les installe lui-même. Sinon, il s'arrête avec la commande à lancer une fois, qui demande `sudo` :

```bash
AB_ISOLATED=1 ab install --with-deps
```

Comptez une minute environ sur une machine vierge, dont l'essentiel pour le téléchargement de Chrome et des bibliothèques, puis une à trois secondes pour une relance.

## Recherche du binaire agent-browser

`ab` prend le premier trouvé :

1. `AGENT_BROWSER_BIN` ;
2. `~/.local/bin/agent-browser` (installé par `install.sh`) ;
3. `agent-browser` dans le `PATH` ;
4. le dossier de la version Node active de nvm (`$NVM_BIN`) ;
5. Homebrew (`/opt/homebrew/bin`, `/usr/local/bin`), Bun (`~/.bun/bin`), Volta (`~/.volta/bin`) ;
6. toute version Node installée par nvm ;
7. le préfixe global de npm (`npm prefix -g`).

## Variables d'environnement

| Variable | Effet |
|---|---|
| `AB_ISOLATED=1` | Mode isolé : Chrome headless lancé par agent-browser, sans profil utilisateur. Les variables `AGENT_BROWSER_CDP`, `AGENT_BROWSER_AUTO_CONNECT` et `AGENT_BROWSER_PROVIDER` y sont ignorées. |
| `AB_SESSION=<nom>` | Nom de session imposé (lettres, chiffres, `-`, `_`). Indispensable pour des sous-agents parallèles. |
| `AB_CDP=<port\|url>` | Vrai Chrome joint par ce port ou cette URL CDP au lieu de la découverte automatique. |
| `AGENT_BROWSER_BIN=<chemin>` | Binaire agent-browser imposé. |

Les sessions s'appellent `cp-<clé>` en vrai Chrome et `cp-iso-<clé>` en mode isolé : `agent-browser session list` les montre.

## Mettre à jour agent-browser

Changer `PINNED` dans `install.sh`, puis :

```bash
npm install --global --prefix ~/.local --ignore-scripts agent-browser@<version>
~/.local/bin/agent-browser --version
```

La seconde ligne remplace le lanceur Node par le binaire natif ; les appels suivants ne passent plus par Node.

## Désinstaller

```bash
rm -f ~/.local/bin/ab ~/.claude/skills/chrome-pilot ~/.codex/skills/chrome-pilot ~/.agents/skills/chrome-pilot
npm uninstall --global --prefix ~/.local agent-browser
rm -rf ~/.agent-browser
```

La dernière ligne supprime aussi le Chrome for Testing téléchargé et l'état des sessions d'agent-browser, y compris celles d'autres outils qui l'utilisent.
