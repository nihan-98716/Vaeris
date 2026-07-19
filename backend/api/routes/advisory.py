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


@router.get("/ivr")
async def get_advisory_ivr(current_aqi: float = 320.0, language: str = "en"):
    """
    Returns TwiML / SSML XML formatted speech advisory for automated IVR phone systems.
    """
    from fastapi.responses import Response

    from backend.agent.advisory_prompt import generate_advisory

    adv = generate_advisory(current_aqi=current_aqi, language=language, enable_llm=False)
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="{language}">
        Attention public health advisory. Current Air Quality Index is {int(current_aqi)}, status {adv.aqi_category}.
        {adv.health_message}
        Key recommendation: {adv.recommended_precautions[0] if adv.recommended_precautions else "Stay indoors."}
    </Say>
</Response>"""
    return Response(content=xml_content, media_type="application/xml")


@router.get("/display")
async def get_advisory_display(current_aqi: float = 320.0, city: str = "Delhi"):
    """
    Returns high-contrast JSON payload formatted for municipal VMS Variable Message Signage.
    """
    from backend.agent.advisory_prompt import generate_advisory

    adv = generate_advisory(current_aqi=current_aqi, language="en", enable_llm=False)
    return {
        "city": city,
        "aqi_value": int(current_aqi),
        "status_header": f"AQI {int(current_aqi)} - {adv.aqi_category.upper()}",
        "line_1": adv.recommended_precautions[0] if adv.recommended_precautions else "STAY INDOORS",
        "line_2": "WEAR N95 MASKS OUTDOORS",
        "alert_color": "RED" if current_aqi > 300 else "ORANGE" if current_aqi > 200 else "YELLOW",
    }

