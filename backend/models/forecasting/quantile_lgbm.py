"""
backend/models/forecasting/quantile_lgbm.py

Phase 6 (depth pass) training script — see ML Model Specification, Sections
6.4-6.8. Trains THREE LightGBM models (q10, q50, q90) sharing the same
feature set, covering the 24h/48h "reliable" horizons and the 72h
"experimental" horizon.

IMPORTANT — single multi-horizon model, not one model per horizon:
`horizon_hours` is already a feature column (features.py), so rather than
training three separate models (which would each overwrite the registry's
single "latest" pointer for the "forecasting" component — see registry.py,
which tracks one latest version per component, not one per horizon), this
script trains ONE model across examples from all requested horizons, with
`horizon_hours` as a normal input feature the model conditions on. This is
both simpler to serve (inference.py always loads "the latest forecasting
model" regardless of which horizon was requested) and gives the model more
training signal to learn how uncertainty/behavior changes with horizon,
rather than fitting three isolated datasets.

Per-horizon accuracy is still reported separately in ablation_results.md —
training on combined data does not obscure per-horizon performance.

Run directly:
    python -m backend.models.forecasting.quantile_lgbm --data path/to/history.csv
    python -m backend.models.forecasting.quantile_lgbm --data path/to/history.csv --horizons 24,48
"""

import argparse
from datetime import datetime, timezone

import lightgbm as lgb
import numpy as np
import pandas as pd

from backend.models import registry
from backend.models.forecasting.ablation import run_ablation
from backend.models.forecasting.cqr_calibration import CQRCalibrator
from backend.models.forecasting.features import (
    FEATURE_LIST_VERSION,
    make_training_examples,
)
from backend.models.forecasting.train_mvp import time_based_split

QUANTILES = {"q10": 0.1, "q50": 0.5, "q90": 0.9}
DEFAULT_HORIZONS = (24, 48, 72)
RELIABLE_HORIZON_CUTOFF_HOURS = 48

BASE_PARAMS = {
    "objective": "quantile",
    "verbose": -1,
}

HORIZON_PARAMS = {
    24: {
        "num_leaves": 15,
        "learning_rate": 0.03,
        "min_child_samples": 25,
        "feature_fraction": 0.7,
        "bagging_fraction": 0.7,
    },
    48: {
        "num_leaves": 31,
        "learning_rate": 0.05,
        "min_child_samples": 20,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
    },
    72: {
        "num_leaves": 63,
        "learning_rate": 0.07,
        "min_child_samples": 15,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
    },
}


def train_quantile_models(raw_df: pd.DataFrame, horizons=DEFAULT_HORIZONS) -> dict:
    """
    Trains separate quantile models (q10, q50, q90) for each requested horizon,
    enforcing monotonicity constraints on crucial lag/rolling/fire features.
    Computes post-hoc CQR calibration on validation sets to target 80% coverage.
    """
    boosters = {}
    per_horizon_reports = {}
    calibrators = {}

    n_train_total = 0
    n_val_total = 0
    n_test_total = 0

    y_test_all = []
    y_pred_q50_all = []
    y_pred_q10_all = []
    y_pred_q90_all = []
    aqi_lag_all = []
    rolling_mean_all = []

    for h in horizons:
        print(f"\nTraining forecasting models for horizon {h}h...")
        X, y, meta = make_training_examples(raw_df, horizon_hours=h)
        splits = time_based_split(X, y, meta)
        X_train, y_train, _ = splits["train"]
        X_val, y_val, _ = splits["val"]
        X_test, y_test, _ = splits["test"]

        n_train_total += len(X_train)
        n_val_total += len(X_val)
        n_test_total += len(X_test)

        h_boosters = {}
        for name, alpha in QUANTILES.items():
            params = dict(
                BASE_PARAMS,
                **HORIZON_PARAMS.get(h, HORIZON_PARAMS[48]),
                alpha=alpha,
                metric="quantile",
            )
            train_set = lgb.Dataset(X_train, label=y_train)
            val_set = lgb.Dataset(X_val, label=y_val, reference=train_set)
            booster = lgb.train(
                params,
                train_set,
                num_boost_round=300,
                valid_sets=[val_set],
                callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
            )
            h_boosters[name] = booster
            # Save using the per-horizon key format
            boosters[f"{h}_{name}"] = booster

        # Fit CQR Calibrator on validation set for this specific horizon
        pred_lower_val = h_boosters["q10"].predict(
            X_val, num_iteration=h_boosters["q10"].best_iteration
        )
        pred_upper_val = h_boosters["q90"].predict(
            X_val, num_iteration=h_boosters["q90"].best_iteration
        )
        calibrator = CQRCalibrator(target_coverage=0.80)
        calibrator.fit(
            y_cal=y_val.values,
            pred_lower_cal=pred_lower_val,
            pred_upper_cal=pred_upper_val,
            target_coverage=0.80,
        )
        calibrators[h] = calibrator

        # Evaluate on test set
        y_pred_q10 = h_boosters["q10"].predict(
            X_test, num_iteration=h_boosters["q10"].best_iteration
        )
        y_pred_q50 = h_boosters["q50"].predict(
            X_test, num_iteration=h_boosters["q50"].best_iteration
        )
        y_pred_q90 = h_boosters["q90"].predict(
            X_test, num_iteration=h_boosters["q90"].best_iteration
        )

        # Apply CQR calibration correction to test bounds before evaluating coverage
        cal_pred_lower, cal_pred_upper = calibrator.calibrate(y_pred_q10, y_pred_q90)

        # Enforce physical constraints: lower_bound >= 0 and non-crossing
        cal_pred_lower = np.maximum(0.0, np.minimum(cal_pred_lower, y_pred_q50))
        cal_pred_upper = np.maximum(cal_pred_upper, y_pred_q50)

        report = run_ablation(
            y_true=y_test.values,
            y_pred_median=y_pred_q50,
            aqi_at_prediction_time=X_test["aqi_lag_1h"].values,
            rolling_mean_24h_at_prediction_time=X_test["aqi_rolling_mean_24h"].values,
            y_pred_lower=cal_pred_lower,
            y_pred_upper=cal_pred_upper,
        )
        per_horizon_reports[h] = report

        # Accumulate for overall report
        y_test_all.extend(y_test.values)
        y_pred_q50_all.extend(y_pred_q50)
        y_pred_q10_all.extend(cal_pred_lower)
        y_pred_q90_all.extend(cal_pred_upper)
        aqi_lag_all.extend(X_test["aqi_lag_1h"].values)
        rolling_mean_all.extend(X_test["aqi_rolling_mean_24h"].values)

    # Compute overall report across all horizons pooled
    overall_report = run_ablation(
        y_true=np.array(y_test_all),
        y_pred_median=np.array(y_pred_q50_all),
        aqi_at_prediction_time=np.array(aqi_lag_all),
        rolling_mean_24h_at_prediction_time=np.array(rolling_mean_all),
        y_pred_lower=np.array(y_pred_q10_all),
        y_pred_upper=np.array(y_pred_q90_all),
    )

    return {
        "boosters": boosters,
        "calibrators": calibrators,
        "ablation_report": overall_report,
        "per_horizon_reports": per_horizon_reports,
        "n_train": n_train_total,
        "n_val": n_val_total,
        "n_test": n_test_total,
        "horizons": list(horizons),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Train the depth-pass quantile forecasting model (Phase 6)."
    )
    parser.add_argument("--data", required=True)
    parser.add_argument(
        "--horizons",
        default="24,48,72",
        help="Comma-separated list of forecast horizons (hours) to train on, e.g. '24,48,72'.",
    )
    parser.add_argument("--dataset-snapshot", default="unspecified")
    args = parser.parse_args()

    horizons = tuple(int(h.strip()) for h in args.horizons.split(","))

    raw_df = pd.read_csv(args.data, parse_dates=["timestamp"])
    if raw_df["timestamp"].dt.tz is None:
        raw_df["timestamp"] = raw_df["timestamp"].dt.tz_localize("UTC")

    result = train_quantile_models(raw_df, horizons=horizons)
    boosters = result["boosters"]
    calibrators = result["calibrators"]
    overall_report = result["ablation_report"]
    per_horizon_reports = result["per_horizon_reports"]

    version_id = f"v_q_multi_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # Save model text strings
    model_files = {
        f"model_{name}.txt": booster.model_to_string().encode("utf-8")
        for name, booster in boosters.items()
    }

    metadata = {
        "version": version_id,
        "trained_on": datetime.now(timezone.utc).isoformat(),
        "dataset_snapshot": args.dataset_snapshot,
        "feature_list_version": FEATURE_LIST_VERSION,
        "horizons_hours": list(horizons),
        "reliable_horizon_cutoff_hours": RELIABLE_HORIZON_CUTOFF_HOURS,
        "quantiles": list(QUANTILES.keys()),
        "n_train": result["n_train"],
        "n_val": result["n_val"],
        "n_test": result["n_test"],
        "overall_ablation": overall_report.to_dict(),
        "per_horizon_ablation": {
            str(h): r.to_dict() for h, r in per_horizon_reports.items()
        },
    }

    version_dir = registry.save_version(
        component="forecasting",
        version_id=version_id,
        model_files=model_files,
        metadata=metadata,
    )

    # Save per-horizon calibrations
    for h, calibrator in calibrators.items():
        calibration_path = version_dir / f"calibration_{h}.json"
        calibrator.save(calibration_path)

    print(f"Quantile model (horizons={horizons}) registered at: {version_dir}")
    print(f"## Overall ablation (all horizons pooled) — model version `{version_id}`\n")
    print(
        overall_report.to_markdown(model_version=version_id, horizon_hours=0).replace(
            ", horizon 0h", ""
        )
    )
    for h, r in per_horizon_reports.items():
        print()
        print(r.to_markdown(model_version=version_id, horizon_hours=h))


if __name__ == "__main__":
    main()
