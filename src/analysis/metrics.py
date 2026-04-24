from __future__ import annotations

import math
from typing import Mapping, Optional

import numpy as np

from src.analysis.kinematics import calculate_angle, calculate_distance, calculate_torso_tilt, midpoint
from src.analysis.motion_intensity import compute_motion_intensity
from src.analysis.smoothing import smooth_metric_dict


LandmarkDict = Mapping[str, Mapping[str, float]]
MetricDict = Mapping[str, float]


def _point_speed(current: Optional[Mapping[str, float]], previous: Optional[Mapping[str, float]], fps: float) -> float:
    if current is None or previous is None or fps <= 0:
        return float("nan")
    try:
        current_xy = np.asarray([current["pixel_x"], current["pixel_y"]], dtype=np.float32)
        previous_xy = np.asarray([previous["pixel_x"], previous["pixel_y"]], dtype=np.float32)
    except KeyError:
        return float("nan")

    if not np.isfinite(current_xy).all() or not np.isfinite(previous_xy).all():
        return float("nan")
    return float(np.linalg.norm(current_xy - previous_xy) * fps)


def _estimate_center_of_mass(landmarks: LandmarkDict) -> tuple[float, float]:
    weighted_points: list[tuple[float, float, float]] = []
    weighted_names = {
        "left_shoulder": 0.2,
        "right_shoulder": 0.2,
        "left_hip": 0.3,
        "right_hip": 0.3,
    }
    for name, weight in weighted_names.items():
        point = landmarks.get(name)
        if point is None:
            continue
        x = point.get("pixel_x")
        y = point.get("pixel_y")
        if x is None or y is None or not np.isfinite([x, y]).all():
            continue
        weighted_points.append((float(x), float(y), weight))

    if weighted_points:
        total_weight = sum(weight for _, _, weight in weighted_points)
        x = sum(px * weight for px, _, weight in weighted_points) / total_weight
        y = sum(py * weight for _, py, weight in weighted_points) / total_weight
        return x, y

    visible_points = []
    for point in landmarks.values():
        x = point.get("pixel_x")
        y = point.get("pixel_y")
        if x is None or y is None or not np.isfinite([x, y]).all():
            continue
        visible_points.append((float(x), float(y)))

    if not visible_points:
        return float("nan"), float("nan")
    xs, ys = zip(*visible_points)
    return float(np.mean(xs)), float(np.mean(ys))


def _mean_visibility(landmarks: LandmarkDict) -> float:
    focus_names = [
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
        "left_wrist",
        "right_wrist",
    ]
    visibilities = []
    for name in focus_names:
        point = landmarks.get(name)
        if not point:
            continue
        visibility = point.get("visibility")
        if visibility is None or not math.isfinite(visibility):
            continue
        visibilities.append(float(visibility))
    if not visibilities:
        return float("nan")
    return float(np.mean(visibilities))


def _safe_diff(current: float, previous: float, fps: float) -> float:
    if fps <= 0 or not math.isfinite(current) or not math.isfinite(previous):
        return float("nan")
    return (current - previous) * fps


def _safe_mean(*values: float) -> float:
    finite_values = [float(value) for value in values if math.isfinite(value)]
    if not finite_values:
        return float("nan")
    return float(sum(finite_values) / len(finite_values))


def compute_frame_metrics(
    landmarks: LandmarkDict,
    previous_landmarks: Optional[LandmarkDict],
    fps: float,
    previous_metrics: Optional[MetricDict] = None,
    previous_smoothed_speeds: Optional[Mapping[str, float]] = None,
    speed_smoothing_alpha: float = 0.35,
) -> tuple[dict[str, float], dict[str, float]]:
    previous_metrics = previous_metrics or {}
    previous_smoothed_speeds = previous_smoothed_speeds or {}

    hip_center = midpoint(landmarks.get("left_hip"), landmarks.get("right_hip"))
    previous_hip_center = midpoint(previous_landmarks.get("left_hip"), previous_landmarks.get("right_hip")) if previous_landmarks else None
    shoulder_center = midpoint(landmarks.get("left_shoulder"), landmarks.get("right_shoulder"))

    raw_speeds = {
        "left_wrist_speed": _point_speed(landmarks.get("left_wrist"), previous_landmarks.get("left_wrist") if previous_landmarks else None, fps),
        "right_wrist_speed": _point_speed(landmarks.get("right_wrist"), previous_landmarks.get("right_wrist") if previous_landmarks else None, fps),
        "left_ankle_speed": _point_speed(landmarks.get("left_ankle"), previous_landmarks.get("left_ankle") if previous_landmarks else None, fps),
        "right_ankle_speed": _point_speed(landmarks.get("right_ankle"), previous_landmarks.get("right_ankle") if previous_landmarks else None, fps),
        "hip_center_speed": _point_speed(hip_center, previous_hip_center, fps),
    }
    smoothed_speeds = smooth_metric_dict(previous_smoothed_speeds, raw_speeds, alpha=speed_smoothing_alpha)

    center_of_mass_x, center_of_mass_y = _estimate_center_of_mass(landmarks)

    metrics = {
        "left_elbow_angle": calculate_angle(landmarks.get("left_shoulder"), landmarks.get("left_elbow"), landmarks.get("left_wrist")),
        "right_elbow_angle": calculate_angle(landmarks.get("right_shoulder"), landmarks.get("right_elbow"), landmarks.get("right_wrist")),
        "left_shoulder_angle": calculate_angle(landmarks.get("left_elbow"), landmarks.get("left_shoulder"), landmarks.get("left_hip")),
        "right_shoulder_angle": calculate_angle(landmarks.get("right_elbow"), landmarks.get("right_shoulder"), landmarks.get("right_hip")),
        "left_hip_angle": calculate_angle(landmarks.get("left_shoulder"), landmarks.get("left_hip"), landmarks.get("left_knee")),
        "right_hip_angle": calculate_angle(landmarks.get("right_shoulder"), landmarks.get("right_hip"), landmarks.get("right_knee")),
        "left_knee_angle": calculate_angle(landmarks.get("left_hip"), landmarks.get("left_knee"), landmarks.get("left_ankle")),
        "right_knee_angle": calculate_angle(landmarks.get("right_hip"), landmarks.get("right_knee"), landmarks.get("right_ankle")),
        "left_ankle_angle": calculate_angle(landmarks.get("left_knee"), landmarks.get("left_ankle"), landmarks.get("left_foot_index")),
        "right_ankle_angle": calculate_angle(landmarks.get("right_knee"), landmarks.get("right_ankle"), landmarks.get("right_foot_index")),
        "torso_tilt_angle": calculate_torso_tilt(
            landmarks.get("left_shoulder"),
            landmarks.get("right_shoulder"),
            landmarks.get("left_hip"),
            landmarks.get("right_hip"),
        ),
        "hip_center_x": float(hip_center.get("pixel_x", float("nan"))),
        "hip_center_y": float(hip_center.get("pixel_y", float("nan"))),
        "hip_height": float(hip_center.get("pixel_y", float("nan"))),
        "shoulder_center_x": float(shoulder_center.get("pixel_x", float("nan"))),
        "shoulder_center_y": float(shoulder_center.get("pixel_y", float("nan"))),
        "foot_distance": calculate_distance(
            landmarks.get("left_foot_index") or landmarks.get("left_ankle"),
            landmarks.get("right_foot_index") or landmarks.get("right_ankle"),
        ),
        "shoulder_width": calculate_distance(landmarks.get("left_shoulder"), landmarks.get("right_shoulder")),
        "hand_distance": calculate_distance(landmarks.get("left_wrist"), landmarks.get("right_wrist")),
        "center_of_mass_x": center_of_mass_x,
        "center_of_mass_y": center_of_mass_y,
        "detection_confidence": _mean_visibility(landmarks),
        "left_wrist_x": float(landmarks.get("left_wrist", {}).get("pixel_x", float("nan"))),
        "left_wrist_y": float(landmarks.get("left_wrist", {}).get("pixel_y", float("nan"))),
        "right_wrist_x": float(landmarks.get("right_wrist", {}).get("pixel_x", float("nan"))),
        "right_wrist_y": float(landmarks.get("right_wrist", {}).get("pixel_y", float("nan"))),
        "left_ankle_x": float(landmarks.get("left_ankle", {}).get("pixel_x", float("nan"))),
        "left_ankle_y": float(landmarks.get("left_ankle", {}).get("pixel_y", float("nan"))),
        "right_ankle_x": float(landmarks.get("right_ankle", {}).get("pixel_x", float("nan"))),
        "right_ankle_y": float(landmarks.get("right_ankle", {}).get("pixel_y", float("nan"))),
    }
    metrics.update(smoothed_speeds)
    metrics["motion_intensity"] = compute_motion_intensity(
        metrics["left_wrist_speed"],
        metrics["right_wrist_speed"],
        metrics["left_ankle_speed"],
        metrics["right_ankle_speed"],
        metrics["hip_center_speed"],
    )

    metrics["hip_angle_mean"] = _safe_mean(metrics["left_hip_angle"], metrics["right_hip_angle"])
    metrics["left_knee_angular_velocity"] = _safe_diff(metrics["left_knee_angle"], float(previous_metrics.get("left_knee_angle", float("nan"))), fps)
    metrics["right_knee_angular_velocity"] = _safe_diff(metrics["right_knee_angle"], float(previous_metrics.get("right_knee_angle", float("nan"))), fps)
    metrics["left_elbow_angular_velocity"] = _safe_diff(metrics["left_elbow_angle"], float(previous_metrics.get("left_elbow_angle", float("nan"))), fps)
    metrics["right_elbow_angular_velocity"] = _safe_diff(metrics["right_elbow_angle"], float(previous_metrics.get("right_elbow_angle", float("nan"))), fps)
    metrics["hip_angular_velocity"] = _safe_diff(metrics["hip_angle_mean"], float(previous_metrics.get("hip_angle_mean", float("nan"))), fps)
    metrics["torso_angular_velocity"] = _safe_diff(metrics["torso_tilt_angle"], float(previous_metrics.get("torso_tilt_angle", float("nan"))), fps)

    metrics["left_knee_angular_acceleration"] = _safe_diff(
        metrics["left_knee_angular_velocity"],
        float(previous_metrics.get("left_knee_angular_velocity", float("nan"))),
        fps,
    )
    metrics["right_knee_angular_acceleration"] = _safe_diff(
        metrics["right_knee_angular_velocity"],
        float(previous_metrics.get("right_knee_angular_velocity", float("nan"))),
        fps,
    )
    metrics["left_elbow_angular_acceleration"] = _safe_diff(
        metrics["left_elbow_angular_velocity"],
        float(previous_metrics.get("left_elbow_angular_velocity", float("nan"))),
        fps,
    )
    metrics["right_elbow_angular_acceleration"] = _safe_diff(
        metrics["right_elbow_angular_velocity"],
        float(previous_metrics.get("right_elbow_angular_velocity", float("nan"))),
        fps,
    )
    return metrics, smoothed_speeds


def initialize_peak_state() -> dict[str, dict[str, float]]:
    tracked_keys = [
        "left_wrist_speed",
        "right_wrist_speed",
        "left_ankle_speed",
        "right_ankle_speed",
        "hip_center_speed",
        "torso_angular_velocity_abs",
    ]
    return {
        key: {"value": float("nan"), "time_sec": float("nan"), "frame_index": float("nan")}
        for key in tracked_keys
    }


def update_peak_metrics(metrics: dict[str, float], peak_state: dict[str, dict[str, float]], timestamp_sec: float, frame_index: int) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    observed_values = {
        "left_wrist_speed": float(metrics.get("left_wrist_speed", float("nan"))),
        "right_wrist_speed": float(metrics.get("right_wrist_speed", float("nan"))),
        "left_ankle_speed": float(metrics.get("left_ankle_speed", float("nan"))),
        "right_ankle_speed": float(metrics.get("right_ankle_speed", float("nan"))),
        "hip_center_speed": float(metrics.get("hip_center_speed", float("nan"))),
        "torso_angular_velocity_abs": abs(float(metrics.get("torso_angular_velocity", float("nan")))),
    }

    for key, value in observed_values.items():
        if not math.isfinite(value):
            continue
        current_peak = float(peak_state[key]["value"])
        if not math.isfinite(current_peak) or value > current_peak:
            peak_state[key] = {"value": value, "time_sec": timestamp_sec, "frame_index": float(frame_index)}

    metrics["left_wrist_speed_peak"] = float(peak_state["left_wrist_speed"]["value"])
    metrics["right_wrist_speed_peak"] = float(peak_state["right_wrist_speed"]["value"])
    metrics["left_ankle_speed_peak"] = float(peak_state["left_ankle_speed"]["value"])
    metrics["right_ankle_speed_peak"] = float(peak_state["right_ankle_speed"]["value"])
    metrics["hip_center_speed_peak"] = float(peak_state["hip_center_speed"]["value"])
    metrics["torso_angular_velocity_peak"] = float(peak_state["torso_angular_velocity_abs"]["value"])

    wrist_peaks = [
        ("left", float(metrics["left_wrist_speed_peak"]), float(peak_state["left_wrist_speed"]["time_sec"])),
        ("right", float(metrics["right_wrist_speed_peak"]), float(peak_state["right_wrist_speed"]["time_sec"])),
    ]
    ankle_peaks = [
        ("left", float(metrics["left_ankle_speed_peak"]), float(peak_state["left_ankle_speed"]["time_sec"])),
        ("right", float(metrics["right_ankle_speed_peak"]), float(peak_state["right_ankle_speed"]["time_sec"])),
    ]

    best_wrist_peak = max(wrist_peaks, key=lambda item: item[1] if math.isfinite(item[1]) else -1.0)
    best_ankle_peak = max(ankle_peaks, key=lambda item: item[1] if math.isfinite(item[1]) else -1.0)

    metrics["wrist_speed_peak"] = best_wrist_peak[1]
    metrics["ankle_speed_peak"] = best_ankle_peak[1]
    metrics["hip_speed_peak"] = float(metrics["hip_center_speed_peak"])

    metrics["wrist_peak_time_sec"] = best_wrist_peak[2]
    metrics["ankle_peak_time_sec"] = best_ankle_peak[2]
    metrics["hip_peak_time_sec"] = float(peak_state["hip_center_speed"]["time_sec"])
    metrics["torso_peak_time_sec"] = float(peak_state["torso_angular_velocity_abs"]["time_sec"])

    metrics["kinetic_chain_stage"] = infer_kinetic_chain_stage(metrics)
    return metrics, peak_state


def infer_kinetic_chain_stage(metrics: MetricDict) -> str:
    ankle_peak = float(metrics.get("ankle_speed_peak", float("nan")))
    hip_peak = float(metrics.get("hip_speed_peak", float("nan")))
    torso_peak = float(metrics.get("torso_angular_velocity_peak", float("nan")))
    wrist_peak = float(metrics.get("wrist_speed_peak", float("nan")))

    lower_signal = _normalized_signal(
        max(float(metrics.get("left_ankle_speed", float("nan"))), float(metrics.get("right_ankle_speed", float("nan")))),
        ankle_peak,
    )
    hip_signal = _normalized_signal(float(metrics.get("hip_center_speed", float("nan"))), hip_peak)
    torso_signal = _normalized_signal(abs(float(metrics.get("torso_angular_velocity", float("nan")))), torso_peak)
    upper_signal = _normalized_signal(
        max(float(metrics.get("left_wrist_speed", float("nan"))), float(metrics.get("right_wrist_speed", float("nan")))),
        wrist_peak,
    )

    signals = {
        "Lower-limb drive": lower_signal,
        "Hip transfer": hip_signal,
        "Torso rotation": torso_signal,
        "Upper-limb release": upper_signal,
    }
    stage, score = max(signals.items(), key=lambda item: item[1])
    if not math.isfinite(score) or score < 0.2:
        return "Transition / Hold"
    return stage


def _normalized_signal(current: float, peak: float) -> float:
    if not math.isfinite(current) or not math.isfinite(peak) or peak <= 1e-6:
        return float("nan")
    return float(np.clip(current / peak, 0.0, 1.0))
