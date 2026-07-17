"""
backend/tests/test_agent_advisory.py

Tests for the citizen health risk advisory prompt generator and API endpoint.
Checks English/Hindi translations, AQI band severities, source-specific additions,
and LLM error fallback mechanisms.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.agent.advisory_prompt import (
    generate_advisory,
    get_deterministic_advisory,
)
from backend.api.main import app

client = TestClient(app)


def test_get_deterministic_advisory_english():
    """Confirms CPCB severity category and precautions in English."""
    # Test Good Band (AQI 30)
    adv_good = get_deterministic_advisory(30.0, "traffic", "en")
    assert adv_good.aqi_category == "Good"
    assert adv_good.language == "en"
    assert any("activities" in p.lower() for p in adv_good.recommended_precautions)

    # Test Severe Band (AQI 450) with agricultural burning source
    adv_severe = get_deterministic_advisory(450.0, "agricultural_burning", "en")
    assert adv_severe.aqi_category == "Severe"
    assert any("N95" in p for p in adv_severe.recommended_precautions)
    # Check source specific stubble burning advice
    assert any(
        "agricultural fields" in p.lower() for p in adv_severe.recommended_precautions
    )


def test_get_deterministic_advisory_hindi():
    """Confirms CPCB severity category and precautions in Hindi."""
    # Test Very Poor Band (AQI 350)
    adv_very_poor = get_deterministic_advisory(350.0, "traffic", "hi")
    assert adv_very_poor.aqi_category == "बहुत खराब"
    assert adv_very_poor.language == "hi"

    # Check source specific traffic advice in Hindi
    assert any("सड़कों" in p for p in adv_very_poor.recommended_precautions)


def test_generate_advisory_llm_disabled():
    """When LLM is disabled, generate_advisory immediately returns the CPCB template."""
    res = generate_advisory(
        current_aqi=150.0,
        forecasted_aqi=140.0,
        primary_cause="industrial",
        language="en",
        enable_llm=False,
    )
    assert res.aqi_category == "Moderate"
    assert res.llm_error is False
    assert any("industrial zones" in p.lower() for p in res.recommended_precautions)


@patch("requests.post")
def test_generate_advisory_llm_success_mock(mock_post):
    """Verifies that a successful LLM call generates structural localized JSON content."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"category": "Very High Alert", "message": "Air quality is highly contaminated.", "precautions": ["Avoid all outdoors", "Stay hydrated"]}'
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    with patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"}):
        res = generate_advisory(
            current_aqi=320.0,
            forecasted_aqi=340.0,
            primary_cause="traffic",
            language="en",
            enable_llm=True,
        )

        assert res.aqi_category == "Very High Alert"
        assert res.health_message == "Air quality is highly contaminated."
        assert "Stay hydrated" in res.recommended_precautions
        assert res.llm_error is False


@patch("requests.post")
def test_generate_advisory_llm_failure_graceful_fallback(mock_post):
    """Verifies fallback to deterministic CPCB template on slow/failed LLM request."""
    # Simulate API connection timeout
    import requests

    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

    with patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"}):
        res = generate_advisory(
            current_aqi=450.0,
            forecasted_aqi=480.0,
            primary_cause="industrial",
            language="hi",
            enable_llm=True,
        )

        # Should fall back to CPCB Hindi severe template
        assert res.aqi_category == "गंभीर"
        assert res.language == "hi"
        assert res.llm_error is True  # Indicates error path occurred


def test_api_advisory_endpoint_valid():
    """GET /api/v1/advisory returns success validation check."""
    params = {
        "current_aqi": 320.0,
        "forecasted_aqi": 300.0,
        "primary_cause": "traffic",
        "language": "hi",
        "enable_llm": False,
    }
    response = client.get("/api/v1/advisory", params=params)
    assert response.status_code == 200

    data = response.json()
    assert data["aqi_category"] == "बहुत खराब"
    assert data["language"] == "hi"
    assert "health_message" in data
    assert len(data["recommended_precautions"]) > 0
    assert data["llm_error"] is False
