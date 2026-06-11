#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Updating models/processed from latest GitHub Release..."
uv run dvc update models/models.dvc data/processed.dvc
