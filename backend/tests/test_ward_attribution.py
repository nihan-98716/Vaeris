"""
backend/tests/test_ward_attribution.py

Unit and integration tests for municipal ward boundary spatial joins and ward-level attribution.
"""

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.schemas import WardInfo
from backend.db.queries import find_ward_for_location

client = TestClient(app)


def test_find_ward_for_location_civil_lines():
    ward = find_ward_for_location(28.69, 77.21)
    assert "ward_id" in ward
    assert "ward_name" in ward
    assert "zone_name" in ward
    assert ward["city"] == "Delhi"


def test_find_ward_for_location_connaught_place():
    ward = find_ward_for_location(28.6139, 77.2090)
    assert ward["ward_id"] == "WARD_DEL_003"
    assert ward["ward_name"] == "Connaught Place Ward"
    assert ward["zone_name"] == "New Delhi Zone"


def test_attribution_endpoint_includes_ward_info():
    response = client.get("/api/v1/attribution", params={"latitude": 28.6139, "longitude": 77.2090})
    assert response.status_code == 200
    data = response.json()
    assert "ward_info" in data
    assert data["ward_info"] is not None
    assert "ward_id" in data["ward_info"]
    assert "ward_name" in data["ward_info"]
    assert "zone_name" in data["ward_info"]


def test_investigate_endpoint_includes_ward_info():
    response = client.get(
        "/api/v1/investigate",
        params={
            "latitude": 28.6139,
            "longitude": 77.2090,
            "enable_llm": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "attribution" in data
    assert "ward_info" in data["attribution"]
    assert data["attribution"]["ward_info"]["ward_name"] is not None
