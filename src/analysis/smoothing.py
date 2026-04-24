from __future__ import annotations

from typing import Mapping

import math


def smooth_scalar(previous: float, current: float, alpha: float) -> float:
    if math.isnan(current):
        return current
    if math.isnan(previous):
        return current
    return alpha * current + (1.0 - alpha) * previous


def smooth_metric_dict(previous_values: Mapping[str, float], current_values: Mapping[str, float], alpha: float) -> dict[str, float]:
    smoothed: dict[str, float] = {}
    for key, current in current_values.items():
        previous = float(previous_values.get(key, float("nan")))
        smoothed[key] = smooth_scalar(previous, float(current), alpha)
    return smoothed
