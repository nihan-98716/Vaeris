"""
Convenience wrapper for the Vaeris forecasting training pipeline.

The lower-level training entrypoints remain in train_mvp.py and
quantile_lgbm.py. This file keeps the documented README command stable.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from backend.models.forecasting.quantile_lgbm import main as quantile_main

DEFAULT_DATA_PATH = Path("data/delhi_flat_history_era5.csv")


def _load_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Training data not found at {path}. Pass --data with a CSV path."
        )
    df = pd.read_csv(path, parse_dates=["timestamp"])
    if df.empty:
        raise ValueError(f"Training data at {path} is empty.")
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
    return df


def prepare(data_path: Path) -> None:
    df = _load_history(data_path)
    required = {"timestamp", "station_id", "latitude", "longitude", "aqi"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Training data is missing required columns: {missing}")
    print(
        f"Prepared training snapshot: {len(df)} rows, "
        f"{df['station_id'].nunique()} stations, source={data_path}"
    )


def train(data_path: Path, horizons: tuple[int, ...], dataset_snapshot: str) -> None:
    _load_history(data_path)

    # Reuse the existing CLI registration behavior so model metadata and
    # calibration artifacts stay identical to direct quantile_lgbm.py runs.
    sys.argv = [
        "quantile_lgbm",
        "--data",
        str(data_path),
        "--horizons",
        ",".join(str(h) for h in horizons),
        "--dataset-snapshot",
        dataset_snapshot,
    ]
    quantile_main()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Vaeris forecasting pipeline.")
    parser.add_argument("--mode", choices=["prepare", "train"], required=True)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--horizons", default="24,48,72")
    parser.add_argument("--dataset-snapshot", default="delhi_flat_history_era5")
    args = parser.parse_args()

    horizons = tuple(int(h.strip()) for h in args.horizons.split(",") if h.strip())
    if args.mode == "prepare":
        prepare(args.data)
    else:
        train(args.data, horizons, args.dataset_snapshot)


if __name__ == "__main__":
    main()
