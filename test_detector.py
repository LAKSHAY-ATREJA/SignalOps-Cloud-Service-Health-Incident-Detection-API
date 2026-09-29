from app.detector import detect_anomaly, severity_for


def test_detects_large_outlier():
    history = [99, 100, 101, 100, 99, 101]
    detected, mean, z_score = detect_anomaly(history, 140, threshold=2.5)
    assert detected is True
    assert 99 <= mean <= 101
    assert z_score > 2.5


def test_normal_value_is_not_incident():
    detected, _, z_score = detect_anomaly([98, 100, 102, 99, 101], 100, threshold=2.5)
    assert detected is False
    assert z_score < 2.5


def test_severity_levels():
    assert severity_for(2.7) == "medium"
    assert severity_for(4.0) == "high"
    assert severity_for(6.0) == "critical"
