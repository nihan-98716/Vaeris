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
from backend.api.schemas import AttributionRequest, AttributionResponse, WardInfo
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
        from pathlib import Path

        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        snapshot_path = str(
            base_dir / "data" / "snapshots" / "delhi_2024-11-13_to_2024-11-18.json"
        )
        if os.path.exists(snapshot_path):
            try:
                with open(snapshot_path, "r") as f:
                    snapshot_data = json.load(f)
                # Ensure t_start and t_end are timezone-naive for safe comparison
                t_start_naive = t_start.tz_localize(None) if t_start.tzinfo is not None else t_start
                t_end_naive = t_end.tz_localize(None) if t_end.tzinfo is not None else t_end

                for f in snapshot_data.get("fire_data", []):
                    f_ts = pd.to_datetime(f["acq_datetime"])
                    f_ts_naive = f_ts.tz_localize(None) if f_ts.tzinfo is not None else f_ts
                    if t_start_naive <= f_ts_naive <= t_end_naive:
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
    latest_ts_naive = latest_ts.tz_localize(None) if latest_ts.tzinfo is not None else latest_ts

    for f in db_fires:
        f_lat = f["latitude"]
        f_lon = f["longitude"]
        dist = queries.haversine_distance(
            location.latitude, location.longitude, f_lat, f_lon
        )
        if dist <= 100.0:
            f_ts = pd.to_datetime(f["acq_datetime"])
            f_ts_naive = f_ts.tz_localize(None) if f_ts.tzinfo is not None else f_ts
            hours_ago = (latest_ts_naive - f_ts_naive).total_seconds() / 3600.0
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


def _find_closest_representative_station(lat: float, lon: float) -> str:
    """
    Finds the closest representative offline station ID based on coordinates.
    """
    stations = {
        "DL001": (28.6476, 77.3158),
        "DL002": (28.8228, 77.0943),
        "DL003": (28.7972, 77.0589),
        "DL004": (28.5660, 77.1866),
        "DL005": (28.6364, 77.2010),
    }
    best_id = "DL001"
    best_dist = float("inf")
    for s_id, (s_lat, s_lon) in stations.items():
        dist = queries.haversine_distance(lat, lon, s_lat, s_lon)
        if dist < best_dist:
            best_dist = dist
            best_id = s_id
    return best_id


def gather_attribution_signals(location: LatLon) -> tuple[dict, list[str]]:
    """
    Queries history and active environmental readings for a coordinate,
    compiles them into a signals dictionary, and identifies unavailable/degraded sources.
    """
    unavailable_sources = []

    # 1. Query nearest station and history (online DB first, fallback to offline)
    station = queries.find_nearest_station(location.latitude, location.longitude)
    if station:
        history_df = queries.get_recent_station_history(station["id"], limit_hours=48)
    else:
        history_df = pd.DataFrame()

    # If database history is missing or insufficient (e.g., single row), fallback to offline snapshot
    if len(history_df) < 10:
        logger.info(
            "Attribution: Insufficient database history. Using offline snapshot history fallback."
        )
        fallback_station = _find_closest_representative_station(
            location.latitude, location.longitude
        )
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
        logger.warning("Weather metrics are missing; degrading attribution rules.")
        unavailable_sources.append("agricultural_burning")  # requires wind trajectory
        wind_dir = 180.0
        wind_speed = 0.0

    # Build fire events list
    t_start = latest_ts - pd.Timedelta(hours=24)
    t_end = latest_ts
    db_fires = _get_active_fires_for_attribution(t_start, t_end, latest_ts)
    fire_events = _extract_fire_events_for_attribution(db_fires, location, latest_ts)

    # Spatial land use & road density resolution based on location
    lat, lon = location.latitude, location.longitude
    if lat >= 28.75 or (lat <= 28.56 and lon >= 77.26):  # Bawana, Narela, Okhla
        land_use = "industrial"
        road_dens = 0.35
    elif lon >= 77.30:  # Anand Vihar / Border
        land_use = "agricultural"
        road_dens = 0.25
    elif (28.62 <= lat <= 28.68 and 77.10 <= lon <= 77.25) or (abs(lat - 28.6286) < 0.02 and abs(lon - 77.2410) < 0.02):  # Punjabi Bagh, ITO
        land_use = "traffic"
        road_dens = 0.88
    else:
        land_use = latest_row.get("land_use_category", "mixed")
        road_dens = latest_row.get("road_density_500m", 0.55)

    # Compile the final signals structure
    signals = {
        "fire_events": fire_events,
        "wind_direction_deg": wind_dir,
        "wind_speed_ms": wind_speed,
        "road_density_500m": road_dens,
        "land_use_category": land_use,
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
            logger.error("Failed to parse cached attribution data", exc_info=True)

    # 2. Compile signals and execute rule engine
    location = LatLon(latitude=req.latitude, longitude=req.longitude)
    try:
        signals, unavailable_sources = gather_attribution_signals(location)
        result = rule_engine.run_attribution(
            signals, unavailable_sources=unavailable_sources
        )

        ward_data = queries.find_ward_for_location(req.latitude, req.longitude)
        ward_info = WardInfo(
            ward_id=ward_data["ward_id"],
            ward_name=ward_data["ward_name"],
            zone_name=ward_data["zone_name"],
            city=ward_data.get("city", "Delhi"),
        )

        response_data = AttributionResponse(
            primary_cause=result.primary_cause,
            confidence_breakdown=result.confidence_breakdown,
            evidence=result.evidence,
            degraded_sources=result.degraded_sources,
            ward_info=ward_info,
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
