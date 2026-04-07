from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
import pandas as pd
import typer

from anomaly_detection.config import (
    DEFAULT_MODEL_NAME,
    MLFLOW_TRACKING_URI,
    MODELS_DIR,
    PROCESSED_DATA_DIR,
)
from anomaly_detection.modeling.models import (
    get_model_class,
    load_model,
)

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

    model_dir = models_dir / model_name
    metadata = json.loads(
        (model_dir / "train_metadata.json").read_text("utf-8")
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

    if log_to_mlflow:
        try:
            import mlflow
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "mlflow is required for log_to_mlflow=True."
            ) from exc
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("anomaly_detection_inference")
        with mlflow.start_run(run_name=f"infer_{model_name}"):
            mlflow.log_params(
                {
                    "model_name": model_name,
                    "source": source,
                    "rows": len(out_df),
                }
            )
            mlflow.log_metric(
                "anomaly_rate", float(out_df["anomaly_flag"].mean())
            )
            mlflow.log_metric("avg_score", float(out_df["score"].mean()))
            mlflow.log_artifact(str(output_path))

    logger.success("Inference complete, saved predictions to {}", output_path)


if __name__ == "__main__":
    app()
