# pumps-anomaly-detection documentation

## Project overview

This project detects anomalies and changepoints in pump sensor time series with
multiple model pipelines:

- `isolation_forest`
- `conv_ae`
- `lstm_ae`

## Airflow-first orchestration

The pipeline is orchestrated by Airflow DAG
`anomaly_detection_orchestration` in `dags/anomaly_pipeline_dag.py`.

Each stage is an explicit task (DVC is **not** part of the DAG—use `make setup_dvc`
/ `make data_pull` before triggering a run if you need remote data):

1. `build_dataset_splits`
2. `build_scaled_features`
3. `train_model`
4. `log_training_summary`
5. `predict_batch`
6. `log_inference_summary`

## Templated runtime controls

The DAG uses Jinja-templated Airflow `params` for runtime control:

- model selection (`model_name`)
- MLflow settings (`tracking_uri`, `experiment_name`, `log_to_mlflow`, `register_model`)
- inference source (`predict_source`, `predict_model_uri`)
- run-safe outputs under `run_root/<dag_id>/<ts_nodash>/...`

See the getting started guide for concrete commands.


