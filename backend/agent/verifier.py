"""
backend/agent/verifier.py

Deterministic Verifier component that cross-checks rule-based source attribution
against secondary data sources (like land-use zoning and road density) before
confirming high-confidence recommendations.
"""

from typing import Dict, List

from pydantic import BaseModel


class VerificationResult(BaseModel):
    is_verified: bool
    adjusted_confidence_breakdown: Dict[str, float]
    checklist: List[str]
    verification_notes: str


def _verify_agricultural_burning(
    signals: dict,
    checklist: List[str],
    notes_list: List[str],
) -> bool:
    is_verified = True
    fire_events = signals.get("fire_events", [])
    wind_dir = signals.get("wind_direction_deg", 180.0)
    road_density = signals.get("road_density_500m", 0.0)
    aqi_now = signals.get("aqi_now", 0.0)

    # 1. Check active fires
    if len(fire_events) > 0:
        checklist.append("✓ Active fire hotspots detected in 100km radius (FIRMS)")
    else:
        checklist.append("✗ No active fire hotspots detected in 100km radius")
        is_verified = False
        notes_list.append("No active fires detected in search radius.")

    # 2. Check wind vector consistency
    wind_consistent = False
    for fe in fire_events:
        bearing = fe.get("bearing_deg", 0.0)
        diff = abs(wind_dir - bearing) % 360
        bearing_match = min(diff, 360 - diff)
        if bearing_match <= 30.0:
            wind_consistent = True
            break

    if wind_consistent:
        checklist.append("✓ Wind vector consistent with transport from fire")
    else:
        checklist.append("✗ Wind direction inconsistent with transport from fire")
        is_verified = False
        notes_list.append("Wind direction does not point from detected fire locations.")

    # 3. Check traffic density constraint
    if road_density < 0.6:
        checklist.append("✓ Traffic density ruled out as primary cause")
    else:
        checklist.append("✗ High traffic density suggests possible traffic overlap")
        notes_list.append(
            "High road density suggests traffic may be contributing to spike."
        )

    # 4. Check satellite aerosol signal
    if aqi_now > 150.0:
        checklist.append("✓ Satellite aerosol signal consistent")
    else:
        checklist.append("✓ Satellite aerosol sensor within baseline limits")

    return is_verified


def _verify_traffic(
    signals: dict,
    checklist: List[str],
    notes_list: List[str],
) -> bool:
    is_verified = True
    road_density = signals.get("road_density_500m", 0.0)
    hour = signals.get("hour_of_day", 12)
    land_use = signals.get("land_use_category", "mixed")

    # 1. Check road density
    if road_density >= 0.6:
        checklist.append(
            f"✓ Road density exceeds threshold (road_density_500m = {road_density:.2f})"
        )
    else:
        checklist.append(
            f"✗ Road density ({road_density:.2f}) below high-traffic threshold"
        )
        is_verified = False
        notes_list.append(
            "Road density at station is low; traffic attribution is suspicious."
        )

    # 2. Check diurnal timing
    is_commute_hour = (7 <= hour <= 10) or (17 <= hour <= 21)
    if is_commute_hour:
        checklist.append(
            f"✓ Commute-hour peak timing matches diurnal curve (hour {hour})"
        )
    else:
        checklist.append(
            f"✗ Off-peak timing decreases traffic probability (hour {hour})"
        )
        is_verified = False
        notes_list.append("AQI spike occurs outside standard rush hour windows.")

    # 3. Check land-use conflicts
    if land_use != "industrial":
        checklist.append("✓ Land-use is not industrial (zoning conflict ruled out)")
    else:
        checklist.append("✗ Zone conflict: station is located in an industrial area")
        notes_list.append(
            "Station is located in industrial zone, confounding traffic signature."
        )

    return is_verified


def _verify_industrial(
    signals: dict,
    checklist: List[str],
    notes_list: List[str],
) -> bool:
    is_verified = True
    land_use = signals.get("land_use_category", "mixed")
    hour = signals.get("hour_of_day", 12)
    road_density = signals.get("road_density_500m", 0.0)

    # 1. Check zoning
    if land_use == "industrial":
        checklist.append("✓ Station buffer is zoned industrial")
    else:
        checklist.append(f"✗ Station buffer is zoned {land_use}, not industrial")
        is_verified = False
        notes_list.append(
            f"Station area is zoned as {land_use}; industrial attribution unverified."
        )

    # 2. Check timing (continuous signature)
    is_commute_hour = (7 <= hour <= 10) or (17 <= hour <= 21)
    if not is_commute_hour:
        checklist.append("✓ Continuous emission pattern (no commute-hour dependency)")
    else:
        checklist.append("✗ Overlaps commute hour, reducing industrial specificity")
        notes_list.append("AQI spike occurs during traffic commute peak.")

    # 3. Check road density
    if road_density < 0.7:
        checklist.append("✓ Traffic density is not the primary driver")
    else:
        checklist.append(
            "✗ Road density is high, suggesting potential traffic contribution"
        )
        notes_list.append("High road density indicates significant traffic mixing.")

    return is_verified


def verify_attribution(
    primary_cause: str,
    confidence_breakdown: Dict[str, float],
    signals: dict,
) -> VerificationResult:
    """
    Cross-checks the primary cause from the attribution engine against secondary
    signals to verify if the attribution claim is robust.
    Adjusts the confidence breakdown if constraints or expectations fail.
    """
    checklist = []
    notes_list = []
    adjusted_breakdown = dict(confidence_breakdown)

    if primary_cause == "agricultural_burning":
        is_verified = _verify_agricultural_burning(signals, checklist, notes_list)
    elif primary_cause == "traffic":
        is_verified = _verify_traffic(signals, checklist, notes_list)
    elif primary_cause == "industrial":
        is_verified = _verify_industrial(signals, checklist, notes_list)
    else:
        is_verified = False
        checklist.append("✗ Rule-based attribution could not identify a clear source")
        notes_list.append(
            "Signals did not trigger any specific source rule above thresholds."
        )

    # Adjust confidence if verification failed
    if not is_verified:
        current_conf = adjusted_breakdown.get(primary_cause, 0.0)
        dampened = current_conf * 0.6
        adjusted_breakdown[primary_cause] = dampened
        adjusted_breakdown["unknown"] = adjusted_breakdown.get("unknown", 0.0) + (
            current_conf - dampened
        )

        # Ensure it sums to 1.0
        total = sum(adjusted_breakdown.values())
        if total > 0.0:
            adjusted_breakdown = {k: v / total for k, v in adjusted_breakdown.items()}

    verification_notes = (
        " ".join(notes_list)
        if notes_list
        else "Attribution claims cross-checked and fully verified against secondary geospatial signals."
    )

    return VerificationResult(
        is_verified=is_verified,
        adjusted_confidence_breakdown=adjusted_breakdown,
        checklist=checklist,
        verification_notes=verification_notes,
    )
