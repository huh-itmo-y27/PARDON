<div align="center">

<img src="./docs/pardon-logo.svg" width="600" alt="PARDON logo">

![Python](https://img.shields.io/badge/python-3.10-blue.svg)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://huh-itmo-y27.github.io/PARDON/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/huh-itmo-y27/PARDON)

</div>

# PARDON

PARDON (Pumps Anomaly Recognition & Detection On Network) is an anomaly
detection platform for pump telemetry. It covers the full lifecycle:

- data preparation and feature generation from SKAB-like datasets
- model training and offline prediction (`isolation_forest`, `conv_ae`, `lstm_ae`)
- experiment tracking with MLflow
- drift and runtime metrics with Prometheus + Grafana
- serving layer (FastAPI + Next.js)
- Kubernetes deployment workflow (Minikube + Argo CD + GHCR)

## Architecture at a glance

- ML pipeline: `anomaly_detection/` modules and `make train` / `make predict`
- Serving stack: `services/api` (FastAPI + PostgreSQL) and `services/ui` (Next.js)
- Observability: `docker-compose.monitoring.yml`, `monitoring/` dashboards
- Kubernetes manifests: `deploy/k8s/` and `deploy/argocd/`

## Scenario quick links

- First run on local data: [docs/docs/getting-started.md](docs/docs/getting-started.md)
- Local API + Web UI serving: [docs/docs/serving.md](docs/docs/serving.md)
- Minikube + Argo CD delivery: [docs/docs/cd-argocd.md](docs/docs/cd-argocd.md)
- Monitoring dashboards and metrics: [docs/docs/monitoring.md](docs/docs/monitoring.md)

## Quick start (local training + prediction)

```bash
make requirements
make data_pull
make dataset DATA_SCENARIO=valve1
make features DATA_SCENARIO=valve1
make train MODEL=isolation_forest DATA_SCENARIO=valve1
make predict MODEL=isolation_forest DATA_SCENARIO=valve1
```

Optional UIs:

```bash
make mlflow_ui
make monitoring_up
```

- MLflow: `http://localhost:5000`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`

## Local model workflow runbook

1. Install dependencies:
   ```bash
   make requirements
   ```
2. Download versioned SKAB raw data, processed features, and models:
   ```bash
   make data_pull
   ```
3. Build processed dataset and features:
   ```bash
   make dataset DATA_SCENARIO=valve1
   make features DATA_SCENARIO=valve1
   ```
4. Train and evaluate:
   ```bash
   make train MODEL=isolation_forest DATA_SCENARIO=valve1
   ```
5. Generate predictions:
   ```bash
   make predict MODEL=isolation_forest DATA_SCENARIO=valve1
   ```

Versioned data is tracked with DVC `import-url` (see `data/skab.dvc`,
`models/models.dvc`, `data/processed.dvc`). Raw CSVs land under `data/raw` with
columns `datetime`, numeric features, `anomaly`, and `changepoint`.

## Local serving runbook (API + Web UI)

Start full app stack:

```bash
make app_up
```

Verify:

```bash
make app_smoke
```

Endpoints:

- API health: `http://localhost:8000/healthz`
- API docs: `http://localhost:8000/docs`
- Web UI: `http://localhost:3001`

Stop:

```bash
make app_down
```

For browser-side API calls from local UI dev server:

```bash
cd services/ui
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## Minikube deployment runbook

1. Start local cluster:
   ```bash
   make k8s_minikube_up
   ```
2. Build local images:
   ```bash
   docker build -f services/api/Dockerfile -t pardon-api:latest .
   docker build -f services/ui/Dockerfile -t pardon-ui:latest .
   ```
3. Load images into Minikube:
   ```bash
   minikube image load pardon-api:latest
   minikube image load pardon-ui:latest
   ```
4. Apply manifests and check status:
   ```bash
   make k8s_deploy
   make k8s_status
   ```
5. Access services:
   ```bash
   make k8s_port_forward
   ```

Then open:

- UI: `http://localhost:3001`
- API health: `http://localhost:8000/healthz`
- Grafana: `http://localhost:3000` (`admin` / `admin`)
- MLflow: `http://localhost:5000`
- Prometheus: `http://localhost:9090`
- Pushgateway: `http://localhost:9091`

The Argo CD deployment includes API, UI, PostgreSQL, MLflow, Prometheus,
Pushgateway, MLflow exporter, and Grafana.

## Common commands

- `make requirements`: install Python dependencies
- `make data_pull`: download SKAB raw data, models, and processed features via DVC
- `make data_pull_skab`: download only SKAB raw scenarios
- `make dataset DATA_SCENARIO=<scenario>`: generate split datasets
- `make features DATA_SCENARIO=<scenario>`: build scaled features
- `make train MODEL=<model> DATA_SCENARIO=<scenario>`: train pipeline
- `make predict MODEL=<model> DATA_SCENARIO=<scenario>`: run inference pipeline
- `make app_up` / `make app_down`: run local serving stack
- `make app_smoke`: quick health checks for API and UI
- `make monitoring_up` / `make monitoring_down`: run monitoring stack
- `make k8s_port_forward`: forward API, UI, Grafana, MLflow, Prometheus, and Pushgateway from Kubernetes
- `make openapi_export` + `make ui_codegen`: refresh typed API schema for UI

## Troubleshooting index

- API container unhealthy on startup: see serving guide troubleshooting section
- UI cannot fetch API from browser: use local UI mode with
  `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- Argo CD install CRD annotation too long: use server-side apply in Argo CD guide
- Empty prediction table in UI: run at least one `POST /api/v1/predict`

## Full documentation

- [docs/docs/index.md](docs/docs/index.md)
- [docs/docs/getting-started.md](docs/docs/getting-started.md)
- [docs/docs/serving.md](docs/docs/serving.md)
- [docs/docs/cd-argocd.md](docs/docs/cd-argocd.md)
- [docs/docs/models.md](docs/docs/models.md)
- [docs/docs/mlflow.md](docs/docs/mlflow.md)
- [docs/docs/monitoring.md](docs/docs/monitoring.md)


