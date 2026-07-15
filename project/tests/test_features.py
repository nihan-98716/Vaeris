"""
tests/test_features.py

Tests for backend/models/forecasting/features.py — runs with only
pandas/numpy, no LightGBM required.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models.forecasting.features import (
    FORECASTING_FEATURE_COLUMNS,
    build_feature_frame,
    build_inference_feature_row,
    make_training_examples,
)
from tests.synthetic_data import generate_history


def test_build_feature_frame_has_expected_columns():
    raw = generate_history(days=10, inject_fire_event=False)
    features = build_feature_frame(raw)
    for col in FORECASTING_FEATURE_COLUMNS:
        if col == "horizon_hours":
            continue  # added separately, not part of build_feature_frame's output
        assert col in features.columns, f"missing expected feature column: {col}"


def test_make_training_examples_shapes_align():
    raw = generate_history(days=15, inject_fire_event=False)
    X, y, meta = make_training_examples(raw, horizon_hours=24)
    assert len(X) == len(y) == len(meta)
    assert list(X.columns) == FORECASTING_FEATURE_COLUMNS
    assert not X.isna().any().any(), "training features should have no NaNs after dropna"


def test_make_training_examples_target_is_shifted_forward():
    raw = generate_history(days=15, inject_fire_event=False)
    X, y, meta = make_training_examples(raw, horizon_hours=24)
    # sanity: target values should be within a plausible AQI range
    assert (y > 0).all()
    assert (y < 500).all()


def test_build_inference_feature_row_single_row():
    raw = generate_history(days=10, inject_fire_event=False)
    station_history = raw[raw["station_id"] == "station_ito_delhi"]
    row = build_inference_feature_row(station_history, horizon_hours=24)
    assert len(row) == 1
    assert list(row.columns) == FORECASTING_FEATURE_COLUMNS
    assert not row.isna().any().any()


def test_build_inference_feature_row_raises_on_insufficient_history():
    raw = generate_history(days=10, inject_fire_event=False)
    station_history = raw[raw["station_id"] == "station_ito_delhi"].tail(2)  # far too little history
    try:
        build_inference_feature_row(station_history, horizon_hours=24)
        assert False, "expected a ValueError due to insufficient history"
    except ValueError:
        pass


if __name__ == "__main__":
    test_build_feature_frame_has_expected_columns()
    test_make_training_examples_shapes_align()
    test_make_training_examples_target_is_shifted_forward()
    test_build_inference_feature_row_single_row()
    test_build_inference_feature_row_raises_on_insufficient_history()
    print("All feature engineering tests passed.")
