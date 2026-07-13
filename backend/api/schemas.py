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


class DecisionRequest(BaseModel):
    """
    Validated request parameters for intervention decision-optimization.
    """

    budget: float = Field(
        default=5000.0, description="Available monetary/resource budget limit", ge=0.0
    )
    inspectors: int = Field(
        default=5, description="Available inspector personnel count", ge=0
    )
    max_travel_time_hours: float = Field(
        default=3.0, description="Maximum travel/dispatch time limit in hours", ge=0.0
    )


class InterventionDetail(BaseModel):
    """
    Detailed output for a single selected intervention.
    """

    id: str = Field(..., description="Unique intervention identifier")
    name: str = Field(..., description="Name of the intervention action")
    description: str = Field(
        ..., description="Human-readable description of the action"
    )
    cost: float = Field(..., description="Cost of executing the action")
    inspectors_required: int = Field(..., description="Number of inspectors required")
    travel_time_hours: float = Field(..., description="Travel time in hours")
    aqi_reduction: float = Field(..., description="Expected raw AQI reduction")
    population_affected: int = Field(..., description="Affected population size")
    health_benefit: float = Field(..., description="Indicative health benefit score")
    score: float = Field(..., description="Weighted objective score")


class DecisionResponse(BaseModel):
    """
    Validated response model for optimal decisions.
    """

    selected_interventions: List[InterventionDetail] = Field(
        ..., description="Optimal subset of selected interventions"
    )
    total_aqi_reduction: float = Field(
        ..., description="Total combined expected AQI reduction"
    )
    total_cost: float = Field(..., description="Total cost of selected interventions")
    total_inspectors_used: int = Field(..., description="Total inspectors deployed")
    total_population_affected: int = Field(..., description="Total population affected")
    total_health_benefit: float = Field(
        ..., description="Total combined indicative health benefit score"
    )
    remaining_budget: float = Field(..., description="Unspent budget")
    remaining_inspectors: int = Field(..., description="Unused inspectors")
    disclaimer: str = Field(
        default="Indicative respiratory exposure risk, estimated using published WHO/Lancet exposure-response coefficients. Not a clinical or epidemiological forecast.",
        description="Medical and predictive disclaimer",
    )
