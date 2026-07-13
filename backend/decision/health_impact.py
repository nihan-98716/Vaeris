"""
backend/decision/health_impact.py

Calculates the indicative health benefit score for interventions based on the
respiratory exposure risk coefficients from WHO (2021) guidelines.
Never uses "DALY" in user-facing or internal indicator strings.
"""

from backend.models.health_impact import DEFAULT_RELATIVE_RISK_PER_UNIT_PM25, DISCLAIMER

def calculate_health_benefit(aqi_reduction: float, population_affected: int) -> float:
    """
    Computes the indicative health benefit score of an intervention.
    This represents the expected reduction in the exposure risk score for the population.
    
    Formula:
        benefit = AQI_reduction * relative_risk_coefficient * population
    """
    return round(aqi_reduction * DEFAULT_RELATIVE_RISK_PER_UNIT_PM25 * population_affected, 2)
