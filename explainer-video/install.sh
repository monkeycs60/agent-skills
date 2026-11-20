#!/usr/bin/env bash
set -uo pipefail

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

if ! command -v node >/dev/null 2>&1; then
  echo "explainer-video : Node est introuvable. Installer Node 20 ou plus (https://nodejs.org), puis relancer ce script."
  exit 1
fi

node "$dir/scripts/outils.js"
