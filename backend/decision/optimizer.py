"""
backend/decision/optimizer.py

Predefines the catalog of possible interventions for Delhi's air quality crisis and
implements an exact constrained knapsack solver to optimize selection.
"""

from itertools import combinations
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
    Optimizes the selection of interventions from the catalog by exhaustively
    evaluating feasible subsets. The intervention catalog is intentionally small,
    so exact search keeps recommendations faithful to the weighted objective.

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

    # 5. Exact constrained selection. Tie-breakers keep output deterministic
    # while preferring higher direct impact, then lower cost, then fewer inspectors.
    best_combo = ()
    best_key = (0.0, 0.0, -0.0, 0, ())
    for size in range(1, len(normalized) + 1):
        for combo in combinations(normalized, size):
            total_cost = sum(item["cost"] for item in combo)
            total_inspectors = sum(item["inspectors_required"] for item in combo)
            if total_cost > budget or total_inspectors > inspectors:
                continue

            total_score = sum(item["score"] for item in combo)
            total_aqi = sum(item["aqi_reduction"] for item in combo)
            ids = tuple(sorted(item["id"] for item in combo))
            key = (
                round(total_score, 12),
                round(total_aqi, 12),
                -round(total_cost, 12),
                -total_inspectors,
                ids,
            )
            if key > best_key:
                best_key = key
                best_combo = combo

    selected_candidates = sorted(
        best_combo,
        key=lambda x: (x["score"], x["aqi_reduction"], -x["cost"], x["id"]),
        reverse=True,
    )
    selected = [
        {
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
        for candidate in selected_candidates
    ]

    current_cost = sum(item["cost"] for item in selected)
    current_inspectors = sum(item["inspectors_required"] for item in selected)
    total_aqi_reduction = sum(item["aqi_reduction"] for item in selected)
    total_population_affected = sum(item["population_affected"] for item in selected)
    total_health_benefit = sum(item["health_benefit"] for item in selected)

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
