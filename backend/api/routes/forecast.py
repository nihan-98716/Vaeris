"""
backend/api/routes/forecast.py

FastAPI router handling AQI trajectory forecasting queries.
"""

from fastapi import APIRouter, Depends

from backend.api.schemas import ForecastRequest, ForecastResponse

router = APIRouter(prefix="/forecast", tags=["Forecasting"])


@router.get("", response_model=ForecastResponse)
async def get_forecast(req: ForecastRequest = Depends()):
    """
    Fetch future air quality trajectory predictions for a given coordinate.
    """
    # Mock data for initial API scaffolding/schema validation
    confidence_tier = "reliable" if req.horizon_hours <= 48 else "experimental"
    return ForecastResponse(
        value=150.0,
        lower_bound=135.0,
        upper_bound=165.0,
        confidence_tier=confidence_tier,
        model_version="v_mvp_mock",
        horizon_hours=req.horizon_hours,
    )
