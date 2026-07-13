from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "Vaeris API"}


def test_forecast_endpoint_valid():
    # Pass valid coordinates and horizon
    params = {"latitude": 28.566, "longitude": 77.186, "horizon_hours": 24}
    response = client.get("/api/v1/forecast", params=params)
    assert response.status_code == 200

    data = response.json()
    assert "value" in data
    assert "lower_bound" in data
    assert "upper_bound" in data
    assert data["horizon_hours"] == 24
    assert data["confidence_tier"] == "reliable"


def test_forecast_endpoint_invalid_params():
    # Pass invalid latitude coordinate
    params = {"latitude": 150.0, "longitude": 77.186, "horizon_hours": 24}
    response = client.get("/api/v1/forecast", params=params)
    assert response.status_code == 422  # Validation Error


def test_attribution_endpoint_valid():
    params = {"latitude": 28.566, "longitude": 77.186}
    response = client.get("/api/v1/attribution", params=params)
    assert response.status_code == 200

    data = response.json()
    assert "primary_cause" in data
    assert "confidence_breakdown" in data
    assert "evidence" in data
    assert isinstance(data["evidence"], list)
