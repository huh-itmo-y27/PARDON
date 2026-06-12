# MLflow

## Summary

MLflow is used for experiment tracking for both training and inference runs.

## Local setup

Run UI locally:

```bash
make mlflow_ui
```

Default endpoint:

- `http://localhost:5000`

## Kubernetes setup

Argo CD deploys MLflow as `pardon-mlflow` in the `pardon` namespace.

- In-cluster tracking URI: `http://pardon-mlflow:5000`
- Local port-forward endpoint: `http://localhost:5000`
- Persistent storage: `pardon-mlflow-data` PVC

The shared Kubernetes ConfigMap sets:

```text
MLFLOW_TRACKING_URI=http://pardon-mlflow:5000
MLFLOW_EXPERIMENT_NAME=anomaly_detection
MLFLOW_INFERENCE_EXPERIMENT_NAME=anomaly_detection_inference
```

Open locally:

```bash
kubectl -n pardon port-forward svc/pardon-mlflow 5000:5000
```

or run the full helper:

```bash
make k8s_port_forward
```

## Experiments

- Training experiment: `anomaly_detection` (configurable)
- Inference experiment: `anomaly_detection_inference` (configurable)

## What is logged

Training logs:

- model and hyperparameter settings
- evaluation metrics (point, changepoint, NAB)
- drift metrics
- model artifacts and metadata files

Inference logs:

- source/model metadata
- `anomaly_rate`, `avg_score`
- inference drift metrics
- predictions artifact and drift report

## Environment configuration

Configure in `.env`:

- `MLFLOW_TRACKING_URI`
- `MLFLOW_EXPERIMENT_NAME`
- `MLFLOW_INFERENCE_EXPERIMENT_NAME`
- `MLFLOW_REGISTERED_MODEL_PREFIX`

## Kubernetes security notes

Recent MLflow versions validate `Host` and CORS headers. The Kubernetes command
allows the in-cluster service host and local port-forward host:

- `pardon-mlflow`
- `pardon-mlflow:5000`
- `localhost:5000`
- `127.0.0.1:5000`

If `http://localhost:5000` shows `Invalid Host header`, update
`--allowed-hosts` in `deploy/k8s/base/observability.yaml` and sync Argo CD.

## Model registry

Training can register models and set the `champion` alias when backend supports
registry operations.
