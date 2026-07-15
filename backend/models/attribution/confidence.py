"""
backend/models/attribution/confidence.py

Confidence normalization for attribution outputs — ML Model Specification,
Section 7.3 and 7.4 (graceful degradation formula).
"""

from typing import Dict, Iterable


def normalize(scores: Dict[str, float]) -> Dict[str, float]:
    """
    Normalizes a dict of raw rule strengths so they sum to 1.0.

    If all scores are zero (no rule triggered with any confidence), returns
    an equal split across all provided keys rather than dividing by zero —
    this represents "no dominant source identified" rather than a crash.
    """
    total = sum(scores.values())
    if total <= 0:
        n = len(scores) or 1
        return dict.fromkeys(scores, 1.0 / n)
    return {k: v / total for k, v in scores.items()}


def renormalize_excluding(
    scores: Dict[str, float], excluded: Iterable[str]
) -> Dict[str, float]:
    """
    Graceful degradation formula (ML Model Specification, Section 7.4):
    if a source's underlying data is unavailable (e.g. FIRMS is down, so
    "agricultural_burning" cannot be evaluated), its weight is forced to
    zero and the REMAINING sources are re-normalized to sum to 1.0 —
    never left as a silent gap, never dividing by a stale denominator.
    """
    excluded = set(excluded)
    remaining = {k: v for k, v in scores.items() if k not in excluded}
    if not remaining:
        # Every source was excluded — nothing left to attribute to.
        # Return an explicit "unknown" bucket rather than an empty dict.
        return {"unknown": 1.0}
    return normalize(remaining)
