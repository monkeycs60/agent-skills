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
  [ -n "$version" ] && note "agent-browser $version is too old (minimum $MINIMUM): installing $PINNED into $bindir"
  command -v npm >/dev/null 2>&1 || die "npm not found: install Node.js 22 or later (https://nodejs.org), then run again."
  node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  [ "$node_major" -ge 22 ] || die "found Node.js $node_major; agent-browser requires Node.js 22 or later."
  npm install --global --prefix "$HOME/.local" --ignore-scripts --no-fund --no-audit \
    --no-update-notifier --loglevel=error "agent-browser@$PINNED" >/dev/null
  "$bindir/agent-browser" --version >/dev/null
  version="$(installed_version)"
  if [ -z "$version" ] || ! at_least "$version" "$MINIMUM"; then
    die "agent-browser $PINNED installed in $bindir, but ab still finds ${version:-nothing} (AGENT_BROWSER_BIN?)."
  fi
  ok "agent-browser $version installed in $bindir"
fi

report="$(iso doctor --offline --quick --json 2>/dev/null || true)"
if grep -q '"id":"chrome.installed","message":"[^"]*","status":"pass"' <<<"$report"; then
  ok "browser available"
else
  echo "  … downloading Chrome for Testing (about 200 MB)"
  iso install 2>&1 | grep -E '^ *(✓|✗)' | sed 's/^ */    /' || true
fi

mkdir -p "$HOME/.claude/skills"
for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills"; do
  [ -d "$dir" ] || continue
  target="$dir/$NAME"
  if [ "$(cd "$target" 2>/dev/null && pwd -P)" = "$skill" ]; then ok "$target"
  elif [ -e "$target" ] || [ -L "$target" ]; then note "$target already exists: left as is"
  else ln -s "$skill" "$target" && ok "$target → $skill"
  fi
done

mkdir -p "$bindir"
if [ "$bindir/ab" -ef "$ab" ]; then ok "$bindir/ab"
elif [ -e "$bindir/ab" ] || [ -L "$bindir/ab" ]; then note "$bindir/ab already exists (another tool): left as is. Call $ab"
else ln -s "$ab" "$bindir/ab" && ok "$bindir/ab → $ab"
fi
case ":$PATH:" in
  *":$bindir:"*)
    resolved="$(command -v ab || true)"
    [ "$resolved" = "$bindir/ab" ] || note "ab resolves to $resolved, which comes before $bindir in PATH: call $ab" ;;
  *) note "$bindir is not in PATH: add export PATH=\"\$HOME/.local/bin:\$PATH\" to the shell profile, or call $ab" ;;
esac

if command -v ffmpeg >/dev/null 2>&1; then
  encoders="$(ffmpeg -hide_banner -encoders 2>/dev/null || true)"
  [[ "$encoders" == *libvpx* && "$encoders" == *libx264* ]] || note "ffmpeg lacks libvpx or libx264: ab record will fail"
else
  note "ffmpeg missing: only videos (ab record) need it. macOS: brew install ffmpeg; Debian/Ubuntu: sudo apt install ffmpeg"
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
      echo "  … installing Chrome's system libraries"
      iso install --with-deps >/dev/null 2>&1 || true
      smoke "$log" || { cat "$log" >&2; die "the isolated browser does not start."; }
    else
      die "Chrome is missing system libraries. Run once: AB_ISOLATED=1 $ab install --with-deps (asks for sudo), then run this script again."
    fi
  else
    cat "$log" >&2
    die "the isolated browser does not start. To diagnose: AB_ISOLATED=1 $ab doctor"
  fi
fi
ok "isolated test: open, snapshot, screenshot, close ($(( $(date +%s) - started )) s in total)"

echo "  Real Chrome (once): Chrome 144 or later, open chrome://inspect/#remote-debugging and allow remote debugging."
