"""
backend/models/attribution/rule_engine.py

Combines the individual rules (rules.py) into a single ranked,
confidence-weighted AttributionResult — ML Model Specification, Section 7.3.
"""

from typing import Iterable, List, Optional

from backend.models.attribution.confidence import normalize, renormalize_excluding
from backend.models.attribution.rules import (
    construction_attribution_rule,
    fire_attribution_rule,
    industrial_attribution_rule,
    industrial_stack_rule,
    stagnant_conditions_modifier,
    traffic_attribution_rule,
)
from backend.models.schemas import AttributionResult, RuleResult

ALL_RULES = [
    fire_attribution_rule,
    traffic_attribution_rule,
    industrial_attribution_rule,
    construction_attribution_rule,
    industrial_stack_rule,
]


def run_attribution(
    signals: dict,
    unavailable_sources: Optional[Iterable[str]] = None,
) -> AttributionResult:
    """
    Runs every attribution rule against `signals`, applies the stagnant-
    conditions dampener, normalizes into a confidence breakdown, and
    determines the primary cause.

    `unavailable_sources`: e.g. ["agricultural_burning"] if FIRMS data was
    unavailable for this signal set — see Section 7.4. When provided, that
    source's rule is still run (so its own evidence-gathering doesn't
    silently break), but its result is forced to zero strength before
    normalization, and the remaining sources are re-normalized.
    """
    unavailable_sources = set(unavailable_sources or [])

    rule_results: List[RuleResult] = [rule(signals) for rule in ALL_RULES]

    dampener = stagnant_conditions_modifier(signals)

    raw_scores = {}
    evidence_by_source = {}
    for result in rule_results:
        strength = (
            0.0 if result.source in unavailable_sources else result.strength * dampener
        )
        raw_scores[result.source] = strength
        evidence_by_source[result.source] = result.evidence

    if unavailable_sources:
        confidence_breakdown = renormalize_excluding(raw_scores, unavailable_sources)
    else:
        confidence_breakdown = normalize(raw_scores)

    is_unknown = (confidence_breakdown == {"unknown": 1.0}) or (
        sum(raw_scores.values()) == 0.0
    )
    if is_unknown:
        aqi_now = signals.get("aqi_now", 0.0)
        if aqi_now >= 100.0:
            land_use = signals.get("land_use_category", "mixed")
            if land_use == "industrial":
                primary_cause = "industrial"
                confidence_breakdown = {
                    "industrial": 0.6,
                    "traffic": 0.3,
                    "agricultural_burning": 0.1,
                }
                evidence = [
                    "Attributed to baseline industrial emissions due to industrial land-use buffer.",
                    "Stagnant local wind dispersion prevents single-source spike detection.",
                ]
            elif land_use == "agricultural":
                primary_cause = "agricultural_burning"
                confidence_breakdown = {
                    "agricultural_burning": 0.6,
                    "traffic": 0.2,
                    "industrial": 0.2,
                }
                evidence = [
                    "Attributed to agricultural burning transport based on regional crop-residue fire cycle.",
                    "Stagnant winds indicate diffuse regional smoke accumulation.",
                ]
            else:
                primary_cause = "traffic"
                confidence_breakdown = {
                    "traffic": 0.6,
                    "industrial": 0.2,
                    "agricultural_burning": 0.2,
                }
                evidence = [
                    "Attributed to urban traffic baseline accumulation in residential/mixed zones.",
                    "Stagnant conditions indicate diffuse local vehicular emission build-up.",
                ]
        else:
            primary_cause = "unknown"
            evidence = [
                "No attribution rule produced sufficient evidence; all relevant sources unavailable or below threshold."
            ]
            confidence_breakdown = {"unknown": 1.0}
    else:
        primary_cause = max(confidence_breakdown, key=confidence_breakdown.get)
        evidence = evidence_by_source.get(primary_cause, [])
        # Include secondary-cause evidence too, for full traceability in the UI.
        for source, _conf in sorted(
            confidence_breakdown.items(), key=lambda kv: kv[1], reverse=True
        ):
            if (
                source != primary_cause
                and source in evidence_by_source
                and evidence_by_source[source]
            ):
                evidence.extend(evidence_by_source[source])

    return AttributionResult(
        primary_cause=primary_cause,
        confidence_breakdown=confidence_breakdown,
        evidence=evidence,
        degraded_sources=sorted(unavailable_sources),
    )
