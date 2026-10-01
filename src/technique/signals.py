"""统一信号组装：把 pose.json + metrics.csv 变成技术诊断所需的信号包。

原则：
- 能复用的指标（髋角速度、肘角速度、腕速度、躯干旋转、身体尺度）直接读 metrics.csv，
  避免重复计算。
- metrics.csv 缺失的信号（肩线速度、头部晃动、肘外翻、重心前冲）从 pose.json 补算，
  不再运行 MediaPipe。
- 所有长度类信号尽量用身体尺度归一化（肩宽 / 躯干长度），降低拍摄距离影响。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.models.pose_result import PoseResult

LANDMARK_KEYS = [
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "nose",
]


@dataclass
class SignalBundle:
    """技术诊断用信号包（帧索引对齐）。"""

    frame_index: np.ndarray
    timestamps: np.ndarray
    fps: float
    # 主手侧信号（strike_hand 确定后填充）
    hip_angular_velocity: np.ndarray = field(default_factory=lambda: np.array([]))
    shoulder_speed: np.ndarray = field(default_factory=lambda: np.array([]))          # 主手侧肩线速度
    elbow_angular_velocity: np.ndarray = field(default_factory=lambda: np.array([]))  # 主手侧肘角速度
    elbow_angle: np.ndarray = field(default_factory=lambda: np.array([]))             # 主手侧肘角
    wrist_speed: np.ndarray = field(default_factory=lambda: np.array([]))             # 主手侧腕速度
    wrist_speed_normalized: np.ndarray = field(default_factory=lambda: np.array([]))
    # 辅助信号
    hip_center_x: np.ndarray = field(default_factory=lambda: np.array([]))
    head_displacement: np.ndarray = field(default_factory=lambda: np.array([]))        # 头部位移（相对肩宽）
    nose_speed: np.ndarray = field(default_factory=lambda: np.array([]))
    elbow_abduction: np.ndarray = field(default_factory=lambda: np.array([]))          # 肘外翻（相对肩宽）
    torso_tilt: np.ndarray = field(default_factory=lambda: np.array([]))
    torso_rotation_velocity: np.ndarray = field(default_factory=lambda: np.array([]))
    shoulder_width: np.ndarray = field(default_factory=lambda: np.array([]))
    torso_length: np.ndarray = field(default_factory=lambda: np.array([]))
    detection_confidence: np.ndarray = field(default_factory=lambda: np.array([]))
    # 参考量
    body_scale_px: float = float("nan")   # 肩宽中位数（px）
    body_scale_world: float = float("nan")
    strike_hand: str = "left"             # 主手（left/right），由 select_strike_hand 决定
    # 原始 DataFrame 保留（诊断需要更多列时用）
    source_df: Optional[pd.DataFrame] = None
    # 另一侧信号（左右差异诊断用）
    other_shoulder_speed: np.ndarray = field(default_factory=lambda: np.array([]))
    other_elbow_abduction: np.ndarray = field(default_factory=lambda: np.array([]))

    def slice(self, start: int, end: int) -> "SignalBundle":
        """按帧范围切片（闭区间 [start, end]），返回新包。"""
        mask = (self.frame_index >= start) & (self.frame_index <= end)
        return SignalBundle(
            frame_index=self.frame_index[mask],
            timestamps=self.timestamps[mask],
            fps=self.fps,
            hip_angular_velocity=self.hip_angular_velocity[mask],
            shoulder_speed=self.shoulder_speed[mask],
            elbow_angular_velocity=self.elbow_angular_velocity[mask],
            elbow_angle=self.elbow_angle[mask],
            wrist_speed=self.wrist_speed[mask],
            wrist_speed_normalized=self.wrist_speed_normalized[mask],
            hip_center_x=self.hip_center_x[mask],
            head_displacement=self.head_displacement[mask],
            nose_speed=self.nose_speed[mask],
            elbow_abduction=self.elbow_abduction[mask],
            torso_tilt=self.torso_tilt[mask],
            torso_rotation_velocity=self.torso_rotation_velocity[mask],
            shoulder_width=self.shoulder_width[mask],
            torso_length=self.torso_length[mask],
            detection_confidence=self.detection_confidence[mask],
            body_scale_px=self.body_scale_px,
            body_scale_world=self.body_scale_world,
            source_df=self.source_df.iloc[mask] if self.source_df is not None else None,
            other_shoulder_speed=self.other_shoulder_speed[mask],
            other_elbow_abduction=self.other_elbow_abduction[mask],
        )

    def time_at(self, frame: int) -> float:
        idx = np.where(self.frame_index == frame)[0]
        if len(idx) == 0:
            return float("nan")
        return float(self.timestamps[idx[0]])

    def value_at(self, signal: np.ndarray, frame: int) -> float:
        idx = np.where(self.frame_index == frame)[0]
        if len(idx) == 0 or len(signal) == 0:
            return float("nan")
        return float(signal[idx[0]])


def build_signal_bundle(pose: PoseResult, metrics_df: pd.DataFrame) -> SignalBundle:
    """从 pose.json + metrics.csv 组装信号包（默认主手为左，检测后可按峰值重选）。"""
    frame_index = np.asarray(pd.to_numeric(metrics_df["frame_index"], errors="coerce").to_numpy(dtype=float), dtype=np.int64)
    timestamps = pd.to_numeric(metrics_df["timestamp_sec"], errors="coerce").to_numpy(dtype=float)

    def _col(name: str) -> np.ndarray:
        if name in metrics_df.columns:
            return pd.to_numeric(metrics_df[name], errors="coerce").to_numpy(dtype=float)
        return np.full(len(metrics_df), float("nan"))

    bundle = SignalBundle(
        frame_index=frame_index,
        timestamps=timestamps,
        fps=float(pose.fps or 0.0),
        hip_angular_velocity=_col("hip_angular_velocity"),
        elbow_angular_velocity=_col("left_elbow_angular_velocity"),
        elbow_angle=_col("left_elbow_angle"),
        wrist_speed=_col("left_wrist_speed"),
        wrist_speed_normalized=_col("left_wrist_speed_normalized"),
        hip_center_x=_col("hip_center_x"),
        torso_tilt=_col("torso_tilt_angle"),
        torso_rotation_velocity=_col("torso_rotation_velocity"),
        shoulder_width=_col("shoulder_width"),
        torso_length=_col("torso_length"),
        detection_confidence=_col("detection_confidence"),
        body_scale_px=_median_finite(_col("shoulder_width")),
        body_scale_world=_median_finite(_col("shoulder_width")),
        source_df=metrics_df,
    )

    # 补充计算（从 pose.json，不重跑 MediaPipe）
    shoulder_speed_l = _landmark_speed(pose, "left_shoulder")
    shoulder_speed_r = _landmark_speed(pose, "right_shoulder")
    nose_speed = _landmark_speed(pose, "nose")
    elbow_abduction_l = _elbow_abduction(pose, "left")
    elbow_abduction_r = _elbow_abduction(pose, "right")
    shoulder_width_frame = _landmark_distance(pose, "left_shoulder", "right_shoulder")
    nose_x = _landmark_x(pose, "nose")
    nose_y = _landmark_y(pose, "nose")

    frame_to_index = {int(f): i for i, f in enumerate(frame_index)}
    bundle.shoulder_speed = _map_to_frames(shoulder_speed_l, frame_to_index, len(frame_index))
    bundle.other_shoulder_speed = _map_to_frames(shoulder_speed_r, frame_to_index, len(frame_index))
    bundle.nose_speed = _map_to_frames(nose_speed, frame_to_index, len(frame_index))
    bundle.elbow_abduction = _map_to_frames(elbow_abduction_l, frame_to_index, len(frame_index))
    bundle.other_elbow_abduction = _map_to_frames(elbow_abduction_r, frame_to_index, len(frame_index))

    # 头部位移（帧间位移累计差，用肩宽归一化）
    nose_x_f = _map_to_frames(nose_x, frame_to_index, len(frame_index))
    nose_y_f = _map_to_frames(nose_y, frame_to_index, len(frame_index))
    sw_f = _map_to_frames(shoulder_width_frame, frame_to_index, len(frame_index))
    scale = _median_finite(sw_f)
    if not math.isfinite(scale) or scale <= 1e-6:
        scale = 1.0
    displacement = np.zeros_like(nose_x_f, dtype=float)
    for i in range(1, len(nose_x_f)):
        dx = _safe_sub(nose_x_f[i], nose_x_f[i - 1])
        dy = _safe_sub(nose_y_f[i], nose_y_f[i - 1])
        displacement[i] = math.sqrt(dx * dx + dy * dy)
    bundle.head_displacement = displacement / scale
    return bundle


def select_strike_hand(bundle: SignalBundle, start: int, end: int) -> str:
    """自动选择主手：窗口内腕速度峰值更大的一侧。"""
    df = bundle.source_df
    if df is None:
        return "left"
    mask = (pd.to_numeric(df["frame_index"], errors="coerce") >= start) & (pd.to_numeric(df["frame_index"], errors="coerce") <= end)
    left_peak = pd.to_numeric(df.loc[mask, "left_wrist_speed"], errors="coerce").max()
    right_peak = pd.to_numeric(df.loc[mask, "right_wrist_speed"], errors="coerce").max()
    left_peak = left_peak if math.isfinite(left_peak) else 0.0
    right_peak = right_peak if math.isfinite(right_peak) else 0.0
    return "right" if right_peak > left_peak else "left"


def reorient_bundle(bundle: SignalBundle, strike_hand: str) -> SignalBundle:
    """按主手方向重填主手侧信号（非破坏性，返回新包）。"""
    df = bundle.source_df
    if df is None:
        return bundle
    prefix = "right" if strike_hand == "right" else "left"

    def _col(name: str) -> np.ndarray:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").to_numpy(dtype=float)
        return np.full(len(df), float("nan"))

    new_bundle = SignalBundle(
        frame_index=bundle.frame_index,
        timestamps=bundle.timestamps,
        fps=bundle.fps,
        hip_angular_velocity=bundle.hip_angular_velocity,
        shoulder_speed=bundle.other_shoulder_speed if strike_hand == "right" else bundle.shoulder_speed,
        elbow_angular_velocity=_col(f"{prefix}_elbow_angular_velocity"),
        elbow_angle=_col(f"{prefix}_elbow_angle"),
        wrist_speed=_col(f"{prefix}_wrist_speed"),
        wrist_speed_normalized=_col(f"{prefix}_wrist_speed_normalized"),
        hip_center_x=bundle.hip_center_x,
        head_displacement=bundle.head_displacement,
        nose_speed=bundle.nose_speed,
        elbow_abduction=bundle.other_elbow_abduction if strike_hand == "right" else bundle.elbow_abduction,
        torso_tilt=bundle.torso_tilt,
        torso_rotation_velocity=bundle.torso_rotation_velocity,
        shoulder_width=bundle.shoulder_width,
        torso_length=bundle.torso_length,
        detection_confidence=bundle.detection_confidence,
        body_scale_px=bundle.body_scale_px,
        body_scale_world=bundle.body_scale_world,
        strike_hand=strike_hand,
        source_df=df,
        other_shoulder_speed=bundle.shoulder_speed if strike_hand == "right" else bundle.other_shoulder_speed,
        other_elbow_abduction=bundle.elbow_abduction if strike_hand == "right" else bundle.other_elbow_abduction,
    )
    return new_bundle


# ---------------------------------------------------------------- 内部工具
def _col_from_df(df: pd.DataFrame, name: str) -> np.ndarray:
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce").to_numpy(dtype=float)
    return np.full(len(df), float("nan"))


def _median_finite(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return float("nan")
    return float(np.median(finite))


def _map_to_frames(by_frame: dict[int, float], frame_to_index: dict[int, int], length: int) -> np.ndarray:
    """把按帧索引的 dict 映射为数组（按 metrics 帧序）。"""
    out = np.full(length, float("nan"))
    for frame, value in by_frame.items():
        idx = frame_to_index.get(frame)
        if idx is not None:
            out[idx] = value
    return out


def _safe_sub(a: float, b: float) -> float:
    if math.isfinite(a) and math.isfinite(b):
        return a - b
    return 0.0


def _landmark_speed(pose: PoseResult, name: str, smoothing: float = 0.35) -> dict[int, float]:
    """逐帧 landmark 线速度（px/s），平滑后返回 {frame_index: speed}。"""
    previous = None
    previous_smoothed = None
    result: dict[int, float] = {}
    for index in range(pose.frame_count):
        lm = pose.frame_landmarks(index).get(name)
        current = None
        if lm and math.isfinite(float(lm.get("pixel_x", float("nan")))) and math.isfinite(float(lm.get("pixel_y", float("nan")))):
            current = np.asarray([float(lm["pixel_x"]), float(lm["pixel_y"])], dtype=np.float32)
        speed = float("nan")
        if current is not None and previous is not None and pose.fps > 0:
            delta = np.linalg.norm(current - previous) * pose.fps
            speed = float(delta)
        if previous_smoothed is not None and math.isfinite(speed):
            speed = smoothing * speed + (1 - smoothing) * previous_smoothed
        result[index] = speed
        previous = current
        previous_smoothed = speed if math.isfinite(speed) else previous_smoothed
    return result


def _elbow_abduction(pose: PoseResult, side: str) -> dict[int, float]:
    """肘外翻：肘到肩-腕连线的垂直距离 / 肩宽（相对值，越小越贴线）。"""
    shoulder_name = f"{side}_shoulder"
    elbow_name = f"{side}_elbow"
    wrist_name = f"{side}_wrist"
    result: dict[int, float] = {}
    for index in range(pose.frame_count):
        lm = pose.frame_landmarks(index)
        s = lm.get(shoulder_name, {})
        e = lm.get(elbow_name, {})
        w = lm.get(wrist_name, {})
        sw = lm.get("left_shoulder", {})
        sw2 = lm.get("right_shoulder", {})
        try:
            sx, sy = float(s["pixel_x"]), float(s["pixel_y"])
            ex, ey = float(e["pixel_x"]), float(e["pixel_y"])
            wx, wy = float(w["pixel_x"]), float(w["pixel_y"])
            scale = math.dist((float(sw["pixel_x"]), float(sw["pixel_y"])), (float(sw2["pixel_x"]), float(sw2["pixel_y"])))
        except (KeyError, TypeError, ValueError):
            result[index] = float("nan")
            continue
        if scale <= 1e-6:
            result[index] = float("nan")
            continue
        line_dx, line_dy = wx - sx, wy - sy
        line_len_sq = line_dx * line_dx + line_dy * line_dy
        if line_len_sq <= 1e-9:
            result[index] = float("nan")
            continue
        t = max(0.0, min(1.0, ((ex - sx) * line_dx + (ey - sy) * line_dy) / line_len_sq))
        proj_x, proj_y = sx + t * line_dx, sy + t * line_dy
        dist = math.dist((ex, ey), (proj_x, proj_y))
        result[index] = dist / scale
    return result


def _landmark_distance(pose: PoseResult, name_a: str, name_b: str) -> dict[int, float]:
    result: dict[int, float] = {}
    for index in range(pose.frame_count):
        lm = pose.frame_landmarks(index)
        try:
            a = lm.get(name_a, {})
            b = lm.get(name_b, {})
            result[index] = math.dist(
                (float(a["pixel_x"]), float(a["pixel_y"])),
                (float(b["pixel_x"]), float(b["pixel_y"])),
            )
        except (KeyError, TypeError, ValueError):
            result[index] = float("nan")
    return result


def _landmark_x(pose: PoseResult, name: str) -> dict[int, float]:
    result: dict[int, float] = {}
    for index in range(pose.frame_count):
        lm = pose.frame_landmarks(index).get(name, {})
        try:
            result[index] = float(lm["pixel_x"])
        except (KeyError, TypeError, ValueError):
            result[index] = float("nan")
    return result


def _landmark_y(pose: PoseResult, name: str) -> dict[int, float]:
    result: dict[int, float] = {}
    for index in range(pose.frame_count):
        lm = pose.frame_landmarks(index).get(name, {})
        try:
            result[index] = float(lm["pixel_y"])
        except (KeyError, TypeError, ValueError):
            result[index] = float("nan")
    return result
