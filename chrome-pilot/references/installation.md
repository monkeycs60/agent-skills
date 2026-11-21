# Install, settings, uninstall

## What `install.sh` does

The script is idempotent: running it again only installs what is missing. It never asks for `sudo` and only writes to the home folder.

1. Looks for agent-browser (order below). If it is missing, or older than the minimum version, installs the pinned version with `npm install --global --prefix ~/.local`. Node.js 22 or later is then required.
2. Checks that a browser is available (`agent-browser doctor`), otherwise downloads Chrome for Testing (about 200 MB, into `~/.agent-browser/browsers`).
3. Links the skill into `~/.claude/skills`, and into `~/.codex/skills` or `~/.agents/skills` if they exist. A folder already present under that name is left as is.
4. Links `ab` into `~/.local/bin`, without overwriting another `ab`, and warns if that folder is missing from `PATH` or if another `ab` comes first.
5. Warns when ffmpeg is missing (only needed for videos).
6. Tests isolated mode for real: opens a page, reads the title, takes a snapshot and a screenshot, closes.

On Linux, Chrome needs system libraries. Run as root (container), the script installs them itself. Otherwise, it stops with the command to run once, which asks for `sudo`:

```bash
AB_ISOLATED=1 ab install --with-deps
```

Expect about a minute on a fresh machine, mostly to download Chrome and the libraries, then one to three seconds for a rerun.

## agent-browser binary lookup

`ab` takes the first one found:

1. `AGENT_BROWSER_BIN`;
2. `~/.local/bin/agent-browser` (installed by `install.sh`);
3. `agent-browser` in `PATH`;
4. the active nvm Node version's folder (`$NVM_BIN`);
5. Homebrew (`/opt/homebrew/bin`, `/usr/local/bin`), Bun (`~/.bun/bin`), Volta (`~/.volta/bin`);
6. any Node version installed by nvm;
7. npm's global prefix (`npm prefix -g`).

## Environment variables

| Variable | Effect |
|---|---|
| `AB_ISOLATED=1` | Isolated mode: headless Chrome launched by agent-browser, without a user profile. `AGENT_BROWSER_CDP`, `AGENT_BROWSER_AUTO_CONNECT` and `AGENT_BROWSER_PROVIDER` are ignored there. |
| `AB_SESSION=<name>` | Forced session name (letters, digits, `-`, `_`). Required for parallel sub-agents. |
| `AB_CDP=<port\|url>` | Real Chrome reached through this CDP port or URL instead of automatic discovery. |
| `AGENT_BROWSER_BIN=<path>` | Forced agent-browser binary. |

Sessions are named `cp-<key>` in real Chrome and `cp-iso-<key>` in isolated mode: `agent-browser session list` shows them.

## Update agent-browser

Change `PINNED` in `install.sh`, then:

```bash
npm install --global --prefix ~/.local --ignore-scripts agent-browser@<version>
~/.local/bin/agent-browser --version
```

The second line replaces the Node launcher with the native binary; later calls no longer go through Node.

## Uninstall

```bash
rm -f ~/.local/bin/ab ~/.claude/skills/chrome-pilot ~/.codex/skills/chrome-pilot ~/.agents/skills/chrome-pilot
npm uninstall --global --prefix ~/.local agent-browser
rm -rf ~/.agent-browser
```

The last line also deletes the downloaded Chrome for Testing and agent-browser's session state, including that of other tools using it.
