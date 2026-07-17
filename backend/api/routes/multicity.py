"""
backend/api/routes/multicity.py

FastAPI router handling comparative reports across four curated Indian cities:
Delhi, Mumbai, Chennai, and Bengaluru.
Supports live DB queries with fallback to curated high-fidelity offline snapshots.
"""

import requests
from fastapi import APIRouter, HTTPException

from backend.api.schemas import CityComparisonReport, MultiCityResponse
from backend.config import settings
from backend.db.connection import get_db_cursor
from backend.db.queries import find_nearest_station
from backend.logging import logger

router = APIRouter(prefix="/multicity", tags=["Multi-City Comparison"])

# Curated reference cities data (Offline Fallbacks)
CURATED_CITIES = [
    {
        "city_name": "Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "current_aqi": 320.0,
        "primary_cause": "agricultural_burning",
        "projected_aqi": 260.0,
        "reduction_pct": 18.75,
        "health_benefit": 420.0,
        "status_level": "high",
        "optimal_actions": [
            "Enforce Stubble Burning Ban",
            "Enforce Waste Burning Fines",
        ],
    },
    {
        "city_name": "Mumbai",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "current_aqi": 145.0,
        "primary_cause": "traffic",
        "projected_aqi": 110.0,
        "reduction_pct": 24.14,
        "health_benefit": 280.0,
        "status_level": "medium",
        "optimal_actions": [
            "Implement Odd-Even Vehicle Rationing",
            "Deploy Road Sprinklers",
        ],
    },
    {
        "city_name": "Bengaluru",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "current_aqi": 165.0,
        "primary_cause": "traffic",
        "projected_aqi": 125.0,
        "reduction_pct": 24.24,
        "health_benefit": 310.0,
        "status_level": "medium",
        "optimal_actions": [
            "Implement Odd-Even Vehicle Rationing",
            "Deploy Road Sprinklers",
        ],
    },
    {
        "city_name": "Chennai",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "current_aqi": 115.0,
        "primary_cause": "industrial",
        "projected_aqi": 92.0,
        "reduction_pct": 20.00,
        "health_benefit": 190.0,
        "status_level": "low",
        "optimal_actions": [
            "Restrict Coal-Fired Industrial Output",
            "Halt Construction Activities",
        ],
    },
]


def fetch_latest_aqi_for_station(station_id: str) -> float:
    """Queries the DB for the latest AQI reading of a given station."""
    query = """
        SELECT aqi FROM aqi_measurements
        WHERE station_id = %s
        ORDER BY timestamp DESC
        LIMIT 1;
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, (station_id,))
            row = cursor.fetchone()
            return float(row["aqi"]) if row else None
    except Exception:
        logger.error(
            f"Failed to query latest AQI for station {station_id}", exc_info=True
        )
        return None


def convert_pm25_to_aqi(pm25: float) -> float:
    """
    Converts PM2.5 concentration (ug/m3) to CPCB Indian AQI index.
    """
    if pm25 <= 30.0:
        return (pm25 * 50.0) / 30.0
    elif pm25 <= 60.0:
        return 50.0 + (pm25 - 30.0) * (50.0 / 30.0)
    elif pm25 <= 90.0:
        return 100.0 + (pm25 - 60.0) * (100.0 / 30.0)
    elif pm25 <= 120.0:
        return 200.0 + (pm25 - 90.0) * (100.0 / 30.0)
    elif pm25 <= 250.0:
        return 300.0 + (pm25 - 120.0) * (100.0 / 130.0)
    else:
        aqi = 400.0 + (pm25 - 250.0) * (100.0 / 150.0)
        return min(500.0, aqi)


def fetch_live_aqi_from_openaq(lat: float, lon: float) -> float:
    """
    Queries the live OpenAQ REST API using the configured X-API-Key
    to find the nearest active monitor and compute its current AQI.
    """
    api_key = settings.apis.openaq_api_key
    if not api_key:
        logger.warning("fetch_live_aqi_from_openaq: No API Key configured.")
        return None

    headers = {"X-API-Key": api_key}

    # Bounding box +/- 0.5 degrees around coordinates
    min_lon = lon - 0.5
    max_lon = lon + 0.5
    min_lat = lat - 0.5
    max_lat = lat + 0.5

    url_locs = "https://api.openaq.org/v3/locations"
    params_locs = {"bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}", "limit": 1}

    try:
        r = requests.get(url_locs, headers=headers, params=params_locs, timeout=10)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            logger.warning(
                f"fetch_live_aqi_from_openaq: No locations found near ({lat}, {lon})"
            )
            return None

        loc = results[0]
        loc_id = loc.get("id")

        # Build map of sensor ID -> parameter name
        sensor_to_param = {}
        for s in loc.get("sensors", []):
            sensor_to_param[s.get("id")] = s.get("parameter", {}).get("name")

        # Fetch latest measurements for this location
        url_latest = f"https://api.openaq.org/v3/locations/{loc_id}/latest"
        r_latest = requests.get(url_latest, headers=headers, timeout=10)
        r_latest.raise_for_status()
        latest_results = r_latest.json().get("results", [])

        pm25_val = None
        for item in latest_results:
            s_id = item.get("sensorsId")
            param = sensor_to_param.get(s_id)
            if param == "pm25":
                pm25_val = item.get("value")
                break

        if pm25_val is None and latest_results:
            pm25_val = latest_results[0].get("value")

        if pm25_val is not None:
            aqi = convert_pm25_to_aqi(pm25_val)
            logger.info(
                f"fetch_live_aqi_from_openaq: Coords ({lat}, {lon}) resolved to Loc {loc_id}, PM2.5 {pm25_val} -> AQI {aqi}"
            )
            return aqi

    except Exception as e:
        logger.error(
            f"fetch_live_aqi_from_openaq: Failed to fetch from OpenAQ for ({lat}, {lon}): {e}",
            exc_info=True,
        )

    return None


@router.get("", response_model=MultiCityResponse)
async def get_multi_city_comparison():
    """
    Fetches comparative metrics for Delhi, Mumbai, Chennai, and Bengaluru.
    Queries the live OpenAQ API directly using OpenAQ API credentials.
    """
    reports = []
    try:
        for city in CURATED_CITIES:
            # Query live AQI directly from OpenAQ REST API
            current_aqi = fetch_live_aqi_from_openaq(
                city["latitude"], city["longitude"]
            )

            # Fallback to local DB query or curated baseline if OpenAQ is unreachable/none
            if current_aqi is None:
                station = find_nearest_station(city["latitude"], city["longitude"])
                current_aqi = city["current_aqi"]
                if station:
                    latest_aqi = fetch_latest_aqi_for_station(station["id"])
                    if latest_aqi is not None and latest_aqi >= 100.0:
                        current_aqi = latest_aqi

            # Scale projected AQI proportionally to represent a reasonable target
            scale = current_aqi / city["current_aqi"]
            projected_aqi = round(city["projected_aqi"] * scale, 1)
            reduction_pct = (
                round(((current_aqi - projected_aqi) / current_aqi) * 100, 2)
                if current_aqi > 0
                else 0.0
            )
            health_benefit = round(city["health_benefit"] * scale, 1)

            reports.append(
                CityComparisonReport(
                    city_name=city["city_name"],
                    latitude=city["latitude"],
                    longitude=city["longitude"],
                    current_aqi=round(current_aqi, 1),
                    primary_cause=city["primary_cause"],
                    projected_aqi=projected_aqi,
                    reduction_pct=reduction_pct,
                    health_benefit=health_benefit,
                    status_level=(
                        "high"
                        if current_aqi > 200.0
                        else "medium" if current_aqi > 100.0 else "low"
                    ),
                    optimal_actions=city["optimal_actions"],
                )
            )

        return MultiCityResponse(cities=reports)

    except Exception as e:
        logger.error("API: Multi-city comparison endpoint failed", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal multi-city comparison error: {str(e)}",
        ) from e
