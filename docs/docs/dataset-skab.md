# Dataset (SKAB)

## Summary

The project expects SKAB-like time series CSV files in `data/raw` and creates
deterministic `train/val/test` splits in `data/processed`.

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

Supported examples in your repo:

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
