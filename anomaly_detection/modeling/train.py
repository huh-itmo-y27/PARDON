from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time

from loguru import logger
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
)
import typer

from anomaly_detection.config import (
    DEFAULT_MODEL_NAME,
    DEFAULT_THRESHOLD_QUANTILE,
    DEFAULT_TIME_STEPS,
    LABEL_COL,
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_REGISTERED_MODEL_PREFIX,
    MLFLOW_TRACKING_URI,
    MODELS_DIR,
    MONITORING_ENABLED,
    PROCESSED_DATA_DIR,
    PROMETHEUS_GROUPING_ENV,
    PROMETHEUS_GROUPING_SERVICE,
    PROMETHEUS_PUSHGATEWAY_URL,
    RANDOM_SEED,
)
from anomaly_detection.modeling.chp_score import chp_score
from anomaly_detection.modeling.models import (
    build_model,
)
from anomaly_detection.monitoring.drift import (
    build_reference_profile,
    compute_concept_proxy,
    compute_data_drift,
    compute_target_drift,
)
from anomaly_detection.monitoring.metrics import MonitoringEmitter

app = typer.Typer()


def load_splits(
    processed_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    train_df = pd.read_csv(processed_dir / "train_features.csv")
    val_df = pd.read_csv(processed_dir / "val_features.csv")
    test_df = pd.read_csv(processed_dir / "test_features.csv")
    if int(val_df[LABEL_COL].sum()) > 0:
        return train_df, val_df, "val"
    if int(test_df[LABEL_COL].sum()) > 0:
        return train_df, test_df, "test_fallback"
    return train_df, val_df, "val_no_positive"


def infer_feature_columns(df: pd.DataFrame) -> list[str]:
    excluded = {"datetime", "source_id", "anomaly", "changepoint"}
    return [col for col in df.columns if col not in excluded]


def compute_classification_metrics(
    y_true: np.ndarray, y_pred: np.ndarray
) -> dict[str, float]:
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
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
    if int(cp_true.sum()) == 0:
        raise ValueError(
            "No true changepoints in evaluation split, NAB is undefined"
        )
    index = pd.to_datetime(datetime_series, errors="coerce")
    if index.isna().any():
        raise ValueError("Invalid datetime values for NAB calculation")

    y_true_cp = pd.Series(cp_true.astype(int), index=index).sort_index()
    y_pred_cp = pd.Series(cp_pred.astype(int), index=index).sort_index()
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


def extract_events(
    labels: np.ndarray, min_event_size: int = 1
) -> list[tuple[int, int]]:
    events = []
    start = None
    for i, value in enumerate(labels):
        if value == 1 and start is None:
            start = i
        elif value == 0 and start is not None:
            if i - start >= min_event_size:
                events.append((start, i - 1))
            start = None
    if start is not None:
        if len(labels) - start >= min_event_size:
            events.append((start, len(labels) - 1))
    return events


def compute_event_recall(
    y_true: np.ndarray, y_pred: np.ndarray, min_event_size: int = 1
) -> dict[str, float]:
    true_events = extract_events(y_true, min_event_size=min_event_size)
    if len(true_events) == 0:
        return {"event_recall": np.nan, "detected_events": 0, "total_events": 0}
    detected = 0
    for start, end in true_events:
        if np.any(y_pred[start : end + 1] == 1):
            detected += 1
    return {
        "event_recall": float(detected / len(true_events)),
        "detected_events": int(detected),
        "total_events": int(len(true_events)),
    }


def compute_false_alarms_per_day(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    timestamps: pd.Series,
    merge_gap_minutes: float = 5.0,
) -> dict[str, float]:
    timestamps = pd.Series(pd.to_datetime(timestamps))
    fp_mask = (y_pred == 1) & (y_true == 0)
    fp_idx = np.where(fp_mask)[0]
    if len(fp_idx) == 0:
        return {"false_alarm_events": 0, "false_alarms_per_day": 0.0}
    num_events = 1
    for prev_idx, cur_idx in zip(fp_idx[:-1], fp_idx[1:]):
        delta_minutes = (
            timestamps.iloc[cur_idx] - timestamps.iloc[prev_idx]
        ).total_seconds() / 60.0
        if delta_minutes > merge_gap_minutes:
            num_events += 1
    normal_mask = y_true == 0
    if normal_mask.sum() == 0:
        return {
            "false_alarm_events": num_events,
            "false_alarms_per_day": np.nan,
        }
    normal_hours = normal_mask.sum() * (
        timestamps.diff().median().total_seconds() / 3600.0
    )
    if normal_hours <= 0:
        return {
            "false_alarm_events": num_events,
            "false_alarms_per_day": np.nan,
        }
    return {
        "false_alarm_events": int(num_events),
        "false_alarms_per_day": float(num_events * 24.0 / normal_hours),
    }


def compute_extended_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_scores: np.ndarray,
    timestamps: pd.Series | None = None,
) -> dict[str, float]:
    metrics = {}
    try:
        metrics["pr_auc"] = float(average_precision_score(y_true, y_scores))
    except Exception:
        metrics["pr_auc"] = np.nan
    metrics.update(compute_event_recall(y_true, y_pred))
    if timestamps is not None:
        metrics.update(compute_false_alarms_per_day(y_true, y_pred, timestamps))
    return metrics


def threshold_sweep(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    train_scores: np.ndarray,
    timestamps: pd.Series | None = None,
    quantiles: list[float] | None = None,
) -> dict:
    if quantiles is None:
        quantiles = [0.85, 0.90, 0.95, 0.98, 0.99]
    results = {
        "threshold": {},
        "precision": {},
        "recall": {},
        "f1": {},
        "f2": {},
        "event_recall": {},
        "false_alarms_per_day": {},
        "alert_rate": {},
    }
    for q in quantiles:
        threshold = float(np.quantile(train_scores, q))
        y_pred = (y_scores > threshold).astype(int)
        results["threshold"][q] = threshold
        results["precision"][q] = float(
            precision_score(y_true, y_pred, zero_division=0)
        )
        results["recall"][q] = float(
            recall_score(y_true, y_pred, zero_division=0)
        )
        results["f1"][q] = float(f1_score(y_true, y_pred, zero_division=0))
        results["f2"][q] = float(
            fbeta_score(y_true, y_pred, beta=2, zero_division=0)
        )
        results["alert_rate"][q] = float(y_pred.mean())
        event_metrics = compute_event_recall(y_true, y_pred)
        results["event_recall"][q] = event_metrics["event_recall"]
        if timestamps is not None:
            fp_metrics = compute_false_alarms_per_day(
                y_true, y_pred, timestamps
            )
            results["false_alarms_per_day"][q] = fp_metrics[
                "false_alarms_per_day"
            ]
    try:
        results["pr_auc"] = float(average_precision_score(y_true, y_scores))
    except Exception:
        results["pr_auc"] = np.nan
    return results


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
    dataset_scenario: str = "unknown",
) -> None:
    run_started_at = time.perf_counter()
    np.random.seed(seed)
    train_df, eval_df, eval_split_name = load_splits(processed_dir)
    feature_cols = infer_feature_columns(train_df)
    emitter = MonitoringEmitter(
        job_name="anomaly_train",
        enabled=MONITORING_ENABLED,
        pushgateway_url=PROMETHEUS_PUSHGATEWAY_URL,
        grouping_key={
            "environment": PROMETHEUS_GROUPING_ENV,
            "service": PROMETHEUS_GROUPING_SERVICE,
            "model_name": model_name,
            "dataset_scenario": dataset_scenario,
        },
    )

    x_train = train_df[feature_cols].to_numpy(dtype=float)
    x_eval = eval_df[feature_cols].to_numpy(dtype=float)
    y_eval = eval_df[LABEL_COL].to_numpy(dtype=int)
    cp_eval = eval_df["changepoint"].to_numpy(dtype=int)

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
    eval_scores = model.score_points(x_eval)

    threshold = float(np.quantile(train_scores, threshold_quantile))
    eval_pred = (eval_scores > threshold).astype(int)
    point_metrics = compute_classification_metrics(y_eval, eval_pred)
    cp_pred = changepoint_flags(eval_pred)
    cp_metrics = compute_classification_metrics(cp_eval, cp_pred)
    nab_metrics: dict[str, float] = {}
    try:
        nab_metrics = compute_nab_metrics(
            cp_true=cp_eval,
            cp_pred=cp_pred,
            datetime_series=eval_df["datetime"],
        )
    except Exception as exc:
        logger.warning("NAB metrics were not computed: {}", exc)

    event_metrics = compute_event_recall(y_eval, eval_pred)
    fp_metrics = compute_false_alarms_per_day(
        y_eval, eval_pred, eval_df["datetime"]
    )
    extended_metrics = compute_extended_metrics(
        y_eval, eval_pred, eval_scores, eval_df["datetime"]
    )
    sweep_results = threshold_sweep(
        y_eval, eval_scores, train_scores, eval_df["datetime"]
    )

    model_dir = output_dir / model_name
    model.save(model_dir)
    label_cols = [LABEL_COL, "changepoint"]
    drift_reference = build_reference_profile(
        train_df, feature_cols, label_cols
    )
    data_drift = compute_data_drift(eval_df[feature_cols], drift_reference)
    target_drift = compute_target_drift(
        eval_df[label_cols], drift_reference["label_rates"]
    )
    concept_drift = compute_concept_proxy(
        current_metrics={
            "f1": point_metrics["f1"],
            "cp_f1": cp_metrics["f1"],
            "anomaly_rate": float(eval_pred.mean()),
        },
        baseline_metrics={
            "f1": point_metrics["f1"],
            "cp_f1": cp_metrics["f1"],
            "anomaly_rate": float(train_df[LABEL_COL].mean()),
        },
    )
    train_meta = {
        "model_name": model_name,
        "feature_columns": feature_cols,
        "threshold": threshold,
        "threshold_quantile": threshold_quantile,
        "time_steps": time_steps,
        "seed": seed,
        "evaluation_split": eval_split_name,
        "metrics_point": point_metrics,
        "metrics_changepoint": cp_metrics,
        "metrics_nab": nab_metrics,
        "metrics_event": event_metrics,
        "metrics_false_alarms": fp_metrics,
        "metrics_extended": extended_metrics,
        "metrics_threshold_sweep": {
            "pr_auc": sweep_results["pr_auc"],
            "quantiles": {
                q: {
                    "threshold": sweep_results["threshold"][q],
                    "precision": sweep_results["precision"][q],
                    "recall": sweep_results["recall"][q],
                    "f1": sweep_results["f1"][q],
                    "f2": sweep_results["f2"][q],
                    "event_recall": sweep_results["event_recall"][q],
                    "false_alarms_per_day": sweep_results[
                        "false_alarms_per_day"
                    ][q],
                    "alert_rate": sweep_results["alert_rate"][q],
                }
                for q in sweep_results["threshold"]
            },
        },
        "dataset_scenario": dataset_scenario,
        "drift_reference": drift_reference,
        "drift_eval": {
            "data_drift": data_drift,
            "target_drift": target_drift,
            "concept_drift_proxy": concept_drift,
        },
    }
    (model_dir / "train_metadata.json").write_text(
        json.dumps(train_meta, indent=2),
        encoding="utf-8",
    )
    (model_dir / "drift_reference.json").write_text(
        json.dumps(drift_reference, indent=2),
        encoding="utf-8",
    )
    drift_report = {
        "phase": "train_eval",
        "data_drift": data_drift,
        "target_drift": target_drift,
        "concept_drift_proxy": concept_drift,
    }
    (model_dir / "drift_report.json").write_text(
        json.dumps(drift_report, indent=2),
        encoding="utf-8",
    )

    emitter.gauge(
        "anomaly_pipeline_rows_total",
        "Processed rows in train job.",
        float(len(train_df) + len(eval_df)),
    )
    emitter.gauge(
        "anomaly_pipeline_anomaly_rate",
        "Observed anomaly rate in evaluation split.",
        float(eval_pred.mean()),
    )
    emitter.gauge(
        "anomaly_pipeline_val_f1", "Validation F1 score.", point_metrics["f1"]
    )
    emitter.gauge(
        "anomaly_pipeline_val_precision",
        "Validation precision score.",
        point_metrics["precision"],
    )
    emitter.gauge(
        "anomaly_pipeline_val_recall",
        "Validation recall score.",
        point_metrics["recall"],
    )
    emitter.gauge(
        "anomaly_pipeline_val_cp_f1",
        "Validation changepoint F1 score.",
        cp_metrics["f1"],
    )
    emitter.gauge(
        "anomaly_pipeline_val_cp_precision",
        "Validation changepoint precision score.",
        cp_metrics["precision"],
    )
    emitter.gauge(
        "anomaly_pipeline_val_cp_recall",
        "Validation changepoint recall score.",
        cp_metrics["recall"],
    )
    if nab_metrics:
        emitter.gauge(
            "anomaly_pipeline_val_nab_standard",
            "Validation NAB Standard score.",
            nab_metrics["standard"],
        )
        emitter.gauge(
            "anomaly_pipeline_val_nab_low_fp",
            "Validation NAB LowFP score.",
            nab_metrics["low_fp"],
        )
        emitter.gauge(
            "anomaly_pipeline_val_nab_low_fn",
            "Validation NAB LowFN score.",
            nab_metrics["low_fn"],
        )

    if not np.isnan(event_metrics["event_recall"]):
        emitter.gauge(
            "anomaly_pipeline_event_recall",
            "Event-based recall.",
            event_metrics["event_recall"],
        )
    emitter.gauge(
        "anomaly_pipeline_false_alarms_per_day",
        "False alarms per day.",
        fp_metrics["false_alarms_per_day"],
    )
    if not np.isnan(extended_metrics["pr_auc"]):
        emitter.gauge(
            "anomaly_pipeline_pr_auc",
            "PR AUC score.",
            extended_metrics["pr_auc"],
        )
    if not np.isnan(sweep_results["pr_auc"]):
        emitter.gauge(
            "anomaly_pipeline_sweep_pr_auc",
            "Threshold sweep PR AUC.",
            sweep_results["pr_auc"],
        )

    emitter.gauge(
        "anomaly_pipeline_data_drift_score",
        "Aggregate data drift score.",
        float(data_drift["data_drift_score"]),
    )
    emitter.gauge(
        "anomaly_pipeline_target_drift_score",
        "Aggregate target drift score.",
        float(target_drift["target_drift_score"]),
    )
    emitter.gauge(
        "anomaly_pipeline_concept_drift_score",
        "Concept drift proxy score.",
        float(concept_drift["concept_drift_proxy_score"]),
    )
    emitter.gauge("anomaly_pipeline_run_success", "Run success marker.", 1.0)
    emitter.observe_runtime()
    emitter.flush()
    train_duration_seconds = time.perf_counter() - run_started_at

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
                    "evaluation_split": eval_split_name,
                    "dataset_scenario": dataset_scenario,
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
                "train_duration_seconds": float(train_duration_seconds),
            }
            if nab_metrics:
                metrics_payload.update(
                    {
                        "val_nab_standard": nab_metrics["standard"],
                        "val_nab_low_fp": nab_metrics["low_fp"],
                        "val_nab_low_fn": nab_metrics["low_fn"],
                    }
                )
            if event_metrics is not None and not np.isnan(
                event_metrics.get("event_recall", np.nan)
            ):
                metrics_payload.update(
                    {
                        "event_recall": event_metrics["event_recall"],
                        "detected_events": float(
                            event_metrics["detected_events"]
                        ),
                        "total_events": float(event_metrics["total_events"]),
                    }
                )
            if fp_metrics is not None and not np.isnan(
                fp_metrics.get("false_alarms_per_day", np.nan)
            ):
                metrics_payload.update(
                    {
                        "false_alarm_events": float(
                            fp_metrics["false_alarm_events"]
                        ),
                        "false_alarms_per_day": fp_metrics[
                            "false_alarms_per_day"
                        ],
                    }
                )
            if extended_metrics is not None and not np.isnan(
                extended_metrics.get("pr_auc", np.nan)
            ):
                metrics_payload.update({"pr_auc": extended_metrics["pr_auc"]})
            if sweep_results is not None and not np.isnan(
                sweep_results.get("pr_auc", np.nan)
            ):
                metrics_payload.update(
                    {"sweep_pr_auc": sweep_results["pr_auc"]}
                )

            metrics_payload.update(
                {
                    "train_data_drift_score": float(
                        data_drift["data_drift_score"]
                    ),
                    "train_target_drift_score": float(
                        target_drift["target_drift_score"]
                    ),
                    "train_concept_drift_proxy_score": float(
                        concept_drift["concept_drift_proxy_score"]
                    ),
                }
            )
            mlflow.log_metrics(metrics_payload)
            mlflow.log_artifact(str(model_dir / "train_metadata.json"))
            mlflow.log_artifact(str(model_dir / "drift_reference.json"))
            mlflow.log_artifact(str(model_dir / "drift_report.json"))

            model_uri = model.mlflow_log_model(model_artifact_name="model")

            if register_model:
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
                    mlflow.log_param("registered_model_version", result.version)
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
