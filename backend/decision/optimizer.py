"""
backend/decision/optimizer.py

Predefines the catalog of possible interventions for Delhi's air quality crisis and
implements the constrained greedy knapsack solver to optimize selection.
"""

from typing import Any, Dict, List

from backend.decision.health_impact import calculate_health_benefit
from backend.decision.normalize import normalize_interventions
from backend.decision.objective import calculate_objective_score, get_optimizer_weights

# Catalog of possible interventions based on Delhi's actual mitigation options
INTERVENTION_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "stubble_burning_enforcement",
        "name": "Enforce Stubble Burning Ban",
        "description": "Deploy enforcement teams to agricultural borders to stop active crop residue burning.",
        "cost": 1500.0,
        "inspectors_required": 4,
        "travel_time_hours": 2.5,
        "aqi_reduction": 45.0,
        "population_affected": 800000,
    },
    {
        "id": "halt_construction",
        "name": "Halt Construction Activities",
        "description": "Temporarily suspend major dust-generating construction and demolition projects.",
        "cost": 800.0,
        "inspectors_required": 2,
        "travel_time_hours": 1.0,
        "aqi_reduction": 20.0,
        "population_affected": 500000,
    },
    {
        "id": "road_sprinklers",
        "name": "Deploy Road Sprinklers & Anti-Smog Guns",
        "description": "Operate misting trucks and anti-smog guns along high-traffic corridors.",
        "cost": 500.0,
        "inspectors_required": 1,
        "travel_time_hours": 0.5,
        "aqi_reduction": 12.0,
        "population_affected": 300000,
    },
    {
        "id": "odd_even_rationing",
        "name": "Implement Odd-Even Vehicle Rationing",
        "description": "Restrict private vehicle usage based on license plate numbers.",
        "cost": 3000.0,
        "inspectors_required": 10,
        "travel_time_hours": 1.5,
        "aqi_reduction": 35.0,
        "population_affected": 2000000,
    },
    {
        "id": "restrict_industries",
        "name": "Restrict Coal-Fired Industrial Output",
        "description": "Temporarily curtail operations at surrounding coal power plants and brick kilns.",
        "cost": 2500.0,
        "inspectors_required": 3,
        "travel_time_hours": 2.0,
        "aqi_reduction": 30.0,
        "population_affected": 1200000,
    },
    {
        "id": "waste_burning_fines",
        "name": "Enforce Waste Burning Fines",
        "description": "Dispatch local municipal patrols to fine open waste burning in neighborhoods.",
        "cost": 300.0,
        "inspectors_required": 1,
        "travel_time_hours": 0.8,
        "aqi_reduction": 8.0,
        "population_affected": 250000,
    },
]


def optimize_interventions(
    budget: float, inspectors: int, max_travel_time_hours: float
) -> Dict[str, Any]:
    """
    Optimizes the selection of interventions from the catalog using a greedy approach.

    Constraints:
    - Total cost of selected interventions <= budget
    - Total inspectors required <= inspectors
    - Individual intervention travel_time_hours <= max_travel_time_hours

    Objective:
    - Maximize weighted multi-objective score
    """
    # 1. Filter by travel time constraint
    filtered = [
        dict(i)
        for i in INTERVENTION_CATALOG
        if i["travel_time_hours"] <= max_travel_time_hours
    ]

    if not filtered:
        return {
            "selected_interventions": [],
            "total_aqi_reduction": 0.0,
            "total_cost": 0.0,
            "total_inspectors_used": 0,
            "total_population_affected": 0,
            "total_health_benefit": 0.0,
            "remaining_budget": budget,
            "remaining_inspectors": inspectors,
        }

    # 2. Compute health benefit score for each candidate
    for i in filtered:
        i["health_benefit"] = calculate_health_benefit(
            i["aqi_reduction"], i["population_affected"]
        )

    # 3. Normalize candidates
    normalized = normalize_interventions(filtered)

    # 4. Score candidates
    weights = get_optimizer_weights()
    for i in normalized:
        i["score"] = calculate_objective_score(i, weights)

    # 5. Greedy Selection: Sort by score descending
    # (Optional refinement: sort by score per unit cost. Raw score is the standard greedy approach here)
    sorted_candidates = sorted(normalized, key=lambda x: x["score"], reverse=True)

    selected = []
    current_cost = 0.0
    current_inspectors = 0
    total_aqi_reduction = 0.0
    total_population_affected = 0
    total_health_benefit = 0.0

    for candidate in sorted_candidates:
        cost = candidate["cost"]
        req_inspectors = candidate["inspectors_required"]

        # Check resource constraints
        if (current_cost + cost <= budget) and (
            current_inspectors + req_inspectors <= inspectors
        ):
            # Select intervention (clean up internal normalized variables)
            clean_item = {
                "id": candidate["id"],
                "name": candidate["name"],
                "description": candidate["description"],
                "cost": candidate["cost"],
                "inspectors_required": candidate["inspectors_required"],
                "travel_time_hours": candidate["travel_time_hours"],
                "aqi_reduction": candidate["aqi_reduction"],
                "population_affected": candidate["population_affected"],
                "health_benefit": candidate["health_benefit"],
                "score": candidate["score"],
            }
            selected.append(clean_item)
            current_cost += cost
            current_inspectors += req_inspectors
            total_aqi_reduction += candidate["aqi_reduction"]
            total_population_affected += candidate["population_affected"]
            total_health_benefit += candidate["health_benefit"]

    return {
        "selected_interventions": selected,
        "total_aqi_reduction": round(total_aqi_reduction, 2),
        "total_cost": round(current_cost, 2),
        "total_inspectors_used": current_inspectors,
        "total_population_affected": total_population_affected,
        "total_health_benefit": round(total_health_benefit, 2),
        "remaining_budget": round(budget - current_cost, 2),
        "remaining_inspectors": inspectors - current_inspectors,
    }
