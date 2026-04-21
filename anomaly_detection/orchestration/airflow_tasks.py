"""Callables for Airflow PythonOperator tasks (dataset → predict).

Nothing here runs DVC; prepare raw inputs before the DAG (e.g. Makefile DVC targets).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger


def _resolve_project_path(path_like: str | Path) -> Path:
    """Turn DAG-relative paths (e.g. data/raw) into absolute paths under the repo.

    Airflow tasks may run with a cwd that is not the project root; relative paths
    must not depend on where the scheduler was started.
    """
    from anomaly_detection.config import PROJ_ROOT

    p = Path(path_like)
    if p.is_absolute():
        return p.resolve()
    return (PROJ_ROOT / p).resolve()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _log_failure(task_name: str, context: dict[str, Any]) -> None:
    context_json = json.dumps(context, default=str, ensure_ascii=True)
    logger.exception(
        "[{}] task failed. Context: {}",
        task_name,
        context_json,
    )


def build_dataset(*, input_dir: str, output_dir: str) -> str:
    """Build train/val/test CSV splits from raw input data."""
    in_p = _resolve_project_path(input_dir)
    out_p = _resolve_project_path(output_dir)
    context = {"input_dir": str(in_p), "output_dir": str(out_p)}
    try:
        from anomaly_detection.dataset import main as dataset_main

        dataset_main(input_dir=in_p, output_dir=out_p)
        msg = f"Dataset prepared in {out_p}."
        logger.success(msg)
        return msg
    except Exception:
        _log_failure("build_dataset", context)
        raise


def build_features(*, input_dir: str, output_dir: str, time_steps: int) -> str:
    """Generate scaled feature splits and metadata artifacts."""
    in_p = _resolve_project_path(input_dir)
    out_p = _resolve_project_path(output_dir)
    context = {
        "input_dir": str(in_p),
        "output_dir": str(out_p),
        "time_steps": time_steps,
    }
    try:
        from anomaly_detection.features import main as features_main

        features_main(
            input_dir=in_p,
            output_dir=out_p,
            time_steps=int(time_steps),
        )
        msg = f"Features prepared in {out_p}."
        logger.success(msg)
        return msg
    except Exception:
        _log_failure("build_features", context)
        raise


def train_model(
    *,
    model_name: str,
    processed_dir: str,
    output_dir: str,
    run_name: str,
    experiment_name: str,
    tracking_uri: str,
    register_model: bool,
    log_to_mlflow: bool,
    threshold_quantile: float,
    time_steps: int,
    seed: int,
    contamination: float,
    n_estimators: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    verbose: int,
) -> str:
    """Train selected model and persist metadata/artifacts."""
    proc_p = _resolve_project_path(processed_dir)
    out_p = _resolve_project_path(output_dir)
    context = {
        "model_name": model_name,
        "processed_dir": str(proc_p),
        "output_dir": str(out_p),
        "run_name": run_name,
        "experiment_name": experiment_name,
        "tracking_uri": tracking_uri,
        "register_model": _as_bool(register_model),
        "log_to_mlflow": _as_bool(log_to_mlflow),
        "threshold_quantile": threshold_quantile,
        "time_steps": time_steps,
        "seed": seed,
        "contamination": contamination,
        "n_estimators": n_estimators,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "verbose": verbose,
    }
    try:
        from anomaly_detection.modeling.train import main as train_main

        train_main(
            model_name=model_name,
            processed_dir=proc_p,
            output_dir=out_p,
            run_name=run_name,
            experiment_name=experiment_name,
            tracking_uri=tracking_uri,
            register_model=_as_bool(register_model),
            log_to_mlflow=_as_bool(log_to_mlflow),
            threshold_quantile=float(threshold_quantile),
            time_steps=int(time_steps),
            seed=int(seed),
            contamination=float(contamination),
            n_estimators=int(n_estimators),
            epochs=int(epochs),
            batch_size=int(batch_size),
            learning_rate=float(learning_rate),
            verbose=int(verbose),
        )
        model_dir = str(out_p / model_name)
        logger.success("Training artifacts saved in {}", model_dir)
        return model_dir
    except Exception:
        _log_failure("train_model", context)
        raise


def log_training_summary(*, model_name: str, models_dir: str) -> dict[str, Any]:
    """Read and log training metadata for task-level observability."""
    models_p = _resolve_project_path(models_dir)
    context = {"model_name": model_name, "models_dir": str(models_p)}
    try:
        metadata_path = models_p / model_name / "train_metadata.json"
        payload = json.loads(metadata_path.read_text("utf-8"))
        logger.info(
            "Train summary model={} split={} f1={:.4f}",
            payload.get("model_name"),
            payload.get("evaluation_split"),
            payload.get("metrics_point", {}).get("f1", 0.0),
        )
        return payload
    except Exception:
        _log_failure("log_training_summary", context)
        raise


def predict_batch(
    *,
    model_name: str,
    processed_dir: str,
    output_path: str,
    models_dir: str,
    source: str,
    model_uri: str,
    tracking_uri: str,
    log_to_mlflow: bool,
) -> str:
    """Run inference and persist predictions for the test split."""
    proc_p = _resolve_project_path(processed_dir)
    out_p = _resolve_project_path(output_path)
    models_p = _resolve_project_path(models_dir)
    context = {
        "model_name": model_name,
        "processed_dir": str(proc_p),
        "output_path": str(out_p),
        "models_dir": str(models_p),
        "source": source,
        "model_uri": model_uri,
        "tracking_uri": tracking_uri,
        "log_to_mlflow": _as_bool(log_to_mlflow),
    }
    try:
        from anomaly_detection.modeling.predict import main as predict_main

        predict_main(
            model_name=model_name,
            processed_dir=proc_p,
            output_path=out_p,
            models_dir=models_p,
            source=source,
            model_uri=model_uri,
            tracking_uri=tracking_uri,
            log_to_mlflow=_as_bool(log_to_mlflow),
        )
        logger.success("Predictions generated at {}", out_p)
        return str(out_p)
    except Exception:
        _log_failure("predict_batch", context)
        raise


def log_inference_summary(*, output_path: str) -> dict[str, float]:
    """Log prediction volume and anomaly rate from generated CSV."""
    out_p = _resolve_project_path(output_path)
    context = {"output_path": str(out_p)}
    try:
        import pandas as pd

        out_df = pd.read_csv(out_p)
        metrics = {
            "rows": float(len(out_df)),
            "anomaly_rate": float(out_df["anomaly_flag"].mean()),
            "avg_score": float(out_df["score"].mean()),
        }
        logger.info(
            "Inference summary rows={} anomaly_rate={:.4f} avg_score={:.4f}",
            int(metrics["rows"]),
            metrics["anomaly_rate"],
            metrics["avg_score"],
        )
        return metrics
    except Exception:
        _log_failure("log_inference_summary", context)
        raise
