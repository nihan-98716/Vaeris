"""
backend/db/queries.py

PostGIS spatial and attribute queries supporting model feature stores and live API routes.
"""

import math
import os
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from backend.db.connection import get_db_cursor
from backend.logging import logger

# Bounding box center/defaults for Delhi
DEFAULT_LAT = 28.6139
DEFAULT_LON = 77.2090


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two coordinates in kilometers.
    """
    R = 6371.0  # Earth's radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


# Compass bearing between two coordinates in degrees (0-360)
def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlon = math.radians(lon2 - lon1)
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
        dlon
    )

    bearing = math.atan2(y, x)
    return (math.degrees(bearing) + 360) % 360


def find_nearest_station(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Finds the nearest monitoring station to the given coordinates using PostGIS.
    """
    query = """
        SELECT id, name, city, latitude, longitude,
               ST_Distance(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) AS distance
        FROM monitoring_stations
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT 1;
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, (lon, lat, lon, lat))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception:
        logger.error("Failed to query nearest station from PostGIS", exc_info=True)
        return None


def _compute_row_fire_features(
    lat: float, lon: float, ts: pd.Timestamp, wind_dir: float, fire_list: list
) -> tuple[int, int, int]:
    f_50 = 0
    f_100 = 0
    upwind = False

    t_start = ts - pd.Timedelta(hours=24)
    t_end = ts

    for f in fire_list:
        f_ts = pd.to_datetime(f["acq_datetime"])
        # Handle tz-awareness comparison
        if f_ts.tzinfo is None and ts.tzinfo is not None:
            f_ts = f_ts.replace(tzinfo=ts.tzinfo)
        elif f_ts.tzinfo is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=f_ts.tzinfo)

        if t_start <= f_ts <= t_end:
            dist_km = haversine_distance(lat, lon, f["latitude"], f["longitude"])
            if dist_km <= 100.0:
                f_100 += 1
                if dist_km <= 50.0:
                    f_50 += 1

                # Upwind flag check
                bearing = calculate_bearing(lat, lon, f["latitude"], f["longitude"])
                diff = abs(bearing - wind_dir) % 360
                ang_diff = min(diff, 360 - diff)
                if ang_diff <= 30.0:
                    upwind = True

    return f_50, f_100, int(upwind)


def get_recent_station_history(station_id: str, limit_hours: int = 48) -> pd.DataFrame:
    """
    Retrieves the raw hourly history for a station from PostGIS.
    Builds the exact schema required by features.py.
    """
    query = """
        SELECT a.timestamp, a.aqi,
               s.id AS station_id, s.latitude, s.longitude, s.name AS station_name,
               w.temperature, w.humidity, w.wind_speed, w.wind_deg AS wind_direction,
               COALESCE(osm.road_count, 100) / 210.0 AS road_density_500m
        FROM aqi_measurements a
        JOIN monitoring_stations s ON a.station_id = s.id
        LEFT JOIN LATERAL (
            SELECT w.temperature, w.humidity, w.wind_speed, w.wind_deg
            FROM weather_readings w
            ORDER BY abs(extract(epoch from (w.timestamp - a.timestamp))) ASC
            LIMIT 1
        ) w ON true
        LEFT JOIN LATERAL (
            SELECT road_count
            FROM osm_road_cache
            LIMIT 1
        ) osm ON true
        WHERE a.station_id = %s
        ORDER BY a.timestamp DESC
        LIMIT %s;
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, (station_id, limit_hours))
            rows = cursor.fetchall()

        if not rows:
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame([dict(r) for r in rows])
        # Sort chronologically as expected by features.py
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Add static and calculated defaults
        df["precipitation"] = 0.0
        df["boundary_layer_height"] = 450.0

        # Map station type category
        df["land_use_category"] = "mixed"

        # Compute fire hotspots within 50km/100km for each row dynamically
        fire_query = """
            SELECT latitude, longitude, acq_datetime
            FROM fire_hotspots
            WHERE acq_datetime >= %s AND acq_datetime <= %s;
        """

        if not df.empty:
            min_ts = df["timestamp"].min()
            max_ts = df["timestamp"].max()
            with get_db_cursor() as cursor:
                cursor.execute(fire_query, (min_ts, max_ts))
                fires = cursor.fetchall()
        else:
            fires = []

        fire_list = [dict(f) for f in fires]

        # For each row, calculate fire counts and upwind flags
        fire_counts_50 = []
        fire_counts_100 = []
        fire_upwind_flags = []

        for _idx, row in df.iterrows():
            f_50, f_100, upwind = _compute_row_fire_features(
                row["latitude"],
                row["longitude"],
                row["timestamp"],
                row["wind_direction"] or 180.0,
                fire_list,
            )
            fire_counts_50.append(f_50)
            fire_counts_100.append(f_100)
            fire_upwind_flags.append(upwind)

        df["fire_count_50km"] = fire_counts_50
        df["fire_count_100km"] = fire_counts_100
        df["fire_upwind_flag"] = fire_upwind_flags

        return df
    except Exception:
        logger.error(
            f"Failed to query recent station history for '{station_id}' from PostGIS",
            exc_info=True,
        )
        return pd.DataFrame()


def get_offline_snapshot_history(
    station_id: Optional[str] = None, limit_hours: int = 48
) -> pd.DataFrame:
    """
    Fallback method loading historical data snapshot from CSV to support offline demos.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = base_dir / "data" / "processed" / "delhi_flat_history.csv"
    if not csv_path.exists():
        # try root/data path
        csv_path = base_dir / "data" / "delhi_flat_history.csv"
    csv_path = str(csv_path)

    if not os.path.exists(csv_path):
        logger.error(f"Offline history snapshot CSV not found at: {csv_path}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

        if station_id:
            df = df[df["station_id"] == station_id]

        df = df.sort_values("timestamp")
        return df.tail(limit_hours).reset_index(drop=True)
    except Exception:
        logger.error("Failed to load offline snapshot history CSV", exc_info=True)
        return pd.DataFrame()
