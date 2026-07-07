import pytest

from backend.ingestion.fallback import AllSourcesFailedError, rebalance_weights


def test_rebalance_weights_all_healthy():
    default_weights = {
        "firms": 0.40,
        "traffic": 0.30,
        "industry": 0.20,
        "weather": 0.10,
    }
    source_status = {"firms": True, "traffic": True, "industry": True, "weather": True}

    weights = rebalance_weights(source_status, default_weights)
    assert weights["firms"] == 0.40
    assert weights["traffic"] == 0.30
    assert weights["industry"] == 0.20
    assert weights["weather"] == 0.10
    assert sum(weights.values()) == 1.0


def test_rebalance_weights_one_failed():
    default_weights = {
        "firms": 0.40,
        "traffic": 0.30,
        "industry": 0.20,
        "weather": 0.10,
    }

    # Simulate FIRMS API down
    source_status = {"firms": False, "traffic": True, "industry": True, "weather": True}

    # Healthy weights sum = 0.3 + 0.2 + 0.1 = 0.6
    # Rebalanced weights:
    # firms: 0.0
    # traffic: 0.3 / 0.6 = 0.50
    # industry: 0.2 / 0.6 = 0.3333
    # weather: 0.1 / 0.6 = 0.1667
    weights = rebalance_weights(source_status, default_weights)
    assert weights["firms"] == 0.0
    assert weights["traffic"] == 0.50
    assert pytest.approx(weights["industry"], 0.0001) == 0.3333
    assert pytest.approx(weights["weather"], 0.0001) == 0.1667
    assert pytest.approx(sum(weights.values()), 0.0001) == 1.0


def test_rebalance_weights_all_failed():
    default_weights = {"firms": 0.40, "traffic": 0.30}
    source_status = {"firms": False, "traffic": False}

    with pytest.raises(AllSourcesFailedError):
        rebalance_weights(source_status, default_weights)
