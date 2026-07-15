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
import pandas as pd

from backend.models import registry
from backend.models.forecasting.ablation import run_ablation
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
    "num_leaves": 31,
    "learning_rate": 0.05,
    "min_child_samples": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "verbose": -1,
}


def _build_multi_horizon_splits(raw_df: pd.DataFrame, horizons):
    """
    For each horizon, builds training examples and does an independent
    time-based split (Section 4.3 — never shuffle, never leak future rows
    into train/val for that horizon), then concatenates the train/val/test
    slices across horizons. Splitting per-horizon first (rather than
    splitting the combined frame) avoids a subtle leak where a late-horizon
    row's target could fall inside another horizon's train window.
    """
    train_parts, val_parts, test_parts = [], [], []
    test_parts_by_horizon = {}

    for h in horizons:
        X, y, meta = make_training_examples(raw_df, horizon_hours=h)
        splits = time_based_split(X, y, meta)
        train_parts.append(splits["train"])
        val_parts.append(splits["val"])
        test_parts.append(splits["test"])
        test_parts_by_horizon[h] = splits["test"]

    def _concat(parts):
        Xs, ys, metas = zip(*parts)
        return (
            pd.concat(Xs, ignore_index=True),
            pd.concat(ys, ignore_index=True),
            pd.concat(metas, ignore_index=True),
        )

    return (
        _concat(train_parts),
        _concat(val_parts),
        _concat(test_parts),
        test_parts_by_horizon,
    )


def train_quantile_models(raw_df: pd.DataFrame, horizons=DEFAULT_HORIZONS) -> dict:
    (
        (X_train, y_train, _),
        (X_val, y_val, _),
        (X_test, y_test, meta_test),
        test_by_horizon,
    ) = _build_multi_horizon_splits(raw_df, horizons)

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

    # Overall ablation report (all horizons pooled) plus one report per
    # individual horizon, so the depth/breadth trade-off from training on
    # combined data is fully visible rather than hidden behind one pooled number.
    def _report_for(X_slice, y_slice):
        y_pred_q10 = boosters["q10"].predict(
            X_slice, num_iteration=boosters["q10"].best_iteration
        )
        y_pred_q50 = boosters["q50"].predict(
            X_slice, num_iteration=boosters["q50"].best_iteration
        )
        y_pred_q90 = boosters["q90"].predict(
            X_slice, num_iteration=boosters["q90"].best_iteration
        )
        return run_ablation(
            y_true=y_slice.values,
            y_pred_median=y_pred_q50,
            aqi_at_prediction_time=X_slice["aqi_lag_1h"].values,
            rolling_mean_24h_at_prediction_time=X_slice["aqi_rolling_mean_24h"].values,
            y_pred_lower=y_pred_q10,
            y_pred_upper=y_pred_q90,
        )

    overall_report = _report_for(X_test, y_test)
    per_horizon_reports = {
        h: _report_for(X_h, y_h) for h, (X_h, y_h, _meta_h) in test_by_horizon.items()
    }

    return {
        "boosters": boosters,
        "ablation_report": overall_report,
        "per_horizon_reports": per_horizon_reports,
        "n_train": len(X_train),
        "n_val": len(X_val),
        "n_test": len(X_test),
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
        help="Comma-separated list of forecast horizons (hours) to train on jointly, e.g. '24,48,72'.",
    )
    parser.add_argument("--dataset-snapshot", default="unspecified")
    args = parser.parse_args()

    horizons = tuple(int(h.strip()) for h in args.horizons.split(","))

    raw_df = pd.read_csv(args.data, parse_dates=["timestamp"])
    if raw_df["timestamp"].dt.tz is None:
        raw_df["timestamp"] = raw_df["timestamp"].dt.tz_localize("UTC")

    result = train_quantile_models(raw_df, horizons=horizons)
    boosters = result["boosters"]
    overall_report = result["ablation_report"]
    per_horizon_reports = result["per_horizon_reports"]

    version_id = f"v_q_multi_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
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
