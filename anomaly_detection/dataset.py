import json
from pathlib import Path

import pandas as pd
import typer
from loguru import logger

from anomaly_detection.config import (
    CHANGEPOINT_COL,
    CSV_SEPARATOR,
    LABEL_COL,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    TIMESTAMP_COL,
    TRAIN_SIZE,
    VAL_SIZE,
)

app = typer.Typer()


def discover_csv_files(input_dir: Path) -> list[Path]:
    return sorted(input_dir.rglob("*.csv"))


def read_and_validate_csv(file_path: Path) -> pd.DataFrame:
    df = pd.read_csv(file_path, sep=CSV_SEPARATOR)
    required = {TIMESTAMP_COL, LABEL_COL, CHANGEPOINT_COL}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(
            f"{file_path} is missing required columns: {sorted(missing)}"
        )

    df[TIMESTAMP_COL] = pd.to_datetime(df[TIMESTAMP_COL], errors="coerce")
    if df[TIMESTAMP_COL].isna().any():
        raise ValueError(f"{file_path} has invalid timestamps")

    df = df.sort_values(TIMESTAMP_COL).reset_index(drop=True)
    df["source_id"] = file_path.stem
    return df


def split_single_series(
    df: pd.DataFrame, train_size: int, val_size: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n_rows = len(df)
    if n_rows < 10:
        raise ValueError(
            f"Series {df['source_id'].iloc[0]} is too short ({n_rows} rows)"
        )

    train_end = min(train_size, max(1, n_rows - 2))
    remaining = n_rows - train_end
    val_take = min(val_size, max(1, remaining // 2))
    val_end = train_end + val_take

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]

    if test_df.empty:
        test_df = val_df.tail(1).copy()
        val_df = val_df.iloc[:-1]
    if val_df.empty:
        val_df = train_df.tail(1).copy()
        train_df = train_df.iloc[:-1]

    return train_df, val_df, test_df


@app.command()
def main(
    input_dir: Path = RAW_DATA_DIR,
    output_dir: Path = PROCESSED_DATA_DIR,
    train_size: int = TRAIN_SIZE,
    val_size: int = VAL_SIZE,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = discover_csv_files(input_dir)
    if not files:
        raise FileNotFoundError(
            f"No CSV files found in {input_dir}. "
            "Put raw SKAB-like files into data/raw."
        )

    train_parts: list[pd.DataFrame] = []
    val_parts: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []
    manifest: dict[str, dict[str, int]] = {}

    for file_path in files:
        df = read_and_validate_csv(file_path)
        train_df, val_df, test_df = split_single_series(
            df=df, train_size=train_size, val_size=val_size
        )
        source = str(file_path.relative_to(input_dir))
        manifest[source] = {
            "rows_total": len(df),
            "rows_train": len(train_df),
            "rows_val": len(val_df),
            "rows_test": len(test_df),
        }
        train_parts.append(train_df)
        val_parts.append(val_df)
        test_parts.append(test_df)

    train_all = pd.concat(train_parts, ignore_index=True)
    val_all = pd.concat(val_parts, ignore_index=True)
    test_all = pd.concat(test_parts, ignore_index=True)

    train_all.to_csv(output_dir / "train.csv", index=False)
    val_all.to_csv(output_dir / "val.csv", index=False)
    test_all.to_csv(output_dir / "test.csv", index=False)
    with (output_dir / "dataset_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=True)

    logger.success(
        "Dataset prepared: train={}, val={}, test={} rows from {} files",
        len(train_all),
        len(val_all),
        len(test_all),
        len(files),
    )


if __name__ == "__main__":
    app()
