"""
backend/models/forecasting/quantile_lgbm.py

Phase 6 (depth pass) training script — see ML Model Specification, Sections
6.4-6.8. Trains THREE LightGBM models (q10, q50, q90) sharing the same
feature set, for both the 24h and 48h "reliable" horizons plus the 72h
"experimental" horizon.

Run directly:  python -m backend.models.forecasting.quantile_lgbm --data path/to/history.csv --horizon 24
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
from backend.models.forecasting.train_mvp import time_based_split

QUANTILES = {"q10": 0.1, "q50": 0.5, "q90": 0.9}

BASE_PARAMS = {
    "objective": "quantile",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "min_child_samples": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "verbose": -1,
}


def train_quantile_models(raw_df: pd.DataFrame, horizon_hours: int) -> dict:
    X, y, meta = make_training_examples(raw_df, horizon_hours=horizon_hours)
    splits = time_based_split(X, y, meta)
    X_train, y_train, _ = splits["train"]
    X_val, y_val, _ = splits["val"]
    X_test, y_test, meta_test = splits["test"]

    boosters = {}
    for name, alpha in QUANTILES.items():
        params = dict(BASE_PARAMS, alpha=alpha, metric="quantile")
        train_set = lgb.Dataset(X_train, label=y_train)
        val_set = lgb.Dataset(X_val, label=y_val, reference=train_set)
        booster = lgb.train(
            params,
            train_set,
            num_boost_round=300,
            valid_sets=[val_set],
            callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
        )
        boosters[name] = booster

    y_pred_q10 = boosters["q10"].predict(
        X_test, num_iteration=boosters["q10"].best_iteration
    )
    y_pred_q50 = boosters["q50"].predict(
        X_test, num_iteration=boosters["q50"].best_iteration
    )
    y_pred_q90 = boosters["q90"].predict(
        X_test, num_iteration=boosters["q90"].best_iteration
    )

    ablation_report = run_ablation(
        y_true=y_test.values,
        y_pred_median=y_pred_q50,
        aqi_at_prediction_time=X_test["aqi_lag_1h"].values,
        rolling_mean_24h_at_prediction_time=X_test["aqi_rolling_mean_24h"].values,
        y_pred_lower=y_pred_q10,
        y_pred_upper=y_pred_q90,
    )

    return {
        "boosters": boosters,
        "ablation_report": ablation_report,
        "n_train": len(X_train),
        "n_val": len(X_val),
        "n_test": len(X_test),
        "horizon_hours": horizon_hours,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Train the depth-pass quantile forecasting model (Phase 6)."
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--horizon", type=int, default=24, choices=[24, 48, 72])
    parser.add_argument("--dataset-snapshot", default="unspecified")
    args = parser.parse_args()

    raw_df = pd.read_csv(args.data, parse_dates=["timestamp"])
    if raw_df["timestamp"].dt.tz is None:
        raw_df["timestamp"] = raw_df["timestamp"].dt.tz_localize("UTC")

    result = train_quantile_models(raw_df, horizon_hours=args.horizon)
    boosters = result["boosters"]
    report = result["ablation_report"]

    version_id = (
        f"v_q_h{args.horizon}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    )
    model_files = {
        f"model_{name}.txt": booster.model_to_string().encode("utf-8")
        for name, booster in boosters.items()
    }

    confidence_tier = "reliable" if args.horizon <= 48 else "experimental"

    metadata = {
        "version": version_id,
        "trained_on": datetime.now(timezone.utc).isoformat(),
        "dataset_snapshot": args.dataset_snapshot,
        "feature_list_version": FEATURE_LIST_VERSION,
        "horizon_hours": args.horizon,
        "confidence_tier": confidence_tier,
        "quantiles": list(QUANTILES.keys()),
        "n_train": result["n_train"],
        "n_val": result["n_val"],
        "n_test": result["n_test"],
        **report.to_dict(),
    }

    version_dir = registry.save_version(
        component="forecasting",
        version_id=version_id,
        model_files=model_files,
        metadata=metadata,
    )

    print(
        f"Quantile model (horizon={args.horizon}h, tier={confidence_tier}) registered at: {version_dir}"
    )
    print(report.to_markdown(model_version=version_id, horizon_hours=args.horizon))


if __name__ == "__main__":
    main()
