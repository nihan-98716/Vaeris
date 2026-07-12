"""
backend/api/routes/forecast.py

FastAPI router handling AQI trajectory forecasting queries with Redis TTL caching
and PostGIS spatial data joins.
"""

import json

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from backend.api.cache import get_cached_value, set_cached_value
from backend.api.schemas import ForecastRequest, ForecastResponse
from backend.config import settings
from backend.db import queries
from backend.logging import logger
from backend.models.forecasting import inference
from backend.models.schemas import LatLon

router = APIRouter(prefix="/forecast", tags=["Forecasting"])


def database_history_provider(location: LatLon) -> pd.DataFrame:
    """
    Fetches raw history from PostGIS, falling back to offline snapshots
    if database records are missing or insufficient.
    """
    station = queries.find_nearest_station(location.latitude, location.longitude)
    if station:
        logger.info(
            f"Nearest station for coordinates ({location.latitude}, {location.longitude}) "
            f"is {station['name']} (ID: {station['id']}, Distance: {station['distance']:.2f}m)"
        )
        df = queries.get_recent_station_history(station["id"], limit_hours=48)
        if len(df) >= 24:
            return df
        logger.warning(
            f"Insufficient database history ({len(df)} rows) for station '{station['id']}'. "
            f"Falling back to offline snapshots."
        )

    # Fallback to offline Delhi snapshot data
    logger.info("Using offline snapshot history fallback.")
    # Fallback default: Anand Vihar (DL001)
    fallback_station = "DL001"
    if station and station["id"] in ["DL001", "DL002", "DL003", "DL004", "DL005"]:
        fallback_station = station["id"]
    return queries.get_offline_snapshot_history(
        fallback_station, limit_hours=48
    )


@router.get("", response_model=ForecastResponse)
async def get_forecast(req: ForecastRequest = Depends()):
    """
    Predicts the future AQI trajectory for the given coordinate and horizon.
    Utilizes Redis caching to accelerate repetitive queries.
    """
    cache_key = f"forecast:{req.latitude:.4f}:{req.longitude:.4f}:{req.horizon_hours}"

    # 1. Try to read from Redis cache
    cached_data = get_cached_value(cache_key)
    if cached_data:
        try:
            logger.info(f"Cache hit for key: {cache_key}")
            return ForecastResponse(**json.loads(cached_data))
        except Exception:
            logger.error("Failed to parse cached forecast data", exc_info=True)

    # 2. Run prediction pipeline
    location = LatLon(latitude=req.latitude, longitude=req.longitude)
    try:
        # Load history
        history_df = database_history_provider(location)
        if history_df.empty:
            raise HTTPException(
                status_code=404,
                detail="Unable to fetch sufficient historical measurements for forecasting.",
            )

        # Execute LightGBM model prediction
        forecast_result = inference.predict_from_history(
            history_df, location, req.horizon_hours
        )

        response_data = ForecastResponse(
            value=forecast_result.value,
            lower_bound=forecast_result.lower_bound,
            upper_bound=forecast_result.upper_bound,
            confidence_tier=forecast_result.confidence_tier,
            model_version=forecast_result.model_version,
            horizon_hours=forecast_result.horizon_hours,
        )

        # 3. Write back to Redis cache
        set_cached_value(
            cache_key,
            json.dumps(response_data.model_dump()),
            ttl_seconds=settings.redis.default_ttl_forecast,
        )

        return response_data
    except Exception as e:
        logger.error("Forecasting endpoint execution failed", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Internal model prediction error: {str(e)}",
        ) from e
