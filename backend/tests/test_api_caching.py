import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.api.cache import get_cached_value, set_cached_value
from backend.api.main import app
from backend.db.queries import calculate_bearing, haversine_distance

client = TestClient(app)


def test_distance_bearing_calculations():
    # Anand Vihar to Lodhi Road
    lat1, lon1 = 28.6476, 77.3158
    lat2, lon2 = 28.5919, 77.2272

    dist = haversine_distance(lat1, lon1, lat2, lon2)
    assert 8.0 <= dist <= 12.0  # Approx 10.6 km

    bearing = calculate_bearing(lat1, lon1, lat2, lon2)
    assert 200.0 <= bearing <= 260.0  # Southwest direction


@patch("backend.api.cache.get_redis_client")
def test_cache_get_set_helper_graceful_fallback(mock_get_client):
    # Setup mock client that throws errors
    mock_redis = MagicMock()
    mock_redis.get.side_effect = Exception("Redis error")
    mock_redis.set.side_effect = Exception("Redis error")
    mock_get_client.return_value = mock_redis

    # Assert helpers degrade gracefully and do not raise exceptions
    assert get_cached_value("test_key") is None
    assert set_cached_value("test_key", "value", 60) is False


@patch("backend.api.routes.forecast.get_cached_value")
@patch("backend.api.routes.forecast.set_cached_value")
def test_forecast_endpoint_cache_hit(mock_set, mock_get):
    # Simulate a cache hit by returning a valid JSON string matching ForecastResponse
    mock_response = {
        "value": 180.5,
        "lower_bound": 170.0,
        "upper_bound": 191.0,
        "confidence_tier": "reliable",
        "model_version": "v_cached",
        "horizon_hours": 24,
    }
    mock_get.return_value = json.dumps(mock_response)

    params = {"latitude": 28.566, "longitude": 77.186, "horizon_hours": 24}
    response = client.get("/api/v1/forecast", params=params)

    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "v_cached"
    assert data["value"] == 180.5

    # Verify set_cached_value was not called since it was a cache hit
    mock_set.assert_not_called()


@patch("backend.api.routes.attribution.get_cached_value")
@patch("backend.api.routes.attribution.set_cached_value")
def test_attribution_endpoint_cache_hit(mock_set, mock_get):
    mock_response = {
        "primary_cause": "agricultural_burning",
        "confidence_breakdown": {"agricultural_burning": 1.0},
        "evidence": ["Fires detected upwind"],
        "degraded_sources": [],
    }
    mock_get.return_value = json.dumps(mock_response)

    params = {"latitude": 28.566, "longitude": 77.186}
    response = client.get("/api/v1/attribution", params=params)

    assert response.status_code == 200
    data = response.json()
    assert data["primary_cause"] == "agricultural_burning"

    mock_set.assert_not_called()
