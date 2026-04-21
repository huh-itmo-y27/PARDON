from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from anomaly_detection import dataset, features
from anomaly_detection.modeling import predict, train
from anomaly_detection.modeling.models import (
    create_sequences,
    get_strategy,
    window_scores_to_point_scores,
)


def test_split_single_series_produces_non_empty_splits() -> None:
    n = 20
    df = pd.DataFrame(
        {
            "datetime": pd.date_range("2024-01-01", periods=n, freq="min"),
            "sensor": np.linspace(0.0, 1.0, n),
            "anomaly": np.zeros(n, dtype=int),
            "changepoint": np.zeros(n, dtype=int),
            "source_id": ["series_a"] * n,
        }
    )

    train_df, val_df, test_df = dataset.split_single_series(
        df, train_size=15, val_size=5
    )

    assert len(train_df) > 0
    assert len(val_df) > 0
    assert len(test_df) > 0
    assert len(train_df) + len(val_df) + len(test_df) == n


def test_read_and_validate_csv_adds_source_id(tmp_path: Path) -> None:
    csv_path = tmp_path / "series_1.csv"
    df = pd.DataFrame(
        {
            "datetime": ["2024-01-01 00:01:00", "2024-01-01 00:00:00"],
            "sensor": [2.0, 1.0],
            "anomaly": [0, 1],
            "changepoint": [0, 1],
        }
    )
    df.to_csv(csv_path, sep=";", index=False)

    out = dataset.read_and_validate_csv(csv_path)

    assert "source_id" in out.columns
    assert out["source_id"].nunique() == 1
    assert out["source_id"].iloc[0] == "series_1"
    assert out["datetime"].is_monotonic_increasing


def test_infer_feature_columns_excludes_service_columns() -> None:
    df = pd.DataFrame(
        {
            "datetime": ["2024-01-01"],
            "source_id": ["s1"],
            "anomaly": [0],
            "changepoint": [0],
            "sensor_a": [1.0],
            "sensor_b": [2.0],
        }
    )

    assert features.infer_feature_columns(df) == ["sensor_a", "sensor_b"]
    assert predict.infer_feature_columns(df) == ["sensor_a", "sensor_b"]
    assert train.infer_feature_columns(df) == ["sensor_a", "sensor_b"]


def test_compute_classification_metrics_basic_case() -> None:
    y_true = np.array([0, 1, 1, 0])
    y_pred = np.array([0, 1, 0, 0])

    metrics = train.compute_classification_metrics(y_true, y_pred)

    assert metrics["precision"] == pytest.approx(1.0)
    assert metrics["recall"] == pytest.approx(0.5)
    assert metrics["f1"] == pytest.approx(2.0 / 3.0)


def test_create_sequences_and_window_score_projection() -> None:
    x = np.arange(10, dtype=float).reshape(5, 2)
    seq = create_sequences(x, time_steps=3)
    scores = window_scores_to_point_scores(
        scores=np.array([1.0, 3.0, 5.0]), n_points=5, time_steps=3
    )

    assert seq.shape == (3, 3, 2)
    assert np.allclose(scores, np.array([1.0, 2.0, 3.0, 4.0, 5.0]))


def test_get_strategy_raises_for_unknown_model() -> None:
    with pytest.raises(ValueError, match="Unknown model_name"):
        get_strategy("unknown_model")
