"""
backend/decision/scenario_approximation.py

Computes the approximate projected AQI given a set of selected optimizer interventions.
Used by both the before/after comparison panel and the scenario slider.

The approximation formula:
  projected_aqi = current_aqi - (total_aqi_reduction * source_weight_factor)

Where source_weight_factor (0.0–1.0) accounts for how directly interventions target
the dominant pollution source at the queried location.
"""

from typing import Dict, List

# Maps each dominant source to a per-intervention effectiveness weight.
# 1.0 = directly targets this source; 0.1 = negligible / off-target effect.
_SOURCE_WEIGHT_MAP: Dict[str, Dict[str, float]] = {
    "agricultural_burning": {
        "stubble_burning_enforcement": 1.0,
        "waste_burning_fines": 0.4,
        "road_sprinklers": 0.3,
        "odd_even_rationing": 0.2,
        "restrict_industries": 0.2,
        "halt_construction": 0.1,
    },
    "traffic": {
        "odd_even_rationing": 1.0,
        "road_sprinklers": 0.7,
        "halt_construction": 0.3,
        "waste_burning_fines": 0.4,
        "restrict_industries": 0.3,
        "stubble_burning_enforcement": 0.1,
    },
    "industrial": {
        "restrict_industries": 1.0,
        "halt_construction": 0.8,
        "waste_burning_fines": 0.5,
        "road_sprinklers": 0.3,
        "odd_even_rationing": 0.2,
        "stubble_burning_enforcement": 0.1,
    },
}

# Default weights when source is unknown / mixed
_DEFAULT_SOURCE_WEIGHTS: Dict[str, float] = {
    k: 0.3
    for k in [
        "stubble_burning_enforcement",
        "halt_construction",
        "road_sprinklers",
        "odd_even_rationing",
        "restrict_industries",
        "waste_burning_fines",
    ]
}


def compute_projected_aqi(
    current_aqi: float,
    selected_interventions: List[Dict],
    primary_cause: str,
) -> Dict:
    """
    Compute projected AQI after applying the selected interventions.

    Args:
        current_aqi: The current measured AQI at the queried location.
        selected_interventions: List of intervention dicts from the optimizer.
        primary_cause: Dominant pollution source ('agricultural_burning', 'traffic', 'industrial').

    Returns:
        dict with:
            projected_aqi       : estimated AQI after interventions
            reduction_applied   : actual AQI reduction applied (weighted)
            source_weight_factor: how well interventions target the dominant source (0–1)
            confidence          : approximation confidence ('high', 'medium', 'low')
            current_aqi         : echo of input
            percent_reduction   : % reduction relative to current_aqi
    """
    source_weights = _SOURCE_WEIGHT_MAP.get(primary_cause, _DEFAULT_SOURCE_WEIGHTS)

    total_weighted_reduction = 0.0
    total_weight = 0.0

    for intervention in selected_interventions:
        iid = intervention.get("id", "")
        aqi_red = float(intervention.get("aqi_reduction", 0))
        weight = source_weights.get(iid, 0.3)
        total_weighted_reduction += aqi_red * weight
        total_weight += weight

    n = len(selected_interventions)
    avg_weight = total_weight / n if n > 0 else 0.0
    reduction_applied = round(total_weighted_reduction, 2)
    projected = max(10.0, current_aqi - reduction_applied)

    if avg_weight >= 0.7:
        confidence = "high"
    elif avg_weight >= 0.4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "projected_aqi": round(projected, 1),
        "reduction_applied": reduction_applied,
        "source_weight_factor": round(avg_weight, 3),
        "confidence": confidence,
        "current_aqi": current_aqi,
        "percent_reduction": (
            round((reduction_applied / current_aqi) * 100, 1)
            if current_aqi > 0
            else 0.0
        ),
    }
