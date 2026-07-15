"""
backend/models/forecasting/features.py

Shared feature engineering for the AQI forecasting model.

CRITICAL: this module is imported by BOTH train.py/train_mvp.py/quantile_lgbm.py
AND inference.py. Never reimplement any of this logic separately in the
inference path — a mismatch between training-time and inference-time feature
computation is the single most common way a model silently degrades
(ML Model Specification, Section 2 and Appendix B).

Expected raw input schema (one row per station per hour):
    station_id          : str
    latitude             : float
    longitude            : float
    timestamp            : pandas.Timestamp (UTC, tz-aware)
    aqi                   : float
    wind_speed            : float   (m/s)
    wind_direction        : float   (degrees, 0-360)
    temperature           : float   (Celsius)
    humidity              : float   (%)
    precipitation         : float   (mm)
    boundary_layer_height : float   (meters, optional — NaN allowed)
    fire_count_50km       : int     (count of FIRMS detections within 50km, last 24h)
    fire_count_100km      : int
    fire_upwind_flag      : bool
    road_density_500m     : float   (arbitrary density unit, consistent across the pipeline)
    land_use_category     : str     ("industrial" | "residential" | "agricultural" | "mixed")
"""

from typing import List, Tuple

import numpy as np
import pandas as pd

FEATURE_LIST_VERSION = "v2"

# The exact, ordered feature set fed to the model. Both training and
# inference must produce a DataFrame with exactly these columns, in this
# order, before calling the model.
#
# v2 additions (ERA5-sourced):
#   blh_log              — log1p(boundary_layer_height): more normally distributed
#                          than raw metres; stronger signal for winter trapping events
#   surface_pressure_hpa — surface pressure in hPa; correlated with anticyclonic
#                          conditions that suppress vertical mixing
FORECASTING_FEATURE_COLUMNS: List[str] = [
    "aqi_lag_1h",
    "aqi_lag_3h",
    "aqi_lag_24h",
    "aqi_rolling_mean_6h",
    "aqi_rolling_mean_24h",
    "aqi_rolling_std_24h",
    "wind_speed",
    "wind_direction_sin",
    "wind_direction_cos",
    "temperature",
    "humidity",
    "precipitation",
    "boundary_layer_height",
    "blh_log",
    "surface_pressure_hpa",
    "hour_of_day_sin",
    "hour_of_day_cos",
    "day_of_week",
    "month_of_year",
    "fire_count_50km",
    "fire_count_100km",
    "fire_upwind_flag",
    "road_density_500m",
    "land_use_category_code",
    "horizon_hours",
]

# Fixed encoding for the categorical land_use_category field, so training
# and inference never disagree on the mapping.
LAND_USE_CODE_MAP = {
    "industrial": 0,
    "residential": 1,
    "agricultural": 2,
    "mixed": 3,
}


def _encode_land_use(series: pd.Series) -> pd.Series:
    return series.map(LAND_USE_CODE_MAP).fillna(LAND_USE_CODE_MAP["mixed"]).astype(int)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Cyclical hour-of-day encoding plus day-of-week / month-of-year."""
    df = df.copy()
    hour = df["timestamp"].dt.hour
    df["hour_of_day_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_of_day_cos"] = np.cos(2 * np.pi * hour / 24)
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month_of_year"] = df["timestamp"].dt.month
    return df


def add_wind_features(df: pd.DataFrame) -> pd.DataFrame:
    """Sine/cosine encoding of wind direction to avoid the 0/360 discontinuity."""
    df = df.copy()
    radians = np.deg2rad(df["wind_direction"].astype(float))
    df["wind_direction_sin"] = np.sin(radians)
    df["wind_direction_cos"] = np.cos(radians)
    return df


def add_lag_rolling_features(
    df: pd.DataFrame,
    group_col: str = "station_id",
    value_col: str = "aqi",
) -> pd.DataFrame:
    """
    Adds lag and rolling features computed per-station. Requires df to be
    sorted by (group_col, timestamp) with an hourly, gap-tolerant index —
    upstream normalization (Section 4.1 of the spec) is responsible for
    ensuring a consistent hourly grid before this is called.
    """
    df = df.sort_values([group_col, "timestamp"]).copy()
    grouped = df.groupby(group_col)[value_col]

    df["aqi_lag_1h"] = grouped.shift(1)
    df["aqi_lag_3h"] = grouped.shift(3)
    df["aqi_lag_24h"] = grouped.shift(24)

    df["aqi_rolling_mean_6h"] = grouped.transform(
        lambda s: s.rolling(6, min_periods=3).mean()
    )
    df["aqi_rolling_mean_24h"] = grouped.transform(
        lambda s: s.rolling(24, min_periods=12).mean()
    )
    df["aqi_rolling_std_24h"] = grouped.transform(
        lambda s: s.rolling(24, min_periods=12).std()
    )

    return df


def add_era5_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derives ERA5-sourced features from columns already present in the DataFrame.

    Expects:
        boundary_layer_height : float (metres) — may be NaN if ERA5 not available
        surface_pressure_hpa  : float (hPa)    — may be NaN if ERA5 not available

    Produces:
        blh_log              : log1p(boundary_layer_height) — log-scaled BLH.
                               NaN-safe: falls back to column mean (or log1p(500)
                               if all NaN) so the downstream dropna in
                               make_training_examples never discards rows that have
                               a valid BLH observation.
        surface_pressure_hpa : passed through as-is (added here if not already
                               present). NaN-safe: filled with ISA standard
                               atmosphere (1013.25 hPa) so rows without ERA5
                               data are not silently dropped during training.

    When real ERA5 data is available (via ERA5Loader.merge_into_df), the NaN
    fallbacks are never needed — all rows will carry real values.
    """
    df = df.copy()

    # blh_log — log1p(BLH) with mean-imputation fallback
    blh = df["boundary_layer_height"].astype(float)
    blh_log = np.log1p(blh.clip(lower=0.0))
    fallback_blh_log = (
        float(blh_log.mean()) if blh_log.notna().any() else np.log1p(500.0)
    )
    df["blh_log"] = blh_log.fillna(fallback_blh_log)

    # surface_pressure_hpa — ISA standard atmosphere fallback
    _ISA_PRESSURE_HPA = 1013.25
    if "surface_pressure_hpa" not in df.columns:
        df["surface_pressure_hpa"] = _ISA_PRESSURE_HPA
    else:
        df["surface_pressure_hpa"] = (
            df["surface_pressure_hpa"].astype(float).fillna(_ISA_PRESSURE_HPA)
        )

    return df


def build_feature_frame(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies all feature engineering steps to a raw hourly station dataframe.
    Does not drop any original columns — callers select FORECASTING_FEATURE_COLUMNS
    (plus `horizon_hours`, added separately per training example / inference call).
    """
    df = raw_df.copy()
    df = add_time_features(df)
    df = add_wind_features(df)
    df = add_lag_rolling_features(df)
    df = add_era5_derived_features(df)
    df["land_use_category_code"] = _encode_land_use(df["land_use_category"])
    df["fire_upwind_flag"] = df["fire_upwind_flag"].astype(int)
    return df


def make_training_examples(
    raw_df: pd.DataFrame,
    horizon_hours: int,
    group_col: str = "station_id",
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Builds (X, y, meta) for a given forecast horizon.

    For each station, at time T, the target y is the observed AQI at time
    T + horizon_hours. Rows where the target isn't available (too close to
    the end of the series) are dropped.

    Returns:
        X    : DataFrame with columns == FORECASTING_FEATURE_COLUMNS
        y    : Series of target AQI values
        meta : DataFrame with station_id and timestamp, aligned with X/y,
               useful for the time-based train/val/test split (Section 4.3)
    """
    features = build_feature_frame(raw_df)
    features["horizon_hours"] = horizon_hours

    # Build the target by shifting the raw AQI series backward by `horizon_hours`
    # within each station group (i.e. "what will AQI be `horizon_hours` from now").
    target = (
        raw_df.sort_values([group_col, "timestamp"])
        .groupby(group_col)["aqi"]
        .shift(-horizon_hours)
    )
    features = features.assign(_target=target.values)

    features = features.dropna(subset=FORECASTING_FEATURE_COLUMNS + ["_target"])

    X = features[FORECASTING_FEATURE_COLUMNS].reset_index(drop=True)
    y = features["_target"].reset_index(drop=True)
    meta = features[[group_col, "timestamp"]].reset_index(drop=True)
    return X, y, meta


def build_inference_feature_row(
    station_history_df: pd.DataFrame,
    horizon_hours: int,
) -> pd.DataFrame:
    """
    Builds a single-row feature DataFrame for inference, using the most
    recent timestamp in `station_history_df` (which must contain at least
    the last 24 hours of history for one station, with the same raw schema
    as make_training_examples's input).

    Returns a 1-row DataFrame with columns == FORECASTING_FEATURE_COLUMNS,
    ready to pass directly into a trained model's .predict().
    """
    features = build_feature_frame(station_history_df)
    features["horizon_hours"] = horizon_hours
    latest_row = features.sort_values("timestamp").iloc[[-1]]
    missing = [c for c in FORECASTING_FEATURE_COLUMNS if latest_row[c].isna().any()]
    if missing:
        raise ValueError(
            f"Cannot build inference feature row — missing/NaN values for: {missing}. "
            f"This usually means station_history_df did not contain enough recent "
            f"history (need at least 24 hourly rows for lag/rolling features)."
        )
    return latest_row[FORECASTING_FEATURE_COLUMNS]
