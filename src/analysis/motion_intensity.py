from __future__ import annotations

import math


def compute_motion_intensity(
    left_wrist_speed: float,
    right_wrist_speed: float,
    left_ankle_speed: float,
    right_ankle_speed: float,
    hip_center_speed: float,
) -> float:
    values = {
        "left_wrist_speed": left_wrist_speed,
        "right_wrist_speed": right_wrist_speed,
        "left_ankle_speed": left_ankle_speed,
        "right_ankle_speed": right_ankle_speed,
        "hip_center_speed": hip_center_speed,
    }
    weights = {
        "left_wrist_speed": 0.25,
        "right_wrist_speed": 0.25,
        "left_ankle_speed": 0.20,
        "right_ankle_speed": 0.20,
        "hip_center_speed": 0.10,
    }

    total = 0.0
    weight_total = 0.0
    for key, value in values.items():
        if math.isnan(value):
            continue
        total += weights[key] * value
        weight_total += weights[key]

    if weight_total <= 0:
        return float("nan")
    return total / weight_total
