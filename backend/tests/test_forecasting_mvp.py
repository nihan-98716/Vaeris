import os
import shutil
import tempfile
from datetime import datetime, timezone

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from backend.models import registry
from backend.models.attribution.rule_engine import run_attribution
from backend.models.forecasting import features, inference, train_mvp
from backend.models.health_impact import estimate_exposure_risk
from backend.models.schemas import LatLon


@pytest.fixture
def dummy_raw_data():
    """Generates a dummy raw hourly history dataset for 2 stations over 96 hours."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-11-13 00:00:00", periods=96, freq="h", tz="UTC")
    data = []

    for station_id in ["station_rk_puram_delhi", "station_anand_vihar_delhi"]:
        for dt in dates:
            data.append(
                {
                    "station_id": station_id,
                    "latitude": 28.566,
                    "longitude": 77.186,
                    "timestamp": dt,
                    "aqi": float(100 + np.random.randint(0, 50)),
                    "wind_speed": float(2.0 + np.random.randn()),
                    "wind_direction": float(180 + np.random.randint(0, 90)),
                    "temperature": 22.0,
                    "humidity": 60.0,
                    "precipitation": 0.0,
                    "boundary_layer_height": 500.0,
                    "fire_count_50km": 0,
                    "fire_count_100km": 0,
                    "fire_upwind_flag": 0,
                    "road_density_500m": 0.5,
                    "land_use_category": "residential",
                }
            )

    return pd.DataFrame(data)


def test_feature_engineering_pipeline(dummy_raw_data):
    # Test building time and wind features
    df_time = features.add_time_features(dummy_raw_data)
    assert "hour_of_day_sin" in df_time.columns
    assert "hour_of_day_cos" in df_time.columns
    assert "day_of_week" in df_time.columns
    assert "month_of_year" in df_time.columns

    df_wind = features.add_wind_features(dummy_raw_data)
    assert "wind_direction_sin" in df_wind.columns
    assert "wind_direction_cos" in df_wind.columns

    # Test lag features computation
    df_lags = features.add_lag_rolling_features(dummy_raw_data)
    assert "aqi_lag_1h" in df_lags.columns
    assert "aqi_rolling_mean_6h" in df_lags.columns

    # Check that lag 1h shifts aqi correctly
    first_station = df_lags[df_lags["station_id"] == "station_rk_puram_delhi"]
    aqi_vals = first_station["aqi"].values
    lag1_vals = first_station["aqi_lag_1h"].values
    assert np.isnan(lag1_vals[0])
    assert lag1_vals[1] == aqi_vals[0]


def test_build_inference_feature_row(dummy_raw_data):
    station_data = dummy_raw_data[
        dummy_raw_data["station_id"] == "station_rk_puram_delhi"
    ]
    feature_row = features.build_inference_feature_row(station_data, horizon_hours=24)

    assert len(feature_row) == 1
    assert list(feature_row.columns) == features.FORECASTING_FEATURE_COLUMNS


def test_health_impact_estimation():
    res = estimate_exposure_risk(
        forecast_pm25=120.0,
        baseline_pm25=20.0,
        exposed_population=10000,
        relative_risk_per_unit=0.01,
    )
    assert res.indicative_risk_score == 10000.0  # (120 - 20) * 0.01 * 10000 = 10000
    assert res.exposed_population == 10000


def test_attribution_engine_with_no_signals():
    # If all trigger strengths are 0.0, it should collapse to unknown
    signals = {
        "fire_events": [],
        "wind_direction_deg": 180.0,
        "wind_speed_ms": 2.0,
        "road_density_500m": 0.1,
        "land_use_category": "residential",
        "aqi_now": 50.0,
        "aqi_rolling_mean_24h": 50.0,
        "hour_of_day": 12,
    }

    res = run_attribution(signals)
    assert res.primary_cause == "unknown"
    assert res.confidence_breakdown == {"unknown": 1.0}


@pytest.fixture
def temp_model_registry():
    """Initializes a temporary directory to act as model registry."""
    temp_dir = tempfile.mkdtemp()
    original_root = registry.DEFAULT_REGISTRY_ROOT
    registry.DEFAULT_REGISTRY_ROOT = temp_dir
    os.environ["MODEL_REGISTRY_ROOT"] = temp_dir
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir)
    registry.DEFAULT_REGISTRY_ROOT = original_root


def test_train_and_inference_flow(dummy_raw_data, temp_model_registry):
    # Train the MVP model
    result = train_mvp.train(dummy_raw_data, horizon_hours=24)
    booster = result["booster"]
    report = result["ablation_report"]

    assert isinstance(booster, lgb.Booster)
    assert report.rmse_improvement_over_persistence_pct is not None

    # Save the trained model to registry
    version_id = "v_mvp_test_version"
    model_bytes = booster.model_to_string().encode("utf-8")
    metadata = {
        "version": version_id,
        "trained_on": datetime.now(timezone.utc).isoformat(),
        "dataset_snapshot": "test_snapshot",
        "feature_list_version": features.FEATURE_LIST_VERSION,
        "horizon_hours": 24,
        "quantiles": ["q50"],
        "n_train": result["n_train"],
        "n_val": result["n_val"],
        "n_test": result["n_test"],
        **report.to_dict(),
    }

    registry.save_version(
        component="forecasting",
        version_id=version_id,
        model_files={"model_q50.txt": model_bytes},
        metadata=metadata,
        registry_root=temp_model_registry,
    )

    # Load and test the inference pipeline
    # Force reload from the temp registry
    inference._load_boosters(force_reload=True)

    station_history = dummy_raw_data[
        dummy_raw_data["station_id"] == "station_rk_puram_delhi"
    ]
    location = LatLon(latitude=28.566, longitude=77.186)

    forecast = inference.predict_from_history(
        station_history, location, horizon_hours=24
    )

    assert forecast.value is not None
    assert forecast.lower_bound == forecast.value  # MVP collapsed bounds
    assert forecast.upper_bound == forecast.value
    assert forecast.horizon_hours == 24
    assert forecast.model_version == version_id
