from __future__ import annotations

import math
from collections import Counter
from typing import Mapping, Sequence

import numpy as np


MUSCLE_LABELS = {
    "quadriceps": "股四头肌",
    "hamstrings": "腘绳肌",
    "glutes": "臀肌",
    "calves": "小腿三头肌",
    "erector_spinae": "竖脊肌",
    "obliques": "腹斜肌",
    "deltoids": "三角肌",
    "forearms": "前臂肌群",
}


def _safe_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def _clip01(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return float(np.clip(value, 0.0, 1.0))


def _positive_norm(value: float, scale: float) -> float:
    if not math.isfinite(value) or scale <= 0:
        return 0.0
    return _clip01(max(0.0, value) / scale)


def _abs_norm(value: float, scale: float) -> float:
    if not math.isfinite(value) or scale <= 0:
        return 0.0
    return _clip01(abs(value) / scale)


def _finite_mean(values: Sequence[float]) -> float:
    finite_values = [float(value) for value in values if math.isfinite(value)]
    if not finite_values:
        return float("nan")
    return float(sum(finite_values) / len(finite_values))


def _finite_max(values: Sequence[float]) -> float:
    finite_values = [float(value) for value in values if math.isfinite(value)]
    if not finite_values:
        return float("nan")
    return float(max(finite_values))


class MuscleEngagementEstimator:
    def __init__(self, smoothing_alpha: float = 0.28, baseline: float = 0.05):
        self.smoothing_alpha = float(np.clip(smoothing_alpha, 0.0, 1.0))
        self.baseline = float(np.clip(baseline, 0.0, 0.25))
        self.previous_engagement: dict[str, float] = {}
        self.history: list[dict[str, object]] = []

    def estimate(
        self,
        landmarks: Mapping[str, Mapping[str, float]] | None,
        metrics: Mapping[str, float] | None,
        frame_index: int,
        timestamp_sec: float,
    ) -> dict[str, float]:
        del landmarks
        metrics = metrics or {}

        left_knee_vel = _safe_float(metrics.get("left_knee_angular_velocity"))
        right_knee_vel = _safe_float(metrics.get("right_knee_angular_velocity"))
        knee_vel = _finite_mean([left_knee_vel, right_knee_vel])
        knee_acc = _finite_mean(
            [
                _safe_float(metrics.get("left_knee_angular_acceleration")),
                _safe_float(metrics.get("right_knee_angular_acceleration")),
            ]
        )

        hip_vel = _safe_float(metrics.get("hip_angular_velocity"))
        ankle_signal = _finite_max(
            [
                _abs_norm(_safe_float(metrics.get("left_ankle_angular_velocity")), 220.0),
                _abs_norm(_safe_float(metrics.get("right_ankle_angular_velocity")), 220.0),
            ]
        )
        ankle_speed_signal = _finite_max(
            [
                _positive_norm(_safe_float(metrics.get("left_ankle_speed")), 900.0),
                _positive_norm(_safe_float(metrics.get("right_ankle_speed")), 900.0),
            ]
        )

        torso_rotation_velocity = _safe_float(metrics.get("torso_rotation_velocity"))
        torso_tilt_velocity = _safe_float(metrics.get("torso_angular_velocity"))
        torso_rotation_angle = _safe_float(metrics.get("torso_rotation_angle"))
        torso_tilt_angle = _safe_float(metrics.get("torso_tilt_angle"))
        shoulder_velocity = _finite_mean(
            [
                _safe_float(metrics.get("left_shoulder_angular_velocity")),
                _safe_float(metrics.get("right_shoulder_angular_velocity")),
            ]
        )
        elbow_velocity = _finite_mean(
            [
                _safe_float(metrics.get("left_elbow_angular_velocity")),
                _safe_float(metrics.get("right_elbow_angular_velocity")),
            ]
        )
        wrist_speed_signal = _finite_max(
            [
                _positive_norm(_safe_float(metrics.get("left_wrist_speed")), 1200.0),
                _positive_norm(_safe_float(metrics.get("right_wrist_speed")), 1200.0),
            ]
        )
        hip_speed_signal = _positive_norm(_safe_float(metrics.get("hip_center_speed")), 600.0)
        motion_signal = _positive_norm(_safe_float(metrics.get("motion_intensity")), 900.0)
        hand_distance = _safe_float(metrics.get("hand_distance"))
        shoulder_width = _safe_float(metrics.get("shoulder_width"))
        arm_spread = hand_distance / shoulder_width if math.isfinite(hand_distance) and math.isfinite(shoulder_width) and shoulder_width > 1e-6 else float("nan")

        raw = {
            "quadriceps": self.baseline
            + 0.55 * _positive_norm(knee_vel, 280.0)
            + 0.18 * _positive_norm(knee_acc, 1800.0)
            + 0.12 * hip_speed_signal
            + 0.08 * motion_signal,
            "hamstrings": self.baseline
            + 0.48 * _positive_norm(-knee_vel, 240.0)
            + 0.18 * _positive_norm(-hip_vel, 220.0)
            + 0.16 * _positive_norm(-knee_acc, 1800.0)
            + 0.08 * hip_speed_signal,
            "glutes": self.baseline
            + 0.58 * _positive_norm(hip_vel, 240.0)
            + 0.22 * hip_speed_signal
            + 0.08 * _positive_norm(abs(_safe_float(metrics.get("hip_angle_mean"))) - 110.0, 55.0)
            + 0.05 * motion_signal,
            "calves": self.baseline
            + 0.45 * float(ankle_signal if math.isfinite(ankle_signal) else 0.0)
            + 0.35 * float(ankle_speed_signal if math.isfinite(ankle_speed_signal) else 0.0)
            + 0.08 * hip_speed_signal,
            "erector_spinae": self.baseline
            + 0.58 * _abs_norm(torso_tilt_velocity, 180.0)
            + 0.18 * _positive_norm(torso_tilt_angle - 8.0, 35.0)
            + 0.12 * hip_speed_signal
            + 0.05 * motion_signal,
            "obliques": self.baseline
            + 0.62 * _abs_norm(torso_rotation_velocity, 180.0)
            + 0.16 * _abs_norm(torso_rotation_angle, 30.0)
            + 0.10 * motion_signal,
            "deltoids": self.baseline
            + 0.52 * _abs_norm(shoulder_velocity, 240.0)
            + 0.12 * _abs_norm(elbow_velocity, 260.0)
            + 0.12 * _positive_norm(arm_spread if math.isfinite(arm_spread) else 0.0, 2.4)
            + 0.08 * wrist_speed_signal,
            "forearms": self.baseline
            + 0.60 * float(wrist_speed_signal if math.isfinite(wrist_speed_signal) else 0.0)
            + 0.16 * _abs_norm(elbow_velocity, 260.0)
            + 0.08 * motion_signal,
        }

        engagement: dict[str, float] = {}
        for muscle_name, raw_value in raw.items():
            previous = self.previous_engagement.get(muscle_name, self.baseline)
            smoothed = previous * (1.0 - self.smoothing_alpha) + raw_value * self.smoothing_alpha
            engagement[muscle_name] = _clip01(smoothed)

        self.previous_engagement = engagement.copy()
        top_muscles = self.get_top_muscles(engagement, top_k=3)
        power_chain_hint = self.analyze_power_chain(metrics)
        self.history.append(
            {
                "frame": int(frame_index),
                "time_sec": float(timestamp_sec),
                "engagement": engagement.copy(),
                "top_muscles": [name for name, _ in top_muscles],
                "power_chain_hint": power_chain_hint,
            }
        )
        return engagement

    def get_top_muscles(self, engagement_dict: Mapping[str, float], top_k: int = 3) -> list[tuple[str, float]]:
        ordered = sorted(
            ((name, _safe_float(value)) for name, value in engagement_dict.items()),
            key=lambda item: item[1] if math.isfinite(item[1]) else -1.0,
            reverse=True,
        )
        return ordered[: max(1, int(top_k))]

    def analyze_power_chain(self, metrics: Mapping[str, float] | None) -> str:
        metrics = metrics or {}
        ankle_drive = max(
            _positive_norm(_safe_float(metrics.get("left_ankle_speed")), 900.0),
            _positive_norm(_safe_float(metrics.get("right_ankle_speed")), 900.0),
            _abs_norm(_safe_float(metrics.get("left_ankle_angular_velocity")), 220.0),
            _abs_norm(_safe_float(metrics.get("right_ankle_angular_velocity")), 220.0),
        )
        hip_transfer = max(
            _positive_norm(_safe_float(metrics.get("hip_center_speed")), 600.0),
            _positive_norm(_safe_float(metrics.get("hip_angular_velocity")), 220.0),
        )
        trunk_link = max(
            _abs_norm(_safe_float(metrics.get("torso_rotation_velocity")), 180.0),
            _abs_norm(_safe_float(metrics.get("torso_angular_velocity")), 180.0),
        )
        upper_release = max(
            _positive_norm(_safe_float(metrics.get("left_wrist_speed")), 1200.0),
            _positive_norm(_safe_float(metrics.get("right_wrist_speed")), 1200.0),
            _abs_norm(_safe_float(metrics.get("left_shoulder_angular_velocity")), 240.0),
            _abs_norm(_safe_float(metrics.get("right_shoulder_angular_velocity")), 240.0),
        )

        signals = {
            "lower": ankle_drive,
            "hip": hip_transfer,
            "trunk": trunk_link,
            "upper": upper_release,
        }
        dominant = max(signals, key=signals.get)
        if signals[dominant] < 0.18:
            return "发力链提示：当前更接近过渡或定势阶段，整体参与度较平缓。"
        if dominant == "lower":
            return "发力链提示：下肢驱动更明显，力量起点主要来自蹬地与步型转换。"
        if dominant == "hip":
            return "发力链提示：髋部传递较活跃，动作正在把地面反作用传向躯干。"
        if dominant == "trunk":
            return "发力链提示：核心连接更明显，躯干旋转/稳定正在接管动作节奏。"
        return "发力链提示：上肢释放更明显，动作能量已传到肩臂与器械控制端。"

    def detect_peak_moments(self, history: Sequence[Mapping[str, object]] | None = None) -> list[dict[str, object]]:
        records = list(history or self.history)
        if not records:
            return []

        scored: list[dict[str, object]] = []
        for record in records:
            engagement = record.get("engagement", {})
            if not isinstance(engagement, Mapping):
                continue
            total_score = float(sum(_safe_float(value) for value in engagement.values() if math.isfinite(_safe_float(value))))
            scored.append(
                {
                    "frame": int(record.get("frame", 0)),
                    "time_sec": float(record.get("time_sec", 0.0)),
                    "score": total_score,
                    "top_muscles": ", ".join(MUSCLE_LABELS.get(name, name) for name in record.get("top_muscles", [])[:3]),
                    "power_chain_hint": str(record.get("power_chain_hint", "")),
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        selected: list[dict[str, object]] = []
        for candidate in scored:
            if any(abs(candidate["time_sec"] - existing["time_sec"]) < 0.35 for existing in selected):
                continue
            selected.append(candidate)
            if len(selected) >= 3:
                break
        return selected

    def summarize_power_chain(self, history: Sequence[Mapping[str, object]] | None = None) -> dict[str, object]:
        records = list(history or self.history)
        if not records:
            return {"dominant_hint": "暂无数据", "hint_counts": {}}
        hints = [str(record.get("power_chain_hint", "")).strip() for record in records if str(record.get("power_chain_hint", "")).strip()]
        counter = Counter(hints)
        dominant_hint = counter.most_common(1)[0][0] if counter else "暂无数据"
        return {"dominant_hint": dominant_hint, "hint_counts": dict(counter)}
