#!/usr/bin/env bash
set -uo pipefail

skill="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
bin="$HOME/.local/bin"
mkdir -p "$bin"
original_path="$PATH"
export PATH="$bin:$PATH"
missing=0

ok() { printf '  ✓ %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*"; }
bad() { printf '  ✗ %s\n' "$*"; missing=1; }
has() { command -v "$1" >/dev/null 2>&1; }

download() {
  if has curl; then curl -fsSL "$1" -o "$2"
  elif has wget; then wget -qO "$2" "$1"
  else python3 -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' "$1" "$2"
  fi
}

python_ok() {
  for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if has "$candidate" && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
      echo "$candidate"; return 0
    fi
  done
  return 1
}

os="$(uname -s)"
echo "Skill youtube : $skill"

echo "1. Emplacement"
for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills"; do
  [ "$dir" = "$HOME/.claude/skills" ] && mkdir -p "$dir"
  [ -d "$dir" ] || continue
  target="$dir/$(basename "$skill")"
  if [ "$(cd "$target" 2>/dev/null && pwd -P)" = "$skill" ]; then ok "$target"
  elif [ -e "$target" ] || [ -L "$target" ]; then warn "$target existe déjà et pointe ailleurs : laissé tel quel"
  else ln -s "$skill" "$target" && ok "$target → $skill"
  fi
done
chmod +x "$skill/scripts/yt" "$skill/install.sh"

echo "2. Python 3.10 ou plus récent"
if py="$(python_ok)"; then ok "$py ($("$py" -V 2>&1))"
elif has uv; then uv python install 3.12 >/dev/null 2>&1 && ok "Python 3.12 installé par uv" || bad "uv n'a pas pu installer Python 3.12"
else bad "introuvable : installer Python 3.10+ (macOS : brew install python) ou uv (https://docs.astral.sh/uv/)"
fi

echo "3. yt-dlp"
if has yt-dlp; then ok "yt-dlp $(yt-dlp --version 2>/dev/null)"
else
  case "$os-$(uname -m)" in
    Linux-x86_64) asset=yt-dlp_linux ;;
    Linux-aarch64|Linux-arm64) asset=yt-dlp_linux_aarch64 ;;
    Darwin-*) asset=yt-dlp_macos ;;
    *) asset=yt-dlp ;;
  esac
  if download "https://github.com/yt-dlp/yt-dlp/releases/latest/download/$asset" "$bin/yt-dlp" && chmod +x "$bin/yt-dlp"; then
    ok "yt-dlp $("$bin/yt-dlp" --version 2>/dev/null) installé dans $bin"
  else bad "téléchargement de yt-dlp impossible"
  fi
fi
case ":$original_path:" in *":$bin:"*) ;; *) warn "$bin n'est pas dans le PATH du shell : ajouter export PATH=\"$bin:\$PATH\" au profil" ;; esac

echo "4. Moteur JavaScript pour YouTube"
if has deno || has node || has bun; then ok "$(for r in deno node bun; do has "$r" && printf '%s ' "$r"; done)"
else warn "ni deno, ni node, ni bun : YouTube peut refuser certaines vidéos ; installer Node.js"
fi

echo "5. Optionnel"
if has ffmpeg; then ok "ffmpeg (vidéos sans sous-titres)"
elif [ "$os" = Darwin ]; then warn "ffmpeg absent : brew install ffmpeg (seulement pour les vidéos sans sous-titres)"
else warn "ffmpeg absent : sudo apt install ffmpeg (seulement pour les vidéos sans sous-titres)"
fi
if has uv; then ok "uv (installation du moteur de transcription locale)"; else warn "uv absent : repli sur python -m venv"; fi
chrome="$("${py:-python3}" -I -c "import sys; sys.path.insert(0, '$skill/scripts'); import report; print(report.find_chrome() or '')" 2>/dev/null)"
if [ -n "$chrome" ]; then ok "Chrome : $chrome (schémas)"; else warn "Chrome introuvable : les schémas resteront en source (CHROME_PATH pour l'indiquer)"; fi
browser="$("${py:-python3}" -I -c "import sys; sys.path.insert(0, '$skill/scripts'); import links; print(links.BROWSER or '')" 2>/dev/null)"
if [ -n "$browser" ]; then ok "agent-browser : $browser (pages des liens)"; else warn "agent-browser absent : liens lus en HTTP simple (npm i -g agent-browser && agent-browser install)"; fi
if has gh && gh auth status >/dev/null 2>&1; then ok "gh connecté (dépôts GitHub)"; else warn "gh absent ou non connecté : les dépôts GitHub cités ne seront pas lus"; fi

echo "6. Essai réel"
if [ "$missing" = 0 ]; then
  started=$(date +%s)
  if out="$("$skill/scripts/yt" transcript "https://youtu.be/KKNCiRWd_j0" 2>&1)"; then
    ok "transcription récupérée en $(( $(date +%s) - started )) s : $(printf '%s' "$out" | tail -1 | cut -c1-110)…"
  else bad "échec : $(printf '%s' "$out" | tail -2)"
  fi
fi

echo
if [ "$missing" = 0 ]; then echo "Prêt. Coller un lien YouTube à l'agent, ou lancer : $skill/scripts/yt transcript <url>"
else echo "Installation incomplète : corriger les lignes marquées ✗ puis relancer install.sh"; exit 1
fi
