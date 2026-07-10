"""
backend/models/schemas.py

Shared data structures used across the forecasting model, attribution engine,
and health-impact module. Kept dependency-free (stdlib only) so this module
can be imported by any layer (models, API, tests) without pulling in
LightGBM/SHAP/etc.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class LatLon:
    """A single geographic point, WGS84 (EPSG:4326)."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class ForecastResult:
    """
    Output of forecasting.inference.predict().

    This exact shape is the interface contract referenced throughout the
    ML Model Specification (Section 6.11). It must not change between the
    MVP model (Phase 2) and the depth-pass quantile model (Phase 6) — only
    the model artifacts backing it change.
    """

    value: float  # median (q50) prediction
    lower_bound: float  # q10 prediction (equals `value` if only a point-estimate model is registered)
    upper_bound: float  # q90 prediction (equals `value` if only a point-estimate model is registered)
    confidence_tier: str  # "reliable" (<=48h) or "experimental" (>48h)
    model_version: str  # version string from the loaded metadata.json
    horizon_hours: int  # the horizon this prediction was made for


@dataclass(frozen=True)
class RuleResult:
    """Raw output of a single attribution rule, before normalization."""

    source: str
    strength: float  # 0.0-1.0, raw trigger strength, not yet normalized across rules
    evidence: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AttributionResult:
    """Output of attribution.rule_engine.run_attribution()."""

    primary_cause: str
    confidence_breakdown: Dict[str, float]  # normalized, sums to 1.0
    evidence: List[str]
    degraded_sources: List[str] = field(
        default_factory=list
    )  # sources excluded due to missing data


@dataclass(frozen=True)
class HealthImpactResult:
    """Output of health_impact.estimate_exposure_risk()."""

    indicative_risk_score: float
    exposed_population: int
    disclaimer: str
