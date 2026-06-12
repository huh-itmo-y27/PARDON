#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p data/external

echo "Fetching SKAB archive from import-url dependency..."
if [ -d .git ]; then
  uv run dvc update data/skab.dvc
else
  uv run python - <<'PY'
from pathlib import Path
import urllib.request

import yaml

dvc_file = Path("data/skab.dvc")
spec = yaml.safe_load(dvc_file.read_text())
url = str(spec["deps"][0]["path"]).strip()
output = dvc_file.parent / str(spec["outs"][0]["path"]).strip()

output.parent.mkdir(parents=True, exist_ok=True)
urllib.request.urlretrieve(url, output)
PY
fi
