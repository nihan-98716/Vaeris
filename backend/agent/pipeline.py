"""
backend/agent/pipeline.py

Orchestrates the deterministic agent investigation pipeline:
forecast -> attribution -> decision -> scenario -> verifier -> evidence_score -> summary.
"""

import time

from backend.agent.evidence_score import compute_evidence_score
from backend.agent.summary import generate_llm_summary
from backend.agent.verifier import verify_attribution
from backend.api.routes.attribution import gather_attribution_signals
from backend.api.routes.forecast import database_history_provider
from backend.api.schemas import (
    AttributionResponse,
    DecisionResponse,
    ForecastResponse,
    InvestigateResponse,
    ScenarioResponse,
)
from backend.decision.optimizer import optimize_interventions
from backend.decision.scenario_approximation import compute_projected_aqi
from backend.logging import logger
from backend.models.attribution import rule_engine
from backend.models.forecasting import inference
from backend.models.schemas import LatLon


def run_investigation_pipeline(
    latitude: float,
    longitude: float,
    horizon_hours: int = 24,
    budget: float = 5000.0,
    inspectors: int = 5,
    max_travel_time_hours: float = 3.0,
    enable_llm: bool = True,
) -> InvestigateResponse:
    """
    Executes the consolidated investigation pipeline for a given coordinate and constraints.
    Returns a unified InvestigateResponse.
    """
    logger.info(
        f"Starting agent investigation pipeline for coordinates ({latitude}, {longitude}) "
        f"with budget={budget}, inspectors={inspectors}"
    )
    start_time = time.time()
    location = LatLon(latitude=latitude, longitude=longitude)

    # 1. Fetch history
    history_df = database_history_provider(location)
    if history_df.empty:
        raise ValueError("Insufficient historical measurements for coordinates.")

    # 2. Run Forecast
    forecast_result = inference.predict_from_history(
        history_df, location, horizon_hours
    )
    forecast_resp = ForecastResponse(
        value=forecast_result.value,
        lower_bound=forecast_result.lower_bound,
        upper_bound=forecast_result.upper_bound,
        confidence_tier=forecast_result.confidence_tier,
        model_version=forecast_result.model_version,
        horizon_hours=forecast_result.horizon_hours,
    )

    # 3. Gather signals and execute source attribution
    signals, unavailable_sources = gather_attribution_signals(location)
    attribution_result = rule_engine.run_attribution(
        signals, unavailable_sources=unavailable_sources
    )

    # 4. Run decision optimizer
    decision_result = optimize_interventions(
        budget=budget,
        inspectors=inspectors,
        max_travel_time_hours=max_travel_time_hours,
    )
    decision_resp = DecisionResponse(**decision_result)

    # 5. Run scenario projection
    current_aqi = signals["aqi_now"]
    scenario = compute_projected_aqi(
        current_aqi=current_aqi,
        selected_interventions=decision_result["selected_interventions"],
        primary_cause=attribution_result.primary_cause,
    )
    scenario_resp = ScenarioResponse(
        decision=decision_resp,
        **scenario,
    )

    # 6. Run verifier
    verification_result = verify_attribution(
        primary_cause=attribution_result.primary_cause,
        confidence_breakdown=attribution_result.confidence_breakdown,
        signals=signals,
    )

    # 7. Compile evidence score
    evidence_score_resp = compute_evidence_score(
        primary_cause=attribution_result.primary_cause,
        verification_result=verification_result,
    )

    # Compile adjusted attribution response based on verifier outputs
    attribution_resp = AttributionResponse(
        primary_cause=attribution_result.primary_cause,
        confidence_breakdown=verification_result.adjusted_confidence_breakdown,
        evidence=attribution_result.evidence,
        degraded_sources=attribution_result.degraded_sources,
    )

    # 8. Generate natural language summary (with timeout and fallback)
    # base confidence score is the primary cause's adjusted confidence
    primary_conf_pct = (
        verification_result.adjusted_confidence_breakdown.get(
            attribution_result.primary_cause, 0.0
        )
        * 100.0
    )

    summary_text, llm_error = generate_llm_summary(
        latitude=latitude,
        longitude=longitude,
        current_aqi=current_aqi,
        primary_cause=attribution_result.primary_cause,
        confidence=primary_conf_pct,
        forecast_value=forecast_result.value,
        forecast_lower=forecast_result.lower_bound,
        forecast_upper=forecast_result.upper_bound,
        selected_interventions=decision_result["selected_interventions"],
        total_aqi_reduction=decision_result["total_aqi_reduction"],
        projected_aqi=scenario["projected_aqi"],
        health_benefit=decision_result["total_health_benefit"],
        enable_llm=enable_llm,
    )

    elapsed_time = time.time() - start_time
    logger.info(
        f"Completed agent investigation pipeline in {elapsed_time:.3f} seconds. "
        f"LLM status: {'Error/Disabled' if llm_error else 'Success'}"
    )

    return InvestigateResponse(
        latitude=latitude,
        longitude=longitude,
        current_aqi=current_aqi,
        primary_cause=attribution_result.primary_cause,
        forecast=forecast_resp,
        attribution=attribution_resp,
        decision=decision_resp,
        scenario=scenario_resp,
        evidence_score=evidence_score_resp,
        summary=summary_text,
        llm_error=llm_error,
    )
