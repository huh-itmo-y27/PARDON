# Dataset (SKAB)

## Summary

PARDON uses SKAB-like time series CSV files in `data/raw` and creates
deterministic `train/val/test` splits in `data/processed`.

Raw SKAB data is not stored in Git. It is downloaded on demand via DVC
`import-url` from the upstream SKAB repository tarball (see `data/skab.dvc` and
`data/skab.lock`).

Trained models and processed feature bundles are pulled via DVC from the **latest**
PARDON GitHub Release assets (`models/models.dvc`, `data/processed.dvc`).

```bash
make data_pull
```

## Raw data format

Each CSV is expected to contain:

- `datetime` (timestamp)
- sensor feature columns (numeric)
- `anomaly` (0/1)
- `changepoint` (0/1)

Default CSV separator is `;`.

## Scenario-based runs

You can run experiments for a subset of files by scenario name:

```bash
make dataset DATA_SCENARIO=valve1
make features DATA_SCENARIO=valve1
```

Supported examples:

- `valve1`
- `valve2`
- `other`
- `anomaly-free`
- `all`

`all` includes every CSV recursively under `data/raw`.

## Important note about anomaly-free data

If a source file does not include `anomaly` and `changepoint`, dataset
generation fails by design because these columns are required for supervised
evaluation and drift reporting.

## Updating pinned upstream versions

- SKAB tarball: edit `skab_rev` in `data/skab.lock`, then refresh `data/skab.dvc`
  with `dvc import-url` or `dvc update data/skab.dvc`.
- Models/processed release: publish a new GitHub Release with `models.tar.gz` and
  `processed.tar.gz`. The next `make data_pull` picks it up automatically via
  `releases/latest/download/...` (no `.dvc` edit required).

  GitHub **Latest** follows semver: if the newest tag is an app release (e.g.
  `v0.2.0`) without data assets, attach the tarballs there or publish a higher
  data tag so it becomes Latest.

Build local release tarballs with:

```bash
./scripts/build-release-artifacts.sh
```

Publish to GitHub Releases:

```bash
GITHUB_TOKEN=... RELEASE_TAG=data-v0.1.0 ./scripts/publish-release-artifacts.sh
```

## Outputs

After `make dataset`, you get:

- `data/processed/train.csv`
- `data/processed/val.csv`
- `data/processed/test.csv`
- `data/processed/dataset_manifest.json`

After `make features`, you get:

- `data/processed/train_features.csv`
- `data/processed/val_features.csv`
- `data/processed/test_features.csv`
- `data/processed/features_metadata.json`
- `data/processed/scaler.pkl`
