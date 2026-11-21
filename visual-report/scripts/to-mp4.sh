#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: to-mp4.sh <input video> <output.mp4> [max width, default 1280] [fps, default 15]" >&2
  exit 2
fi
in="$1"; out="$2"; width="${3:-1280}"; fps="${4:-15}"
command -v ffmpeg >/dev/null 2>&1 || { echo "to-mp4.sh: ffmpeg not found (sudo apt install ffmpeg, or brew install ffmpeg)" >&2; exit 127; }
[ -f "$in" ] || { echo "to-mp4.sh: input not found: $in" >&2; exit 1; }

mkdir -p "$(dirname "$out")"
ffmpeg -loglevel error -y -i "$in" \
  -vf "fps=${fps},scale='min(${width},iw)':-2:flags=lanczos" \
  -c:v libx264 -pix_fmt yuv420p -crf 28 -preset veryfast -movflags +faststart -an "$out"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$out" 2>/dev/null || echo "?")"
printf '%s  %s KB  %s s\n' "$out" "$(( $(wc -c <"$out") / 1024 ))" "${duration%.*}"
