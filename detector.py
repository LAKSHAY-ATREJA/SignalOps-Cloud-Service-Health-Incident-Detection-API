from math import sqrt


def detect_anomaly(history: list[float], value: float, threshold: float = 2.5) -> tuple[bool, float, float]:
    """Return (is_anomaly, mean, z_score) using population standard deviation."""
    if len(history) < 2:
        mean = sum(history) / len(history) if history else value
        return False, mean, 0.0

    mean = sum(history) / len(history)
    variance = sum((sample - mean) ** 2 for sample in history) / len(history)
    stddev = sqrt(variance)
    if stddev == 0:
        z_score = 0.0 if value == mean else float("inf")
    else:
        z_score = abs(value - mean) / stddev
    return z_score >= threshold, mean, z_score


def severity_for(z_score: float) -> str:
    if z_score >= 5:
        return "critical"
    if z_score >= 3.5:
        return "high"
    return "medium"
