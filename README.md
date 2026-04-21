# pumps-anomaly-detection

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

## Implemented pipelines

- `isolation_forest` (baseline, sklearn)
- `conv_ae` (TensorFlow/Keras convolutional autoencoder)
- `lstm_ae` (TensorFlow/Keras sequence autoencoder)

All pipelines are integrated in `anomaly_detection` and trained/predicted
through a unified CLI.

## Data contract

Place raw CSV files under `data/raw`. Each file must contain:

- `datetime` (timestamp column)
- feature columns (any numeric sensor columns)
- `anomaly` (0/1)
- `changepoint` (0/1)

CSV separator is `;` by default.

## Quick start

Install dependencies:

```bash
make requirements
```

Configure DVC credentials from `.env` and pull versioned data:

```bash
# Set MINIO_ACCESS_KEY and MINIO_SECRET_KEY in .env first
make setup_dvc
make data_pull
```

Prepare canonical train/val/test splits:

```bash
make dataset
```

Generate scaled feature files:

```bash
make features
```

Train a model (`MODEL=isolation_forest|conv_ae|lstm_ae`):

```bash
make train MODEL=isolation_forest
```

Run inference:

```bash
make predict MODEL=isolation_forest
```

## Airflow orchestration

The project now includes an Airflow DAG that treats each stage as a task:

- dataset split
- feature generation
- model training
- training summary logging
- batch prediction
- inference summary logging

DAG file:

- `dags/anomaly_pipeline_dag.py`

Default run outputs are isolated under:

- `data/airflow_runs/<dag_id>/<ts_nodash>/processed`
- `data/airflow_runs/<dag_id>/<ts_nodash>/models`
- `data/airflow_runs/<dag_id>/<ts_nodash>/predictions`

Run DVC separately from Airflow (if you need remote data):

```bash
make setup_dvc
make data_pull
```

Install Airflow dependencies:

```bash
make airflow_requirements
```

Airflow services are started with `AIRFLOW__CORE__LOAD_EXAMPLES=False`, so
only project DAGs are shown by default.

Initialize Airflow metadata DB:

```bash
make airflow_init
```

For Airflow 3 local bootstrap credentials, run once:

```bash
make airflow_standalone
```

Start scheduler and API server (recommended auto-port mode, in separate terminals):

```bash
make airflow_scheduler_auto
make airflow_webserver_auto
```

Alternative manual port control:

```bash
make airflow_scheduler AIRFLOW_LOG_SERVER_PORT=8794
make airflow_webserver AIRFLOW_API_PORT=8081
```

Trigger DAG:

```bash
make airflow_unpause
make airflow_trigger MODEL=isolation_forest
```

Example with custom templated params through Airflow CLI:

```bash
uv run airflow dags trigger anomaly_detection_orchestration \
  --conf '{"model_name":"conv_ae","time_steps":30,"register_model":false}'
```

Check DAG/runs:

```bash
make airflow_list_dags
make airflow_list_runs
```

Open MLflow UI for current `mlruns`:

```bash
make mlflow_ui
# optional custom port:
# make mlflow_ui MLFLOW_PORT=5001
```

## MLflow

Training logs parameters, metrics, and model artifacts to MLflow
(`file:./mlruns` by default). The training command also attempts model
registration in MLflow registry under:

- `anomaly_detection_isolation_forest`
- `anomaly_detection_conv_ae`
- `anomaly_detection_lstm_ae`

## Main directories

- `anomaly_detection/config.py` - project constants and defaults
- `anomaly_detection/dataset.py` - raw data validation and deterministic split
- `anomaly_detection/features.py` - scaling and feature metadata generation
- `anomaly_detection/modeling/train.py` - train + evaluate + MLflow logging
- `anomaly_detection/modeling/predict.py` - inference for local or MLflow model
- `models/` - serialized model artifacts and metadata
- `data/processed/` - canonical split and transformed feature files

