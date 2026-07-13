"""
backend/api/routes/decision.py

FastAPI router handling decision-optimization queries. Evaluates candidate interventions
against resource limits using a multi-objective greedy knapsack solver.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas import DecisionRequest, DecisionResponse
from backend.decision.optimizer import optimize_interventions
from backend.logging import logger

router = APIRouter(prefix="/decision", tags=["Decision Optimization"])


@router.get("", response_model=DecisionResponse)
async def get_decision(req: DecisionRequest = Depends()):
    """
    Optimizes intervention selection subject to resource limits (budget, inspectors, dispatch window).
    """
    try:
        logger.info(
            f"Solving decision optimization with constraints: "
            f"budget={req.budget}, inspectors={req.inspectors}, max_travel_time={req.max_travel_time_hours}h"
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
