#!/usr/bin/env sh
set -eu

PVC_ROOT="${PARDON_DVC_DATA_ROOT:-/mnt/pardon-data}"
cd /app

export DVC_CACHE_DIR="$PVC_ROOT/dvc-cache"
mkdir -p "$DVC_CACHE_DIR" \
  "$PVC_ROOT/data/raw" \
  "$PVC_ROOT/data/processed" \
  "$PVC_ROOT/data/external" \
  "$PVC_ROOT/models/base_models"

echo "Fetching SKAB archive..."
./scripts/pull-skab-data.sh

echo "Updating models/processed from latest GitHub Release..."
./scripts/pull-release-artifacts.sh

echo "Extracting SKAB scenarios..."
./scripts/extract-skab-data.sh data/external/skab.tar.gz "$PVC_ROOT/data/raw"

echo "Extracting models and processed packages..."
./scripts/extract-release-artifacts.sh \
  models/models-package.tar.gz \
  data/processed-package.tar.gz

mkdir -p "$PVC_ROOT/models/base_models" "$PVC_ROOT/data/processed"
cp -R models/base_models/. "$PVC_ROOT/models/base_models/"
cp -R data/processed/. "$PVC_ROOT/data/processed/"

echo "DVC data synced to $PVC_ROOT"
