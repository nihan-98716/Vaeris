"""
tests/test_health_impact.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models.health_impact import DISCLAIMER, estimate_exposure_risk


def test_disclaimer_never_mentions_daly():
    assert "DALY" not in DISCLAIMER
    assert "daly" not in DISCLAIMER.lower()


def test_estimate_exposure_risk_basic():
    result = estimate_exposure_risk(
        forecast_pm25=180.0, baseline_pm25=60.0, exposed_population=50000
    )
    assert result.indicative_risk_score > 0
    assert result.exposed_population == 50000
    assert result.disclaimer == DISCLAIMER


def test_estimate_exposure_risk_no_negative_excess():
    # forecast below baseline should not produce a negative risk score
    result = estimate_exposure_risk(
        forecast_pm25=40.0, baseline_pm25=60.0, exposed_population=50000
    )
    assert result.indicative_risk_score == 0.0


if __name__ == "__main__":
    test_disclaimer_never_mentions_daly()
    test_estimate_exposure_risk_basic()
    test_estimate_exposure_risk_no_negative_excess()
    print("All health impact tests passed.")
