"""
backend/tests/test_api_multicity.py

Tests for the multi-city comparison API endpoint.
Checks city counts, schema validation, offline fallbacks, and specific keys.
"""

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_multicity_comparison_endpoint():
    """GET /api/v1/multicity returns summary data for all 4 target cities."""
    response = client.get("/api/v1/multicity")
    assert response.status_code == 200

    data = response.json()
    assert "cities" in data
    cities = data["cities"]
    assert len(cities) == 4

    city_names = {c["city_name"] for c in cities}
    assert city_names == {"Delhi", "Mumbai", "Chennai", "Bengaluru"}

    for city in cities:
        assert "latitude" in city
        assert "longitude" in city
        assert "current_aqi" in city
        assert "primary_cause" in city
        assert "projected_aqi" in city
        assert "reduction_pct" in city
        assert "health_benefit" in city
        assert "status_level" in city
        assert "optimal_actions" in city

        # Assert correct typing and values
        assert isinstance(city["optimal_actions"], list)
        assert len(city["optimal_actions"]) == 2
        assert city["current_aqi"] >= 0
        assert city["projected_aqi"] <= city["current_aqi"]
        assert city["status_level"] in {"high", "medium", "low"}
