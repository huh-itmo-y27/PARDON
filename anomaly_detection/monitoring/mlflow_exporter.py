from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import time

from loguru import logger
from prometheus_client import Gauge, start_http_server
import typer

from anomaly_detection.config import (
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_INFERENCE_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    MODELS_DIR,
    MONITORING_EXPORTER_PORT,
)

app = typer.Typer()


TRAIN_METRICS = [
    "val_precision",
    "val_recall",
    "val_f1",
    "val_cp_precision",
    "val_cp_recall",
    "val_cp_f1",
    "val_nab_standard",
    "val_nab_low_fp",
    "val_nab_low_fn",
    "train_data_drift_score",
    "train_target_drift_score",
    "train_concept_drift_proxy_score",
    "train_duration_seconds",
]

INFER_METRICS = [
    "anomaly_rate",
    "avg_score",
    "infer_data_drift_score",
    "infer_target_drift_score",
    "infer_concept_drift_proxy_score",
    "infer_duration_seconds",
]


def _get_runs(client, experiment_name: str, max_results: int = 100):
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        return []
    return client.search_runs(
        experiment_ids=[experiment.experiment_id],
        max_results=max_results,
        order_by=["attributes.start_time DESC"],
    )


def _series_for_metric(runs, metric_key: str) -> list[float]:
    values: list[float] = []
    for run in runs:
        value = run.data.metrics.get(metric_key)
        if value is not None:
            values.append(float(value))
    return values


def _group_runs_by_model_dataset(runs):
    grouped = defaultdict(list)
    for run in runs:
        params = run.data.params
        model_name = params.get("model_name", "unknown")
        dataset_scenario = params.get("dataset_scenario", "unknown")
        grouped[(model_name, dataset_scenario)].append(run)
    return grouped


def _safe_float(value) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@app.command()
def main(
    tracking_uri: str = MLFLOW_TRACKING_URI,
    train_experiment_name: str = MLFLOW_EXPERIMENT_NAME,
    inference_experiment_name: str = MLFLOW_INFERENCE_EXPERIMENT_NAME,
    port: int = MONITORING_EXPORTER_PORT,
    scrape_interval_seconds: int = 30,
    models_dir: Path = MODELS_DIR,
) -> None:
    try:
        import mlflow
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("mlflow is required for mlflow_exporter.") from exc

    mlflow.set_tracking_uri(tracking_uri)
    client = mlflow.tracking.MlflowClient()

    train_metric_value = Gauge(
        "mlflow_train_metric_value",
        "Train metric aggregates with labels.",
        ["model_name", "dataset_scenario", "metric", "aggregation"],
    )
    train_runs_total = Gauge(
        "mlflow_train_runs_total",
        "Count of train runs in experiment per model/dataset.",
        ["model_name", "dataset_scenario"],
    )
    infer_metric_value = Gauge(
        "mlflow_infer_metric_value",
        "Inference metric aggregates with labels.",
        ["model_name", "dataset_scenario", "metric", "aggregation"],
    )
    infer_runs_total = Gauge(
        "mlflow_infer_runs_total",
        "Count of inference runs in experiment per model/dataset.",
        ["model_name", "dataset_scenario"],
    )
    drift_reference_row_count = Gauge(
        "drift_artifact_reference_row_count",
        "Row count from drift_reference.json.",
        ["model_name", "dataset_scenario"],
    )
    drift_reference_label_rate = Gauge(
        "drift_artifact_reference_label_rate",
        "Label rates from drift_reference.json.",
        ["model_name", "dataset_scenario", "label"],
    )
    drift_reference_feature_stat = Gauge(
        "drift_artifact_reference_feature_stat",
        "Feature reference stats from drift_reference.json.",
        ["model_name", "dataset_scenario", "feature", "stat"],
    )
    drift_report_feature_metric = Gauge(
        "drift_artifact_feature_metric",
        "Feature metrics from drift_report.json.",
        ["model_name", "dataset_scenario", "feature", "metric"],
    )
    drift_report_aggregate_metric = Gauge(
        "drift_artifact_aggregate_metric",
        "Aggregate drift metrics from drift_report.json.",
        ["model_name", "dataset_scenario", "metric"],
    )
    start_http_server(port)
    logger.info("MLflow exporter started on port {}", port)

    while True:
        train_runs = _get_runs(client, train_experiment_name)
        grouped_train_runs = _group_runs_by_model_dataset(train_runs)
        for (model_name, dataset_scenario), runs in grouped_train_runs.items():
            train_runs_total.labels(
                model_name=model_name, dataset_scenario=dataset_scenario
            ).set(float(len(runs)))
            for metric in TRAIN_METRICS:
                values = _series_for_metric(runs, metric)
                latest = values[0] if values else 0.0
                previous = values[1:] if len(values) > 1 else []
                all_mean = sum(values) / len(values) if values else 0.0
                prev_mean = (
                    sum(previous) / len(previous) if previous else 0.0
                )
                rolling = sum(values[:5]) / len(values[:5]) if values else 0.0
                best = max(values) if values else 0.0
                common = {
                    "model_name": model_name,
                    "dataset_scenario": dataset_scenario,
                    "metric": metric,
                }
                train_metric_value.labels(
                    **common, aggregation="latest"
                ).set(latest)
                train_metric_value.labels(
                    **common, aggregation="previous_mean"
                ).set(prev_mean)
                train_metric_value.labels(
                    **common, aggregation="rolling_mean_5"
                ).set(rolling)
                train_metric_value.labels(
                    **common, aggregation="all_mean"
                ).set(all_mean)
                train_metric_value.labels(
                    **common, aggregation="best"
                ).set(best)
                train_metric_value.labels(
                    **common, aggregation="delta_vs_previous_mean"
                ).set(latest - prev_mean)

        infer_runs = _get_runs(client, inference_experiment_name)
        grouped_infer_runs = _group_runs_by_model_dataset(infer_runs)
        for (model_name, dataset_scenario), runs in grouped_infer_runs.items():
            infer_runs_total.labels(
                model_name=model_name, dataset_scenario=dataset_scenario
            ).set(float(len(runs)))
            for metric in INFER_METRICS:
                values = _series_for_metric(runs, metric)
                latest = values[0] if values else 0.0
                previous = values[1:] if len(values) > 1 else []
                all_mean = sum(values) / len(values) if values else 0.0
                prev_mean = (
                    sum(previous) / len(previous) if previous else 0.0
                )
                rolling = sum(values[:5]) / len(values[:5]) if values else 0.0
                best = max(values) if values else 0.0
                common = {
                    "model_name": model_name,
                    "dataset_scenario": dataset_scenario,
                    "metric": metric,
                }
                infer_metric_value.labels(
                    **common, aggregation="latest"
                ).set(latest)
                infer_metric_value.labels(
                    **common, aggregation="previous_mean"
                ).set(prev_mean)
                infer_metric_value.labels(
                    **common, aggregation="rolling_mean_5"
                ).set(rolling)
                infer_metric_value.labels(
                    **common, aggregation="all_mean"
                ).set(all_mean)
                infer_metric_value.labels(
                    **common, aggregation="best"
                ).set(best)
                infer_metric_value.labels(
                    **common, aggregation="delta_vs_previous_mean"
                ).set(latest - prev_mean)

        for model_path in sorted(models_dir.glob("*")):
            if not model_path.is_dir():
                continue
            model_name = model_path.name
            reference_path = model_path / "drift_reference.json"
            report_path = model_path / "drift_report.json"
            metadata_path = model_path / "train_metadata.json"
            if not reference_path.exists():
                continue

            dataset_scenario = "unknown"
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text("utf-8"))
                    dataset_scenario = str(
                        metadata.get("dataset_scenario", "unknown")
                    )
                except Exception:
                    dataset_scenario = "unknown"

            reference = json.loads(reference_path.read_text("utf-8"))
            drift_reference_row_count.labels(
                model_name=model_name, dataset_scenario=dataset_scenario
            ).set(_safe_float(reference.get("row_count", 0)))

            label_rates = reference.get("label_rates", {})
            for label_name, rate in label_rates.items():
                drift_reference_label_rate.labels(
                    model_name=model_name,
                    dataset_scenario=dataset_scenario,
                    label=str(label_name),
                ).set(_safe_float(rate))

            for feature, feature_stats in reference.get("feature_profile", {}).items():
                for stat_name in ("mean", "std", "p05", "p50", "p95", "min", "max"):
                    if stat_name in feature_stats:
                        drift_reference_feature_stat.labels(
                            model_name=model_name,
                            dataset_scenario=dataset_scenario,
                            feature=str(feature),
                            stat=stat_name,
                        ).set(_safe_float(feature_stats[stat_name]))

            if report_path.exists():
                report = json.loads(report_path.read_text("utf-8"))
                data_drift = report.get("data_drift", {})
                target_drift = report.get("target_drift", {})
                concept_drift = report.get("concept_drift_proxy", {})
                aggregate_values = {
                    "data_drift_score": data_drift.get("data_drift_score", 0.0),
                    "data_drift_ks_score": data_drift.get("data_drift_ks_score", 0.0),
                    "drifted_feature_count": data_drift.get(
                        "drifted_feature_count", 0
                    ),
                    "target_drift_score": target_drift.get(
                        "target_drift_score", 0.0
                    ),
                    "concept_drift_proxy_score": concept_drift.get(
                        "concept_drift_proxy_score", 0.0
                    ),
                }
                for metric_name, metric_value in aggregate_values.items():
                    drift_report_aggregate_metric.labels(
                        model_name=model_name,
                        dataset_scenario=dataset_scenario,
                        metric=metric_name,
                    ).set(_safe_float(metric_value))

                for feature, feature_metrics in data_drift.get(
                    "feature_stats", {}
                ).items():
                    for metric_name in (
                        "psi",
                        "outside_reference_band_rate",
                        "mean_shift_z",
                        "drift_detected",
                    ):
                        if metric_name in feature_metrics:
                            drift_report_feature_metric.labels(
                                model_name=model_name,
                                dataset_scenario=dataset_scenario,
                                feature=str(feature),
                                metric=metric_name,
                            ).set(_safe_float(feature_metrics[metric_name]))

        time.sleep(scrape_interval_seconds)


if __name__ == "__main__":
    app()
