"""
backend/api/routes/investigate.py

FastAPI router handling consolidated agent orchestrator queries.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.agent.pipeline import run_investigation_pipeline
from backend.api.schemas import InvestigateRequest, InvestigateResponse
from backend.logging import logger

router = APIRouter(prefix="/investigate", tags=["Agent Orchestrator"])


@router.get("", response_model=InvestigateResponse)
async def get_investigation(req: InvestigateRequest = Depends()):
    """
    Consolidated agent orchestrator endpoint. Runs the full forecasting,
    attribution, optimization, verification, and natural language summary
    pipeline for a given coordinate and constraints.
    """
    try:
        logger.info(
            f"API: Running investigation at coordinates ({req.latitude}, {req.longitude}) "
            f"with horizon_hours={req.horizon_hours}, budget={req.budget}, enable_llm={req.enable_llm}"
        )
        result = run_investigation_pipeline(
            latitude=req.latitude,
            longitude=req.longitude,
            horizon_hours=req.horizon_hours,
            budget=req.budget,
            inspectors=req.inspectors,
            max_travel_time_hours=req.max_travel_time_hours,
            enable_llm=req.enable_llm,
        )
        return result

    except Exception as e:
        logger.error("API: Investigation endpoint execution failed", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal agent orchestrator error: {str(e)}",
        ) from e
