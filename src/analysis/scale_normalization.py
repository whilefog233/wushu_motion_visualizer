from __future__ import annotations

"""身体尺度归一化速度指标。

旧的 ``*_speed`` 是像素速度（px/s），受人物离摄像头远近影响。
这里在保留旧指标的基础上新增三套口径：

- ``*_speed``            px/s（保留，兼容旧数据）
- ``*_speed_normalized`` 身体尺度/秒（用肩宽/髋宽/躯干长度中位数做尺度基准）
- ``*_speed_world``      MediaPipe world 坐标速度（近似米制，未标定，明确为近似值）

说明：无法可靠得到真实物理单位时，统一使用 normalized 单位，不伪造“真实米/秒”。
"""

import math
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from src.models.pose_result import PoseResult

SCALE_COLUMNS = ("shoulder_width", "hip_width", "torso_length")

_SIDE_PX_SPEEDS = {
    "left_wrist_speed": "left_wrist",
    "right_wrist_speed": "right_wrist",
    "left_ankle_speed": "left_ankle",
    "right_ankle_speed": "right_ankle",
    "hip_center_speed": "hip_center",
}


def compute_body_scale_px(metrics_df: pd.DataFrame) -> float:
    """身体尺度基准：肩宽/髋宽/躯干长度的中位数（像素）。"""
    values: list[float] = []
    for column in SCALE_COLUMNS:
        if column not in metrics_df.columns:
            continue
        series = pd.to_numeric(metrics_df[column], errors="coerce").dropna()
        values.extend(float(v) for v in series.values if math.isfinite(float(v)) and float(v) > 1.0)
    if not values:
        return float("nan")
    return float(np.median(values))


def _nan_safe_divide(numerator: pd.Series, denominator: float) -> pd.Series:
    if not math.isfinite(denominator) or denominator <= 1e-6:
        return pd.Series(float("nan"), index=numerator.index, dtype="float64")
    return numerator / denominator


def _world_speed_series(pose: PoseResult, point_name: str) -> list[float]:
    """基于 world 坐标的逐帧速度（world 单位/秒，近似米制）。"""
    speeds: list[float] = []
    previous: Optional[np.ndarray] = None
    for frame in pose.world_landmarks:
        point = frame.get(point_name)
        current = (
            np.asarray([point["x"], point["y"], point["z"]], dtype=np.float32)
            if point and all(math.isfinite(v) for v in (point.get("x"), point.get("y"), point.get("z")))
            else None
        )
        if previous is not None and current is not None and pose.fps > 0:
            speeds.append(float(np.linalg.norm(current - previous)) * pose.fps)
        else:
            speeds.append(float("nan"))
        previous = current
    return speeds


def _hip_center_world_series(pose: PoseResult) -> list[float]:
    speeds: list[float] = []
    previous: Optional[np.ndarray] = None
    for frame in pose.world_landmarks:
        left = frame.get("left_hip")
        right = frame.get("right_hip")
        current = None
        if left and right:
            vals = [left.get("x"), left.get("y"), left.get("z"), right.get("x"), right.get("y"), right.get("z")]
            if all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in vals):
                current = np.asarray(
                    [
                        (float(left["x"]) + float(right["x"])) / 2.0,
                        (float(left["y"]) + float(right["y"])) / 2.0,
                        (float(left["z"]) + float(right["z"])) / 2.0,
                    ],
                    dtype=np.float32,
                )
        if previous is not None and current is not None and pose.fps > 0:
            speeds.append(float(np.linalg.norm(current - previous)) * pose.fps)
        else:
            speeds.append(float("nan"))
        previous = current
    return speeds


def augment_scale_metrics(metrics_df: pd.DataFrame, pose: PoseResult) -> pd.DataFrame:
    """在旧指标基础上追加 normalized / world 速度列（不修改旧列）。"""
    df = metrics_df.copy()
    body_scale = compute_body_scale_px(df)
    df["body_scale_px"] = body_scale

    # normalized：身体尺度/秒
    for column in _SIDE_PX_SPEEDS:
        if column in df.columns:
            df[f"{column}_normalized"] = _nan_safe_divide(pd.to_numeric(df[column], errors="coerce"), body_scale)

    # world：world 坐标速度
    if pose.world_landmarks:
        for column, point_name in _SIDE_PX_SPEEDS.items():
            if point_name == "hip_center":
                df[f"{column}_world"] = _hip_center_world_series(pose)
            else:
                df[f"{column}_world"] = _world_speed_series(pose, point_name)

    # 聚合列（左右取更快一侧）
    df["wrist_speed_px"] = _row_max(df, "left_wrist_speed", "right_wrist_speed")
    df["wrist_speed_normalized"] = _row_max(df, "left_wrist_speed_normalized", "right_wrist_speed_normalized")
    df["wrist_speed_world"] = _row_max(df, "left_wrist_speed_world", "right_wrist_speed_world")
    df["hip_speed_px"] = df.get("hip_center_speed", float("nan"))
    df["hip_speed_normalized"] = df.get("hip_center_speed_normalized", float("nan"))
    df["hip_speed_world"] = df.get("hip_center_speed_world", float("nan"))
    return df


def _row_max(df: pd.DataFrame, *columns: str) -> pd.Series:
    series_list = []
    for column in columns:
        if column in df.columns:
            series_list.append(pd.to_numeric(df[column], errors="coerce"))
    if not series_list:
        return pd.Series(float("nan"), index=df.index, dtype="float64")
    result = series_list[0]
    for series in series_list[1:]:
        result = result.combine(series, lambda a, b: _max_nan(a, b))
    return result


def _max_nan(a, b) -> float:
    if not math.isfinite(a) and not math.isfinite(b):
        return float("nan")
    if not math.isfinite(a):
        return float(b)
    if not math.isfinite(b):
        return float(a)
    return float(max(a, b))


def normalized_speed_summary(metrics_df: pd.DataFrame) -> dict[str, float]:
    """normalized/world 速度的均值与峰值摘要（供 analysis.json / coach 使用）。"""
    summary: dict[str, float] = {}
    for column in [
        "wrist_speed_px",
        "wrist_speed_normalized",
        "wrist_speed_world",
        "hip_speed_px",
        "hip_speed_normalized",
        "hip_speed_world",
        "left_wrist_speed_normalized",
        "right_wrist_speed_normalized",
        "hip_center_speed_normalized",
        "left_wrist_speed_world",
        "right_wrist_speed_world",
        "hip_center_speed_world",
    ]:
        if column not in metrics_df.columns:
            continue
        series = pd.to_numeric(metrics_df[column], errors="coerce").dropna()
        summary[f"{column}_mean"] = float(series.mean()) if not series.empty else float("nan")
        summary[f"{column}_peak"] = float(series.max()) if not series.empty else float("nan")
    return summary
