"""
tests/synthetic_data.py

TEST/DEMO UTILITY ONLY — not part of the production ingestion pipeline.

Generates a plausible synthetic hourly dataset for the 5 MVP representative
stations (ML Model Specification, Section 6.9.1), with a daily AQI cycle,
wind, and a handful of injected FIRMS-style fire events, so the rest of the
pipeline (features -> training -> inference -> attribution) can be exercised
end-to-end without a live database or real API keys.

Real ingestion (Implementation Plan, Phase 1) replaces this entirely.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

STATIONS = {
    "station_ito_delhi": {
        "lat": 28.6304,
        "lon": 77.2495,
        "land_use": "residential",
        "road_density": 0.85,
    },
    "station_wazirpur_delhi": {
        "lat": 28.6996,
        "lon": 77.1652,
        "land_use": "industrial",
        "road_density": 0.40,
    },
    "station_rohini_delhi": {
        "lat": 28.7495,
        "lon": 77.0565,
        "land_use": "residential",
        "road_density": 0.35,
    },
    "station_rk_puram_delhi": {
        "lat": 28.5641,
        "lon": 77.1765,
        "land_use": "mixed",
        "road_density": 0.55,
    },
    "station_anand_vihar_delhi": {
        "lat": 28.6469,
        "lon": 77.3151,
        "land_use": "mixed",
        "road_density": 0.75,
    },
}


def generate_history(
    days: int = 60,
    seed: int = 42,
    inject_fire_event: bool = True,
) -> pd.DataFrame:
    """
    Returns a DataFrame matching the raw schema documented in
    backend/models/forecasting/features.py, for all 5 representative
    stations, hourly, for `days` days ending "now" (UTC).
    """
    rng = np.random.default_rng(seed)
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    timestamps = pd.date_range(start, end, freq="h", tz="UTC")

    rows = []
    for station_id, meta in STATIONS.items():
        base_aqi = 120 if meta["land_use"] == "industrial" else 90
        for i, ts in enumerate(timestamps):
            hour = ts.hour
            # daily cycle: worse in morning/evening commute, better midday/overnight
            commute_bump = 25 * (
                np.exp(-((hour - 8) ** 2) / 8) + np.exp(-((hour - 19) ** 2) / 8)
            )
            seasonal = 20 * np.sin(
                2 * np.pi * ts.dayofyear / 365
            )  # rough winter/summer swing
            noise = rng.normal(0, 8)
            aqi = max(20, base_aqi + commute_bump + seasonal + noise)

            wind_speed = max(0.2, rng.normal(2.5, 1.2))
            wind_direction = (
                280 + rng.normal(0, 25)
            ) % 360  # prevailing NW-ish wind, roughly stubble-transport direction

            fire_count_50 = 0
            fire_count_100 = 0
            fire_upwind = False

            rows.append(
                {
                    "station_id": station_id,
                    "latitude": meta["lat"],
                    "longitude": meta["lon"],
                    "timestamp": ts,
                    "aqi": aqi,
                    "wind_speed": wind_speed,
                    "wind_direction": wind_direction,
                    "temperature": 18
                    + 10 * np.sin(2 * np.pi * (ts.dayofyear - 80) / 365)
                    + rng.normal(0, 2),
                    "humidity": min(95, max(20, 55 + rng.normal(0, 10))),
                    "precipitation": (
                        max(0.0, rng.normal(0, 0.3)) if rng.random() < 0.05 else 0.0
                    ),
                    "boundary_layer_height": max(100, rng.normal(600, 150)),
                    "fire_count_50km": fire_count_50,
                    "fire_count_100km": fire_count_100,
                    "fire_upwind_flag": fire_upwind,
                    "road_density_500m": meta["road_density"],
                    "land_use_category": meta["land_use"],
                }
            )

    df = pd.DataFrame(rows)

    if inject_fire_event:
        df = _inject_stubble_burning_episode(df)

    return df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)


def _inject_stubble_burning_episode(df: pd.DataFrame) -> pd.DataFrame:
    """
    Injects a synthetic multi-day fire-driven AQI spike near the end of the
    series, loosely modeled on the confirmed historical replay window
    (Nov 13-18, 2024) — for demo/testing purposes only; real replay uses
    the actual captured snapshot (Implementation Plan, Phase 1/7).
    """
    df = df.copy()
    last_ts = df["timestamp"].max()
    episode_start = last_ts - pd.Timedelta(hours=48)

    fire_bearing_from_station = (
        315.0  # roughly NW, consistent with Punjab/Haryana stubble transport
    )

    mask_window = df["timestamp"] >= episode_start
    df.loc[mask_window, "wind_direction"] = (
        fire_bearing_from_station + np.random.normal(0, 5, size=mask_window.sum())
    )
    df.loc[mask_window, "wind_speed"] = np.random.uniform(
        2.0, 4.0, size=mask_window.sum()
    )
    df.loc[mask_window, "fire_count_100km"] = 6
    df.loc[mask_window, "fire_count_50km"] = 2
    df.loc[mask_window, "fire_upwind_flag"] = True

    # AQI ramps up over the window, peaking near the end — simulates a
    # multi-hour transport delay after the fires were detected.
    hours_into_window = (
        df.loc[mask_window, "timestamp"] - episode_start
    ).dt.total_seconds() / 3600
    ramp = np.clip(hours_into_window / 48.0, 0, 1) * 140
    df.loc[mask_window, "aqi"] = df.loc[mask_window, "aqi"] + ramp

    return df


def get_fire_events_for_signals(hours_ago_options=(3, 6, 9)) -> list:
    """Returns a plausible fire_events list matching the schema expected by attribution.rules.fire_attribution_rule."""
    return [
        {
            "distance_km": 42.0,
            "bearing_deg": 315.0,
            "detected_hours_ago": hours_ago_options[0],
        },
        {
            "distance_km": 78.0,
            "bearing_deg": 320.0,
            "detected_hours_ago": hours_ago_options[1],
        },
    ]
