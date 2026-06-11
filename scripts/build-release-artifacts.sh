#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RELEASE_TAG="${RELEASE_TAG:-data-v0.1.0}"
DIST_DIR="${DIST_DIR:-$ROOT/.release-artifacts}"
MODELS_TAR="$DIST_DIR/models.tar.gz"
PROCESSED_TAR="$DIST_DIR/processed.tar.gz"

mkdir -p "$DIST_DIR"

if [ ! -d models/base_models ] || [ -z "$(ls -A models/base_models 2>/dev/null)" ]; then
  echo "models/base_models is missing. Run training or 'make data_pull' first." >&2
  exit 1
fi

if [ ! -f data/processed/scaler.pkl ]; then
  echo "data/processed/scaler.pkl is missing. Run 'make dataset' and 'make features' first." >&2
  exit 1
fi

tar -czf "$MODELS_TAR" -C models base_models
tar -czf "$PROCESSED_TAR" -C data processed

echo "Built release artifacts:"
echo "  $MODELS_TAR"
echo "  $PROCESSED_TAR"
echo
echo "Publish to GitHub Releases tag '$RELEASE_TAG', then refresh DVC metadata:"
echo "  make data_import_release RELEASE_TAG=$RELEASE_TAG"
