from __future__ import annotations

from typing import Mapping, Optional

import numpy as np


PointLike = Optional[Mapping[str, float]]


def _to_xy(point: PointLike) -> Optional[np.ndarray]:
    if not point:
        return None

    if "pixel_x" in point and "pixel_y" in point:
        x = point.get("pixel_x")
        y = point.get("pixel_y")
    else:
        x = point.get("x")
        y = point.get("y")

    if x is None or y is None:
        return None
    if not np.isfinite(x) or not np.isfinite(y):
        return None
    return np.asarray([float(x), float(y)], dtype=np.float32)


def calculate_angle(point_a: PointLike, point_b: PointLike, point_c: PointLike) -> float:
    a = _to_xy(point_a)
    b = _to_xy(point_b)
    c = _to_xy(point_c)

    if a is None or b is None or c is None:
        return float("nan")

    ba = a - b
    bc = c - b

    ba_norm = np.linalg.norm(ba)
    bc_norm = np.linalg.norm(bc)
    if ba_norm <= 1e-6 or bc_norm <= 1e-6:
        return float("nan")

    cosine = np.dot(ba, bc) / (ba_norm * bc_norm)
    cosine = float(np.clip(cosine, -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def midpoint(point_a: PointLike, point_b: PointLike) -> dict[str, float]:
    a = _to_xy(point_a)
    b = _to_xy(point_b)
    if a is None and b is None:
        return {"x": float("nan"), "y": float("nan"), "pixel_x": float("nan"), "pixel_y": float("nan")}
    if a is None:
        xy = b
    elif b is None:
        xy = a
    else:
        xy = (a + b) / 2.0
    return {"x": float(xy[0]), "y": float(xy[1]), "pixel_x": float(xy[0]), "pixel_y": float(xy[1])}


def calculate_torso_tilt(left_shoulder: PointLike, right_shoulder: PointLike, left_hip: PointLike, right_hip: PointLike) -> float:
    shoulder_center = _to_xy(midpoint(left_shoulder, right_shoulder))
    hip_center = _to_xy(midpoint(left_hip, right_hip))
    if shoulder_center is None or hip_center is None:
        return float("nan")

    vector = shoulder_center - hip_center
    magnitude = np.linalg.norm(vector)
    if magnitude <= 1e-6:
        return float("nan")

    angle = np.degrees(np.arctan2(vector[0], -vector[1]))
    return float(abs(angle))


def calculate_distance(point_a: PointLike, point_b: PointLike) -> float:
    a = _to_xy(point_a)
    b = _to_xy(point_b)
    if a is None or b is None:
        return float("nan")
    return float(np.linalg.norm(a - b))
