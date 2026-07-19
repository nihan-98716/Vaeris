"""
backend/api/schemas.py

Pydantic schemas representing request and response shapes for Vaeris API endpoints.
Provides validation and documentation boundaries.
"""

from typing import Dict, List, Optional

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


class WardInfo(BaseModel):
    """
    Validated municipal ward boundary spatial details.
    """

    ward_id: str = Field(..., description="Unique MCD Ward identifier")
    ward_name: str = Field(..., description="Name of the municipal ward")
    zone_name: str = Field(..., description="Name of the municipal zone")
    city: str = Field(default="Delhi", description="City governing authority")


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
    ward_info: WardInfo = Field(
        default=None, description="Municipal ward and zone spatial details"
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


class ScenarioRequest(BaseModel):
    """
    Validated request for before/after scenario approximation.
    """

    current_aqi: float = Field(
        ..., description="Current measured AQI at the target location", ge=0.0
    )
    budget: float = Field(
        default=5000.0, description="Available monetary/resource budget limit", ge=0.0
    )
    inspectors: int = Field(
        default=5, description="Available inspector personnel count", ge=0
    )
    max_travel_time_hours: float = Field(
        default=3.0, description="Maximum travel/dispatch time limit in hours", ge=0.0
    )
    primary_cause: str = Field(
        default="traffic",
        description="Dominant pollution source driving current AQI. "
        "One of: 'traffic', 'agricultural_burning', 'industrial'.",
    )


class ScenarioResponse(BaseModel):
    """
    Validated response for the projected AQI scenario calculation.
    Combines the optimizer recommendation with the source-weighted AQI projection.
    """

    # Decision optimizer outputs (pass-through summary)
    decision: DecisionResponse = Field(
        ..., description="Optimal intervention set from the decision optimizer"
    )

    # Scenario projection outputs
    projected_aqi: float = Field(
        ...,
        description="Projected (estimated) AQI after applying recommended interventions",
    )
    reduction_applied: float = Field(
        ..., description="Weighted AQI reduction after accounting for source targeting"
    )
    source_weight_factor: float = Field(
        ...,
        description="Average effectiveness weight of selected interventions vs. dominant source (0–1)",
    )
    confidence: str = Field(
        ...,
        description="Approximation confidence: 'high' (≥0.7), 'medium' (≥0.4), or 'low' (<0.4)",
    )
    current_aqi: float = Field(..., description="Echo of the input current AQI")
    percent_reduction: float = Field(
        ..., description="Percentage reduction in AQI relative to current"
    )
    disclaimer: str = Field(
        default=(
            "Projected AQI is an indicative estimate. "
            "Actual outcomes depend on meteorological conditions, enforcement fidelity, "
            "and source variability not modelled here."
        ),
        description="Disclaimer for the projected AQI value",
    )


class EvidenceScoreResponse(BaseModel):
    """
    Consolidated confidence score and check verification status items.
    """

    confidence_score: float = Field(
        ..., description="Overall confidence score as a percentage (0-100)"
    )
    checklist: List[str] = Field(
        ..., description="Verification checklist of signals cross-checked"
    )
    status: str = Field(
        ..., description="Confidence status level ('high' | 'medium' | 'low')"
    )


class InvestigateRequest(BaseModel):
    """
    Validated request parameters for running the full orchestrator investigation pipeline.
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
    budget: float = Field(
        default=5000.0, description="Available monetary/resource budget limit", ge=0.0
    )
    inspectors: int = Field(
        default=5, description="Available inspector personnel count", ge=0
    )
    max_travel_time_hours: float = Field(
        default=3.0, description="Maximum travel/dispatch time limit in hours", ge=0.0
    )
    enable_llm: bool = Field(
        default=True, description="Flag to enable LLM summary generation"
    )


class InvestigateResponse(BaseModel):
    """
    Consolidated investigation report returned by the agent orchestrator.
    """

    latitude: float = Field(..., description="Target latitude coordinate")
    longitude: float = Field(..., description="Target longitude coordinate")
    current_aqi: float = Field(
        ..., description="Current measured AQI at target location"
    )
    primary_cause: str = Field(..., description="Attributed primary cause of pollution")
    forecast: ForecastResponse = Field(..., description="AQI forecasting results")
    attribution: AttributionResponse = Field(
        ..., description="Pollution source attribution results"
    )
    decision: DecisionResponse = Field(
        ..., description="Optimal intervention decisions"
    )
    scenario: ScenarioResponse = Field(
        ..., description="Before/after scenario projections"
    )
    evidence_score: EvidenceScoreResponse = Field(
        ..., description="Consolidated verification and confidence checklist"
    )
    summary: str = Field(
        ..., description="Natural language summary prose of the investigation"
    )
    llm_error: bool = Field(
        default=False,
        description="True if LLM summary failed/timed out, falling back to deterministic summary",
    )


class AdvisoryRequest(BaseModel):
    """
    Validated request parameters for generating citizen health advisory alerts.
    """

    current_aqi: float = Field(..., description="Current measured AQI value", ge=0.0)
    forecasted_aqi: Optional[float] = Field(
        default=None, description="Forecasted 24h AQI value (optional)"
    )
    primary_cause: str = Field(
        default="traffic", description="Attributed primary cause of pollution spike"
    )
    language: str = Field(
        default="en",
        description="Target language code: 'en' (English), 'hi' (Hindi), 'kn' (Kannada), or 'ta' (Tamil)",
        pattern="^(en|hi|kn|ta)$",
    )
    enable_llm: bool = Field(
        default=True, description="Flag to enable LLM summary generation"
    )


class AdvisoryResponse(BaseModel):
    """
    Validated response model for the citizen health advisory alert.
    """

    aqi_category: str = Field(..., description="AQI severity band category")
    health_message: str = Field(..., description="Summary alert warning message")
    recommended_precautions: List[str] = Field(
        ..., description="List of recommended precaution bullet points"
    )
    language: str = Field(..., description="Assigned response language code")
    llm_error: bool = Field(
        default=False,
        description="True if LLM generation failed/timed out, falling back to deterministic template",
    )


class CityComparisonReport(BaseModel):
    """
    Comparison metrics summary for a specific city.
    """

    city_name: str = Field(..., description="Name of the city")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    current_aqi: float = Field(..., description="Current measured AQI value")
    primary_cause: str = Field(
        ..., description="Attributed primary cause of pollution spike"
    )
    projected_aqi: float = Field(..., description="Projected AQI after optimization")
    reduction_pct: float = Field(..., description="Percentage of AQI reduction")
    health_benefit: float = Field(
        ..., description="Indicative Respiratory Risk Reduction"
    )
    status_level: str = Field(
        ..., description="Attribution confidence status level (high/medium/low)"
    )
    optimal_actions: List[str] = Field(
        ..., description="Top recommended intervention actions"
    )


class MultiCityResponse(BaseModel):
    """
    List of comparison reports across multiple target cities.
    """

    cities: List[CityComparisonReport] = Field(
        ..., description="Curated list of city comparison reports"
    )
