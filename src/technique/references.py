"""参考系统：Self Baseline / Personal Best / Expert Template。

V3 原则：没有可靠依据时不伪造绝对标准。所有"好坏"判断优先来自：
1. Self Baseline —— 用户自己最近 N 次动作的数据分布（均值/标准差）。
2. Personal Best —— 用户自己的优秀动作模板（归一化曲线 + 事件时序）。
3. Expert Template —— 专家模板（V3 预留接口，只建结构与归一化比较方法）。

存储位置：data/analyses/_technique_refs/{technique_id}/ 下三个文件。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from src.storage.analysis_store import AnalysisStore

BASELINE_WINDOW = 10  # 滚动基线保留最近 N 个窗口

# 基线聚合的指标键（与 errors.py 消费的 ref key 一一对应）
BASELINE_KEYS = [
    "hip_shoulder_gap_ms",
    "hip_angular_velocity_peak",
    "terminal_amplification",
    "recovery_strike_ratio",
    "head_displacement",
    "wrist_jitter",
    "hip_forward_shift",
]


def _refs_dir(technique_id: str) -> Path:
    # 点开头：analysis_store.list_analyses 会跳过隐藏目录
    root = AnalysisStore().root / "._technique_refs"
    return root / technique_id


def refs_dir(technique_id: str) -> Path:
    return _refs_dir(technique_id)


# ---------------------------------------------------------------- Self Baseline
def load_baseline(technique_id: str) -> dict[str, Any]:
    """加载基线，返回 {metric: {mean, std, count, values}}。"""
    path = _refs_dir(technique_id) / "baseline.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data.get("metrics", {})


def update_baseline(technique_id: str, window_stats: dict[str, float], analysis_id: str = "") -> None:
    """用一个窗口的统计更新滚动基线（保留最近 BASELINE_WINDOW 次）。"""
    metrics = load_baseline(technique_id)
    for key in BASELINE_KEYS:
        value = window_stats.get(key)
        if value is None or not math.isfinite(float(value)):
            continue
        entry = metrics.setdefault(key, {"values": [], "mean": float("nan"), "std": float("nan"), "count": 0})
        values = list(entry.get("values", []))[- (BASELINE_WINDOW - 1):]
        values.append(float(value))
        entry["values"] = values
        entry["count"] = len(values)
        if values:
            entry["mean"] = float(np.mean(values))
            entry["std"] = float(np.std(values)) if len(values) > 1 else float("nan")
    directory = _refs_dir(technique_id)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "technique_id": technique_id,
        "window_count": BASELINE_WINDOW,
        "last_analysis_id": analysis_id,
        "metrics": metrics,
    }
    with (directory / "baseline.json").open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- Personal Best
@dataclass
class PersonalBestTemplate:
    """个人优秀动作模板：归一化曲线 + 事件时序 + 关键指标。"""

    technique_id: str
    analysis_id: str
    window_index: int = 0
    event_times_normalized: dict[str, float] = None  # 事件时间归一化到 0~100%
    curves: dict[str, list[float]] = None            # 0~100% 采样的归一化曲线
    metrics: dict[str, float] = None                 # 关键指标
    total_issues: int = 0
    recorded_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "technique_id": self.technique_id,
            "analysis_id": self.analysis_id,
            "window_index": self.window_index,
            "event_times_normalized": self.event_times_normalized or {},
            "curves": self.curves or {},
            "metrics": self.metrics or {},
            "total_issues": self.total_issues,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonalBestTemplate":
        return cls(
            technique_id=str(data.get("technique_id", "")),
            analysis_id=str(data.get("analysis_id", "")),
            window_index=int(data.get("window_index", 0)),
            event_times_normalized=data.get("event_times_normalized", {}),
            curves=data.get("curves", {}),
            metrics=data.get("metrics", {}),
            total_issues=int(data.get("total_issues", 0)),
            recorded_at=str(data.get("recorded_at", "")),
        )


def load_personal_best(technique_id: str) -> Optional[PersonalBestTemplate]:
    path = _refs_dir(technique_id) / "personal_best.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return PersonalBestTemplate.from_dict(json.load(file))


def save_personal_best(template: PersonalBestTemplate) -> None:
    directory = _refs_dir(template.technique_id)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "personal_best.json").open("w", encoding="utf-8") as file:
        json.dump(template.to_dict(), file, ensure_ascii=False, indent=2)


def set_personal_best(technique_id: str, analysis_id: str, window_index: int = 0) -> PersonalBestTemplate:
    """把某次分析的某个窗口设为 Personal Best（显式调用；也可自动选取）。"""
    from src.technique.engine import _build_pb_template

    template = _build_pb_template(technique_id, analysis_id, window_index)
    save_personal_best(template)
    return template


def auto_personal_best(technique_id: str) -> Optional[PersonalBestTemplate]:
    """自动选择历史诊断中问题最少的一次作为 Personal Best（无手动标记时）。"""
    store = AnalysisStore()
    candidates: list[tuple[int, str, int]] = []  # (issues_count, analysis_id, window_index)
    for item in store.list_analyses():
        analysis_id = item["analysis_id"]
        technique_path = store.paths(analysis_id).analysis_dir / "technique" / f"{technique_id}.json"
        if not technique_path.exists():
            continue
        try:
            from src.technique.models import TechniqueResult

            result = TechniqueResult.load(technique_path)
        except Exception:
            continue
        for window in result.windows:
            severity_weight = sum(1 + (2 if d.severity == "high" else 1 if d.severity == "medium" else 0) for d in window.diagnoses)
            candidates.append((severity_weight, analysis_id, window.window_index))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    _, analysis_id, window_index = candidates[0]
    return set_personal_best(technique_id, analysis_id, window_index)


# ---------------------------------------------------------------- Expert Template（预留）
def expert_template_path(technique_id: str) -> Path:
    return _refs_dir(technique_id) / "expert_template.json"


def ensure_expert_template(technique_id: str) -> dict[str, Any]:
    """专家模板文件不存在时创建空模板（schema 就绪，指标待教练标注）。

    未来由教练/专家录入：把动作归一化到 0-100%，比较髋/肩/肘/腕曲线与事件时序。
    """
    path = expert_template_path(technique_id)
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    template = {
        "technique_id": technique_id,
        "schema_version": "3.0",
        "source": "expert_coach",
        "curves": {"hip_angular_velocity": None, "shoulder_speed": None, "elbow_angle": None, "wrist_speed": None},
        "event_times_normalized": {"hip_start": None, "shoulder_start": None, "elbow_extension_peak": None, "wrist_speed_peak": None},
        "metrics_goals": {},
        "notes": "预留专家模板：由教练标注直拳优秀动作的归一化曲线与事件时序。",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(template, file, ensure_ascii=False, indent=2)
    return template


# ---------------------------------------------------------------- 曲线归一化与比较
def normalize_curve(signal: np.ndarray, samples: int = 101) -> list[float]:
    """把信号归一化为 0~1 幅值的等长序列（0~100% 时间采样）。"""
    finite = signal[np.isfinite(signal)]
    if len(finite) == 0:
        return [float("nan")] * samples
    low, high = float(finite.min()), float(finite.max())
    span = high - low
    if span <= 1e-9:
        return [0.5] * samples
    normalized = (signal - low) / span
    x_old = np.linspace(0, 1, len(signal))
    x_new = np.linspace(0, 1, samples)
    interpolated = np.interp(x_new, x_old, normalized, left=float("nan"), right=float("nan"))
    return [float(v) for v in interpolated]


def normalize_event_times(events: list, start_time: float, end_time: float) -> dict[str, float]:
    """事件时间归一化到 0~100（动作周期百分比）。"""
    duration = end_time - start_time
    if duration <= 0:
        return {}
    result: dict[str, float] = {}
    for event in events:
        if math.isfinite(float(event.time_sec)):
            result[event.name] = round((float(event.time_sec) - start_time) / duration * 100.0, 1)
    return result


def curve_similarity(a: list[float], b: list[float]) -> float:
    """两条 0~1 归一化曲线的相似度：1 - 平均绝对差（越大越相似）。"""
    if not a or not b or len(a) != len(b):
        return float("nan")
    pairs = [(x, y) for x, y in zip(a, b) if math.isfinite(x) and math.isfinite(y)]
    if not pairs:
        return float("nan")
    return 1.0 - float(np.mean([abs(x - y) for x, y in pairs]))


# ---------------------------------------------------------------- 汇总入口
def load_reference(technique_id: str) -> dict[str, Any]:
    """汇总三类参考，返回引擎消费的 ref dict。

    ref["baseline_available"] / ref["personal_best_available"] / ref["expert_template_available"]
    让诊断层知道依据是否充分（决定 confidence）。
    """
    baseline = load_baseline(technique_id)
    pb = load_personal_best(technique_id)
    expert = ensure_expert_template(technique_id)
    ref: dict[str, Any] = dict(baseline)  # metric -> {mean, std, count, values}
    ref["baseline_available"] = any(
        entry.get("count", 0) >= 3 for entry in baseline.values()
    )
    ref["personal_best_available"] = pb is not None
    ref["expert_template_available"] = bool(expert.get("curves") and any(expert.get("curves", {}).values()))
    ref["personal_best"] = pb.to_dict() if pb is not None else None
    ref["expert_template"] = expert
    return ref
