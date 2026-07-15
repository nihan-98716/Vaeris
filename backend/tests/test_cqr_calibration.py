import shutil
import tempfile
from pathlib import Path

import numpy as np

from backend.models.forecasting.cqr_calibration import CQRCalibrator


def test_cqr_calibrator_fit_and_calibrate():
    # Simple synthetic case: interval too narrow
    # True values consistently fall outside the bounds
    np.random.seed(42)
    y_cal = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    pred_lower = np.array([12.0, 22.0, 32.0, 42.0, 52.0])  # too high (narrow)
    pred_upper = np.array([8.0, 18.0, 28.0, 38.0, 48.0])  # too low (narrow)

    calibrator = CQRCalibrator(target_coverage=0.80)
    calibrator.fit(y_cal, pred_lower, pred_upper)

    # Correction should be computed and be positive (widening the interval)
    assert calibrator.correction is not None
    assert calibrator.correction > 0.0

    # Apply calibration
    cal_lower, cal_upper = calibrator.calibrate(pred_lower, pred_upper)

    # Calibrated interval must be wider than uncalibrated
    assert np.all(cal_lower < pred_lower)
    assert np.all(cal_upper > pred_upper)


def test_cqr_calibrator_serialization():
    y_cal = np.array([10.0, 20.0])
    pred_lower = np.array([9.0, 19.0])
    pred_upper = np.array([11.0, 21.0])

    calibrator = CQRCalibrator(target_coverage=0.80)
    calibrator.fit(y_cal, pred_lower, pred_upper)

    # Save to temp dir
    temp_dir = tempfile.mkdtemp()
    try:
        save_path = Path(temp_dir) / "calibration.json"
        calibrator.save(save_path)
        assert save_path.exists()

        # Load back
        loaded = CQRCalibrator()
        loaded.load(save_path)
        assert loaded.target_coverage == 0.80
        assert loaded.correction == calibrator.correction
    finally:
        shutil.rmtree(temp_dir)
