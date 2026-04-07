from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from anomaly_detection import dataset, features
from anomaly_detection.modeling import predict, train
from anomaly_detection.modeling.models import MODEL_REGISTRY


def _make_raw_csv(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    n = 220
    ts = pd.date_range("2024-01-01", periods=n, freq="min")
    x1 = np.sin(np.linspace(0, 8 * np.pi, n))
    x2 = np.cos(np.linspace(0, 8 * np.pi, n))
    anomaly = np.zeros(n, dtype=int)
    anomaly[170:180] = 1
    changepoint = np.zeros(n, dtype=int)
    changepoint[170] = 1
    df = pd.DataFrame(
        {
            "datetime": ts,
            "sensor_1": x1,
            "sensor_2": x2,
            "anomaly": anomaly,
            "changepoint": changepoint,
        }
    )
    df.to_csv(raw_dir / "series_1.csv", sep=";", index=False)


def test_end_to_end_smoke_all_models(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    models_dir = tmp_path / "models"
    mlruns_dir = tmp_path / "mlruns"

    _make_raw_csv(raw_dir)

    dataset.main(
        input_dir=raw_dir,
        output_dir=processed_dir,
        train_size=120,
        val_size=50,
    )
    features.main(
        input_dir=processed_dir,
        output_dir=processed_dir,
        time_steps=5,
    )

    model_names = list(MODEL_REGISTRY.keys())
    for model_name in model_names:
        train.main(
            model_name=model_name,
            processed_dir=processed_dir,
            output_dir=models_dir,
            register_model=False,
            log_to_mlflow=False,
            tracking_uri=f"file:{mlruns_dir}",
            threshold_quantile=0.95,
            time_steps=5,
            epochs=1,
            batch_size=8,
            verbose=0,
        )
        pred_path = processed_dir / f"predictions_{model_name}.csv"
        predict.main(
            model_name=model_name,
            processed_dir=processed_dir,
            output_path=pred_path,
            models_dir=models_dir,
            source="local",
            log_to_mlflow=False,
        )
        assert pred_path.exists()
        pred_df = pd.read_csv(pred_path)
        assert {"score", "threshold", "anomaly_flag"}.issubset(pred_df.columns)
