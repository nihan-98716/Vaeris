"""
backend/models/attribution/rules.py

Individual attribution rules — ML Model Specification, Section 7.2.

This is deliberately NOT a trained classifier (see Section 7.1 for why).
Each rule is a deterministic function of real, cited signals, returning a
raw trigger strength (0.0-1.0) and a list of human-readable evidence
strings. The rule_engine module combines and normalizes these.

Expected `signals` dict schema (built upstream from ingested + engineered
data, see features.py and the ingestion layer):

    fire_events: List[dict]        # [{"distance_km": float, "bearing_deg": float, "detected_hours_ago": float}, ...]
    wind_direction_deg: float      # direction the wind is blowing FROM, 0-360
    wind_speed_ms: float
    road_density_500m: float
    land_use_category: str         # "industrial" | "residential" | "agricultural" | "mixed"
    aqi_now: float
    aqi_rolling_mean_24h: float
    hour_of_day: int               # 0-23, local time at the station
"""

from typing import List

from backend.config import settings
from backend.models.schemas import RuleResult

# --- tunable thresholds loaded dynamically from settings ---
FIRE_SEARCH_RADIUS_KM = settings.attribution.fire_search_radius_km
FIRE_BEARING_TOLERANCE_DEG = settings.attribution.fire_bearing_tolerance_deg
TRANSPORT_SPEED_TOLERANCE_HOURS = settings.attribution.transport_speed_tolerance_hours
ROAD_DENSITY_HIGH_TRAFFIC_THRESHOLD = (
    settings.attribution.road_density_high_traffic_threshold
)
AQI_SPIKE_THRESHOLD = settings.attribution.aqi_spike_threshold
STAGNANT_WIND_SPEED_MS = settings.attribution.stagnant_wind_speed_ms


def _angle_difference(a: float, b: float) -> float:
    """Smallest difference between two compass bearings, 0-180 degrees."""
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def _estimated_transport_hours(distance_km: float, wind_speed_ms: float) -> float:
    if wind_speed_ms <= 0:
        return float("inf")
    speed_km_per_hour = wind_speed_ms * 3.6
    return distance_km / speed_km_per_hour


def fire_attribution_rule(signals: dict) -> RuleResult:
    """
    Fire / agricultural-burning attribution — the compound causal chain
    described in ML Model Specification Section 7.2: a FIRMS detection,
    consistent wind direction, and a plausibly-timed downstream AQI spike.
    """
    fire_events: List[dict] = signals.get("fire_events", [])
    wind_direction_deg = signals.get("wind_direction_deg")
    wind_speed_ms = signals.get("wind_speed_ms", 0.0)
    aqi_spike = signals.get("aqi_now", 0.0) - signals.get("aqi_rolling_mean_24h", 0.0)

    if not fire_events or wind_direction_deg is None or aqi_spike < AQI_SPIKE_THRESHOLD:
        return RuleResult(source="agricultural_burning", strength=0.0, evidence=[])

    best_strength = 0.0
    best_evidence: List[str] = []

    for event in fire_events:
        distance_km = event.get("distance_km")
        bearing_deg = event.get("bearing_deg")
        detected_hours_ago = event.get("detected_hours_ago")
        if distance_km is None or bearing_deg is None or detected_hours_ago is None:
            continue
        if distance_km > FIRE_SEARCH_RADIUS_KM:
            continue

        # The station is downwind of the fire if the wind is blowing FROM the
        # fire's bearing TOWARD the station — i.e. wind_direction_deg should
        # be close to bearing_deg (bearing is measured from station to fire).
        bearing_match = _angle_difference(wind_direction_deg, bearing_deg)
        if bearing_match > FIRE_BEARING_TOLERANCE_DEG:
            continue

        expected_transport_hours = _estimated_transport_hours(
            distance_km, wind_speed_ms
        )
        timing_match = (
            abs(expected_transport_hours - detected_hours_ago)
            <= TRANSPORT_SPEED_TOLERANCE_HOURS
        )
        if not timing_match:
            continue

        # Strength scales with how tight the bearing match is and how close
        # the timing match is — both closer to ideal increases confidence.
        bearing_score = 1.0 - (bearing_match / FIRE_BEARING_TOLERANCE_DEG)
        timing_score = 1.0 - (
            abs(expected_transport_hours - detected_hours_ago)
            / TRANSPORT_SPEED_TOLERANCE_HOURS
        )
        strength = max(0.0, min(1.0, 0.5 * bearing_score + 0.5 * timing_score))

        if strength > best_strength:
            best_strength = strength
            best_evidence = [
                f"FIRMS fire detection {distance_km:.0f}km away, bearing {bearing_deg:.0f} degrees",
                f"Wind direction {wind_direction_deg:.0f} degrees consistent with transport from detected fire "
                f"(bearing match within {bearing_match:.0f} degrees)",
                f"AQI spike ({aqi_spike:.0f} points above 24h rolling mean) consistent with "
                f"~{expected_transport_hours:.1f}h transport window (fire detected {detected_hours_ago:.1f}h ago)",
            ]

    return RuleResult(
        source="agricultural_burning", strength=best_strength, evidence=best_evidence
    )


def traffic_attribution_rule(signals: dict) -> RuleResult:
    """
    Traffic attribution: high road density near the station, plus a
    commute-hour diurnal AQI pattern (elevated during typical commute
    windows, not a flat/overnight elevation).
    """
    road_density = signals.get("road_density_500m", 0.0)
    hour_of_day = signals.get("hour_of_day")
    aqi_spike = signals.get("aqi_now", 0.0) - signals.get("aqi_rolling_mean_24h", 0.0)

    if (
        road_density < ROAD_DENSITY_HIGH_TRAFFIC_THRESHOLD
        or aqi_spike < AQI_SPIKE_THRESHOLD
    ):
        return RuleResult(source="traffic", strength=0.0, evidence=[])

    is_commute_hour = hour_of_day is not None and (
        (7 <= hour_of_day <= 10) or (17 <= hour_of_day <= 21)
    )
    if not is_commute_hour:
        return RuleResult(source="traffic", strength=0.0, evidence=[])

    density_score = min(1.0, road_density)
    strength = round(
        0.5 + 0.5 * density_score, 3
    )  # commute-hour match plus density-scaled boost
    strength = min(strength, 1.0)

    evidence = [
        f"Road density near station ({road_density:.2f}) exceeds high-traffic threshold "
        f"({ROAD_DENSITY_HIGH_TRAFFIC_THRESHOLD:.2f})",
        f"AQI spike occurs during a typical commute-hour window (hour {hour_of_day})",
    ]
    return RuleResult(source="traffic", strength=strength, evidence=evidence)


def industrial_attribution_rule(signals: dict) -> RuleResult:
    """
    Industrial attribution: station's land-use buffer is classified
    industrial, and the AQI elevation does NOT show the commute-hour
    pattern (i.e. more consistent with continuous emission).
    """
    land_use = signals.get("land_use_category")
    hour_of_day = signals.get("hour_of_day")
    aqi_spike = signals.get("aqi_now", 0.0) - signals.get("aqi_rolling_mean_24h", 0.0)

    if land_use != "industrial" or aqi_spike < AQI_SPIKE_THRESHOLD:
        return RuleResult(source="industrial", strength=0.0, evidence=[])

    is_commute_hour = hour_of_day is not None and (
        (7 <= hour_of_day <= 10) or (17 <= hour_of_day <= 21)
    )
    # Industrial attribution is stronger precisely when it's NOT a commute-hour
    # pattern — that's what distinguishes it from the traffic rule above.
    strength = 0.75 if not is_commute_hour else 0.35

    evidence = [
        "Station's 500m buffer is classified as industrial land use",
        (
            "AQI elevation does not follow a commute-hour diurnal pattern, "
            "consistent with continuous industrial emission"
            if not is_commute_hour
            else "AQI elevation overlaps a commute-hour window, reducing confidence relative to a pure industrial signature"
        ),
    ]
    return RuleResult(source="industrial", strength=strength, evidence=evidence)


def stagnant_conditions_modifier(signals: dict) -> float:
    """
    Not a source-attribution rule — a confidence DAMPENER applied across
    all triggered rules when wind is stagnant (favors diffuse local
    accumulation over a single attributable source). Returns a multiplier
    in (0, 1]; 1.0 means no dampening.
    """
    wind_speed_ms = signals.get("wind_speed_ms", 10.0)
    if wind_speed_ms < STAGNANT_WIND_SPEED_MS:
        return 0.6  # meaningfully reduce confidence in any single-source attribution
    return 1.0
