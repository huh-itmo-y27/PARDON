# pumps-anomaly-detection

[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://huh-itmo-y27.github.io/PARDON/)

Production-oriented anomaly detection project with:

- SKAB-style dataset processing
- multiple model backends (`isolation_forest`, `conv_ae`, `lstm_ae`)
- MLflow experiment tracking and optional model registry
- drift metrics (data, target, concept proxy)
- Prometheus + Grafana monitoring dashboards

## Quick start

```bash
make requirements
make dataset DATA_SCENARIO=valve1
make features DATA_SCENARIO=valve1
make train MODEL=isolation_forest DATA_SCENARIO=valve1
make predict MODEL=isolation_forest DATA_SCENARIO=valve1
```

Start local monitoring:

```bash
make monitoring_up
```

Endpoints:

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- MLflow UI: `make mlflow_ui` (default port `5000`)

## Documentation

Detailed docs live in `docs/` and are split by topic:

- `Getting Started`
- `Dataset (SKAB)`
- `Models`
- `MLflow`
- `Monitoring`
- `Publish Docs`

## Common commands

- `make requirements` - install dependencies
- `make dataset DATA_SCENARIO=<scenario>` - build train/val/test splits
- `make features DATA_SCENARIO=<scenario>` - build scaled feature datasets
- `make train MODEL=<model> DATA_SCENARIO=<scenario>` - train and evaluate model
- `make predict MODEL=<model> DATA_SCENARIO=<scenario>` - generate predictions
- `make mlflow_ui` - start MLflow tracking UI
- `make monitoring_up` / `make monitoring_down` - start/stop monitoring stack

## Data requirements

Raw CSV files are discovered recursively under `data/raw` and are expected to
contain:

- `datetime`
- numeric feature columns
- `anomaly` (0/1)
- `changepoint` (0/1)

If a file is missing required label columns, dataset creation fails for that
scenario.

## Project structure

- `anomaly_detection/` - core package
- `anomaly_detection/modeling/` - model training and inference
- `anomaly_detection/monitoring/` - drift and metrics integration
- `monitoring/` - Prometheus/Grafana configs and dashboards
- `data/processed/` - generated splits and feature data
- `models/` - saved model artifacts and metadata

