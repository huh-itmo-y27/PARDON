from pathlib import Path

import pandas as pd


def read_csv_in_folder(
    folder: str | Path,
    sep: str = ";",
    parse_dates: bool = True,
    add_source_column: bool = True,
) -> pd.DataFrame:
    folder = Path(folder)

    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    csv_files = sorted(folder.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in: {folder}")

    dfs = []
    for file_path in csv_files:
        df = pd.read_csv(
            file_path,
            sep=sep,
            parse_dates=["datetime"] if parse_dates else None,
        )

        if add_source_column:
            df["source_file"] = file_path.name

        dfs.append(df)

    result = pd.concat(dfs, ignore_index=True)
    return result
