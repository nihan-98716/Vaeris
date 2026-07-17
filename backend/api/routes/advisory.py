"""
backend/api/routes/advisory.py

FastAPI router handling citizen health risk advisory queries.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.agent.advisory_prompt import generate_advisory
from backend.api.schemas import AdvisoryRequest, AdvisoryResponse
from backend.logging import logger

router = APIRouter(prefix="/advisory", tags=["Citizen Advisory"])


@router.get("", response_model=AdvisoryResponse)
async def get_citizen_advisory(req: AdvisoryRequest = Depends()):
    """
    Generates health warnings and protective precaution recommendations for standard citizens
    and sensitive subgroups, based on current/forecasted air quality and source attribution.
    Supports English ('en') and Hindi ('hi') languages.
    """
    try:
        logger.info(
            f"API: Running citizen health advisory. AQI={req.current_aqi}, "
            f"forecasted={req.forecasted_aqi}, cause={req.primary_cause}, lang={req.language}"
        )
        result = generate_advisory(
            current_aqi=req.current_aqi,
            forecasted_aqi=req.forecasted_aqi,
            primary_cause=req.primary_cause,
            language=req.language,
            enable_llm=req.enable_llm,
        )
        return result

    except Exception as e:
        logger.error("API: Citizen health advisory endpoint failed", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal citizen health advisory error: {str(e)}",
        ) from e
