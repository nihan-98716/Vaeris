"""
backend/tests/test_decision.py

Unit and integration tests for the decision-optimization engine.
Validates normalization, multi-objective scoring, resource constraints,
and config-driven weight updates.
"""

import os
import shutil
from pathlib import Path

import yaml

from backend.config.settings import Settings
from backend.decision.health_impact import calculate_health_benefit
from backend.decision.normalize import min_max_normalize
from backend.decision.optimizer import optimize_interventions


def test_min_max_normalize():
    # Regular case
    vals = [10.0, 20.0, 30.0, 40.0]
    norm = min_max_normalize(vals)
    assert norm == [0.0, 1 / 3, 2 / 3, 1.0]

    # Identical values case (should fallback to 1.0s to avoid div by zero)
    vals_same = [10.0, 10.0, 10.0]
    norm_same = min_max_normalize(vals_same)
    assert norm_same == [1.0, 1.0, 1.0]

    # Empty list
    assert min_max_normalize([]) == []


def test_calculate_health_benefit():
    benefit = calculate_health_benefit(aqi_reduction=20.0, population_affected=100000)
    # 20 * 0.0104 * 100000 = 20800.0
    assert benefit == 20800.0


def test_constrained_greedy_solver_basic():
    # Case 1: Unconstrained (large budget, many inspectors, long travel time)
    # Should select multiple high-impact interventions
    res = optimize_interventions(
        budget=10000.0, inspectors=20, max_travel_time_hours=5.0
    )
    assert len(res["selected_interventions"]) > 0
    assert res["total_cost"] <= 10000.0
    assert res["total_inspectors_used"] <= 20

    # Case 2: Severely budget constrained
    # Cost limits should restrict selection
    res_budget = optimize_interventions(
        budget=400.0, inspectors=10, max_travel_time_hours=5.0
    )
    # Only cheap items like waste burning fines (cost 300) should fit
    for item in res_budget["selected_interventions"]:
        assert item["cost"] <= 400.0

    # Case 3: Inspector constrained
    res_inspectors = optimize_interventions(
        budget=10000.0, inspectors=1, max_travel_time_hours=5.0
    )
    for item in res_inspectors["selected_interventions"]:
        assert item["inspectors_required"] <= 1

    # Case 4: Dispatch window / travel time constrained
    # With max_travel_time_hours = 0.6, only items with travel time <= 0.6 should be selected
    # (e.g. road sprinklers = 0.5)
    res_time = optimize_interventions(
        budget=10000.0, inspectors=20, max_travel_time_hours=0.6
    )
    for item in res_time["selected_interventions"]:
        assert item["travel_time_hours"] <= 0.6


def test_config_driven_weight_change():
    """
    Validates that modifying weights in weights.yaml updates the scoring
    ranking of interventions without requiring a code change.
    """
    # 1. Back up the existing weights.yaml if it exists
    config_dir = Path(__file__).parent.parent / "config"
    weights_path = config_dir / "weights.yaml"
    backup_path = config_dir / "weights.yaml.bak"

    has_backup = False
    if weights_path.exists():
        shutil.copy(weights_path, backup_path)
        has_backup = True

    try:
        # 2. Write custom weights emphasizing cost penalty over everything else
        # A high cost penalty should push low-cost items to the top
        cost_heavy_weights = {
            "optimizer": {
                "weights": {
                    "aqi": 0.05,
                    "population": 0.05,
                    "health": 0.05,
                    "cost": 0.85,
                }
            }
        }
        with open(weights_path, "w") as f:
            yaml.dump(cost_heavy_weights, f)

        # Reload settings instance dynamically

        # Re-trigger settings loading
        new_settings = Settings.load()
        # Override the global settings attributes for the optimizer module
        import backend.config

        backend.config.settings = new_settings

        # Optimize with sufficient budget/inspectors but check sorted scores
        res_cost_heavy = optimize_interventions(
            budget=10000.0, inspectors=50, max_travel_time_hours=5.0
        )
        selected_cost_heavy = res_cost_heavy["selected_interventions"]

        # 3. Write custom weights emphasizing AQI benefit over cost
        aqi_heavy_weights = {
            "optimizer": {
                "weights": {
                    "aqi": 0.85,
                    "population": 0.05,
                    "health": 0.05,
                    "cost": 0.05,
                }
            }
        }
        with open(weights_path, "w") as f:
            yaml.dump(aqi_heavy_weights, f)

        # Re-trigger settings loading again
        new_settings_aqi = Settings.load()
        backend.config.settings = new_settings_aqi

        res_aqi_heavy = optimize_interventions(
            budget=10000.0, inspectors=50, max_travel_time_hours=5.0
        )
        selected_aqi_heavy = res_aqi_heavy["selected_interventions"]

        # Verify that the two configurations produced different selected rankings/orders
        # Because we sorted by score, the top items (or score ordering) should be different
        order_cost_heavy = [item["id"] for item in selected_cost_heavy]
        order_aqi_heavy = [item["id"] for item in selected_aqi_heavy]

        # The scores assigned to individual items must be different
        assert (
            order_cost_heavy != order_aqi_heavy
            or selected_cost_heavy[0]["score"] != selected_aqi_heavy[0]["score"]
        )

    finally:
        # Restore the original weights.yaml
        if has_backup:
            shutil.copy(backup_path, weights_path)
            if backup_path.exists():
                os.remove(backup_path)
        elif weights_path.exists():
            os.remove(weights_path)

        # Restore global settings
        backend.config.settings = Settings.load()
