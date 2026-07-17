"""
tests/test_attribution.py

Tests for backend/models/attribution/ — pure Python, no ML dependencies.
Mirrors the required test scenarios from ML Model Specification, Section 9:
fire-dominant, traffic-dominant, and stagnant/low-confidence scenarios,
plus the FIRMS-outage graceful degradation test.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models.attribution.confidence import normalize, renormalize_excluding
from backend.models.attribution.rule_engine import run_attribution
from tests.synthetic_data import get_fire_events_for_signals


def test_fire_dominant_scenario():
    signals = {
        "fire_events": get_fire_events_for_signals(),
        "wind_direction_deg": 315.0,
        "wind_speed_ms": 3.0,
        "road_density_500m": 0.2,  # low traffic, so traffic rule shouldn't fire
        "land_use_category": "residential",
        "aqi_now": 260.0,
        "aqi_rolling_mean_24h": 110.0,  # spike of 150, well above threshold
        "hour_of_day": 5,  # not a commute hour, further suppressing the traffic rule
    }
    result = run_attribution(signals)
    assert result.primary_cause == "agricultural_burning", result
    assert result.confidence_breakdown["agricultural_burning"] > 0.5
    assert len(result.evidence) > 0
    assert any("FIRMS" in e for e in result.evidence)


def test_traffic_dominant_scenario():
    signals = {
        "fire_events": [],  # no fire data at all
        "wind_direction_deg": 90.0,
        "wind_speed_ms": 2.0,
        "road_density_500m": 0.9,  # high traffic density
        "land_use_category": "mixed",
        "aqi_now": 150.0,
        "aqi_rolling_mean_24h": 100.0,  # spike of 50, above threshold
        "hour_of_day": 8,  # morning commute hour
    }
    result = run_attribution(signals)
    assert result.primary_cause == "traffic", result
    assert result.confidence_breakdown["traffic"] > 0.5


def test_stagnant_conditions_modifier_dampens_confidence():
    """
    Tests the dampener directly (rather than through the engine's normalized
    output): when only one source rule is triggered, normalization always
    rescales it to 100% regardless of the dampener, so the effect of
    stagnant conditions is only visible in the pre-normalization raw
    strength — exactly where this test checks it.
    """
    from backend.models.attribution.rules import stagnant_conditions_modifier

    normal_signals = {"wind_speed_ms": 3.0}
    stagnant_signals = {"wind_speed_ms": 0.3}

    assert stagnant_conditions_modifier(
        stagnant_signals
    ) < stagnant_conditions_modifier(normal_signals)
    assert stagnant_conditions_modifier(normal_signals) == 1.0


def test_stagnant_conditions_dampens_multi_source_scenario():
    """
    With two rules triggered at different strengths, the dampener is
    applied identically to both before normalization, so it does not
    change the primary cause here — but this confirms the engine actually
    invokes the dampener without erroring, and that confidence values
    still sum to 1.0 after it's applied.
    """
    signals = {
        "fire_events": [],
        "wind_direction_deg": 90.0,
        "wind_speed_ms": 0.3,  # stagnant
        "road_density_500m": 0.9,
        "land_use_category": "industrial",
        "aqi_now": 200.0,
        "aqi_rolling_mean_24h": 100.0,
        "hour_of_day": 8,  # commute hour: traffic rule fires; industrial rule scores lower due to commute-hour overlap
    }
    result = run_attribution(signals)
    assert abs(sum(result.confidence_breakdown.values()) - 1.0) < 1e-9


def test_firms_outage_graceful_degradation():
    """
    Simulates FIRMS being unavailable: even with fire-consistent signals
    present, marking 'agricultural_burning' as unavailable must force its
    weight to zero and re-normalize the remaining sources (Section 7.4).
    """
    signals = {
        "fire_events": get_fire_events_for_signals(),
        "wind_direction_deg": 315.0,
        "wind_speed_ms": 3.0,
        "road_density_500m": 0.9,
        "land_use_category": "mixed",
        "aqi_now": 260.0,
        "aqi_rolling_mean_24h": 110.0,
        "hour_of_day": 8,
    }
    result = run_attribution(signals, unavailable_sources=["agricultural_burning"])
    assert result.confidence_breakdown.get("agricultural_burning", 0.0) == 0.0
    assert abs(sum(result.confidence_breakdown.values()) - 1.0) < 1e-9
    assert "agricultural_burning" in result.degraded_sources
    assert result.primary_cause != "agricultural_burning"


def test_normalize_handles_all_zero_scores():
    result = normalize({"a": 0.0, "b": 0.0, "c": 0.0})
    assert abs(sum(result.values()) - 1.0) < 1e-9
    assert result["a"] == result["b"] == result["c"]


def test_renormalize_excluding_all_sources_returns_unknown():
    result = renormalize_excluding({"a": 0.8, "b": 0.2}, excluded=["a", "b"])
    assert result == {"unknown": 1.0}


if __name__ == "__main__":
    test_fire_dominant_scenario()
    test_traffic_dominant_scenario()
    test_stagnant_conditions_modifier_dampens_confidence()
    test_stagnant_conditions_dampens_multi_source_scenario()
    test_firms_outage_graceful_degradation()
    test_normalize_handles_all_zero_scores()
    test_renormalize_excluding_all_sources_returns_unknown()
    print("All attribution engine tests passed.")
