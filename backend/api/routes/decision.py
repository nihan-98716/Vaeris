"""
backend/api/routes/decision.py

FastAPI router handling decision-optimization queries and before/after scenario
projections. Evaluates candidate interventions against resource limits using a
multi-objective greedy knapsack solver, then optionally chains the scenario
approximation to project the resulting AQI improvement.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas import (
    DecisionRequest,
    DecisionResponse,
    ScenarioRequest,
    ScenarioResponse,
)
from backend.decision.optimizer import optimize_interventions
from backend.decision.scenario_approximation import compute_projected_aqi
from backend.logging import logger

router = APIRouter(prefix="/decision", tags=["Decision Optimization"])


@router.get("", response_model=DecisionResponse)
async def get_decision(req: DecisionRequest = Depends()):
    """
    Optimizes intervention selection subject to resource limits
    (budget, inspectors, dispatch window).
    """
    try:
        logger.info(
            f"Solving decision optimization with constraints: "
            f"budget={req.budget}, inspectors={req.inspectors}, "
            f"max_travel_time={req.max_travel_time_hours}h"
        )

        result = optimize_interventions(
            budget=req.budget,
            inspectors=req.inspectors,
            max_travel_time_hours=req.max_travel_time_hours,
        )

        return DecisionResponse(**result)

    except Exception as e:
        logger.error("Decision optimization endpoint failed", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal decision optimization solver error: {str(e)}",
        ) from e


@router.get("/scenario", response_model=ScenarioResponse)
async def get_scenario(req: ScenarioRequest = Depends()):
    """
    Before/after scenario projection.

    Chains the decision optimizer with the source-weight approximation to
    compute projected AQI after applying the optimal intervention set.
    The "Projected AQI" label is always used for output values — never "Actual".
    """
    try:
        logger.info(
            f"Computing scenario projection: current_aqi={req.current_aqi}, "
            f"primary_cause={req.primary_cause}, budget={req.budget}"
        )

        # Step 1: optimize interventions
        decision_result = optimize_interventions(
            budget=req.budget,
            inspectors=req.inspectors,
            max_travel_time_hours=req.max_travel_time_hours,
        )

        # Step 2: project AQI using source-weight approximation
        scenario = compute_projected_aqi(
            current_aqi=req.current_aqi,
            selected_interventions=decision_result["selected_interventions"],
            primary_cause=req.primary_cause,
        )

        return ScenarioResponse(
            decision=DecisionResponse(**decision_result),
            **scenario,
        )

    except Exception as e:
        logger.error("Scenario projection endpoint failed", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal scenario projection error: {str(e)}",
        ) from e
