from __future__ import annotations

import time

from loguru import logger
from prometheus_client import Gauge, start_http_server
import typer

from anomaly_detection.config import (
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_INFERENCE_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    MONITORING_EXPORTER_PORT,
)

app = typer.Typer()


def _read_latest_metric(client, experiment_name: str, metric_key: str) -> float:
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        return 0.0
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        max_results=1,
        order_by=["attributes.start_time DESC"],
    )
    if not runs:
        return 0.0
    return float(runs[0].data.metrics.get(metric_key, 0.0))


@app.command()
def main(
    tracking_uri: str = MLFLOW_TRACKING_URI,
    train_experiment_name: str = MLFLOW_EXPERIMENT_NAME,
    inference_experiment_name: str = MLFLOW_INFERENCE_EXPERIMENT_NAME,
    port: int = MONITORING_EXPORTER_PORT,
    scrape_interval_seconds: int = 30,
) -> None:
    try:
        import mlflow
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("mlflow is required for mlflow_exporter.") from exc

    mlflow.set_tracking_uri(tracking_uri)
    client = mlflow.tracking.MlflowClient()

    train_f1 = Gauge(
        "mlflow_latest_train_val_f1",
        "Latest validation F1 from training experiment.",
    )
    train_cp_f1 = Gauge(
        "mlflow_latest_train_val_cp_f1",
        "Latest validation changepoint F1 from training experiment.",
    )
    infer_anomaly_rate = Gauge(
        "mlflow_latest_infer_anomaly_rate",
        "Latest inference anomaly rate from inference experiment.",
    )
    infer_avg_score = Gauge(
        "mlflow_latest_infer_avg_score",
        "Latest inference average score from inference experiment.",
    )
    start_http_server(port)
    logger.info("MLflow exporter started on port {}", port)

    while True:
        train_f1.set(
            _read_latest_metric(client, train_experiment_name, "val_f1")
        )
        train_cp_f1.set(
            _read_latest_metric(client, train_experiment_name, "val_cp_f1")
        )
        infer_anomaly_rate.set(
            _read_latest_metric(
                client, inference_experiment_name, "anomaly_rate"
            )
        )
        infer_avg_score.set(
            _read_latest_metric(client, inference_experiment_name, "avg_score")
        )
        time.sleep(scrape_interval_seconds)


if __name__ == "__main__":
    app()
