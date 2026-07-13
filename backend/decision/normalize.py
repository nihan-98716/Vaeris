"""
backend/decision/normalize.py

Min-Max normalization helper functions for multi-objective optimization.
Ensures all metrics (AQI reduction, population, health benefit, cost) are scaled
to a [0, 1] range before weights are applied.
"""

from typing import List, Dict, Any

def min_max_normalize(values: List[float]) -> List[float]:
    """
    Normalizes a list of values to [0, 1] range using Min-Max scaling.
    If all values are identical, returns a list of 1.0s.
    """
    if not values:
        return []
    
    val_min = min(values)
    val_max = max(values)
    val_range = val_max - val_min
    
    if val_range == 0.0:
        return [1.0] * len(values)
        
    return [(v - val_min) / val_range for v in values]


def normalize_interventions(interventions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Computes min-max normalized values for each objective term across a list of interventions.
    Adds key-value pairs to each intervention dictionary:
    - norm_aqi
    - norm_population
    - norm_health
    - norm_cost
    """
    if not interventions:
        return []
        
    aqi_vals = [float(i.get("aqi_reduction", 0.0)) for i in interventions]
    pop_vals = [float(i.get("population_affected", 0.0)) for i in interventions]
    health_vals = [float(i.get("health_benefit", 0.0)) for i in interventions]
    cost_vals = [float(i.get("cost", 0.0)) for i in interventions]
    
    norm_aqi = min_max_normalize(aqi_vals)
    norm_pop = min_max_normalize(pop_vals)
    norm_health = min_max_normalize(health_vals)
    norm_cost = min_max_normalize(cost_vals)
    
    normalized_list = []
    for idx, intervention in enumerate(interventions):
        # Create a copy to avoid in-place side effects
        i_copy = dict(intervention)
        i_copy["norm_aqi"] = norm_aqi[idx]
        i_copy["norm_population"] = norm_pop[idx]
        i_copy["norm_health"] = norm_health[idx]
        i_copy["norm_cost"] = norm_cost[idx]
        normalized_list.append(i_copy)
        
    return normalized_list
