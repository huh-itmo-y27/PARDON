from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
import pandas as pd
import typer

from anomaly_detection.config import (
    DEFAULT_MODEL_NAME,
    MLFLOW_INFERENCE_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    MODELS_DIR,
    MONITORING_ENABLED,
    PROCESSED_DATA_DIR,
    PROMETHEUS_GROUPING_ENV,
    PROMETHEUS_GROUPING_SERVICE,
    PROMETHEUS_PUSHGATEWAY_URL,
)
from anomaly_detection.modeling.models import (
    get_model_class,
    load_model,
)
from anomaly_detection.monitoring.drift import (
    compute_concept_proxy,
    compute_data_drift,
    compute_target_drift,
)
from anomaly_detection.monitoring.metrics import MonitoringEmitter

app = typer.Typer()


def infer_feature_columns(df: pd.DataFrame) -> list[str]:
    excluded = {"datetime", "source_id", "anomaly", "changepoint"}
    return [col for col in df.columns if col not in excluded]


@app.command()
def main(
    model_name: str = DEFAULT_MODEL_NAME,
    processed_dir: Path = PROCESSED_DATA_DIR,
    output_path: Path = PROCESSED_DATA_DIR / "predictions.csv",
    models_dir: Path = MODELS_DIR,
    source: str = "local",
    model_uri: str = "",
    tracking_uri: str = MLFLOW_TRACKING_URI,
    log_to_mlflow: bool = True,
) -> None:
    test_df = pd.read_csv(processed_dir / "test_features.csv")
    feature_cols = infer_feature_columns(test_df)
    x_test = test_df[feature_cols].to_numpy(dtype=float)
    emitter = MonitoringEmitter(
        job_name="anomaly_predict",
        enabled=MONITORING_ENABLED,
        pushgateway_url=PROMETHEUS_PUSHGATEWAY_URL,
        grouping_key={
            "environment": PROMETHEUS_GROUPING_ENV,
            "service": PROMETHEUS_GROUPING_SERVICE,
            "model_name": model_name,
        },
    )

    model_dir = models_dir / model_name
    metadata = json.loads(
        (model_dir / "train_metadata.json").read_text("utf-8")
    )
    drift_reference = metadata.get("drift_reference")
    if drift_reference is None:
        drift_reference_path = model_dir / "drift_reference.json"
        if drift_reference_path.exists():
            drift_reference = json.loads(
                drift_reference_path.read_text("utf-8")
            )
    threshold = float(metadata["threshold"])
    time_steps = int(metadata["time_steps"])
    model_cls = get_model_class(model_name)

    if source == "mlflow":
        try:
            import mlflow
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("mlflow is required for source=mlflow.") from exc
        mlflow.set_tracking_uri(tracking_uri)
        if not model_uri:
            raise ValueError("Pass --model-uri when source=mlflow")
        loaded = model_cls.mlflow_load_model(model_uri)
        scores = model_cls.score_points_with_mlflow_model(
            loaded_model=loaded, x_data=x_test, time_steps=time_steps
        )
    else:
        model = load_model(model_name, model_dir)
        scores = model.score_points(x_test)

    flags = (scores > threshold).astype(int)
    data_drift: dict[str, object] = {"data_drift_score": 0.0}
    target_drift: dict[str, object] = {"target_drift_score": 0.0}
    if drift_reference:
        data_drift = compute_data_drift(test_df[feature_cols], drift_reference)
        label_rates = drift_reference.get("label_rates", {})
        if label_rates and {"anomaly", "changepoint"}.issubset(test_df.columns):
            target_drift = compute_target_drift(
                test_df[["anomaly", "changepoint"]],
                label_rates,
            )
    concept_drift = compute_concept_proxy(
        current_metrics={"anomaly_rate": float(flags.mean())},
        baseline_metrics={
            "anomaly_rate": float(
                metadata.get("drift_reference", {})
                .get("label_rates", {})
                .get("anomaly", 0.0)
            )
        },
    )
    out_df = pd.DataFrame(
        {
            "datetime": test_df["datetime"],
            "source_id": test_df["source_id"],
            "score": scores,
            "threshold": threshold,
            "anomaly_flag": flags,
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)
    drift_report_path = output_path.parent / "drift_report.json"
    drift_report_path.write_text(
        json.dumps(
            {
                "phase": "inference",
                "data_drift": data_drift,
                "target_drift": target_drift,
                "concept_drift_proxy": concept_drift,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    emitter.gauge(
        "anomaly_pipeline_rows_total",
        "Processed rows in prediction job.",
        float(len(out_df)),
    )
    emitter.gauge(
        "anomaly_pipeline_anomaly_rate",
        "Anomaly rate in prediction output.",
        float(out_df["anomaly_flag"].mean()),
    )
    emitter.gauge(
        "anomaly_pipeline_avg_score",
        "Average anomaly score in prediction output.",
        float(out_df["score"].mean()),
    )
    emitter.gauge(
        "anomaly_pipeline_data_drift_score",
        "Aggregate data drift score.",
        float(data_drift.get("data_drift_score", 0.0)),
    )
    emitter.gauge(
        "anomaly_pipeline_target_drift_score",
        "Aggregate target drift score.",
        float(target_drift.get("target_drift_score", 0.0)),
    )
    emitter.gauge(
        "anomaly_pipeline_concept_drift_score",
        "Concept drift proxy score.",
        float(concept_drift["concept_drift_proxy_score"]),
    )
    emitter.gauge("anomaly_pipeline_run_success", "Run success marker.", 1.0)
    emitter.observe_runtime()
    emitter.flush()

    if log_to_mlflow:
        try:
            import mlflow
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "mlflow is required for log_to_mlflow=True."
            ) from exc
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(MLFLOW_INFERENCE_EXPERIMENT_NAME)
        with mlflow.start_run(run_name=f"infer_{model_name}"):
            mlflow.log_params(
                {
                    "model_name": model_name,
                    "source": source,
                    "rows": len(out_df),
                    "model_uri": model_uri,
                }
            )
            mlflow.log_metric(
                "anomaly_rate", float(out_df["anomaly_flag"].mean())
            )
            mlflow.log_metric("avg_score", float(out_df["score"].mean()))
            mlflow.log_metric(
                "infer_data_drift_score",
                float(data_drift.get("data_drift_score", 0.0)),
            )
            mlflow.log_metric(
                "infer_target_drift_score",
                float(target_drift.get("target_drift_score", 0.0)),
            )
            mlflow.log_metric(
                "infer_concept_drift_proxy_score",
                float(concept_drift["concept_drift_proxy_score"]),
            )
            mlflow.log_artifact(str(output_path))
            mlflow.log_artifact(str(drift_report_path))

    logger.success("Inference complete, saved predictions to {}", output_path)


if __name__ == "__main__":
    app()
