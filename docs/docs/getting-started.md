# Getting Started

This guide is the fastest end-to-end local path:
prepare data, train a model, run predictions, and inspect results.

## 1) Install dependencies

```bash
make requirements
```

## 2) Download versioned data

Raw SKAB scenarios, processed features, and trained models are tracked with DVC
`import-url` metadata (no MinIO remote). Pull everything with:

```bash
make data_pull
```

This downloads:

- SKAB upstream archive from [waico/SKAB](https://github.com/waico/SKAB) (pinned in `data/skab.lock`)
- `models.tar.gz` and `processed.tar.gz` from the **latest** PARDON GitHub Release
  (`releases/latest/download/...` in `models/models.dvc` and `data/processed.dvc`)

Each `make data_pull` runs `dvc update` on the release artifacts so you always get
the newest published models and processed features.

GitHub resolves `releases/latest/download/...` to the repository's current
**Latest** release (highest semver). That release must include `models.tar.gz` and
`processed.tar.gz`. If `make data_pull` fails, publish assets with
`Release data artifacts` or `GITHUB_TOKEN=... make data_import_release`.

SKAB-only pull:

```bash
make data_pull_skab
```

## 3) Build dataset and features

Choose a scenario from `data/raw` (`valve1`, `valve2`, `other`,
`anomaly-free`, `all`):

```bash
make dataset DATA_SCENARIO=valve1
make features DATA_SCENARIO=valve1
```

Tip: avoid `all` if any raw files are missing required label columns.

## 4) Train and predict

```bash
make train MODEL=isolation_forest DATA_SCENARIO=valve1
make predict MODEL=isolation_forest DATA_SCENARIO=valve1
```

Swap `MODEL=` to `conv_ae` or `lstm_ae` to compare model families.

## 5) Inspect experiments and metrics

Start optional local observability services:

```bash
make mlflow_ui
make monitoring_up
```

Endpoints:

- MLflow: `http://localhost:5000`
- Grafana: `http://localhost:3000` (`admin` / `admin`)
- Prometheus: `http://localhost:9090`
- Pushgateway: `http://localhost:9091`

In Grafana, check dashboards such as:

- `Recent Train and Predict Runs`
- `Operational Health`
- `MLflow Quality: Current vs History`

## 6) Optional: run serving stack

To test FastAPI + Web UI locally:

```bash
make app_up
make app_smoke
```

Open:

- UI: `http://localhost:3001`
- API docs: `http://localhost:8000/docs`

Stop:

```bash
make app_down
```

## 7) Next guides by scenario

- Local model workflow details: `Models`, `MLflow`, `Monitoring`
- Local serving and API/UI troubleshooting: `Serving Platform`
- Kubernetes and GitOps flow: `CD with Argo CD`

Stop monitoring when done:

```bash
make monitoring_down
```
