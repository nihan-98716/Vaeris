"""
backend/api/routes/attribution.py

FastAPI router handling physical air quality spike attribution queries.
"""

from fastapi import APIRouter, Depends

from backend.api.schemas import AttributionRequest, AttributionResponse

router = APIRouter(prefix="/attribution", tags=["Attribution"])


@router.get("", response_model=AttributionResponse)
async def get_attribution(req: AttributionRequest = Depends()):
    """
    Query physical source attribution for air pollution spikes at a coordinate.
    """
    # Mock data for initial API scaffolding/schema validation
    return AttributionResponse(
        primary_cause="traffic",
        confidence_breakdown={
            "traffic": 0.7,
            "agricultural_burning": 0.2,
            "industrial": 0.1,
        },
        evidence=[
            "Road density near station (0.85) exceeds high-traffic threshold (0.60)",
            "AQI spike occurs during a typical commute-hour window (hour 8)",
        ],
        degraded_sources=[],
    )
