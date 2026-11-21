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
echo "youtube skill: $skill"

echo "1. Location"
for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills"; do
  [ "$dir" = "$HOME/.claude/skills" ] && mkdir -p "$dir"
  [ -d "$dir" ] || continue
  target="$dir/$(basename "$skill")"
  if [ "$(cd "$target" 2>/dev/null && pwd -P)" = "$skill" ]; then ok "$target"
  elif [ -e "$target" ] || [ -L "$target" ]; then warn "$target already exists and points elsewhere: left as is"
  else ln -s "$skill" "$target" && ok "$target → $skill"
  fi
done
chmod +x "$skill/scripts/yt" "$skill/install.sh"

echo "2. Python 3.10 or newer"
if py="$(python_ok)"; then ok "$py ($("$py" -V 2>&1))"
elif has uv; then uv python install 3.12 >/dev/null 2>&1 && ok "Python 3.12 installed by uv" || bad "uv could not install Python 3.12"
else bad "not found: install Python 3.10+ (macOS: brew install python) or uv (https://docs.astral.sh/uv/)"
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
    ok "yt-dlp $("$bin/yt-dlp" --version 2>/dev/null) installed in $bin"
  else bad "could not download yt-dlp"
  fi
fi
case ":$original_path:" in *":$bin:"*) ;; *) warn "$bin is not in the shell PATH: add export PATH=\"$bin:\$PATH\" to your profile" ;; esac

echo "4. JavaScript runtime for YouTube"
if has deno || has node || has bun; then ok "$(for r in deno node bun; do has "$r" && printf '%s ' "$r"; done)"
else warn "no deno, node or bun: YouTube may refuse some videos; install Node.js"
fi

echo "5. Optional"
if has ffmpeg; then ok "ffmpeg (videos without captions)"
elif [ "$os" = Darwin ]; then warn "ffmpeg missing: brew install ffmpeg (only for videos without captions)"
else warn "ffmpeg missing: sudo apt install ffmpeg (only for videos without captions)"
fi
if has uv; then ok "uv (installs the local transcription engine)"; else warn "uv missing: falls back to python -m venv"; fi
chrome="$("${py:-python3}" -I -c "import sys; sys.path.insert(0, '$skill/scripts'); import report; print(report.find_chrome() or '')" 2>/dev/null)"
if [ -n "$chrome" ]; then ok "Chrome: $chrome (diagrams)"; else warn "Chrome not found: diagrams will stay as source (set CHROME_PATH to point to it)"; fi
browser="$("${py:-python3}" -I -c "import sys; sys.path.insert(0, '$skill/scripts'); import links; print(links.BROWSER or '')" 2>/dev/null)"
if [ -n "$browser" ]; then ok "agent-browser: $browser (linked pages)"; else warn "agent-browser missing: links read over plain HTTP (npm i -g agent-browser && agent-browser install)"; fi
if has gh && gh auth status >/dev/null 2>&1; then ok "gh signed in (GitHub repositories)"; else warn "gh missing or not signed in: GitHub repositories cited will not be read"; fi

echo "6. Live test"
if [ "$missing" = 0 ]; then
  started=$(date +%s)
  if out="$("$skill/scripts/yt" transcript "https://youtu.be/KKNCiRWd_j0" 2>&1)"; then
    ok "transcript fetched in $(( $(date +%s) - started )) s: $(printf '%s' "$out" | tail -1 | cut -c1-110)…"
  else bad "failed: $(printf '%s' "$out" | tail -2)"
  fi
fi

echo
if [ "$missing" = 0 ]; then echo "Ready. Paste a YouTube link to the agent, or run: $skill/scripts/yt transcript <url>"
else echo "Incomplete installation: fix the lines marked ✗ then run install.sh again"; exit 1
fi
