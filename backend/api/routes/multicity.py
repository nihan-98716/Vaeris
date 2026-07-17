"""
backend/api/routes/multicity.py

FastAPI router handling comparative reports across four curated Indian cities:
Delhi, Mumbai, Chennai, and Bengaluru.
Supports live DB queries with fallback to curated high-fidelity offline snapshots.
"""

from fastapi import APIRouter, HTTPException

from backend.api.schemas import CityComparisonReport, MultiCityResponse
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


@router.get("", response_model=MultiCityResponse)
async def get_multi_city_comparison():
    """
    Fetches comparative metrics for Delhi, Mumbai, Chennai, and Bengaluru.
    Queries the database for live measurements if available; otherwise falls back
    to curated representative snapshots.
    """
    reports = []
    try:
        for city in CURATED_CITIES:
            # Attempt to query live station near the city center
            station = find_nearest_station(city["latitude"], city["longitude"])
            current_aqi = city["current_aqi"]

            if station:
                latest_aqi = fetch_latest_aqi_for_station(station["id"])
                if latest_aqi is not None:
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
                    status_level=city["status_level"],
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
