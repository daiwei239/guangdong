def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def normalize_ratio(value: float, lower: float, upper: float) -> float:
    if upper <= lower:
        return clamp(value)
    scaled = (value - lower) / (upper - lower) * 100.0
    return clamp(scaled)
