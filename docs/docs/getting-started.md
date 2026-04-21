# Getting started

This guide covers a full end-to-end Airflow run for the anomaly pipeline.

## 1) Install dependencies

```bash
make airflow_requirements
```

Airflow services are started with `AIRFLOW__CORE__LOAD_EXAMPLES=False`, so
example DAGs are hidden by default.

## 2) Prepare data input

The DAG expects raw CSV files under `data/raw` with the project data contract
(`datetime`, feature columns, `anomaly`, `changepoint`).

If you use DVC remote data, configure and pull first:

```bash
make setup_dvc
make data_pull
```

Airflow pipeline does not run DVC steps. Keep DVC operations separate from DAG
execution.

## 3) Initialize Airflow metadata DB

```bash
make airflow_init
```

## 4) Start Airflow services (recommended split mode)

Run scheduler and API server in separate terminals. Auto targets are recommended
because they select free ports automatically.

Terminal A:

```bash
make airflow_scheduler_auto
```

Terminal B:

```bash
make airflow_webserver_auto
```

Alternative manual port control:

```bash
make airflow_scheduler AIRFLOW_LOG_SERVER_PORT=8794
make airflow_webserver AIRFLOW_API_PORT=8081
```

## 5) Optional single-command local bootstrap

For quick local setup you can run:

```bash
make airflow_standalone
```

This mode bootstraps Airflow 3 and prints generated local credentials.

## 6) Trigger the anomaly DAG

Default trigger:

```bash
make airflow_unpause
make airflow_trigger MODEL=isolation_forest
```

Custom templated runtime parameters:

```bash
uv run airflow dags trigger anomaly_detection_orchestration \
  --conf '{"model_name":"lstm_ae","time_steps":30,"register_model":false}'
```

## 7) Monitor runs and artifacts

The DAG writes run-scoped outputs to:

- `data/airflow_runs/anomaly_detection_orchestration/<ts_nodash>/processed`
- `data/airflow_runs/anomaly_detection_orchestration/<ts_nodash>/models`
- `data/airflow_runs/anomaly_detection_orchestration/<ts_nodash>/predictions`

Useful checks:

```bash
make airflow_list_runs
```

For experiment tracking, open MLflow UI in another terminal:

```bash
make mlflow_ui
```

## 8) Common issues

- **`airflow command not found`**: run `make airflow_requirements`.
- **`address already in use`**: prefer `airflow_scheduler_auto` and
  `airflow_webserver_auto`, or pass custom ports.
- **No data found**: verify `data/raw` contains CSVs or run `make setup_dvc && make data_pull`.
