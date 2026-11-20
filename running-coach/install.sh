#!/usr/bin/env bash
set -uo pipefail

case "${1:-}" in
  -h|--help)
    cat <<'EOF'
usage : install.sh [--upgrade]

Installe le skill running-coach : lien dans ~/.claude/skills (et Codex), environnement
Python dans <skill>/.venv (fitdecode, garminconnect), dossiers de configuration et de
données, puis essai complet hors ligne sur les données de test. Relançable sans risque.

  --upgrade   met à jour les dépendances (utile quand la connexion Garmin casse)
EOF
    exit 0 ;;
  ""|--upgrade) ;;
  *) echo "option inconnue : $1 (voir --help)" >&2; exit 2 ;;
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

echo "Skill running-coach : $skill"

echo "1. Emplacement"
for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills"; do
  [ "$dir" = "$HOME/.claude/skills" ] && mkdir -p "$dir"
  [ -d "$dir" ] || continue
  target="$dir/running-coach"
  if [ "$(cd "$target" 2>/dev/null && pwd -P)" = "$skill" ]; then ok "$target"
  elif [ -e "$target" ] || [ -L "$target" ]; then warn "$target existe déjà et pointe ailleurs : laissé tel quel"
  else ln -s "$skill" "$target" && ok "$target → $skill"
  fi
done
chmod +x "$skill/scripts/coach" "$skill/install.sh" "$skill/tests/e2e.sh"

echo "2. Python"
if [ -x "$venv/bin/python" ] && at_least "$venv/bin/python" 3 10; then
  ok "environnement existant : Python $(pyver "$venv/bin/python")"
else
  rm -rf "$venv"
  if has uv && uv venv -q --python 3.12 "$venv" >/dev/null 2>&1; then
    ok "Python $(pyver "$venv/bin/python") installé par uv dans .venv"
  elif py="$(find_python 10)"; then
    if "$py" -m venv "$venv" >/dev/null 2>&1; then ok "Python $(pyver "$py") ($py) → .venv"
    else bad "$py -m venv a échoué (Debian/Ubuntu : sudo apt install python3-venv)"
    fi
  else
    bad "Python 3.10 ou plus récent introuvable : installer uv (https://docs.astral.sh/uv/) ou Python 3.12 (macOS : brew install python)"
  fi
fi

echo "3. Dépendances"
if [ -x "$venv/bin/python" ]; then
  pip_install() {
    if has uv; then uv pip install -q --python "$venv/bin/python" ${upgrade:+--upgrade} "$@"
    else "$venv/bin/python" -m pip install -q --disable-pip-version-check ${upgrade:+--upgrade} "$@"
    fi
  }
  started=$(date +%s)
  if pip_install -r "$skill/requirements.txt" >"$venv/install.log" 2>&1; then
    ok "fitdecode et garminconnect installés en $(( $(date +%s) - started )) s"
  elif pip_install "$(grep -E '^fitdecode' "$skill/requirements.txt")" >>"$venv/install.log" 2>&1; then
    warn "garminconnect impossible à installer (voir $venv/install.log) : Garmin indisponible, Strava et l'import restent utilisables"
  else
    bad "installation impossible, détail dans $venv/install.log"
  fi
  if ! at_least "$venv/bin/python" 3 12; then
    warn "Python $(pyver "$venv/bin/python") : garminconnect est limité à la version 0.3.2. La connexion Garmin suit mieux les changements de Garmin avec Python 3.12 ou plus (installer uv, supprimer .venv, relancer)."
  fi
fi

echo "4. Dossiers"
config="${RUNNING_COACH_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/running-coach}"
data="${RUNNING_COACH_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/running-coach}"
mkdir -p "$config" "$data" && chmod 700 "$config" && ok "configuration $config" && ok "données $data"

echo "5. Essai hors ligne"
if [ "$missing" = 0 ]; then
  trial="$(mktemp -d)"
  mkdir -p "$trial/config"
  cp "$skill/tests/fixtures/profile.json" "$trial/config/"
  started=$(date +%s)
  if out="$(RUNNING_COACH_CONFIG="$trial/config" RUNNING_COACH_DATA="$trial/data" "$skill/scripts/coach" import "$skill/tests/fixtures/files" 2>&1 \
        && RUNNING_COACH_CONFIG="$trial/config" RUNNING_COACH_DATA="$trial/data" "$skill/scripts/coach" --today 2026-10-11 week 2>&1)" \
     && printf '%s' "$out" | grep -q "4 sortie(s), 43.2 km"; then
    ok "import GPX/TCX/FIT/JSON et bilan de semaine en $(( $(date +%s) - started )) s"
  else
    bad "échec de l'essai : $(printf '%s' "$out" | tail -3)"
  fi
  rm -rf "$trial"
fi

echo
if [ "$missing" = 0 ]; then
  echo "Prêt. Commandes : $skill/scripts/coach --help ; premier pas : $skill/scripts/coach doctor"
else
  echo "Installation incomplète : corriger les lignes marquées ✗ puis relancer install.sh"
  exit 1
fi
