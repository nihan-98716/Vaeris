"""
backend/models/forecasting/ablation.py

Evaluation of the forecasting model against the two required baselines
(persistence, moving-average), plus quantile-specific metrics (pinball loss,
empirical coverage). See ML Model Specification, Section 6.7 and 6.8.

This module must be run on the held-out test set only, using the time-based
split from Section 4.3 — never on data used for training or validation.
"""

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np


@dataclass
class AblationReport:
    rmse_model_vs_persistence: float
    rmse_model_vs_moving_average: float
    rmse_persistence_baseline: float
    rmse_moving_average_baseline: float
    rmse_improvement_over_persistence_pct: float
    pinball_loss_q10: Optional[float] = None
    pinball_loss_q90: Optional[float] = None
    coverage_80pct_interval: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self, model_version: str, horizon_hours: int) -> str:
        lines = [
            f"## Ablation results — model version `{model_version}`, horizon {horizon_hours}h",
            "",
            "- RMSE (model, median forecast): reported relative to baselines below",
            f"- RMSE (persistence baseline): {self.rmse_persistence_baseline:.2f}",
            f"- RMSE (moving-average baseline): {self.rmse_moving_average_baseline:.2f}",
            f"- RMSE improvement over persistence: {self.rmse_improvement_over_persistence_pct:.1f}%",
        ]
        if self.pinball_loss_q10 is not None:
            lines.append(f"- Pinball loss (q10): {self.pinball_loss_q10:.3f}")
        if self.pinball_loss_q90 is not None:
            lines.append(f"- Pinball loss (q90): {self.pinball_loss_q90:.3f}")
        if self.coverage_80pct_interval is not None:
            lines.append(
                f"- Empirical coverage of the 80% interval (target ~0.80): "
                f"{self.coverage_80pct_interval:.2f}"
            )
        lines.append("")
        lines.append(
            "_These are the actual measured numbers on the held-out test set — "
            "report this figure regardless of whether it clears the target "
            "(ML Model Specification, Section 6.7)._"
        )
        return "\n".join(lines)


def compute_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def persistence_baseline_predictions(y_true_at_t: np.ndarray) -> np.ndarray:
    """
    Persistence baseline: predicted AQI at T+h == observed AQI at T.
    `y_true_at_t` must be the AQI value at the time the forecast was made
    (i.e. the `aqi_lag_1h`-equivalent value at prediction time), aligned
    row-for-row with the test set.
    """
    return np.asarray(y_true_at_t, dtype=float)


def moving_average_baseline_predictions(
    rolling_mean_24h_at_t: np.ndarray,
) -> np.ndarray:
    """
    Moving-average baseline: predicted AQI at T+h == rolling 24h mean AQI as of T.
    """
    return np.asarray(rolling_mean_24h_at_t, dtype=float)


def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, quantile: float) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    diff = y_true - y_pred
    return float(np.mean(np.maximum(quantile * diff, (quantile - 1) * diff)))


def empirical_coverage(
    y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray
) -> float:
    y_true = np.asarray(y_true, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    inside = (y_true >= lower) & (y_true <= upper)
    return float(np.mean(inside))


def run_ablation(
    y_true: np.ndarray,
    y_pred_median: np.ndarray,
    aqi_at_prediction_time: np.ndarray,
    rolling_mean_24h_at_prediction_time: np.ndarray,
    y_pred_lower: Optional[np.ndarray] = None,
    y_pred_upper: Optional[np.ndarray] = None,
) -> AblationReport:
    """
    Full ablation report for one horizon. All arrays must be aligned
    row-for-row against the same held-out test set.
    """
    persistence_pred = persistence_baseline_predictions(aqi_at_prediction_time)
    moving_avg_pred = moving_average_baseline_predictions(
        rolling_mean_24h_at_prediction_time
    )

    rmse_model = compute_rmse(y_true, y_pred_median)
    rmse_persistence = compute_rmse(y_true, persistence_pred)
    rmse_moving_avg = compute_rmse(y_true, moving_avg_pred)

    improvement_pct = (
        (rmse_persistence - rmse_model) / rmse_persistence * 100.0
        if rmse_persistence > 0
        else 0.0
    )

    report = AblationReport(
        rmse_model_vs_persistence=rmse_model,
        rmse_model_vs_moving_average=rmse_model,
        rmse_persistence_baseline=rmse_persistence,
        rmse_moving_average_baseline=rmse_moving_avg,
        rmse_improvement_over_persistence_pct=improvement_pct,
    )

    if y_pred_lower is not None and y_pred_upper is not None:
        report.pinball_loss_q10 = pinball_loss(y_true, y_pred_lower, 0.1)
        report.pinball_loss_q90 = pinball_loss(y_true, y_pred_upper, 0.9)
        report.coverage_80pct_interval = empirical_coverage(
            y_true, y_pred_lower, y_pred_upper
        )

    return report
