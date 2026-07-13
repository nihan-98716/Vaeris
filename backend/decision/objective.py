"""
backend/decision/objective.py

Formulates the multi-objective decision score using normalized terms and
weights loaded dynamically from config/weights.yaml.
"""

from typing import Any, Dict

import backend.config

# Default weights as specified in the PRD/implementation plan
DEFAULT_WEIGHTS = {"aqi": 0.45, "population": 0.25, "health": 0.20, "cost": 0.10}


def get_optimizer_weights() -> Dict[str, float]:
    """
    Returns the weights dictionary, falling back to defaults if not found
    or incomplete in the global settings.
    """
    weights = getattr(backend.config.settings, "optimizer_weights", {})
    # Ensure all required keys are present, fallback to defaults if not
    for key in DEFAULT_WEIGHTS:
        if key not in weights:
            return DEFAULT_WEIGHTS
    return weights


def calculate_objective_score(
    intervention: Dict[str, Any], weights: Dict[str, float] = None
) -> float:
    """
    Calculates the weighted, normalized multi-objective score for a candidate intervention.

    Formula:
        Score = w_aqi * norm_aqi
              + w_pop * norm_population
              + w_health * norm_health
              - w_cost * norm_cost
    """
    if weights is None:
        weights = get_optimizer_weights()

    w_aqi = weights.get("aqi", DEFAULT_WEIGHTS["aqi"])
    w_pop = weights.get("population", DEFAULT_WEIGHTS["population"])
    w_health = weights.get("health", DEFAULT_WEIGHTS["health"])
    w_cost = weights.get("cost", DEFAULT_WEIGHTS["cost"])

    norm_aqi = float(intervention.get("norm_aqi", 0.0))
    norm_pop = float(intervention.get("norm_population", 0.0))
    norm_health = float(intervention.get("norm_health", 0.0))
    norm_cost = float(intervention.get("norm_cost", 0.0))

    score = (
        (w_aqi * norm_aqi)
        + (w_pop * norm_pop)
        + (w_health * norm_health)
        - (w_cost * norm_cost)
    )
    return round(score, 4)
