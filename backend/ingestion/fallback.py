from typing import Dict

from backend.logging import logger


class AllSourcesFailedError(Exception):
    """Exception raised when all input sources are marked as unhealthy/failed."""

    pass


def rebalance_weights(
    source_status: Dict[str, bool], default_weights: Dict[str, float]
) -> Dict[str, float]:
    """
    Implements graceful degradation with explicit re-normalization.
    If a source is unavailable (status = False), its weight is set to 0.0,
    and the remaining active sources are re-normalized proportionally to
    sum to 1.0 (100%).
    """
    logger.info(
        "Evaluating source health for weight rebalancing",
        extra={"source_status": source_status, "default_weights": default_weights},
    )

    # Filter for active healthy sources that are defined in default weights
    healthy_sources = [
        s for s, active in source_status.items() if active and s in default_weights
    ]

    if not healthy_sources:
        logger.critical(
            "Graceful degradation failed: All configured sources are unhealthy."
        )
        raise AllSourcesFailedError(
            "All configured data sources have failed; cannot balance weights."
        )

    # Calculate sum of active/healthy source weights
    sum_healthy = sum(default_weights[s] for s in healthy_sources)

    if sum_healthy <= 0.0:
        logger.critical("Sum of healthy source weights is zero or negative.")
        raise ValueError("Sum of healthy source weights must be greater than zero.")

    new_weights = {}
    for s in default_weights:
        if s in healthy_sources:
            new_weights[s] = round(default_weights[s] / sum_healthy, 4)
        else:
            new_weights[s] = 0.0

    logger.info(
        "Successfully rebalanced source weights",
        extra={"rebalanced_weights": new_weights},
    )
    return new_weights
