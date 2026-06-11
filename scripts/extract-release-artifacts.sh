#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODELS_PKG="${1:-models/models-package.tar.gz}"
PROCESSED_PKG="${2:-data/processed-package.tar.gz}"

if [ ! -f "$MODELS_PKG" ]; then
  echo "Models package not found: $MODELS_PKG" >&2
  exit 1
fi

if [ ! -f "$PROCESSED_PKG" ]; then
  echo "Processed package not found: $PROCESSED_PKG" >&2
  exit 1
fi

rm -rf models/base_models data/processed
mkdir -p models data
tar -xzf "$MODELS_PKG" -C models
tar -xzf "$PROCESSED_PKG" -C data

echo "Extracted models -> models/base_models"
echo "Extracted processed -> data/processed"
