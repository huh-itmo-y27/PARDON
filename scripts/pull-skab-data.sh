#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p data/external

echo "Fetching SKAB archive from import-url dependency..."
uv run dvc update data/skab.dvc
