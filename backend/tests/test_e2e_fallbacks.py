from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


@pytest.fixture
def mock_external_apis_failed():
    """
    Mocks requests.get to simulate connection/timeout failures on all external APIs.
    """

    def mock_get(url, *args, **kwargs):
        raise requests.exceptions.ConnectTimeout(
            "Connection to external API timed out."
        )

    with patch("requests.get", side_effect=mock_get) as mock:
        yield mock


def test_investigate_endpoint_openaq_and_firms_failure_fallback(
    mock_external_apis_failed,
):
    """
    Explicitly tests that /api/v1/investigate succeeds and falls back to snapshots
    even if all external networks (OpenAQ, FIRMS, Weather) time out or crash.
    """
    response = client.get(
        "/api/v1/investigate",
        params={
            "latitude": 28.6139,
            "longitude": 77.2090,
            "horizon_hours": 24,
            "budget": 4000.0,
            "inspectors": 5,
            "max_travel_time_hours": 3.0,
            "enable_llm": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["latitude"] == pytest.approx(28.6139)
    assert data["longitude"] == pytest.approx(77.2090)
    assert data["current_aqi"] > 0
    assert data["forecast"]["value"] > 0
    assert data["attribution"]["primary_cause"] in [
        "traffic",
        "industrial",
        "agricultural_burning",
        "unknown",
    ]
    assert len(data["decision"]["selected_interventions"]) > 0
    assert "Environmental Investigation Report" in data["summary"]


def test_multicity_endpoint_openaq_failure_fallback(mock_external_apis_failed):
    """
    Explicitly tests that /api/v1/multicity falls back to local database or
    curated snapshots if OpenAQ is offline.
    """
    from backend.api.cache import get_redis_client

    redis = get_redis_client()
    if redis:
        redis.delete("multicity:report")

    response = client.get("/api/v1/multicity")

    assert response.status_code == 200
    data = response.json()
    assert len(data["cities"]) == 4
    for city in data["cities"]:
        assert city["current_aqi"] > 0
        assert city["projected_aqi"] > 0
        assert len(city["optimal_actions"]) > 0


def test_forecast_endpoint_database_missing_fallback(mock_external_apis_failed):
    """
    Explicitly tests that /api/v1/forecast falls back to offline snapshots
    if database connection is down or returns insufficient rows.
    """
    with patch("backend.db.queries.find_nearest_station", return_value=None):
        response = client.get(
            "/api/v1/forecast",
            params={"latitude": 28.6139, "longitude": 77.2090, "horizon_hours": 24},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["value"] > 0
        assert data["lower_bound"] > 0
        assert data["upper_bound"] > 0
