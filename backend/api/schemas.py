"""
backend/api/schemas.py

Pydantic schemas representing request and response shapes for Vaeris API endpoints.
Provides validation and documentation boundaries.
"""

from typing import Dict, List

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    """
    Validated request parameters for predicting AQI trajectories.
    """

    latitude: float = Field(
        ..., description="Latitude coordinate, WGS84 format", ge=-90.0, le=90.0
    )
    longitude: float = Field(
        ..., description="Longitude coordinate, WGS84 format", ge=-180.0, le=180.0
    )
    horizon_hours: int = Field(
        default=24,
        description="Forecast horizon range in hours (1-72)",
        ge=1,
        le=72,
    )


class ForecastResponse(BaseModel):
    """
    Validated response model matching ForecastResult format.
    """

    value: float = Field(..., description="Median (q50) predicted AQI value")
    lower_bound: float = Field(..., description="Lower confidence interval (q10) bound")
    upper_bound: float = Field(..., description="Upper confidence interval (q90) bound")
    confidence_tier: str = Field(
        ..., description="Model confidence tier ('reliable' | 'experimental')"
    )
    model_version: str = Field(..., description="Registered version identifier")
    horizon_hours: int = Field(..., description="Forecast horizon range in hours")


class AttributionRequest(BaseModel):
    """
    Validated request parameters for physical source attribution.
    """

    latitude: float = Field(
        ..., description="Latitude coordinate, WGS84 format", ge=-90.0, le=90.0
    )
    longitude: float = Field(
        ..., description="Longitude coordinate, WGS84 format", ge=-180.0, le=180.0
    )


class AttributionResponse(BaseModel):
    """
    Validated response model matching AttributionResult format.
    """

    primary_cause: str = Field(
        ..., description="Primary attributed cause of AQI spike/elevation"
    )
    confidence_breakdown: Dict[str, float] = Field(
        ..., description="Normalized confidence breakdown by source type (sums to 1.0)"
    )
    evidence: List[str] = Field(
        ..., description="Traceable evidence list supporting the attribution"
    )
    degraded_sources: List[str] = Field(
        ..., description="Sources excluded due to missing signals or sensor failures"
    )
