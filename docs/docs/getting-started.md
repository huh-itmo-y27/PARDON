# Getting Started

This guide is the fastest end-to-end local path:
prepare data, train a model, run predictions, and inspect results.

## 1) Install dependencies

```bash
make requirements
```

## 2) Build dataset and features

Choose a scenario from `data/raw` (`valve1`, `valve2`, `other`,
`anomaly-free`, `all`):

```bash
make dataset DATA_SCENARIO=valve1
make features DATA_SCENARIO=valve1
```

Tip: avoid `all` if any raw files are missing required label columns.

## 3) Train and predict

```bash
make train MODEL=isolation_forest DATA_SCENARIO=valve1
make predict MODEL=isolation_forest DATA_SCENARIO=valve1
```

Swap `MODEL=` to `conv_ae` or `lstm_ae` to compare model families.

## 4) Inspect experiments and metrics

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

## 5) Optional: run serving stack

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

## 6) Next guides by scenario

- Local model workflow details: `Models`, `MLflow`, `Monitoring`
- Local serving and API/UI troubleshooting: `Serving Platform`
- Kubernetes and GitOps flow: `CD with Argo CD`

Stop monitoring when done:

```bash
make monitoring_down
```
