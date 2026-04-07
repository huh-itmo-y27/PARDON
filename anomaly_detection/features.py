import json
from pathlib import Path

import joblib
import pandas as pd
import typer
from loguru import logger
from sklearn.preprocessing import StandardScaler

from anomaly_detection.config import (
    CHANGEPOINT_COL,
    DEFAULT_TIME_STEPS,
    LABEL_COL,
    PROCESSED_DATA_DIR,
    TIMESTAMP_COL,
)

app = typer.Typer()


def infer_feature_columns(df: pd.DataFrame) -> list[str]:
    excluded = {TIMESTAMP_COL, "source_id", LABEL_COL, CHANGEPOINT_COL}
    return [col for col in df.columns if col not in excluded]


@app.command()
def main(
    input_dir: Path = PROCESSED_DATA_DIR,
    output_dir: Path = PROCESSED_DATA_DIR,
    time_steps: int = DEFAULT_TIME_STEPS,
) -> None:
    train_df = pd.read_csv(input_dir / "train.csv")
    val_df = pd.read_csv(input_dir / "val.csv")
    test_df = pd.read_csv(input_dir / "test.csv")

    feature_cols = infer_feature_columns(train_df)
    if not feature_cols:
        raise ValueError("No feature columns found in processed dataset")

    scaler = StandardScaler()
    scaler.fit(train_df[feature_cols])

    for name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        out = df.copy()
        out[feature_cols] = scaler.transform(df[feature_cols])
        out.to_csv(output_dir / f"{name}_features.csv", index=False)

    joblib.dump(scaler, output_dir / "scaler.pkl")
    metadata = {
        "feature_columns": feature_cols,
        "time_steps": time_steps,
        "label_column": LABEL_COL,
        "changepoint_column": CHANGEPOINT_COL,
        "timestamp_column": TIMESTAMP_COL,
    }
    with (output_dir / "features_metadata.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(metadata, f, indent=2, ensure_ascii=True)

    logger.success(
        "Features generated: {} columns, scaler saved to {}",
        len(feature_cols),
        output_dir / "scaler.pkl",
    )


if __name__ == "__main__":
    app()
