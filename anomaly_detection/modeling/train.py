from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import typer
from loguru import logger
from sklearn.metrics import f1_score, precision_score, recall_score

from anomaly_detection.config import (
    DEFAULT_MODEL_NAME,
    DEFAULT_THRESHOLD_QUANTILE,
    DEFAULT_TIME_STEPS,
    LABEL_COL,
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_REGISTERED_MODEL_PREFIX,
    MLFLOW_TRACKING_URI,
    MODELS_DIR,
    PROCESSED_DATA_DIR,
    RANDOM_SEED,
)
from anomaly_detection.modeling.chp_score import chp_score
from anomaly_detection.modeling.models import (
    build_model,
)

app = typer.Typer()


def load_splits(processed_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_df = pd.read_csv(processed_dir / "train_features.csv")
    val_df = pd.read_csv(processed_dir / "val_features.csv")
    return train_df, val_df


def infer_feature_columns(df: pd.DataFrame) -> list[str]:
    excluded = {"datetime", "source_id", "anomaly", "changepoint"}
    return [col for col in df.columns if col not in excluded]


def compute_classification_metrics(
    y_true: np.ndarray, y_pred: np.ndarray
) -> dict[str, float]:
    return {
        "precision": float(
            precision_score(y_true, y_pred, zero_division=0)
        ),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def changepoint_flags(flags: np.ndarray) -> np.ndarray:
    cp = np.zeros_like(flags)
    cp[1:] = np.abs(np.diff(flags))
    return cp


def compute_nab_metrics(
    cp_true: np.ndarray, cp_pred: np.ndarray, datetime_series: pd.Series
) -> dict[str, float]:
    index = pd.to_datetime(datetime_series, errors="coerce")
    if index.isna().any():
        raise ValueError("Invalid datetime values for NAB calculation")

    y_true_cp = pd.Series(cp_true.astype(int), index=index)
    y_pred_cp = pd.Series(cp_pred.astype(int), index=index)
    results = chp_score(
        y_true_cp,
        y_pred_cp,
        metric="nab",
        window_width="60s",
        anomaly_window_destination="righter",
        verbose=False,
    )
    return {
        "standard": float(results.get("Standard", 0.0)),
        "low_fp": float(results.get("LowFP", 0.0)),
        "low_fn": float(results.get("LowFN", 0.0)),
    }


def resolve_run_name(
    run_name: str | None,
    model_name: str,
    *,
    seed: int,
    threshold_quantile: float,
    contamination: float,
    n_estimators: int,
    time_steps: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
) -> str:
    if run_name:
        return run_name
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if model_name == "isolation_forest":
        hp = (
            f"seed={seed}_cont={contamination}_"
            f"nest={n_estimators}_q={threshold_quantile}"
        )
    else:
        hp = (
            f"seed={seed}_ts={time_steps}_ep={epochs}_bs={batch_size}_"
            f"lr={learning_rate}_q={threshold_quantile}"
        )
    return f"{model_name}__{ts}__{hp}"


@app.command()
def main(
    model_name: str = DEFAULT_MODEL_NAME,
    processed_dir: Path = PROCESSED_DATA_DIR,
    output_dir: Path = MODELS_DIR,
    run_name: str | None = None,
    experiment_name: str = MLFLOW_EXPERIMENT_NAME,
    tracking_uri: str = MLFLOW_TRACKING_URI,
    register_model: bool = True,
    log_to_mlflow: bool = True,
    threshold_quantile: float = DEFAULT_THRESHOLD_QUANTILE,
    time_steps: int = DEFAULT_TIME_STEPS,
    seed: int = RANDOM_SEED,
    contamination: float = 0.005,
    n_estimators: int = 200,
    epochs: int = 20,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    verbose: int = 0,
) -> None:
    np.random.seed(seed)
    train_df, val_df = load_splits(processed_dir)
    feature_cols = infer_feature_columns(train_df)

    x_train = train_df[feature_cols].to_numpy(dtype=float)
    x_val = val_df[feature_cols].to_numpy(dtype=float)
    y_val = val_df[LABEL_COL].to_numpy(dtype=int)
    cp_val = val_df["changepoint"].to_numpy(dtype=int)

    model = build_model(
        model_name,
        seed=seed,
        contamination=contamination,
        n_estimators=n_estimators,
        time_steps=time_steps,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        verbose=verbose,
    )
    resolved_run_name = resolve_run_name(
        run_name=run_name,
        model_name=model_name,
        seed=seed,
        threshold_quantile=threshold_quantile,
        contamination=contamination,
        n_estimators=n_estimators,
        time_steps=time_steps,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
    )

    model.fit_points(x_train)
    train_scores = model.score_points(x_train)
    val_scores = model.score_points(x_val)

    threshold = float(np.quantile(train_scores, threshold_quantile))
    val_pred = (val_scores > threshold).astype(int)
    point_metrics = compute_classification_metrics(y_val, val_pred)
    cp_pred = changepoint_flags(val_pred)
    cp_metrics = compute_classification_metrics(cp_val, cp_pred)
    nab_metrics: dict[str, float] = {}
    try:
        nab_metrics = compute_nab_metrics(
            cp_true=cp_val,
            cp_pred=cp_pred,
            datetime_series=val_df["datetime"],
        )
    except Exception as exc:
        logger.warning("NAB metrics were not computed: {}", exc)

    model_dir = output_dir / model_name
    model.save(model_dir)
    train_meta = {
        "model_name": model_name,
        "feature_columns": feature_cols,
        "threshold": threshold,
        "threshold_quantile": threshold_quantile,
        "time_steps": time_steps,
        "seed": seed,
        "metrics_point": point_metrics,
        "metrics_changepoint": cp_metrics,
        "metrics_nab": nab_metrics,
    }
    (model_dir / "train_metadata.json").write_text(
        json.dumps(train_meta, indent=2),
        encoding="utf-8",
    )

    if log_to_mlflow:
        try:
            import mlflow
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "mlflow is required for log_to_mlflow=True. "
                "Install dependencies or pass --log-to-mlflow False."
            ) from exc

        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=resolved_run_name):
            mlflow.log_params(
                {
                    "model_name": model_name,
                    "time_steps": time_steps,
                    "threshold_quantile": threshold_quantile,
                    "seed": seed,
                    "contamination": contamination,
                    "n_estimators": n_estimators,
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "learning_rate": learning_rate,
                }
            )
            metrics_payload = {
                "val_precision": point_metrics["precision"],
                "val_recall": point_metrics["recall"],
                "val_f1": point_metrics["f1"],
                "val_cp_precision": cp_metrics["precision"],
                "val_cp_recall": cp_metrics["recall"],
                "val_cp_f1": cp_metrics["f1"],
                "threshold": threshold,
            }
            if nab_metrics:
                metrics_payload.update(
                    {
                        "val_nab_standard": nab_metrics["standard"],
                        "val_nab_low_fp": nab_metrics["low_fp"],
                        "val_nab_low_fn": nab_metrics["low_fn"],
                    }
                )
            mlflow.log_metrics(metrics_payload)
            mlflow.log_artifact(str(model_dir / "train_metadata.json"))

            model.mlflow_log_model(model_artifact_name="model")

            if register_model:
                model_uri = f"runs:/{mlflow.active_run().info.run_id}/model"
                reg_name = f"{MLFLOW_REGISTERED_MODEL_PREFIX}_{model_name}"
                try:
                    result = mlflow.register_model(
                        model_uri=model_uri, name=reg_name
                    )
                    client = mlflow.tracking.MlflowClient()
                    client.set_registered_model_alias(
                        name=reg_name,
                        alias="champion",
                        version=result.version,
                    )
                    mlflow.log_param("registered_model_name", reg_name)
                    mlflow.log_param(
                        "registered_model_version", result.version
                    )
                    mlflow.log_param("registered_model_alias", "champion")
                except Exception as exc:  # pragma: no cover
                    logger.warning(
                        "Model registration skipped due to backend limitation: {}",
                        exc,
                    )

    logger.success(
        "Training complete for {}. Val F1={:.4f}, threshold={:.6f}",
        model_name,
        point_metrics["f1"],
        threshold,
    )


if __name__ == "__main__":
    app()
