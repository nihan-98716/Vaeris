"""
backend/agent/evidence_score.py

Consolidates the verifier checks and attribution confidence into an overall
evidence score and status level.
"""

from backend.agent.verifier import VerificationResult
from backend.api.schemas import EvidenceScoreResponse


def compute_evidence_score(
    primary_cause: str,
    verification_result: VerificationResult,
) -> EvidenceScoreResponse:
    """
    Computes a percentage-based confidence score and mapping status
    from the verifier result and attribution primary cause.
    """
    # 1. Base confidence is the verified primary cause's confidence percentage
    if primary_cause == "unknown":
        confidence_score = 0.0
    else:
        confidence_score = (
            verification_result.adjusted_confidence_breakdown.get(primary_cause, 0.0)
            * 100.0
        )

    # Ensure it lies in 0-100
    confidence_score = max(0.0, min(100.0, confidence_score))

    # 2. Determine confidence status tier
    if confidence_score >= 70.0:
        status = "high"
    elif confidence_score >= 40.0:
        status = "medium"
    else:
        status = "low"

    return EvidenceScoreResponse(
        confidence_score=round(confidence_score, 1),
        checklist=verification_result.checklist,
        status=status,
    )
