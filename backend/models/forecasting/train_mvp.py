"""
backend/models/forecasting/train_mvp.py

Phase 2 (MVP) training script — see ML Model Specification, Section 6.9.
Trains a SINGLE point-estimate (median-only) LightGBM model for the 24h
horizon, on the manually-selected representative stations. This is
deliberately simpler than the depth-pass quantile model in quantile_lgbm.py —
the goal here is a working end-to-end vertical slice, not final accuracy.

Run directly:  python -m backend.models.forecasting.train_mvp --data path/to/history.csv
"""

import argparse
from datetime import datetime, timezone

import lightgbm as lgb
import pandas as pd

from backend.models import registry
from backend.models.forecasting.ablation import run_ablation
from backend.models.forecasting.features import (
    FEATURE_LIST_VERSION,
    make_training_examples,
)

HORIZON_HOURS_MVP = 24

# Manually-selected representative stations for the MVP, per Section 6.9.1
# of the ML Model Specification. Update station_id values to match your
# actual ingested CPCB/OpenAQ station identifiers before running against
# real data.
REPRESENTATIVE_STATIONS = {
    "traffic_dominant": "station_ito_delhi",
    "industrial": "station_wazirpur_delhi",
    "stubble_transport_exposed": "station_rohini_delhi",
    "general_coverage_1": "station_rk_puram_delhi",
    "general_coverage_2": "station_anand_vihar_delhi",
}


def time_based_split(
    X: pd.DataFrame, y: pd.Series, meta: pd.DataFrame, val_frac=0.2, test_frac=0.2
):
    """
    Strict time-based split — never shuffle. See ML Model Specification,
    Section 4.3. Sorts by timestamp, then slices chronologically.
    """
    order = meta["timestamp"].argsort()
    X, y, meta = (
        X.iloc[order].reset_index(drop=True),
        y.iloc[order].reset_index(drop=True),
        meta.iloc[order].reset_index(drop=True),
    )

    n = len(X)
    test_start = int(n * (1 - test_frac))
    val_start = int(test_start * (1 - val_frac))

    return {
        "train": (X.iloc[:val_start], y.iloc[:val_start], meta.iloc[:val_start]),
        "val": (
            X.iloc[val_start:test_start],
            y.iloc[val_start:test_start],
            meta.iloc[val_start:test_start],
        ),
        "test": (X.iloc[test_start:], y.iloc[test_start:], meta.iloc[test_start:]),
    }


def train(raw_df: pd.DataFrame, horizon_hours: int = HORIZON_HOURS_MVP) -> dict:
    """
    Trains the MVP point-estimate model and returns a dict with the trained
    booster, the ablation report, and metadata — the caller (main()) is
    responsible for registering it.
    """
    X, y, meta = make_training_examples(raw_df, horizon_hours=horizon_hours)
    splits = time_based_split(X, y, meta)
    X_train, y_train, _ = splits["train"]
    X_val, y_val, _ = splits["val"]
    X_test, y_test, meta_test = splits["test"]

    train_set = lgb.Dataset(X_train, label=y_train)
    val_set = lgb.Dataset(X_val, label=y_val, reference=train_set)

    params = {
        "objective": "regression",
        "metric": "rmse",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "min_child_samples": 20,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "verbose": -1,
    }

    booster = lgb.train(
        params,
        train_set,
        num_boost_round=300,
        valid_sets=[val_set],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
    )

    y_pred_test = booster.predict(X_test, num_iteration=booster.best_iteration)

    # Baseline inputs: aqi_lag_1h stands in for "AQI at prediction time" (persistence),
    # aqi_rolling_mean_24h stands in for the moving-average baseline.
    ablation_report = run_ablation(
        y_true=y_test.values,
        y_pred_median=y_pred_test,
        aqi_at_prediction_time=X_test["aqi_lag_1h"].values,
        rolling_mean_24h_at_prediction_time=X_test["aqi_rolling_mean_24h"].values,
    )

    return {
        "booster": booster,
        "ablation_report": ablation_report,
        "n_train": len(X_train),
        "n_val": len(X_val),
        "n_test": len(X_test),
        "horizon_hours": horizon_hours,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Train the MVP forecasting model (Phase 2)."
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Path to a CSV of raw hourly station history matching the schema in features.py",
    )
    parser.add_argument(
        "--dataset-snapshot",
        default="unspecified",
        help="Label identifying which data snapshot this was trained on",
    )
    args = parser.parse_args()

    raw_df = pd.read_csv(args.data, parse_dates=["timestamp"])
    if raw_df["timestamp"].dt.tz is None:
        raw_df["timestamp"] = raw_df["timestamp"].dt.tz_localize("UTC")

    result = train(raw_df)
    booster = result["booster"]
    report = result["ablation_report"]

    version_id = f"v_mvp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    model_bytes = booster.model_to_string().encode("utf-8")

    metadata = {
        "version": version_id,
        "trained_on": datetime.now(timezone.utc).isoformat(),
        "dataset_snapshot": args.dataset_snapshot,
        "feature_list_version": FEATURE_LIST_VERSION,
        "horizon_hours": result["horizon_hours"],
        "quantiles": ["q50"],  # MVP is point-estimate only — inference.py handles this
        "n_train": result["n_train"],
        "n_val": result["n_val"],
        "n_test": result["n_test"],
        **report.to_dict(),
    }

    version_dir = registry.save_version(
        component="forecasting",
        version_id=version_id,
        model_files={"model_q50.txt": model_bytes},
        metadata=metadata,
    )

    print(f"MVP model registered at: {version_dir}")
    print(
        report.to_markdown(
            model_version=version_id, horizon_hours=result["horizon_hours"]
        )
    )


if __name__ == "__main__":
    main()
