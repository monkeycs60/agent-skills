#!/usr/bin/env bash
# Usage: launch.sh <slug> <workdir> <prompt-file>
# Lance Codex (gpt-6-luna par défaut, CODEX_IMAGE_MODEL pour un autre ; effort high) en processus détaché et écrit son PID dans /tmp/<slug>.pid.
set -euo pipefail
slug="$1"; workdir="$(cd "$2" && pwd)"; prompt="$3"
[ -f "$prompt" ] || { echo "prompt introuvable : $prompt" >&2; exit 1; }
log="/tmp/$slug.log"; last="/tmp/$slug-last.md"; pidfile="/tmp/$slug.pid"
if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then echo "déjà en cours (PID $(cat "$pidfile"))" >&2; exit 1; fi
cd "$workdir"
model="${CODEX_IMAGE_MODEL:-gpt-6-luna}"
detach=(nohup); command -v setsid >/dev/null 2>&1 && detach=(setsid nohup)
"${detach[@]}" codex exec -m "$model" -c model_reasoning_effort=high -s workspace-write --skip-git-repo-check \
  -C "$workdir" -o "$last" "$(cat "$prompt")" > "$log" 2>&1 < /dev/null &
echo $! > "$pidfile"
for _ in $(seq 1 30); do grep -q "^model:" "$log" 2>/dev/null && break; sleep 1; done
grep -E "^(model|reasoning effort):" "$log" || { echo "Codex n'a pas démarré, voir $log" >&2; exit 1; }
echo "PID $(cat "$pidfile") · log $log · dernier message $last"
