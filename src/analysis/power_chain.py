from __future__ import annotations

"""发力链分析。

从逐帧指标中打分下肢驱动 / 髋部传递 / 躯干连接 / 上肢释放，
输出每帧分数与阶段，以及整段视频的主导发力链摘要。

注意：这是启发式时序标签，不是对“真实力量传导”的精确测量。
"""

import math
from collections import Counter
from typing import Any, Mapping

import numpy as np
import pandas as pd


def _safe_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def _positive_norm(value: float, scale: float) -> float:
    if not math.isfinite(value) or scale <= 0:
        return 0.0
    return float(np.clip(max(0.0, value) / scale, 0.0, 1.0))


def _abs_norm(value: float, scale: float) -> float:
    if not math.isfinite(value) or scale <= 0:
        return 0.0
    return float(np.clip(abs(value) / scale, 0.0, 1.0))


def score_power_chain(metrics: Mapping[str, Any]) -> dict[str, float]:
    """打分四段发力链信号，返回 {lower, hip, trunk, upper}。"""
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
    return {
        "lower": float(ankle_drive),
        "hip": float(hip_transfer),
        "trunk": float(trunk_link),
        "upper": float(upper_release),
    }


HINT_TEXTS = {
    "lower": "发力链提示：下肢驱动更明显，力量起点主要来自蹬地与步型转换。",
    "hip": "发力链提示：髋部传递较活跃，动作正在把地面反作用传向躯干。",
    "trunk": "发力链提示：核心连接更明显，躯干旋转/稳定正在接管动作节奏。",
    "upper": "发力链提示：上肢释放更明显，动作能量已传到肩臂与器械控制端。",
}
TRANSITION_HINT = "发力链提示：当前更接近过渡或定势阶段，整体参与度较平缓。"
STAGE_LABELS = {"lower": "Lower-limb drive", "hip": "Hip transfer", "trunk": "Torso rotation", "upper": "Upper-limb release"}


def hint_from_scores(scores: Mapping[str, float]) -> str:
    if not scores:
        return TRANSITION_HINT
    dominant = max(scores, key=scores.get)
    if scores[dominant] < 0.18:
        return TRANSITION_HINT
    return HINT_TEXTS[dominant]


def stage_from_scores(scores: Mapping[str, float]) -> str:
    if not scores:
        return "Transition / Hold"
    dominant = max(scores, key=scores.get)
    if scores[dominant] < 0.18:
        return "Transition / Hold"
    return STAGE_LABELS[dominant]


def analyze_power_chain(metrics_df: pd.DataFrame) -> dict[str, Any]:
    """对整段视频做发力链分析，返回结构化结果。"""
    rows: list[dict[str, Any]] = []
    hints: list[str] = []
    for _, row in metrics_df.iterrows():
        scores = score_power_chain(row.to_dict())
        hint = hint_from_scores(scores)
        hints.append(hint)
        rows.append(
            {
                "frame": int(row.get("frame_index", 0)),
                "timestamp_sec": float(row.get("timestamp_sec", 0.0)),
                "scores": scores,
                "stage": stage_from_scores(scores),
                "hint": hint,
            }
        )
    counter = Counter(hints)
    dominant = counter.most_common(1)[0][0] if counter else TRANSITION_HINT
    stage_counter = Counter(row["stage"] for row in rows)
    return {
        "frames": rows,
        "dominant_hint": dominant,
        "hint_counts": dict(counter),
        "stage_distribution": dict(stage_counter),
    }
