#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Updating models/processed from latest GitHub Release..."
if [ -d .git ]; then
  uv run dvc update models/models.dvc data/processed.dvc
else
  uv run python - <<'PY'
from pathlib import Path
import urllib.request

import yaml

for dvc_path in (Path("models/models.dvc"), Path("data/processed.dvc")):
    spec = yaml.safe_load(dvc_path.read_text())
    url = str(spec["deps"][0]["path"]).strip()
    output = dvc_path.parent / str(spec["outs"][0]["path"]).strip()

    output.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, output)
PY
fi
