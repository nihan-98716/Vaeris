from backend.models.attribution.rule_engine import run_attribution
from backend.models.attribution.rules import (
    fire_attribution_rule,
    industrial_attribution_rule,
    stagnant_conditions_modifier,
    traffic_attribution_rule,
)


def test_fire_attribution_rule_success():
    # Active fire 36km away, bearing 90 (East), detected 5 hours ago.
    # Wind speed is 2.0 m/s (7.2 km/h).
    # Estimated transport time = 36 / 7.2 = 5 hours.
    # Wind direction is 90 degrees (blowing FROM East).
    # AQI spike is 30 points (exceeds threshold 15).
    signals = {
        "fire_events": [
            {"distance_km": 36.0, "bearing_deg": 90.0, "detected_hours_ago": 5.0}
        ],
        "wind_direction_deg": 90.0,
        "wind_speed_ms": 2.0,
        "road_density_500m": 0.2,
        "land_use_category": "residential",
        "aqi_now": 100.0,
        "aqi_rolling_mean_24h": 70.0,
        "hour_of_day": 12,
    }
    res = fire_attribution_rule(signals)
    assert res.source == "agricultural_burning"
    assert res.strength > 0.8
    assert len(res.evidence) == 3


def test_fire_attribution_rule_mismatched_wind():
    # Wind direction is 270 (blowing FROM West, opposing fire bearing of 90)
    signals = {
        "fire_events": [
            {"distance_km": 36.0, "bearing_deg": 90.0, "detected_hours_ago": 5.0}
        ],
        "wind_direction_deg": 270.0,
        "wind_speed_ms": 2.0,
        "road_density_500m": 0.2,
        "land_use_category": "residential",
        "aqi_now": 100.0,
        "aqi_rolling_mean_24h": 70.0,
        "hour_of_day": 12,
    }
    res = fire_attribution_rule(signals)
    assert res.strength == 0.0


def test_fire_attribution_rule_mismatched_timing():
    # Detected 12 hours ago but transport takes 5 hours
    signals = {
        "fire_events": [
            {"distance_km": 36.0, "bearing_deg": 90.0, "detected_hours_ago": 12.0}
        ],
        "wind_direction_deg": 90.0,
        "wind_speed_ms": 2.0,
        "road_density_500m": 0.2,
        "land_use_category": "residential",
        "aqi_now": 100.0,
        "aqi_rolling_mean_24h": 70.0,
        "hour_of_day": 12,
    }
    res = fire_attribution_rule(signals)
    assert res.strength == 0.0


def test_traffic_attribution_rule_success():
    # Commute hour (8 AM), high road density (0.8), AQI spike (20)
    signals = {
        "road_density_500m": 0.8,
        "hour_of_day": 8,
        "aqi_now": 120.0,
        "aqi_rolling_mean_24h": 100.0,
    }
    res = traffic_attribution_rule(signals)
    assert res.source == "traffic"
    assert res.strength >= 0.5
    assert len(res.evidence) == 2


def test_traffic_attribution_rule_non_commute():
    # Midday (12 PM), high density, AQI spike
    signals = {
        "road_density_500m": 0.8,
        "hour_of_day": 12,
        "aqi_now": 120.0,
        "aqi_rolling_mean_24h": 100.0,
    }
    res = traffic_attribution_rule(signals)
    assert res.strength == 0.0


def test_industrial_attribution_rule():
    # Industrial zone, continuous emission (12 PM, non-commute), AQI spike (20)
    signals = {
        "land_use_category": "industrial",
        "hour_of_day": 12,
        "aqi_now": 120.0,
        "aqi_rolling_mean_24h": 100.0,
    }
    res = industrial_attribution_rule(signals)
    assert res.source == "industrial"
    assert res.strength == 0.75


def test_stagnant_conditions_modifier():
    # Wind speed 0.5 m/s (stagnant) -> returns 0.6 dampener
    assert stagnant_conditions_modifier({"wind_speed_ms": 0.5}) == 0.6
    # Wind speed 3.0 m/s (clean/ventilated) -> returns 1.0
    assert stagnant_conditions_modifier({"wind_speed_ms": 3.0}) == 1.0


def test_run_attribution_end_to_end():
    # Simulate a traffic-dominant commute hour spike
    signals = {
        "fire_events": [],
        "wind_direction_deg": 180.0,
        "wind_speed_ms": 3.0,
        "road_density_500m": 0.8,
        "land_use_category": "residential",
        "aqi_now": 150.0,
        "aqi_rolling_mean_24h": 100.0,
        "hour_of_day": 8,
    }
    res = run_attribution(signals)
    assert res.primary_cause == "traffic"
    assert res.confidence_breakdown["traffic"] == 1.0
    assert res.confidence_breakdown["agricultural_burning"] == 0.0
    assert res.confidence_breakdown["industrial"] == 0.0


def test_run_attribution_graceful_degradation():
    # Traffic and industrial trigger, but traffic data source is unavailable
    signals = {
        "road_density_500m": 0.8,
        "land_use_category": "industrial",
        "aqi_now": 120.0,
        "aqi_rolling_mean_24h": 100.0,
        "hour_of_day": 8,
    }
    res = run_attribution(signals, unavailable_sources=["traffic"])
    assert res.primary_cause == "industrial"
    assert "traffic" in res.degraded_sources
    assert "traffic" not in res.confidence_breakdown
    assert res.confidence_breakdown["industrial"] == 1.0
