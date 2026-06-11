#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RELEASE_TAG="${RELEASE_TAG:-data-v0.1.0}"
REPO="${GITHUB_REPOSITORY:-huh-itmo-y27/PARDON}"
TARGET_COMMITISH="${TARGET_COMMITISH:-}"
export RELEASE_TAG TARGET_COMMITISH
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
GH_ACCEPT="Accept: application/vnd.github+json"

fetch_release_json() {
  curl -fsS -H "$AUTH" -H "$GH_ACCEPT" "$API/releases/tags/$RELEASE_TAG" 2>/dev/null || true
}

RELEASE_JSON="$(fetch_release_json)"

if [ -z "$RELEASE_JSON" ] || ! printf '%s' "$RELEASE_JSON" | python3 -c 'import json,sys; json.load(sys.stdin)["id"]' >/dev/null 2>&1; then
  echo "Creating release $RELEASE_TAG..."
  CREATE_PAYLOAD="$(python3 - <<PY
import json
import os

payload = {
    "tag_name": os.environ["RELEASE_TAG"],
    "name": os.environ["RELEASE_TAG"],
    "body": (
        "PARDON models and processed data for DVC import-url. "
        "Trained on SKAB valve1 with project defaults "
        "(epochs=20, batch_size=32 for neural models)."
    ),
    "draft": False,
    "prerelease": False,
}
target = os.environ.get("TARGET_COMMITISH", "").strip()
if target:
    payload["target_commitish"] = target
print(json.dumps(payload))
PY
)"
  RELEASE_JSON="$(curl -fsS -X POST -H "$AUTH" -H "$GH_ACCEPT" -H "Content-Type: application/json" \
    "$API/releases" \
    -d "$CREATE_PAYLOAD")"
fi

UPLOAD_URL="$(printf '%s' "$RELEASE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["upload_url"].partition("{")[0])')"

upload_asset() {
  file_path="$1"
  file_name="$(basename "$file_path")"
  echo "Uploading $file_name to $RELEASE_TAG..."
  curl -fsS -X POST -H "$AUTH" -H "Content-Type: application/octet-stream" \
    --data-binary @"$file_path" \
    "${UPLOAD_URL}?name=${file_name}"
}

upload_asset "$MODELS_TAR"
upload_asset "$PROCESSED_TAR"

echo "Published $RELEASE_TAG assets to https://github.com/$REPO/releases/tag/$RELEASE_TAG"
