"""
backend/models/forecasting/cqr_calibration.py

Conformalized Quantile Regression (CQR) calibration module for post-hoc
calibration of quantile prediction intervals. Used to adjust prediction
intervals to achieve target coverage guarantees on held-out data.
"""

import json
import math
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import lightgbm as lgb
import numpy as np

from backend.models import registry


class CQRCalibrator:
    """
    Conformalized Quantile Regression (CQR) calibrator.

    Computes a post-hoc calibration correction value from a held-out
    validation/calibration set and applies it to new predictions to achieve the
    target coverage.
    """

    def __init__(self, target_coverage: float = 0.80) -> None:
        """
        Initialize the calibrator.

        Parameters
        ----------
        target_coverage : float, default=0.80
            The target coverage probability (e.g. 0.80 for 80% intervals).
        """
        self.target_coverage = target_coverage
        self.correction: Optional[float] = None

    def fit(
        self,
        y_cal,
        pred_lower_cal,
        pred_upper_cal,
        target_coverage: float = 0.80,
    ) -> "CQRCalibrator":
        """
        Compute the calibration correction from a held-out calibration set.

        Parameters
        ----------
        y_cal : array-like
            True target values in the calibration set.
        pred_lower_cal : array-like
            Predicted lower quantile (q10) for the calibration set.
        pred_upper_cal : array-like
            Predicted upper quantile (q90) for the calibration set.
        target_coverage : float, default=0.80
            The desired coverage probability of the prediction intervals.

        Returns
        -------
        CQRCalibrator
            The fitted calibrator instance.
        """
        y_cal = np.asarray(y_cal)
        pred_lower_cal = np.asarray(pred_lower_cal)
        pred_upper_cal = np.asarray(pred_upper_cal)

        if len(y_cal) == 0:
            raise ValueError("Calibration set cannot be empty.")
        if len(y_cal) != len(pred_lower_cal) or len(y_cal) != len(pred_upper_cal):
            raise ValueError(
                f"Length mismatch: y_cal ({len(y_cal)}), "
                f"pred_lower_cal ({len(pred_lower_cal)}), "
                f"pred_upper_cal ({len(pred_upper_cal)}) must all be of the same length."
            )

        self.target_coverage = target_coverage

        # Compute nonconformity scores: E_i = max(pred_lower - y_true, y_true - pred_upper)
        scores = np.maximum(pred_lower_cal - y_cal, y_cal - pred_upper_cal)

        # Compute the correction as the ceil((n+1) * target_coverage) / n-th quantile of the scores
        n = len(scores)
        q_level = math.ceil((n + 1) * target_coverage) / n

        # Clip quantile level to [0.0, 1.0] to handle boundary issues / small datasets
        q_level = min(1.0, max(0.0, q_level))

        # Compute the correction value using numpy's quantile
        self.correction = float(np.quantile(scores, q_level))
        return self

    def calibrate(
        self,
        pred_lower,
        pred_upper,
    ) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
        """
        Apply the calibration correction to new predictions.

        Parameters
        ----------
        pred_lower : array-like or float
            Uncalibrated lower quantile predictions.
        pred_upper : array-like or float
            Uncalibrated upper quantile predictions.

        Returns
        -------
        Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]
            Calibrated (lower, upper) predictions.
        """
        if self.correction is None:
            raise ValueError("Calibrator has not been fitted or loaded yet.")

        # Return symmetric widening: (pred_lower - correction, pred_upper + correction)
        return pred_lower - self.correction, pred_upper + self.correction

    def save(self, path: Union[str, Path]) -> None:
        """
        Persist the calibration state (JSON).

        Parameters
        ----------
        path : str or Path
            The file path where the JSON state should be saved.
        """
        if self.correction is None:
            raise ValueError("Calibrator must be fitted before saving.")

        state = {
            "target_coverage": self.target_coverage,
            "correction": self.correction,
        }

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def load(self, path: Union[str, Path]) -> "CQRCalibrator":
        """
        Restore the calibration state (JSON).

        Parameters
        ----------
        path : str or Path
            The file path from which the JSON state should be loaded.

        Returns
        -------
        CQRCalibrator
            The loaded calibrator instance.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Calibration file not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        self.target_coverage = state["target_coverage"]
        self.correction = state["correction"]
        return self


def calibrate_from_splits(
    boosters: Dict[str, lgb.Booster],
    X_cal,
    y_cal,
    target_coverage: float = 0.80,
) -> CQRCalibrator:
    """
    Convenience function to fit a CQRCalibrator from trained LightGBM boosters.

    Parameters
    ----------
    boosters : dict of str to lgb.Booster
        Trained LightGBM boosters dict (keys: "q10", "q50", "q90").
    X_cal : array-like or DataFrame
        Features for the calibration set.
    y_cal : array-like
        True target values for the calibration set.
    target_coverage : float, default=0.80
        The desired coverage probability of the prediction intervals.

    Returns
    -------
    CQRCalibrator
        The fitted CQRCalibrator.
    """
    for q_key in ("q10", "q90"):
        if q_key not in boosters:
            raise KeyError(f"Booster dictionary is missing required key '{q_key}'")

    booster_q10 = boosters["q10"]
    booster_q90 = boosters["q90"]

    # Use best_iteration if available
    num_iter_q10 = getattr(booster_q10, "best_iteration", -1)
    num_iter_q90 = getattr(booster_q90, "best_iteration", -1)

    pred_lower = booster_q10.predict(
        X_cal, num_iteration=num_iter_q10 if num_iter_q10 > 0 else -1
    )
    pred_upper = booster_q90.predict(
        X_cal, num_iteration=num_iter_q90 if num_iter_q90 > 0 else -1
    )

    calibrator = CQRCalibrator(target_coverage=target_coverage)
    calibrator.fit(
        y_cal=y_cal,
        pred_lower_cal=pred_lower,
        pred_upper_cal=pred_upper,
        target_coverage=target_coverage,
    )
    return calibrator


def save_calibration(
    component: str,
    version_id: str,
    calibrator: CQRCalibrator,
    registry_root: Optional[str] = None,
) -> Path:
    """
    Save the calibration state to the specified model version directory in the registry.

    Parameters
    ----------
    component : str
        The model component name (e.g., "forecasting").
    version_id : str
        The version ID of the model (e.g., "v1_2026-07-10").
    calibrator : CQRCalibrator
        The fitted CQRCalibrator instance to save.
    registry_root : str, optional
        Custom root directory of the model registry.

    Returns
    -------
    Path
        The path where the calibration state was saved.
    """
    reg_root = registry_root or registry.DEFAULT_REGISTRY_ROOT
    version_dir = Path(reg_root) / component / version_id

    if not version_dir.exists():
        raise FileNotFoundError(
            f"Model version directory does not exist: {version_dir}. "
            "Please register the model version before saving calibration."
        )

    calibration_path = version_dir / "calibration.json"
    calibrator.save(calibration_path)
    return calibration_path


def load_calibration(
    component: str,
    registry_root: Optional[str] = None,
) -> CQRCalibrator:
    """
    Load the calibration state from the latest registered version of a component.

    Parameters
    ----------
    component : str
        The model component name (e.g., "forecasting").
    registry_root : str, optional
        Custom root directory of the model registry.

    Returns
    -------
    CQRCalibrator
        The loaded CQRCalibrator instance.
    """
    version_dir, _ = registry.load_latest(component, registry_root=registry_root)
    calibration_path = version_dir / "calibration.json"

    if not calibration_path.exists():
        raise FileNotFoundError(
            f"No calibration.json found in the latest version directory: {version_dir}"
        )

    calibrator = CQRCalibrator()
    calibrator.load(calibration_path)
    return calibrator
