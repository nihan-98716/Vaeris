"""
backend/api/routes/attribution.py

FastAPI router handling physical air quality spike attribution queries with Redis TTL caching
and PostGIS spatial data joins.
"""

import json
import os

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from backend.api.cache import get_cached_value, set_cached_value
from backend.api.schemas import AttributionRequest, AttributionResponse
from backend.config import settings
from backend.db import queries
from backend.db.connection import get_db_cursor
from backend.logging import logger
from backend.models.attribution import rule_engine
from backend.models.schemas import LatLon

router = APIRouter(prefix="/attribution", tags=["Attribution"])


def _get_active_fires_for_attribution(
    t_start: pd.Timestamp, t_end: pd.Timestamp, latest_ts: pd.Timestamp
) -> list:
    """
    Queries fire hotspots in the last 24h from the database,
    falling back to Delhi snapshot JSON file if queries fail or return empty.
    """
    fire_query = """
        SELECT latitude, longitude, acq_datetime
        FROM fire_hotspots
        WHERE acq_datetime >= %s AND acq_datetime <= %s;
    """
    db_fires = []
    try:
        with get_db_cursor() as cursor:
            cursor.execute(fire_query, (t_start, t_end))
            db_fires = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.warning(
            f"PostGIS fire hotspot query failed: {e}. Falling back to snapshot."
        )

    if not db_fires:
        # Fallback: get fires from offline snapshot JSON
        logger.info(
            "Attribution: Fetching fires from offline snapshot database fallback."
        )
        snapshot_path = os.path.join(
            "C:\\Users\\Public\\Projects\\Vaeris",
            "data",
            "snapshots",
            "delhi_2024-11-13_to_2024-11-18.json",
        )
        if os.path.exists(snapshot_path):
            try:
                with open(snapshot_path, "r") as f:
                    snapshot_data = json.load(f)
                for f in snapshot_data.get("fire_data", []):
                    f_ts = pd.to_datetime(f["acq_datetime"])
                    # Align timezone
                    if f_ts.tzinfo is None and latest_ts.tzinfo is not None:
                        f_ts = f_ts.replace(tzinfo=latest_ts.tzinfo)
                    if t_start <= f_ts <= t_end:
                        db_fires.append(f)
            except Exception as err:
                logger.error(
                    "Failed to load fires from offline snapshot file",
                    exc_info=err,
                )

    return db_fires


def _extract_fire_events_for_attribution(
    db_fires: list, location: LatLon, latest_ts: pd.Timestamp
) -> list:
    """
    Computes distance, bearing, and hours_ago for each fire hotspot,
    retaining only those within 100km.
    """
    fire_events = []
    for f in db_fires:
        f_lat = f["latitude"]
        f_lon = f["longitude"]
        dist = queries.haversine_distance(
            location.latitude, location.longitude, f_lat, f_lon
        )
        if dist <= 100.0:
            f_ts = pd.to_datetime(f["acq_datetime"])
            if f_ts.tzinfo is None and latest_ts.tzinfo is not None:
                f_ts = f_ts.replace(tzinfo=latest_ts.tzinfo)
            hours_ago = (latest_ts - f_ts).total_seconds() / 3600.0
            bearing = queries.calculate_bearing(
                location.latitude, location.longitude, f_lat, f_lon
            )
            fire_events.append(
                {
                    "distance_km": dist,
                    "bearing_deg": bearing,
                    "detected_hours_ago": max(0.0, hours_ago),
                }
            )
    return fire_events


def gather_attribution_signals(location: LatLon) -> tuple[dict, list[str]]:
    """
    Queries history and active environmental readings for a coordinate,
    compiles them into a signals dictionary, and identifies unavailable/degraded sources.
    """
    unavailable_sources = []

    # 1. Query nearest station and history (online DB first, fallback to offline)
    station = queries.find_nearest_station(location.latitude, location.longitude)
    if station:
        history_df = queries.get_recent_station_history(
            station["id"], limit_hours=48
        )
    else:
        history_df = pd.DataFrame()

    if history_df.empty:
        # Fallback to offline Delhi snapshot
        logger.info("Attribution: Using offline snapshot history fallback.")
        fallback_station = "DL001"
        if (
            station
            and station["id"] in ["DL001", "DL002", "DL003", "DL004", "DL005"]
        ):
            fallback_station = station["id"]
        history_df = queries.get_offline_snapshot_history(
            fallback_station, limit_hours=48
        )

    if history_df.empty:
        raise ValueError(
            "No historical or snapshot measurements available for attribution."
        )

    # Get the latest record
    latest_row = history_df.iloc[-1]
    latest_ts = pd.to_datetime(latest_row["timestamp"])

    # Compute 24h rolling mean of AQI
    recent_aqi = history_df["aqi"].tail(24)
    aqi_rolling_mean_24h = recent_aqi.mean()

    # Weather fields check
    wind_dir = latest_row.get("wind_direction")
    wind_speed = latest_row.get("wind_speed")

    if wind_dir is None or wind_speed is None:
        logger.warning(
            "Weather metrics are missing; degrading attribution rules."
        )
        unavailable_sources.append(
            "agricultural_burning"
        )  # requires wind trajectory
        wind_dir = 180.0
        wind_speed = 0.0

    # Build fire events list
    t_start = latest_ts - pd.Timedelta(hours=24)
    t_end = latest_ts
    db_fires = _get_active_fires_for_attribution(t_start, t_end, latest_ts)
    fire_events = _extract_fire_events_for_attribution(
        db_fires, location, latest_ts
    )

    # Compile the final signals structure
    signals = {
        "fire_events": fire_events,
        "wind_direction_deg": wind_dir,
        "wind_speed_ms": wind_speed,
        "road_density_500m": latest_row.get("road_density_500m", 0.5),
        "land_use_category": latest_row.get("land_use_category", "mixed"),
        "aqi_now": latest_row["aqi"],
        "aqi_rolling_mean_24h": aqi_rolling_mean_24h,
        "hour_of_day": (latest_ts.hour + 5)
        % 24,  # Rough local time conversion (UTC+5:30)
    }

    return signals, unavailable_sources


@router.get("", response_model=AttributionResponse)
async def get_attribution(req: AttributionRequest = Depends()):
    """
    Resolves the physical cause of air pollution spikes at a coordinate.
    Utilizes Redis caching to accelerate repetitive queries.
    """
    cache_key = f"attribution:{req.latitude:.4f}:{req.longitude:.4f}"

    # 1. Try to read from Redis cache
    cached_data = get_cached_value(cache_key)
    if cached_data:
        try:
            logger.info(f"Cache hit for key: {cache_key}")
            return AttributionResponse(**json.loads(cached_data))
        except Exception:
            logger.error(
                "Failed to parse cached attribution data", exc_info=True
            )

    # 2. Compile signals and execute rule engine
    location = LatLon(latitude=req.latitude, longitude=req.longitude)
    try:
        signals, unavailable_sources = gather_attribution_signals(location)
        result = rule_engine.run_attribution(
            signals, unavailable_sources=unavailable_sources
        )

        response_data = AttributionResponse(
            primary_cause=result.primary_cause,
            confidence_breakdown=result.confidence_breakdown,
            evidence=result.evidence,
            degraded_sources=result.degraded_sources,
        )

        # 3. Write back to Redis cache
        set_cached_value(
            cache_key,
            json.dumps(response_data.model_dump()),
            ttl_seconds=settings.redis.default_ttl_attribution,
        )

        return response_data
    except Exception as e:
        logger.error("Attribution endpoint execution failed", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal attribution processing error: {str(e)}",
        ) from e
