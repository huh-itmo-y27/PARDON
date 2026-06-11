#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RELEASE_TAG="${RELEASE_TAG:-data-v0.1.0}"
REPO="${GITHUB_REPOSITORY:-huh-itmo-y27/PARDON}"
DIST_DIR="${DIST_DIR:-$ROOT/.release-artifacts}"

./scripts/build-release-artifacts.sh

MODELS_TAR="$DIST_DIR/models.tar.gz"
PROCESSED_TAR="$DIST_DIR/processed.tar.gz"

if [ -n "${GITHUB_TOKEN:-}" ]; then
  AUTH="Authorization: Bearer $GITHUB_TOKEN"
elif [ -n "${GH_TOKEN:-}" ]; then
  AUTH="Authorization: Bearer $GH_TOKEN"
else
  echo "Set GITHUB_TOKEN or GH_TOKEN to publish release assets." >&2
  exit 1
fi

API="https://api.github.com/repos/$REPO"
RELEASE_ID="$(curl -fsS -H "$AUTH" "$API/releases/tags/$RELEASE_TAG" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("id",""))' 2>/dev/null || true)"

if [ -z "$RELEASE_ID" ] || [ "$RELEASE_ID" = "None" ]; then
  echo "Creating release $RELEASE_TAG..."
  RELEASE_ID="$(curl -fsS -X POST -H "$AUTH" -H "Content-Type: application/json" \
    "$API/releases" \
    -d "{\"tag_name\":\"$RELEASE_TAG\",\"name\":\"$RELEASE_TAG\",\"body\":\"PARDON models and processed data for DVC import-url. Trained on SKAB valve1 with project defaults (epochs=20, batch_size=32 for neural models).\",\"draft\":false,\"prerelease\":false}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
fi

upload_asset() {
  file_path="$1"
  file_name="$(basename "$file_path")"
  echo "Uploading $file_name to $RELEASE_TAG..."
  curl -fsS -X POST -H "$AUTH" -H "Content-Type: application/gzip" \
    --data-binary @"$file_path" \
    "$API/releases/$RELEASE_ID/assets?name=$file_name"
}

upload_asset "$MODELS_TAR"
upload_asset "$PROCESSED_TAR"

echo "Published $RELEASE_TAG assets to https://github.com/$REPO/releases/tag/$RELEASE_TAG"
