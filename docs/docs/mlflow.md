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

## Model registry

Training can register models and set the `champion` alias when backend supports
registry operations.
