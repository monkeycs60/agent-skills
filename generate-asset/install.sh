#!/usr/bin/env bash
set -uo pipefail

skill="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
has() { command -v "$1" >/dev/null 2>&1; }
echo "generate-asset: $skill"

if python3 -c 'import PIL' 2>/dev/null; then echo "  ✓ Pillow (system Python)"
elif [ -x "$skill/.venv/bin/python" ] && "$skill/.venv/bin/python" -c 'import PIL' 2>/dev/null; then echo "  ✓ Pillow ($skill/.venv)"
elif has uv && uv venv -q "$skill/.venv" && uv pip install -q --python "$skill/.venv/bin/python" pillow; then echo "  ✓ Pillow installed in .venv (uv)"
elif python3 -m venv "$skill/.venv" 2>/dev/null && "$skill/.venv/bin/python" -m pip install -q pillow; then echo "  ✓ Pillow installed in .venv"
else echo "  ✗ Pillow: install python3-venv (Debian, Ubuntu) or uv, then run again"; exit 1
fi

if has codex; then echo "  ✓ Codex CLI ($(codex --version 2>/dev/null | head -1))"
else echo "  ! Codex CLI missing: npm install -g @openai/codex, then codex login (ChatGPT account)"
fi

tmp="$(mktemp -d)"
py="$skill/.venv/bin/python"; [ -x "$py" ] || py=python3
"$py" - "$tmp" <<'PY'
import sys
from PIL import Image
for i, color in enumerate(["#c84040", "#40a05a", "#3a5adc"]):
    Image.new("RGB", (64, 64), color).save(f"{sys.argv[1]}/s{i}.png")
PY
if python3 "$skill/scripts/contact_sheet.py" "$tmp" "$tmp/out/sheet.jpg" >/dev/null && python3 "$skill/scripts/to_webp.py" "$tmp" "$tmp/out/webp" 64 80 >/dev/null; then
  echo "  ✓ contact sheet and WebP conversion"
else echo "  ✗ script smoke test failed"; rm -rf "$tmp"; exit 1
fi
rm -rf "$tmp"
echo "Ready."
