#!/usr/bin/env bash
set -uo pipefail

case "${1:-}" in
  -h|--help)
    cat <<'EOF'
usage: install.sh [--upgrade]

Installs the running-coach skill: link in ~/.claude/skills (and Codex), Python
environment in <skill>/.venv (fitdecode, garminconnect), config and data folders,
then a full offline trial on the test data. Safe to run again.

  --upgrade   upgrades the dependencies (useful when the Garmin login breaks)
EOF
    exit 0 ;;
  ""|--upgrade) ;;
  *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
esac
upgrade="${1:-}"

skill="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
venv="$skill/.venv"
missing=0

ok() { printf '  ✓ %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*"; }
bad() { printf '  ✗ %s\n' "$*"; missing=1; }
has() { command -v "$1" >/dev/null 2>&1; }
pyver() { "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null; }
at_least() { "$1" -c "import sys; sys.exit(sys.version_info < ($2, $3))" 2>/dev/null; }

find_python() {
  local minor="$1" candidate
  for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if has "$candidate" && at_least "$candidate" 3 "$minor"; then echo "$candidate"; return 0; fi
  done
  return 1
}

echo "running-coach skill: $skill"

echo "1. Location"
for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills"; do
  [ "$dir" = "$HOME/.claude/skills" ] && mkdir -p "$dir"
  [ -d "$dir" ] || continue
  target="$dir/running-coach"
  if [ "$(cd "$target" 2>/dev/null && pwd -P)" = "$skill" ]; then ok "$target"
  elif [ -e "$target" ] || [ -L "$target" ]; then warn "$target already exists and points elsewhere: left as is"
  else ln -s "$skill" "$target" && ok "$target → $skill"
  fi
done
chmod +x "$skill/scripts/coach" "$skill/install.sh" "$skill/tests/e2e.sh"

echo "2. Python"
if [ -x "$venv/bin/python" ] && at_least "$venv/bin/python" 3 10; then
  ok "existing environment: Python $(pyver "$venv/bin/python")"
else
  rm -rf "$venv"
  if has uv && uv venv -q --python 3.12 "$venv" >/dev/null 2>&1; then
    ok "Python $(pyver "$venv/bin/python") installed by uv in .venv"
  elif py="$(find_python 10)"; then
    if "$py" -m venv "$venv" >/dev/null 2>&1; then ok "Python $(pyver "$py") ($py) → .venv"
    else bad "$py -m venv failed (Debian/Ubuntu: sudo apt install python3-venv)"
    fi
  else
    bad "Python 3.10 or newer not found: install uv (https://docs.astral.sh/uv/) or Python 3.12 (macOS: brew install python)"
  fi
fi

echo "3. Dependencies"
if [ -x "$venv/bin/python" ]; then
  pip_install() {
    if has uv; then uv pip install -q --python "$venv/bin/python" ${upgrade:+--upgrade} "$@"
    else "$venv/bin/python" -m pip install -q --disable-pip-version-check ${upgrade:+--upgrade} "$@"
    fi
  }
  started=$(date +%s)
  if pip_install -r "$skill/requirements.txt" >"$venv/install.log" 2>&1; then
    ok "fitdecode and garminconnect installed in $(( $(date +%s) - started )) s"
  elif pip_install "$(grep -E '^fitdecode' "$skill/requirements.txt")" >>"$venv/install.log" 2>&1; then
    warn "garminconnect could not be installed (see $venv/install.log): Garmin unavailable, Strava and import still work"
  else
    bad "installation failed, details in $venv/install.log"
  fi
  if ! at_least "$venv/bin/python" 3 12; then
    warn "Python $(pyver "$venv/bin/python"): garminconnect is capped at version 0.3.2. The Garmin login keeps up better with Garmin changes on Python 3.12 or newer (install uv, delete .venv, run again)."
  fi
fi

echo "4. Folders"
config="${RUNNING_COACH_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/running-coach}"
data="${RUNNING_COACH_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/running-coach}"
mkdir -p "$config" "$data" && chmod 700 "$config" && ok "configuration $config" && ok "data $data"

echo "5. Offline trial"
if [ "$missing" = 0 ]; then
  trial="$(mktemp -d)"
  mkdir -p "$trial/config"
  cp "$skill/tests/fixtures/profile.json" "$trial/config/"
  started=$(date +%s)
  if out="$(RUNNING_COACH_CONFIG="$trial/config" RUNNING_COACH_DATA="$trial/data" "$skill/scripts/coach" import "$skill/tests/fixtures/files" 2>&1 \
        && RUNNING_COACH_CONFIG="$trial/config" RUNNING_COACH_DATA="$trial/data" "$skill/scripts/coach" --today 2026-10-11 week 2>&1)" \
     && printf '%s' "$out" | grep -q "4 run(s), 43.2 km"; then
    ok "GPX/TCX/FIT/JSON import and weekly report in $(( $(date +%s) - started )) s"
  else
    bad "trial failed: $(printf '%s' "$out" | tail -3)"
  fi
  rm -rf "$trial"
fi

echo
if [ "$missing" = 0 ]; then
  echo "Ready. Commands: $skill/scripts/coach --help; first step: $skill/scripts/coach doctor"
else
  echo "Incomplete installation: fix the lines marked ✗, then run install.sh again"
  exit 1
fi
