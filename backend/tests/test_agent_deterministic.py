"""
backend/tests/test_agent_deterministic.py

Tests the agent orchestrator pipeline with the LLM summary step disabled
or configured to use the deterministic fallback template.
"""

from fastapi.testclient import TestClient

from backend.agent.evidence_score import compute_evidence_score
from backend.agent.pipeline import run_investigation_pipeline
from backend.agent.summary import generate_deterministic_summary
from backend.agent.verifier import verify_attribution
from backend.api.main import app

client = TestClient(app)


def test_verifier_agricultural_burning_success():
    """Verifier should approve agricultural burning when fires are present and wind is consistent."""
    signals = {
        "fire_events": [
            {"distance_km": 40.0, "bearing_deg": 315.0, "detected_hours_ago": 2.0}
        ],
        "wind_direction_deg": 310.0,
        "wind_speed_ms": 5.0,
        "road_density_500m": 0.3,
        "land_use_category": "residential",
        "aqi_now": 300.0,
        "aqi_rolling_mean_24h": 200.0,
        "hour_of_day": 14,
    }
    confidence_breakdown = {
        "agricultural_burning": 0.8,
        "traffic": 0.1,
        "industrial": 0.1,
    }
    res = verify_attribution("agricultural_burning", confidence_breakdown, signals)

    assert res.is_verified is True
    assert res.adjusted_confidence_breakdown["agricultural_burning"] == 0.8
    assert any("Active fire hotspots" in item for item in res.checklist)
    assert any("Wind vector consistent" in item for item in res.checklist)


def test_verifier_traffic_failure_missing_commute():
    """Verifier should flag traffic attribution if timing is outside commute hours."""
    signals = {
        "fire_events": [],
        "wind_direction_deg": 180.0,
        "wind_speed_ms": 2.0,
        "road_density_500m": 0.8,
        "land_use_category": "residential",
        "aqi_now": 250.0,
        "aqi_rolling_mean_24h": 200.0,
        "hour_of_day": 3,  # 3 AM is not commute hours
    }
    confidence_breakdown = {
        "traffic": 0.7,
        "industrial": 0.2,
        "agricultural_burning": 0.1,
    }
    res = verify_attribution("traffic", confidence_breakdown, signals)

    assert res.is_verified is False
    assert res.adjusted_confidence_breakdown["traffic"] < 0.7
    assert any("Off-peak timing decreases traffic" in item for item in res.checklist)


def test_compute_evidence_score():
    """Tests the confidence scoring and status mapping."""
    # Verified case
    signals = {
        "fire_events": [],
        "wind_direction_deg": 180.0,
        "wind_speed_ms": 2.0,
        "road_density_500m": 0.8,
        "land_use_category": "residential",
        "aqi_now": 250.0,
        "aqi_rolling_mean_24h": 200.0,
        "hour_of_day": 8,  # 8 AM is commute hour
    }
    confidence_breakdown = {
        "traffic": 0.8,
        "industrial": 0.1,
        "agricultural_burning": 0.1,
    }
    verification = verify_attribution("traffic", confidence_breakdown, signals)
    score = compute_evidence_score("traffic", verification)

    assert score.confidence_score == 80.0
    assert score.status == "high"

    # Failed verification case
    verification_failed = verify_attribution(
        "traffic", confidence_breakdown, {**signals, "hour_of_day": 12}
    )
    score_failed = compute_evidence_score("traffic", verification_failed)

    assert score_failed.confidence_score < 80.0
    assert score_failed.status in ("medium", "low")


def test_deterministic_summary_contents():
    """Deterministic summary output must contain key report blocks."""
    summary = generate_deterministic_summary(
        latitude=28.566,
        longitude=77.186,
        current_aqi=312.0,
        primary_cause="traffic",
        confidence=80.0,
        forecast_value=290.0,
        forecast_lower=250.0,
        forecast_upper=320.0,
        selected_interventions=[
            {
                "name": "Odd-Even Vehicle Rationing",
                "cost": 1500.0,
                "aqi_reduction": 15.0,
            }
        ],
        total_aqi_reduction=15.0,
        projected_aqi=297.0,
        health_benefit=1.8,
    )

    assert "Environmental Investigation Report" in summary
    assert "Vehicular Traffic Accumulation" in summary
    assert "Odd-Even Vehicle Rationing" in summary
    assert "80.0%" in summary
    assert "297" in summary


def test_pipeline_deterministic_mode():
    """Pipeline runs and returns structured InvestigateResponse with LLM disabled."""
    res = run_investigation_pipeline(
        latitude=28.566,
        longitude=77.186,
        horizon_hours=24,
        budget=5000.0,
        inspectors=5,
        max_travel_time_hours=3.0,
        enable_llm=False,
    )

    assert res.latitude == 28.566
    assert res.longitude == 77.186
    assert res.current_aqi > 0.0
    assert res.forecast.horizon_hours == 24
    assert res.decision.total_cost <= 5000.0
    assert res.scenario.projected_aqi <= res.current_aqi
    assert len(res.evidence_score.checklist) > 0
    assert "Environmental Investigation Report" in res.summary
    assert res.llm_error is False


def test_investigate_endpoint_valid():
    """GET /api/v1/investigate returns success with valid params and enable_llm=false."""
    params = {
        "latitude": 28.566,
        "longitude": 77.186,
        "horizon_hours": 24,
        "budget": 5000.0,
        "inspectors": 5,
        "max_travel_time_hours": 3.0,
        "enable_llm": False,
    }
    response = client.get("/api/v1/investigate", params=params)
    assert response.status_code == 200

    data = response.json()
    assert data["latitude"] == 28.566
    assert "forecast" in data
    assert "attribution" in data
    assert "decision" in data
    assert "scenario" in data
    assert "evidence_score" in data
    assert "summary" in data
    assert data["llm_error"] is False
