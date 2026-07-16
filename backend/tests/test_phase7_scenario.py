"""
backend/tests/test_phase7_scenario.py

Phase 7 unit tests for the scenario approximation module and the
/api/v1/decision/scenario API endpoint.

Tests confirm:
- scenario_approximation correctly weights interventions by source type
- different sources produce different (correct) weighting outcomes
- the /scenario endpoint returns a valid ScenarioResponse
- projected AQI is always <= current AQI (interventions never make things worse)
- confidence labels map correctly to source_weight_factor ranges
- API endpoint gracefully handles edge cases (zero budget, no interventions)
"""

import pytest
from fastapi.testclient import TestClient

from backend.decision.optimizer import INTERVENTION_CATALOG
from backend.decision.scenario_approximation import compute_projected_aqi

# ─── Unit tests: compute_projected_aqi ────────────────────────────────────────


class TestComputeProjectedAqi:
    """Tests for the core scenario approximation function."""

    def _stub_interventions(self, ids):
        """Pull real intervention data from the catalog by id."""
        return [dict(i) for i in INTERVENTION_CATALOG if i["id"] in ids]

    def test_agricultural_burning_stubble_enforcement_high_weight(self):
        """stubble_burning_enforcement should have weight 1.0 for agricultural_burning."""
        interventions = self._stub_interventions(["stubble_burning_enforcement"])
        result = compute_projected_aqi(400.0, interventions, "agricultural_burning")
        # Weight = 1.0, so reduction = aqi_reduction * 1.0 = 45.0
        assert result["reduction_applied"] == pytest.approx(45.0, abs=0.1)
        assert result["confidence"] == "high"
        assert result["projected_aqi"] == pytest.approx(355.0, abs=0.5)

    def test_traffic_odd_even_high_weight(self):
        """odd_even_rationing should have weight 1.0 for traffic."""
        interventions = self._stub_interventions(["odd_even_rationing"])
        result = compute_projected_aqi(250.0, interventions, "traffic")
        # Weight = 1.0, reduction = 35.0
        assert result["reduction_applied"] == pytest.approx(35.0, abs=0.1)
        assert result["confidence"] == "high"
        assert result["projected_aqi"] < 250.0

    def test_industrial_restrict_industries_high_weight(self):
        """restrict_industries should have weight 1.0 for industrial."""
        interventions = self._stub_interventions(["restrict_industries"])
        result = compute_projected_aqi(320.0, interventions, "industrial")
        assert result["reduction_applied"] == pytest.approx(30.0, abs=0.1)
        assert result["confidence"] == "high"

    def test_mismatched_source_gives_lower_weight(self):
        """stubble_burning_enforcement against traffic source should give low weight."""
        interventions = self._stub_interventions(["stubble_burning_enforcement"])
        result_matched = compute_projected_aqi(
            400.0, interventions, "agricultural_burning"
        )
        result_mismatched = compute_projected_aqi(400.0, interventions, "traffic")
        assert (
            result_matched["reduction_applied"] > result_mismatched["reduction_applied"]
        )

    def test_projected_aqi_never_exceeds_current(self):
        """Interventions should never increase AQI."""
        interventions = self._stub_interventions(
            ["stubble_burning_enforcement", "odd_even_rationing", "road_sprinklers"]
        )
        for cause in ("agricultural_burning", "traffic", "industrial"):
            result = compute_projected_aqi(300.0, interventions, cause)
            assert (
                result["projected_aqi"] <= 300.0
            ), f"Projected AQI exceeded current for {cause}"

    def test_projected_aqi_floor_is_10(self):
        """Even with enormous reductions the floor is AQI 10."""
        # Use all interventions against their best source
        all_interventions = [dict(i) for i in INTERVENTION_CATALOG]
        result = compute_projected_aqi(50.0, all_interventions, "traffic")
        assert result["projected_aqi"] >= 10.0

    def test_empty_interventions_returns_zero_reduction(self):
        """With no interventions, projected AQI equals current AQI."""
        result = compute_projected_aqi(300.0, [], "traffic")
        assert result["reduction_applied"] == 0.0
        assert result["projected_aqi"] == pytest.approx(300.0, abs=0.1)

    def test_unknown_source_falls_back_to_defaults(self):
        """Unknown source key should not raise; falls back to default weights."""
        interventions = self._stub_interventions(["road_sprinklers"])
        result = compute_projected_aqi(200.0, interventions, "unknown_source")
        assert "projected_aqi" in result
        assert result["projected_aqi"] <= 200.0

    def test_percent_reduction_correct(self):
        """percent_reduction = (reduction / current) * 100."""
        interventions = self._stub_interventions(["stubble_burning_enforcement"])
        result = compute_projected_aqi(200.0, interventions, "agricultural_burning")
        expected_pct = round((result["reduction_applied"] / 200.0) * 100, 1)
        assert result["percent_reduction"] == pytest.approx(expected_pct, abs=0.2)

    def test_confidence_thresholds(self):
        """Verify confidence labels correspond to avg_weight thresholds."""
        # stubble_burning_enforcement has weight 1.0 against agricultural_burning → 'high'
        high = compute_projected_aqi(
            300.0,
            self._stub_interventions(["stubble_burning_enforcement"]),
            "agricultural_burning",
        )
        assert high["confidence"] == "high"
        assert high["source_weight_factor"] >= 0.7

        # stubble_burning_enforcement has weight 0.1 against traffic → 'low'
        low = compute_projected_aqi(
            300.0,
            self._stub_interventions(["stubble_burning_enforcement"]),
            "traffic",
        )
        assert low["confidence"] == "low"
        assert low["source_weight_factor"] < 0.4

    def test_output_keys_present(self):
        """All expected keys must be present in the output dict."""
        result = compute_projected_aqi(
            250.0,
            self._stub_interventions(["road_sprinklers"]),
            "traffic",
        )
        for key in (
            "projected_aqi",
            "reduction_applied",
            "source_weight_factor",
            "confidence",
            "current_aqi",
            "percent_reduction",
        ):
            assert key in result, f"Missing key: {key}"


# ─── API endpoint tests: /api/v1/decision/scenario ───────────────────────────


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient for the FastAPI app (DB not required for this endpoint)."""
    from backend.api.main import app

    with TestClient(app) as c:
        yield c


class TestScenarioEndpoint:
    """Integration tests for GET /api/v1/decision/scenario."""

    def test_scenario_returns_200_with_valid_params(self, client):
        resp = client.get(
            "/api/v1/decision/scenario",
            params={
                "current_aqi": 350.0,
                "budget": 5000,
                "inspectors": 10,
                "max_travel_time_hours": 3.0,
                "primary_cause": "agricultural_burning",
            },
        )
        assert resp.status_code == 200, resp.text

    def test_scenario_response_has_required_fields(self, client):
        resp = client.get(
            "/api/v1/decision/scenario",
            params={"current_aqi": 300.0, "primary_cause": "traffic"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for key in (
            "projected_aqi",
            "reduction_applied",
            "source_weight_factor",
            "confidence",
            "current_aqi",
            "percent_reduction",
            "decision",
        ):
            assert key in data, f"Missing field: {key}"

    def test_projected_aqi_labeling_not_actual(self, client):
        """Confirm no 'actual' in the response JSON keys (terminology check)."""
        resp = client.get(
            "/api/v1/decision/scenario",
            params={"current_aqi": 200.0},
        )
        assert resp.status_code == 200
        raw = resp.text.lower()
        # 'projected_aqi' is expected; the word 'actual' must not appear as a key
        assert '"actual"' not in raw

    def test_projected_aqi_does_not_exceed_current(self, client):
        current = 400.0
        resp = client.get(
            "/api/v1/decision/scenario",
            params={"current_aqi": current, "budget": 10000, "inspectors": 20},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["projected_aqi"] <= current

    def test_decision_contains_selected_interventions(self, client):
        resp = client.get(
            "/api/v1/decision/scenario",
            params={"current_aqi": 300.0, "budget": 5000, "inspectors": 6},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data
        assert "selected_interventions" in data["decision"]
        assert isinstance(data["decision"]["selected_interventions"], list)

    def test_zero_budget_returns_empty_interventions(self, client):
        resp = client.get(
            "/api/v1/decision/scenario",
            params={"current_aqi": 300.0, "budget": 0, "inspectors": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"]["selected_interventions"] == []
        assert data["reduction_applied"] == 0.0
        assert data["projected_aqi"] == pytest.approx(300.0, abs=0.1)

    def test_health_benefit_terminology(self, client):
        """Confirm the decision response contains health_benefit (not DALY)."""
        resp = client.get(
            "/api/v1/decision/scenario",
            params={"current_aqi": 350.0, "budget": 5000},
        )
        assert resp.status_code == 200
        raw = resp.text
        assert "daly" not in raw.lower()
        # health_benefit is the correct field name
        assert "health_benefit" in raw.lower()
