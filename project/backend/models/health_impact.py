"""
backend/models/health_impact.py

Indicative respiratory exposure risk estimation — ML Model Specification,
Section 8. This is a coefficient-based calculation, NOT a trained model.

IMPORTANT: DEFAULT_RELATIVE_RISK_PER_UNIT_PM25 below is a placeholder and
MUST be replaced with the exact coefficient your team extracts from the
cited WHO Global Air Quality Guidelines (2021) and/or GBD relative-risk
functions (see ML Model Specification, Section 3.6) before this number is
shown to anyone outside the team. Do not present the placeholder value as
a validated figure.
"""

from dataclasses import dataclass

from backend.models.schemas import HealthImpactResult

DISCLAIMER = (
    "Indicative respiratory exposure risk, estimated using published WHO/Lancet "
    "exposure-response coefficients. Not a clinical or epidemiological forecast."
)

# PLACEHOLDER — replace with the exact cited coefficient before using this
# for anything beyond internal development. Do not treat this number as
# validated; it exists so the calculation shape is correct and testable.
DEFAULT_RELATIVE_RISK_PER_UNIT_PM25 = 0.0104


def estimate_exposure_risk(
    forecast_pm25: float,
    baseline_pm25: float,
    exposed_population: int,
    relative_risk_per_unit: float = DEFAULT_RELATIVE_RISK_PER_UNIT_PM25,
) -> HealthImpactResult:
    """
    Very deliberately simple: risk scales linearly with (forecast - baseline)
    PM2.5 concentration and the exposed population. This is NOT a clinical
    dose-response model — it is an indicative, order-of-magnitude signal
    intended to rank interventions relative to each other (used by the
    decision-optimization layer), not to make individual health claims.
    """
    excess_concentration = max(0.0, forecast_pm25 - baseline_pm25)
    indicative_risk_score = excess_concentration * relative_risk_per_unit * exposed_population

    return HealthImpactResult(
        indicative_risk_score=round(indicative_risk_score, 2),
        exposed_population=exposed_population,
        disclaimer=DISCLAIMER,
    )
