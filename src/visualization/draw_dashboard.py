from __future__ import annotations

import math
from typing import Mapping

import pandas as pd

from src.utils.time_utils import format_seconds


def _format_float(value: float, unit: str = "", precision: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "未检测到"
    suffix = f" {unit}" if unit else ""
    return f"{value:.{precision}f}{suffix}"


def _format_time(value: float) -> str:
    if value is None or not math.isfinite(value):
        return "未检测到"
    return format_seconds(float(value))


def build_metric_groups(metrics: Mapping[str, float], frame_index: int, fps: float) -> dict[str, pd.DataFrame]:
    current_time = format_seconds(frame_index / fps if fps > 0 else 0.0)
    groups = {
        "基础信息": [
            ("当前帧", str(frame_index)),
            ("当前时间", current_time),
            ("FPS", _format_float(fps)),
            ("检测置信度", _format_float(float(metrics.get("detection_confidence", float("nan"))))),
            ("Kinetic Chain Stage", str(metrics.get("kinetic_chain_stage", "未检测到"))),
        ],
        "上肢角度": [
            ("左肩", _format_float(float(metrics.get("left_shoulder_angle", float("nan"))), "deg")),
            ("右肩", _format_float(float(metrics.get("right_shoulder_angle", float("nan"))), "deg")),
            ("左肘", _format_float(float(metrics.get("left_elbow_angle", float("nan"))), "deg")),
            ("右肘", _format_float(float(metrics.get("right_elbow_angle", float("nan"))), "deg")),
        ],
        "下肢角度": [
            ("左髋", _format_float(float(metrics.get("left_hip_angle", float("nan"))), "deg")),
            ("右髋", _format_float(float(metrics.get("right_hip_angle", float("nan"))), "deg")),
            ("左膝", _format_float(float(metrics.get("left_knee_angle", float("nan"))), "deg")),
            ("右膝", _format_float(float(metrics.get("right_knee_angle", float("nan"))), "deg")),
            ("左踝", _format_float(float(metrics.get("left_ankle_angle", float("nan"))), "deg")),
            ("右踝", _format_float(float(metrics.get("right_ankle_angle", float("nan"))), "deg")),
        ],
        "姿态与位置": [
            ("躯干倾斜角", _format_float(float(metrics.get("torso_tilt_angle", float("nan"))), "deg")),
            ("髋部高度", _format_float(float(metrics.get("hip_height", float("nan"))), "px")),
            ("双脚距离", _format_float(float(metrics.get("foot_distance", float("nan"))), "px")),
            ("粗略重心 X", _format_float(float(metrics.get("center_of_mass_x", float("nan"))), "px")),
            ("粗略重心 Y", _format_float(float(metrics.get("center_of_mass_y", float("nan"))), "px")),
        ],
        "速度与强度": [
            ("左手腕速度", _format_float(float(metrics.get("left_wrist_speed", float("nan"))), "px/s")),
            ("右手腕速度", _format_float(float(metrics.get("right_wrist_speed", float("nan"))), "px/s")),
            ("左脚踝速度", _format_float(float(metrics.get("left_ankle_speed", float("nan"))), "px/s")),
            ("右脚踝速度", _format_float(float(metrics.get("right_ankle_speed", float("nan"))), "px/s")),
            ("髋部中心速度", _format_float(float(metrics.get("hip_center_speed", float("nan"))), "px/s")),
            ("motion_intensity", _format_float(float(metrics.get("motion_intensity", float("nan"))), "px/s")),
        ],
        "角速度": [
            ("左膝角速度", _format_float(float(metrics.get("left_knee_angular_velocity", float("nan"))), "deg/s")),
            ("右膝角速度", _format_float(float(metrics.get("right_knee_angular_velocity", float("nan"))), "deg/s")),
            ("左肘角速度", _format_float(float(metrics.get("left_elbow_angular_velocity", float("nan"))), "deg/s")),
            ("右肘角速度", _format_float(float(metrics.get("right_elbow_angular_velocity", float("nan"))), "deg/s")),
            ("髋部角速度", _format_float(float(metrics.get("hip_angular_velocity", float("nan"))), "deg/s")),
            ("躯干角速度", _format_float(float(metrics.get("torso_angular_velocity", float("nan"))), "deg/s")),
        ],
        "角加速度": [
            ("左膝角加速度", _format_float(float(metrics.get("left_knee_angular_acceleration", float("nan"))), "deg/s²")),
            ("右膝角加速度", _format_float(float(metrics.get("right_knee_angular_acceleration", float("nan"))), "deg/s²")),
            ("左肘角加速度", _format_float(float(metrics.get("left_elbow_angular_acceleration", float("nan"))), "deg/s²")),
            ("右肘角加速度", _format_float(float(metrics.get("right_elbow_angular_acceleration", float("nan"))), "deg/s²")),
        ],
        "速度峰值": [
            ("左手腕速度峰值", _format_float(float(metrics.get("left_wrist_speed_peak", float("nan"))), "px/s")),
            ("右手腕速度峰值", _format_float(float(metrics.get("right_wrist_speed_peak", float("nan"))), "px/s")),
            ("左脚踝速度峰值", _format_float(float(metrics.get("left_ankle_speed_peak", float("nan"))), "px/s")),
            ("右脚踝速度峰值", _format_float(float(metrics.get("right_ankle_speed_peak", float("nan"))), "px/s")),
            ("髋部速度峰值", _format_float(float(metrics.get("hip_center_speed_peak", float("nan"))), "px/s")),
            ("腕部聚合峰值", _format_float(float(metrics.get("wrist_speed_peak", float("nan"))), "px/s")),
            ("踝部聚合峰值", _format_float(float(metrics.get("ankle_speed_peak", float("nan"))), "px/s")),
            ("躯干角速度峰值", _format_float(float(metrics.get("torso_angular_velocity_peak", float("nan"))), "deg/s")),
        ],
        "峰值时间": [
            ("手腕峰值时间", _format_time(float(metrics.get("wrist_peak_time_sec", float("nan"))))),
            ("脚踝峰值时间", _format_time(float(metrics.get("ankle_peak_time_sec", float("nan"))))),
            ("髋部峰值时间", _format_time(float(metrics.get("hip_peak_time_sec", float("nan"))))),
            ("躯干峰值时间", _format_time(float(metrics.get("torso_peak_time_sec", float("nan"))))),
        ],
    }
    return {title: pd.DataFrame(rows, columns=["指标", "当前值"]) for title, rows in groups.items()}


def build_overlay_lines(metrics: Mapping[str, float], frame_index: int, fps: float) -> list[str]:
    def fmt(key: str, unit: str = "", precision: int = 1) -> str:
        value = float(metrics.get(key, float("nan")))
        if not math.isfinite(value):
            return "NaN"
        suffix = f"{unit}" if unit else ""
        return f"{value:.{precision}f}{suffix}"

    return [
        f"Frame: {frame_index}",
        f"FPS: {fps:.1f}",
        f"Left Knee: {fmt('left_knee_angle', ' deg')}",
        f"Right Knee: {fmt('right_knee_angle', ' deg')}",
        f"Left Elbow: {fmt('left_elbow_angle', ' deg')}",
        f"Right Elbow: {fmt('right_elbow_angle', ' deg')}",
        f"Torso Tilt: {fmt('torso_tilt_angle', ' deg')}",
        f"Motion Intensity: {fmt('motion_intensity')}",
        f"Wrist Speed Peak: {fmt('wrist_speed_peak', ' px/s')}",
        f"Ankle Speed Peak: {fmt('ankle_speed_peak', ' px/s')}",
        f"Hip Speed Peak: {fmt('hip_speed_peak', ' px/s')}",
        f"Kinetic Chain Stage: {metrics.get('kinetic_chain_stage', 'N/A')}",
    ]
