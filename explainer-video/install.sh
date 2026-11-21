#!/usr/bin/env bash
set -uo pipefail

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

if ! command -v node >/dev/null 2>&1; then
  echo "explainer-video: Node not found. Install Node 20 or later (https://nodejs.org), then run this script again."
  exit 1
fi

node "$dir/scripts/tools.js"
