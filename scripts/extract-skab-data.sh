#!/usr/bin/env sh
set -eu

ARCHIVE="${1:?Usage: extract-skab-data.sh <skab.tar.gz> [output_dir] [scenario]}"
OUT_DIR="${2:-data/raw}"
SCENARIO="${3:-}"

mkdir -p "$OUT_DIR"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

tar -xzf "$ARCHIVE" -C "$TMP_DIR"

ROOT="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
DATA_DIR="$ROOT/data"

if [ ! -d "$DATA_DIR" ]; then
  echo "SKAB archive does not contain data/: $ARCHIVE" >&2
  exit 1
fi

copy_scenario() {
  name="$1"
  if [ ! -d "$DATA_DIR/$name" ]; then
    echo "Scenario not found in SKAB archive: $name" >&2
    exit 1
  fi
  rm -rf "$OUT_DIR/$name"
  mkdir -p "$OUT_DIR"
  cp -R "$DATA_DIR/$name" "$OUT_DIR/$name"
  echo "Extracted SKAB scenario '$name' -> $OUT_DIR/$name"
}

if [ -n "$SCENARIO" ]; then
  copy_scenario "$SCENARIO"
else
  for name in valve1 valve2 other; do
    if [ -d "$DATA_DIR/$name" ]; then
      copy_scenario "$name"
    fi
  done
fi
