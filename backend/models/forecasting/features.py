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

FEATURE_LIST_VERSION = "v3"

# The exact, ordered feature set fed to the model. Both training and
# inference must produce a DataFrame with exactly these columns, in this
# order, before calling the model.
#
# v3 additions:
#   NWP weather forecast, persistence-corrected lag, and spatial features.
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
    "boundary_layer_height_12h_forecast",
    "boundary_layer_height_24h_forecast",
    "boundary_layer_height_48h_forecast",
    "wind_speed_6h_forecast",
    "wind_speed_12h_forecast",
    "wind_speed_24h_forecast",
    "precipitation_next_24h_forecast",
    "temperature_inversion_flag",
    "aqi_lag_1h_diurnal",
    "aqi_delta_6h",
    "aqi_rolling_max_12h",
    "mean_aqi_neighbouring_stations_last_1h",
    "max_aqi_within_10km_last_6h",
    "distance_weighted_upwind_aqi_lag_1h",
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


def add_weather_forecast_features(
    df: pd.DataFrame, group_col: str = "station_id"
) -> pd.DataFrame:
    """
    Adds weather forecast proxy features. During training, uses future values
    as perfect-forecast proxies. During inference (when future rows are NaN
    after shifting), falls back to persistence (current value) or defaults.
    """
    df = df.sort_values([group_col, "timestamp"]).copy()
    grouped = df.groupby(group_col)

    # 1. BLH forecasts
    df["boundary_layer_height_12h_forecast"] = (
        grouped["boundary_layer_height"].shift(-12).fillna(df["boundary_layer_height"])
    )
    df["boundary_layer_height_24h_forecast"] = (
        grouped["boundary_layer_height"].shift(-24).fillna(df["boundary_layer_height"])
    )
    df["boundary_layer_height_48h_forecast"] = (
        grouped["boundary_layer_height"].shift(-48).fillna(df["boundary_layer_height"])
    )

    # 2. Wind speed forecasts
    df["wind_speed_6h_forecast"] = (
        grouped["wind_speed"].shift(-6).fillna(df["wind_speed"])
    )
    df["wind_speed_12h_forecast"] = (
        grouped["wind_speed"].shift(-12).fillna(df["wind_speed"])
    )
    df["wind_speed_24h_forecast"] = (
        grouped["wind_speed"].shift(-24).fillna(df["wind_speed"])
    )

    # 3. Precipitation forecast
    df["precipitation_next_24h_forecast"] = (
        grouped["precipitation"]
        .transform(lambda s: s.shift(-24).rolling(24, min_periods=1).sum())
        .fillna(0.0)
    )

    # 4. Temperature inversion flag
    df["temperature_inversion_flag"] = (df["boundary_layer_height"] < 150.0).astype(int)

    return df


def add_persistence_corrected_lag_features(
    df: pd.DataFrame, group_col: str = "station_id"
) -> pd.DataFrame:
    """
    Adds non-linear persistence-corrected and trend features.
    """
    df = df.sort_values([group_col, "timestamp"]).copy()
    grouped = df.groupby(group_col)

    # aqi_lag_1h_diurnal (diurnal modulation of persistence)
    df["aqi_lag_1h_diurnal"] = df["aqi_lag_1h"] * df["hour_of_day_sin"]

    # aqi_delta_6h (6-hour trend indicator)
    aqi_lag_6h = grouped["aqi"].shift(6)
    df["aqi_delta_6h"] = (df["aqi_lag_1h"] - aqi_lag_6h).fillna(0.0)

    # aqi_rolling_max_12h (recent spike intensity)
    df["aqi_rolling_max_12h"] = (
        grouped["aqi"]
        .transform(lambda s: s.rolling(12, min_periods=1).max())
        .fillna(df["aqi"])
    )

    return df


def _haversine_dist(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return float(R * 2 * np.arcsin(np.sqrt(a)))


def _calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing in degrees from point 1 to point 2."""
    dlon = np.radians(lon2 - lon1)
    lat1_rad, lat2_rad = np.radians(lat1), np.radians(lat2)
    y = np.sin(dlon) * np.cos(lat2_rad)
    x = np.cos(lat1_rad) * np.sin(lat2_rad) - np.sin(lat1_rad) * np.cos(
        lat2_rad
    ) * np.cos(dlon)
    return float((np.degrees(np.arctan2(y, x)) + 360) % 360)


def _compute_row_spatial_features(
    st: str,
    wind_dir: float,
    i: int,
    unique_stations: np.ndarray,
    station_indices: dict,
    aqi_lag_pivot_vals: np.ndarray,
    aqi_pivot_vals: np.ndarray,
    dist_matrix: dict,
    bearing_matrix: dict,
    default_aqi_lag: float,
    default_aqi: float,
) -> Tuple[float, float, float]:
    """Calculates neighboring mean, 10km max, and upwind lag for a single row."""
    other_sts = [s for s in unique_stations if s != st]

    # 1. Mean neighboring AQI lag 1h
    other_idxs = [station_indices[s] for s in other_sts]
    row_lag_vals = aqi_lag_pivot_vals[i, other_idxs]
    valid_lag_vals = row_lag_vals[~np.isnan(row_lag_vals)]
    mean_neigh = (
        float(np.mean(valid_lag_vals)) if len(valid_lag_vals) > 0 else default_aqi_lag
    )

    # 2. Max AQI within 10km last 6h (per-row first, rolling max applied after)
    close_sts = [s for s in other_sts if dist_matrix[(st, s)] <= 10.0]
    target_idxs = [station_indices[s] for s in close_sts + [st]]
    row_aqi_vals = aqi_pivot_vals[i, target_idxs]
    valid_aqi_vals = row_aqi_vals[~np.isnan(row_aqi_vals)]
    max_close = (
        float(np.max(valid_aqi_vals)) if len(valid_aqi_vals) > 0 else default_aqi
    )

    # 3. Distance-weighted upwind AQI lag 1h
    upwind_val = 0.0
    for other in other_sts:
        dist = dist_matrix[(st, other)]
        if dist > 0:
            bearing = bearing_matrix[(st, other)]
            diff = abs(bearing - wind_dir) % 360
            ang_diff = min(diff, 360 - diff)
            if ang_diff <= 45.0:  # upwind station (within 45 degrees of wind dir)
                val = aqi_lag_pivot_vals[i, station_indices[other]]
                if not np.isnan(val):
                    upwind_val += val / dist

    return mean_neigh, max_close, upwind_val


def add_spatial_neighbourhood_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds spatial neighborhood and wind-aligned upwind lag features.
    Handles single-station inputs (like inference time) gracefully by falling
    back to the station's own metrics or 0.0.
    """
    df = df.copy()

    # Pre-populate empty/fallback defaults
    df["mean_aqi_neighbouring_stations_last_1h"] = df["aqi_lag_1h"]
    df["max_aqi_within_10km_last_6h"] = df["aqi_rolling_mean_6h"]
    df["distance_weighted_upwind_aqi_lag_1h"] = 0.0

    unique_stations = df["station_id"].unique()
    if len(unique_stations) <= 1:
        # Single station (inference fallback), return defaults
        return df

    # Build coordinates map
    station_coords = {}
    for st in unique_stations:
        st_rows = df[df["station_id"] == st]
        if not st_rows.empty:
            station_coords[st] = (
                float(st_rows.iloc[0]["latitude"]),
                float(st_rows.iloc[0]["longitude"]),
            )

    # Pivot AQI tables to align by timestamp
    aqi_lag_pivot = df.pivot(
        index="timestamp", columns="station_id", values="aqi_lag_1h"
    )
    aqi_pivot = df.pivot(index="timestamp", columns="station_id", values="aqi")

    # Align indexes to match original rows
    aqi_lag_pivot_vals = aqi_lag_pivot.reindex(df["timestamp"]).values
    aqi_pivot_vals = aqi_pivot.reindex(df["timestamp"]).values

    station_indices = {st: idx for idx, st in enumerate(unique_stations)}

    # Precompute distances and bearings between all station pairs
    dist_matrix = {}
    bearing_matrix = {}
    for st1 in unique_stations:
        for st2 in unique_stations:
            if st1 != st2:
                lat1, lon1 = station_coords[st1]
                lat2, lon2 = station_coords[st2]
                dist_matrix[(st1, st2)] = _haversine_dist(lat1, lon1, lat2, lon2)
                bearing_matrix[(st1, st2)] = _calculate_bearing(lat1, lon1, lat2, lon2)

    station_ids = df["station_id"].values
    wind_dirs = df["wind_direction"].values
    aqi_lag_1h_vals = df["aqi_lag_1h"].values
    aqi_vals = df["aqi"].values

    mean_neighs = []
    max_10kms = []
    upwind_lags = []

    for i in range(len(df)):
        mean_neigh, max_close, upwind_val = _compute_row_spatial_features(
            st=station_ids[i],
            wind_dir=wind_dirs[i],
            i=i,
            unique_stations=unique_stations,
            station_indices=station_indices,
            aqi_lag_pivot_vals=aqi_lag_pivot_vals,
            aqi_pivot_vals=aqi_pivot_vals,
            dist_matrix=dist_matrix,
            bearing_matrix=bearing_matrix,
            default_aqi_lag=float(aqi_lag_1h_vals[i]),
            default_aqi=float(aqi_vals[i]),
        )
        mean_neighs.append(mean_neigh)
        max_10kms.append(max_close)
        upwind_lags.append(upwind_val)

    df["mean_aqi_neighbouring_stations_last_1h"] = mean_neighs
    df["max_aqi_within_10km_last_6h"] = max_10kms
    # Add rolling max over last 6h per station
    df["max_aqi_within_10km_last_6h"] = df.groupby("station_id")[
        "max_aqi_within_10km_last_6h"
    ].transform(lambda s: s.rolling(6, min_periods=1).max())
    df["distance_weighted_upwind_aqi_lag_1h"] = upwind_lags

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
    df = add_weather_forecast_features(df)
    df = add_persistence_corrected_lag_features(df)
    df = add_spatial_neighbourhood_features(df)
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
