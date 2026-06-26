import statistics

from custom_components.adaptive_alerting.baseline_model import BaselineModel


def test_not_ready_below_30_samples():
    model = BaselineModel(sensitivity=2.5)
    for value in range(29):
        model.add_sample(value)

    assert model.is_ready is False
    result = model.evaluate(100.0)
    assert result == {
        "is_anomaly": False,
        "z_score": 0.0,
        "mean": 0.0,
        "std_dev": 0.0,
        "is_ready": False,
    }


def test_ready_at_30_samples():
    model = BaselineModel(sensitivity=2.5)
    for value in range(30):
        model.add_sample(value)

    assert model.is_ready is True


def test_z_score_matches_hand_computed_value():
    model = BaselineModel(sensitivity=2.5)
    samples = [10.0] * 29 + [20.0]
    for value in samples:
        model.add_sample(value)

    mean = statistics.mean(samples)
    std_dev = statistics.stdev(samples)
    expected_z = abs((15.0 - mean) / std_dev)

    result = model.evaluate(15.0)
    assert result["is_ready"] is True
    assert result["mean"] == round(mean, 3)
    assert result["std_dev"] == round(std_dev, 3)
    assert result["z_score"] == round(expected_z, 3)


def test_anomaly_threshold_boundary():
    model = BaselineModel(sensitivity=2.0)
    for value in [10.0] * 30:
        model.add_sample(value)
    # All samples identical -> std_dev is 0 -> z_score forced to 0, never an anomaly.
    result = model.evaluate(999.0)
    assert result["std_dev"] == 0.0
    assert result["z_score"] == 0.0
    assert result["is_anomaly"] is False


def test_anomaly_detected_past_sensitivity():
    model = BaselineModel(sensitivity=2.0)
    samples = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0,
               11.0, 9.0, 11.0, 9.0, 11.0, 9.0, 11.0, 9.0, 11.0, 9.0,
               10.5, 9.5, 10.5, 9.5, 10.5, 9.5, 10.5, 9.5, 10.5, 9.5]
    for value in samples:
        model.add_sample(value)

    not_anomalous = model.evaluate(10.0)
    assert not_anomalous["is_anomaly"] is False

    anomalous = model.evaluate(1000.0)
    assert anomalous["is_anomaly"] is True
    assert anomalous["z_score"] >= 2.0


def test_reset_clears_samples_and_readiness():
    model = BaselineModel(sensitivity=2.5)
    for value in range(40):
        model.add_sample(value)
    assert model.is_ready is True

    model.reset()

    assert model.is_ready is False
    assert model.sample_count == 0
    assert model.evaluate(50.0)["is_ready"] is False


def test_to_dict_from_dict_round_trip():
    model = BaselineModel(sensitivity=3.0)
    for value in range(35):
        model.add_sample(float(value))

    data = model.to_dict()
    restored = BaselineModel.from_dict(data)

    assert restored.sensitivity == 3.0
    assert restored.is_ready is True
    assert restored.sample_count == model.sample_count
    assert restored.evaluate(17.0) == model.evaluate(17.0)


def test_from_dict_defaults_sensitivity_when_missing():
    from custom_components.adaptive_alerting.const import DEFAULT_SENSITIVITY

    restored = BaselineModel.from_dict({"samples": [1.0, 2.0, 3.0]})
    assert restored.sensitivity == DEFAULT_SENSITIVITY
    assert restored.sample_count == 3
