#!/usr/bin/env bash
set -euo pipefail

PINNED=0.43.0
MINIMUM=0.42.0
NAME=chrome-pilot

skill="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ab="$skill/scripts/ab"
bindir="$HOME/.local/bin"
started=$(date +%s)

ok() { printf '  ✓ %s\n' "$*"; }
note() { printf '  ! %s\n' "$*"; }
die() { printf '  ✗ %s\n' "$*" >&2; exit 1; }
iso() { AB_ISOLATED=1 AB_SESSION=install-check "$ab" "$@"; }

at_least() {
  local IFS=. i
  local -a have want
  read -r -a have <<<"${1%%[!0-9.]*}"
  read -r -a want <<<"$2"
  for i in 0 1 2; do
    [ "${have[i]:-0}" -gt "${want[i]:-0}" ] && return 0
    [ "${have[i]:-0}" -lt "${want[i]:-0}" ] && return 1
  done
  return 0
}

installed_version() {
  iso --version 2>/dev/null | awk '{print $NF}' || true
}

chmod +x "$ab"

version="$(installed_version)"
if [ -n "$version" ] && at_least "$version" "$MINIMUM"; then
  ok "agent-browser $version"
else
  [ -n "$version" ] && note "agent-browser $version trop ancien (minimum $MINIMUM) : installation de $PINNED dans $bindir"
  command -v npm >/dev/null 2>&1 || die "npm introuvable : installer Node.js 22 ou plus récent (https://nodejs.org), puis relancer."
  node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  [ "$node_major" -ge 22 ] || die "Node.js $node_major trouvé, agent-browser exige Node.js 22 ou plus récent."
  npm install --global --prefix "$HOME/.local" --ignore-scripts --no-fund --no-audit \
    --no-update-notifier --loglevel=error "agent-browser@$PINNED" >/dev/null
  "$bindir/agent-browser" --version >/dev/null
  version="$(installed_version)"
  if [ -z "$version" ] || ! at_least "$version" "$MINIMUM"; then
    die "agent-browser $PINNED installé dans $bindir, mais ab trouve encore ${version:-rien} (AGENT_BROWSER_BIN ?)."
  fi
  ok "agent-browser $version installé dans $bindir"
fi

report="$(iso doctor --offline --quick --json 2>/dev/null || true)"
if grep -q '"id":"chrome.installed","message":"[^"]*","status":"pass"' <<<"$report"; then
  ok "navigateur disponible"
else
  echo "  … téléchargement de Chrome for Testing (environ 200 Mo)"
  iso install 2>&1 | grep -E '^ *(✓|✗)' | sed 's/^ */    /' || true
fi

mkdir -p "$HOME/.claude/skills"
for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills"; do
  [ -d "$dir" ] || continue
  target="$dir/$NAME"
  if [ "$(cd "$target" 2>/dev/null && pwd -P)" = "$skill" ]; then ok "$target"
  elif [ -e "$target" ] || [ -L "$target" ]; then note "$target existe déjà : laissé tel quel"
  else ln -s "$skill" "$target" && ok "$target → $skill"
  fi
done

mkdir -p "$bindir"
if [ "$bindir/ab" -ef "$ab" ]; then ok "$bindir/ab"
elif [ -e "$bindir/ab" ] || [ -L "$bindir/ab" ]; then note "$bindir/ab existe déjà (autre outil) : laissé tel quel. Appeler $ab"
else ln -s "$ab" "$bindir/ab" && ok "$bindir/ab → $ab"
fi
case ":$PATH:" in
  *":$bindir:"*)
    resolved="$(command -v ab || true)"
    [ "$resolved" = "$bindir/ab" ] || note "ab désigne $resolved, placé avant $bindir dans le PATH : appeler $ab" ;;
  *) note "$bindir n'est pas dans le PATH : ajouter export PATH=\"\$HOME/.local/bin:\$PATH\" au profil du shell, ou appeler $ab" ;;
esac

if command -v ffmpeg >/dev/null 2>&1; then
  encoders="$(ffmpeg -hide_banner -encoders 2>/dev/null || true)"
  [[ "$encoders" == *libvpx* && "$encoders" == *libx264* ]] || note "ffmpeg sans libvpx ou libx264 : ab record échouera"
else
  note "ffmpeg absent : seules les vidéos (ab record) en ont besoin. macOS : brew install ffmpeg ; Debian/Ubuntu : sudo apt install ffmpeg"
fi

smoke() {
  local shot="${TMPDIR:-/tmp}/chrome-pilot-check.png" status=0
  iso open "data:text/html,<title>chrome-pilot</title><button>ok</button>" >/dev/null 2>"$1" &&
    [ "$(iso get title 2>>"$1")" = chrome-pilot ] &&
    [[ "$(iso snapshot -i 2>>"$1")" == *'button "ok"'* ]] &&
    iso screenshot "$shot" >/dev/null 2>>"$1" &&
    [ -s "$shot" ] || status=1
  iso close >/dev/null 2>&1 || true
  rm -f "$shot"
  return "$status"
}

log="$(mktemp "${TMPDIR:-/tmp}/chrome-pilot-install.XXXXXX")"
trap 'rm -f "$log"' EXIT
if ! smoke "$log"; then
  if [ "$(uname -s)" = Linux ] && grep -q 'shared libraries' "$log"; then
    if [ "$(id -u)" = 0 ]; then
      echo "  … installation des bibliothèques système de Chrome"
      iso install --with-deps >/dev/null 2>&1 || true
      smoke "$log" || { cat "$log" >&2; die "le navigateur isolé ne démarre pas."; }
    else
      die "Chrome manque de bibliothèques système. Lancer une fois : AB_ISOLATED=1 $ab install --with-deps (demande sudo), puis relancer ce script."
    fi
  else
    cat "$log" >&2
    die "le navigateur isolé ne démarre pas. Diagnostic : AB_ISOLATED=1 $ab doctor"
  fi
fi
ok "test isolé : ouverture, snapshot, capture, fermeture ($(( $(date +%s) - started )) s au total)"

echo "  Vrai Chrome (une seule fois) : Chrome 144 ou plus récent, ouvrir chrome://inspect/#remote-debugging et autoriser le débogage à distance."
