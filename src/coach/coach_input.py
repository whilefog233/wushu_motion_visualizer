from __future__ import annotations

"""AI Coach 预留接口（第一阶段只建结构，不接任何大模型）。

设计目标：未来 AI Coach 读取 coach_input.json 即可给出教练建议，
不需要直接处理完整视频 / 原始姿态数据。

链路::

    视频 → MediaPipe / 动作引擎 → CoachInput JSON → GPT / Gemini → 武术教练建议
"""

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.models.pose_result import PoseResult
from src.storage.analysis_store import AnalysisStore


@dataclass
class CoachInput:
    """AI Coach 的结构化输入。"""

    analysis_id: str
    video_info: dict[str, Any] = field(default_factory=dict)      # 时长/fps/帧数/分辨率
    base_metrics: dict[str, Any] = field(default_factory=dict)     # 基础指标摘要
    joint_angles: dict[str, Any] = field(default_factory=dict)     # 各关节角度统计
    speeds: dict[str, Any] = field(default_factory=dict)           # px / normalized / world 速度摘要
    accelerations: dict[str, Any] = field(default_factory=dict)    # 角加速度统计
    left_right_diff: dict[str, Any] = field(default_factory=dict)  # 左右差异
    motion_phases: dict[str, Any] = field(default_factory=dict)    # Kinetic Chain Stage 分布
    power_chain: dict[str, Any] = field(default_factory=dict)      # 发力链顺序 / 主导提示
    abnormal_peaks: list[dict[str, Any]] = field(default_factory=list)  # 异常峰值
    abnormal_frames: list[dict[str, Any]] = field(default_factory=list)  # 异常帧（低置信/极端值）
    timeline: list[dict[str, Any]] = field(default_factory=list)   # 时间轴（压缩采样）
    muscle_estimate: dict[str, Any] = field(default_factory=dict)  # 肌肉估计摘要
    stability: dict[str, Any] = field(default_factory=dict)        # 动作稳定性指标

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stat(series: pd.Series) -> dict[str, float]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {"mean": float("nan"), "min": float("nan"), "max": float("nan"), "std": float("nan")}
    return {
        "mean": float(numeric.mean()),
        "min": float(numeric.min()),
        "max": float(numeric.max()),
        "std": float(numeric.std()),
    }


def build_coach_context(analysis_id: str, write_json: bool = True) -> dict[str, Any]:
    """读取 analysis 目录全部产物，组装结构化 CoachInput 并返回 dict。

    写出的 coach_input.json 是未来 GPT / Gemini 的唯一输入。
    """
    store = AnalysisStore()
    paths = store.paths(analysis_id)
    metadata = store.load_metadata(analysis_id)
    pose = PoseResult.load(paths.pose_json) if paths.pose_json.exists() else None
    metrics_df = pd.read_csv(paths.metrics_csv) if paths.metrics_csv.exists() else None
    analysis = _load_json(paths.analysis_json)
    muscle = _load_json(paths.muscle_json)
    power_chain = _load_json(paths.power_chain_json)

    coach = CoachInput(analysis_id=analysis_id)
    coach.video_info = {
        "duration_sec": float(metadata.get("video", {}).get("duration", 0.0)),
        "fps": float(metadata.get("video", {}).get("fps", 0.0)),
        "frame_count": int(metadata.get("video", {}).get("frame_count", 0)),
        "width": int(metadata.get("video", {}).get("width", 0)),
        "height": int(metadata.get("video", {}).get("height", 0)),
        "source_filename": metadata.get("source_filename", ""),
    }

    if metrics_df is not None and not metrics_df.empty:
        _fill_metrics_context(coach, metrics_df)

    if analysis:
        coach.base_metrics.update(analysis.get("summary", {}))
        coach.speeds.update(analysis.get("normalized_speed", {}))
        power = analysis.get("power_chain", {})
        coach.power_chain["dominant_hint"] = power.get("dominant_hint", "")
        coach.power_chain["hint_counts"] = power.get("hint_counts", {})
        coach.power_chain["stage_distribution"] = power.get("stage_distribution", {})

    if power_chain:
        frames = power_chain.get("frames", [])
        # 发力链顺序：按时间轴采样关键阶段序列（压缩到 <= 20 段）
        step = max(1, len(frames) // 20)
        coach.power_chain["sequence"] = [
            {"timestamp_sec": f.get("timestamp_sec", 0.0), "stage": f.get("stage", "")} for f in frames[::step]
        ]

    if muscle:
        muscle_summary = muscle.get("summary", {})
        coach.muscle_estimate = {
            "muscle_statistics": muscle_summary.get("muscle_statistics", []),
            "dominant_power_chain_hint": muscle_summary.get("dominant_power_chain_hint", ""),
            "peak_moments": muscle_summary.get("peak_moments", []),
        }

    if metrics_df is not None and not metrics_df.empty:
        coach.stability = _stability(metrics_df)
        coach.abnormal_frames = _abnormal_frames(metrics_df)
        coach.abnormal_peaks = _abnormal_peaks(metrics_df)
        coach.timeline = _timeline(metrics_df)

    coach_dict = coach.to_dict()
    if write_json:
        paths.coach_input_json.parent.mkdir(parents=True, exist_ok=True)
        with paths.coach_input_json.open("w", encoding="utf-8") as file:
            json.dump(coach_dict, file, ensure_ascii=False, indent=2)
    return coach_dict


def _fill_metrics_context(coach: CoachInput, metrics_df: pd.DataFrame) -> None:
    angle_columns = [
        "left_shoulder_angle",
        "right_shoulder_angle",
        "left_elbow_angle",
        "right_elbow_angle",
        "left_hip_angle",
        "right_hip_angle",
        "left_knee_angle",
        "right_knee_angle",
        "left_ankle_angle",
        "right_ankle_angle",
        "torso_tilt_angle",
    ]
    for column in angle_columns:
        if column in metrics_df.columns:
            coach.joint_angles[column] = _stat(metrics_df[column])

    speed_columns = [
        "left_wrist_speed",
        "right_wrist_speed",
        "left_ankle_speed",
        "right_ankle_speed",
        "hip_center_speed",
        "left_wrist_speed_normalized",
        "right_wrist_speed_normalized",
        "hip_center_speed_normalized",
        "left_wrist_speed_world",
        "right_wrist_speed_world",
        "hip_center_speed_world",
    ]
    for column in speed_columns:
        if column in metrics_df.columns:
            coach.speeds[column] = _stat(metrics_df[column])

    accel_columns = [
        "left_knee_angular_acceleration",
        "right_knee_angular_acceleration",
        "left_elbow_angular_acceleration",
        "right_elbow_angular_acceleration",
    ]
    for column in accel_columns:
        if column in metrics_df.columns:
            coach.accelerations[column] = _stat(metrics_df[column])

    # 左右差异：均值差（绝对值）与不对称度
    pairs = [
        ("left_knee_angle", "right_knee_angle", "knee"),
        ("left_elbow_angle", "right_elbow_angle", "elbow"),
        ("left_shoulder_angle", "right_shoulder_angle", "shoulder"),
        ("left_wrist_speed", "right_wrist_speed", "wrist_speed"),
        ("left_ankle_speed", "right_ankle_speed", "ankle_speed"),
    ]
    for left_col, right_col, label in pairs:
        if left_col in metrics_df.columns and right_col in metrics_df.columns:
            left = pd.to_numeric(metrics_df[left_col], errors="coerce").dropna()
            right = pd.to_numeric(metrics_df[right_col], errors="coerce").dropna()
            if not left.empty and not right.empty:
                diff_mean = abs(float(left.mean()) - float(right.mean()))
                base = max(abs(float(left.mean())), abs(float(right.mean())))
                coach.left_right_diff[label] = {
                    "mean_diff": diff_mean,
                    "asymmetry_ratio": diff_mean / base if base > 1e-6 else float("nan"),
                }

    if "kinetic_chain_stage" in metrics_df.columns:
        coach.motion_phases["stage_distribution"] = metrics_df["kinetic_chain_stage"].value_counts().to_dict()


def _stability(metrics_df: pd.DataFrame) -> dict[str, Any]:
    """稳定性：关键指标的变异系数（越小越稳定）。"""
    stability: dict[str, Any] = {}
    for column in ["left_knee_angle", "right_knee_angle", "torso_tilt_angle", "hip_height"]:
        if column not in metrics_df.columns:
            continue
        stats = _stat(metrics_df[column])
        mean = stats.get("mean")
        std = stats.get("std")
        stability[column] = {
            "mean": mean,
            "std": std,
            "coefficient_of_variation": float(std / abs(mean)) if mean is not None and abs(float(mean)) > 1e-6 else float("nan"),
        }
    return stability


def _abnormal_frames(metrics_df: pd.DataFrame) -> list[dict[str, Any]]:
    """异常帧：检测置信度过低，或关键指标超过 3σ。"""
    abnormal: list[dict[str, Any]] = []
    if "detection_confidence" in metrics_df.columns:
        low_conf = metrics_df[pd.to_numeric(metrics_df["detection_confidence"], errors="coerce") < 0.35]
        for _, row in low_conf.head(30).iterrows():
            abnormal.append(
                {
                    "frame": int(row.get("frame_index", 0)),
                    "timestamp_sec": float(row.get("timestamp_sec", 0.0)),
                    "reason": "low_detection_confidence",
                    "value": float(row.get("detection_confidence", float("nan"))),
                }
            )
    for column in ["left_wrist_speed_normalized", "right_wrist_speed_normalized", "torso_angular_velocity"]:
        if column not in metrics_df.columns:
            continue
        series = pd.to_numeric(metrics_df[column], errors="coerce").dropna()
        if series.empty:
            continue
        mean, std = float(series.mean()), float(series.std())
        if not math.isfinite(std) or std <= 1e-9:
            continue
        extreme = metrics_df[np.abs(pd.to_numeric(metrics_df[column], errors="coerce") - mean) > 3 * std]
        for _, row in extreme.head(20).iterrows():
            abnormal.append(
                {
                    "frame": int(row.get("frame_index", 0)),
                    "timestamp_sec": float(row.get("timestamp_sec", 0.0)),
                    "reason": f"extreme_{column}",
                    "value": float(row.get(column, float("nan"))),
                }
            )
    # 去重（同一帧保留第一个原因）
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    for item in abnormal:
        if item["frame"] in seen:
            continue
        seen.add(item["frame"])
        unique.append(item)
    return unique[:50]


def _abnormal_peaks(metrics_df: pd.DataFrame) -> list[dict[str, Any]]:
    """异常峰值：normalized 手腕速度峰值与发力链阶段对应关系。"""
    peaks: list[dict[str, Any]] = []
    if "wrist_speed_normalized" in metrics_df.columns and "kinetic_chain_stage" in metrics_df.columns:
        series = pd.to_numeric(metrics_df["wrist_speed_normalized"], errors="coerce")
        threshold = series.quantile(0.95) if series.notna().sum() > 5 else float("nan")
        if math.isfinite(threshold):
            top = metrics_df[series >= threshold].head(10)
            for _, row in top.iterrows():
                peaks.append(
                    {
                        "frame": int(row.get("frame_index", 0)),
                        "timestamp_sec": float(row.get("timestamp_sec", 0.0)),
                        "metric": "wrist_speed_normalized",
                        "value": float(row.get("wrist_speed_normalized", float("nan"))),
                        "stage": str(row.get("kinetic_chain_stage", "")),
                    }
                )
    return peaks


def _timeline(metrics_df: pd.DataFrame, max_points: int = 120) -> list[dict[str, Any]]:
    """时间轴（压缩采样）：帧/时间/运动强度/发力阶段。"""
    if metrics_df.empty:
        return []
    step = max(1, len(metrics_df) // max_points)
    rows = []
    for _, row in metrics_df.iloc[::step].iterrows():
        rows.append(
            {
                "frame": int(row.get("frame_index", 0)),
                "timestamp_sec": float(row.get("timestamp_sec", 0.0)),
                "motion_intensity": float(row.get("motion_intensity", float("nan"))),
                "kinetic_chain_stage": str(row.get("kinetic_chain_stage", "")),
                "wrist_speed_normalized": float(row.get("wrist_speed_normalized", float("nan"))),
            }
        )
    return rows


def _load_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
