"""Anomaly pipeline DAG.

DVC (remote credentials, `dvc pull`, etc.) is intentionally not orchestrated here—run
`make setup_dvc` / `make data_pull` (or equivalent) before triggering runs so
`params.raw_input_dir` points at populated raw data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import Param

from anomaly_detection.orchestration.airflow_tasks import (
    build_dataset,
    build_features,
    log_inference_summary,
    log_training_summary,
    predict_batch,
    train_model,
)

RUN_STAMP = "{{ run_id | replace(':', '_') | replace('+', '_') }}"
RUN_ROOT = "{{ params.run_root }}/{{ dag.dag_id }}/" + RUN_STAMP
PROCESSED_DIR = RUN_ROOT + "/processed"
MODELS_DIR = RUN_ROOT + "/models"
PREDICTIONS_PATH = RUN_ROOT + "/predictions/{{ params.model_name }}_predictions.csv"


with DAG(
    dag_id="anomaly_detection_orchestration",
    description="Airflow orchestration for anomaly detection train/predict flow.",
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "mlops",
        "depends_on_past": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    render_template_as_native_obj=True,
    params={
        "run_root": Param("data/airflow_runs", type="string"),
        "raw_input_dir": Param("data/raw", type="string"),
        "model_name": Param(
            "isolation_forest",
            enum=["isolation_forest", "conv_ae", "lstm_ae"],
        ),
        "time_steps": Param(20, type="integer"),
        "seed": Param(42, type="integer"),
        "threshold_quantile": Param(0.995, type="number"),
        "experiment_name": Param("anomaly_detection", type="string"),
        "tracking_uri": Param("file:./mlruns", type="string"),
        "register_model": Param(True, type="boolean"),
        "log_to_mlflow": Param(True, type="boolean"),
        "contamination": Param(0.005, type="number"),
        "n_estimators": Param(200, type="integer"),
        "epochs": Param(20, type="integer"),
        "batch_size": Param(32, type="integer"),
        "learning_rate": Param(0.001, type="number"),
        "verbose": Param(0, type="integer"),
        "predict_source": Param("local", enum=["local", "mlflow"]),
        "predict_model_uri": Param("", type="string"),
    },
    doc_md="""
    # Anomaly Detection Orchestration DAG

    This DAG orchestrates the full anomaly-detection workflow with one task per
    logical stage:
    1. Dataset build
    2. Feature generation
    3. Model training
    4. Training summary logging
    5. Batch prediction
    6. Inference summary logging

    Task parameters are Jinja-templated via DAG `params`, and run outputs are
    isolated by execution timestamp under `params.run_root`.
    """,
) as dag:
    dataset = PythonOperator(
        task_id="build_dataset_splits",
        python_callable=build_dataset,
        op_kwargs={
            "input_dir": "{{ params.raw_input_dir }}",
            "output_dir": PROCESSED_DIR,
        },
        doc_md="""
        ### build_dataset_splits
        Validates raw CSV files and creates deterministic train/val/test splits.
        - Input: raw CSV directory
        - Output: `train.csv`, `val.csv`, `test.csv`, `dataset_manifest.json`
        """,
    )

    features = PythonOperator(
        task_id="build_scaled_features",
        python_callable=build_features,
        op_kwargs={
            "input_dir": PROCESSED_DIR,
            "output_dir": PROCESSED_DIR,
            "time_steps": "{{ params.time_steps }}",
        },
        doc_md="""
        ### build_scaled_features
        Fits scaler on train split and writes transformed feature datasets.
        - Input: canonical split CSVs
        - Output: `*_features.csv`, `scaler.pkl`, `features_metadata.json`
        """,
    )

    train = PythonOperator(
        task_id="train_model",
        python_callable=train_model,
        op_kwargs={
            "model_name": "{{ params.model_name }}",
            "processed_dir": PROCESSED_DIR,
            "output_dir": MODELS_DIR,
            "run_name": "airflow_{{ params.model_name }}_" + RUN_STAMP,
            "experiment_name": "{{ params.experiment_name }}",
            "tracking_uri": "{{ params.tracking_uri }}",
            "register_model": "{{ params.register_model }}",
            "log_to_mlflow": "{{ params.log_to_mlflow }}",
            "threshold_quantile": "{{ params.threshold_quantile }}",
            "time_steps": "{{ params.time_steps }}",
            "seed": "{{ params.seed }}",
            "contamination": "{{ params.contamination }}",
            "n_estimators": "{{ params.n_estimators }}",
            "epochs": "{{ params.epochs }}",
            "batch_size": "{{ params.batch_size }}",
            "learning_rate": "{{ params.learning_rate }}",
            "verbose": "{{ params.verbose }}",
        },
        doc_md="""
        ### train_model
        Trains selected model, computes anomaly/changepoint metrics, and writes
        model artifacts and `train_metadata.json`.
        Optional MLflow logging/registration is controlled by DAG params.
        """,
    )

    train_log = PythonOperator(
        task_id="log_training_summary",
        python_callable=log_training_summary,
        op_kwargs={
            "model_name": "{{ params.model_name }}",
            "models_dir": MODELS_DIR,
        },
        doc_md="""
        ### log_training_summary
        Reads model training metadata and logs key outcomes to task logs/XCom.
        """,
    )

    predict = PythonOperator(
        task_id="predict_batch",
        python_callable=predict_batch,
        op_kwargs={
            "model_name": "{{ params.model_name }}",
            "processed_dir": PROCESSED_DIR,
            "output_path": PREDICTIONS_PATH,
            "models_dir": MODELS_DIR,
            "source": "{{ params.predict_source }}",
            "model_uri": "{{ params.predict_model_uri }}",
            "tracking_uri": "{{ params.tracking_uri }}",
            "log_to_mlflow": "{{ params.log_to_mlflow }}",
        },
        doc_md="""
        ### predict_batch
        Runs inference on test features and writes a prediction CSV.
        Supports local model loading or MLflow URI loading.
        """,
    )

    inference_log = PythonOperator(
        task_id="log_inference_summary",
        python_callable=log_inference_summary,
        op_kwargs={"output_path": PREDICTIONS_PATH},
        doc_md="""
        ### log_inference_summary
        Logs row count, anomaly rate, and average score from prediction output.
        """,
    )

    dataset >> features >> train
    train >> train_log
    train >> predict >> inference_log
