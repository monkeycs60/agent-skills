#!/usr/bin/env bash
set -uo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
if [ "$#" -gt 0 ]; then skills=("$@")
else skills=(); for d in "$repo"/*/; do [ -f "$d/SKILL.md" ] && skills+=("$(basename "$d")"); done
fi

mkdir -p "$HOME/.claude/skills"
for skill in "${skills[@]}"; do
  if [ ! -f "$repo/$skill/SKILL.md" ]; then echo "✗ $skill : skill inconnu"; continue; fi
  echo "→ $skill"
  for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills"; do
    [ -d "$dir" ] || continue
    target="$dir/$skill"
    if [ "$(cd "$target" 2>/dev/null && pwd -P)" = "$repo/$skill" ]; then echo "  ✓ $target"
    elif [ -e "$target" ] || [ -L "$target" ]; then echo "  ! $target existe déjà : laissé tel quel"
    else ln -s "$repo/$skill" "$target" && echo "  ✓ $target → $repo/$skill"
    fi
  done
  [ -f "$repo/$skill/install.sh" ] && bash "$repo/$skill/install.sh"
done
