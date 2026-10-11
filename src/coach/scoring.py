"""直拳评分系统（100 分制，7 维度，基于 V3 诊断证据，不随机打分）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.technique.engine import load_technique_result
from src.technique.models import TechniqueResult


# 评分维度定义（与用户指定权重一致）
DIMENSIONS: list[dict[str, Any]] = [
    {"key": "chain_sequence", "name": "发力链顺序", "max_score": 20},
    {"key": "hip_involvement", "name": "髋部参与", "max_score": 15},
    {"key": "shoulder_elbow_wrist_transfer", "name": "肩肘腕动力传递", "max_score": 15},
    {"key": "trajectory_elbow_control", "name": "出拳轨迹和肘部控制", "max_score": 15},
    {"key": "end_speed_completion", "name": "末端速度和击打完成度", "max_score": 15},
    {"key": "body_stability", "name": "身体稳定性", "max_score": 10},
    {"key": "recovery_speed", "name": "回收速度", "max_score": 10},
]

# V3 错误模式 → 影响的维度 + 该维度内的扣分比例（占该维度满分的比例）
_PROBLEM_DIMENSION_MAP: dict[str, list[dict[str, float]]] = {
    "shoulder_starts_early": [{"dimension": "chain_sequence", "fraction": 0.5}],
    "chain_order_mixed": [{"dimension": "chain_sequence", "fraction": 0.5}],
    "insufficient_hip": [{"dimension": "hip_involvement", "fraction": 0.6}],
    "arm_dominant": [
        {"dimension": "hip_involvement", "fraction": 0.4},
        {"dimension": "shoulder_elbow_wrist_transfer", "fraction": 0.3},
    ],
    "elbow_flare": [{"dimension": "trajectory_elbow_control", "fraction": 0.7}],
    "excessive_forward_shift": [{"dimension": "body_stability", "fraction": 0.6}],
    "insufficient_end_speed": [{"dimension": "end_speed_completion", "fraction": 0.7}],
    "slow_recovery": [{"dimension": "recovery_speed", "fraction": 0.8}],
    "excessive_head_motion": [{"dimension": "body_stability", "fraction": 0.3}],
    "poor_stability": [{"dimension": "body_stability", "fraction": 0.4}],
    "left_right_asymmetry": [{"dimension": "shoulder_elbow_wrist_transfer", "fraction": 0.4}],
}

_SEVERITY_FACTOR = {"high": 1.0, "medium": 0.6, "low": 0.3}


@dataclass
class DimensionScore:
    key: str
    name: str
    max_score: float
    score: float
    deductions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "max_score": self.max_score,
            "score": round(self.score, 1),
            "deductions": self.deductions,
        }


@dataclass
class ScoreResult:
    total_score: float
    dimensions: list[DimensionScore]
    has_expert_template: bool
    is_experimental: bool
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": round(self.total_score, 1),
            "dimensions": [d.to_dict() for d in self.dimensions],
            "has_expert_template": self.has_expert_template,
            "is_experimental": self.is_experimental,
            "confidence": round(self.confidence, 2),
        }


def _max_severity(diagnoses: list[dict[str, Any]], problem_id: str) -> str | None:
    """取某 problem_id 的最严重级别。"""
    severities = [d.get("severity") for d in diagnoses if d.get("problem_id") == problem_id]
    if not severities:
        return None
    order = {"high": 3, "medium": 2, "low": 1}
    return max(severities, key=lambda s: order.get(s, 0))


def _diagnoses_flat(result: TechniqueResult) -> list[dict[str, Any]]:
    """把所有窗口的 diagnoses 拍平成 list[dict]。"""
    flat: list[dict[str, Any]] = []
    for window in result.windows:
        for d in window.diagnoses:
            item = {
                "problem_id": d.problem_id,
                "problem": d.problem,
                "severity": d.severity,
                "confidence": d.confidence,
                "evidence_text": d.evidence_text,
                "meaning": d.meaning,
                "training_advice": d.training_advice,
                "window_index": window.window_index,
                "strike_hand": window.strike_hand,
                "duration_ms": window.duration_ms,
            }
            flat.append(item)
    return flat


def compute_score(analysis_id: str) -> ScoreResult | None:
    """基于 V3 诊断结果计算 100 分制评分。

    评分规则：
    - 初始每维度满分
    - V3 检测到某 problem → 按映射表扣对应维度分数
    - severity high/medium/low → 全额/60%/30% 扣分
    - 同维度多个问题扣分叠加，但不低于 0
    - 没有专家模板时，结果标记为"实验性估计"
    """
    result = load_technique_result(analysis_id)
    if result is None:
        return None

    diagnoses = _diagnoses_flat(result)

    # 初始化维度
    dim_map = {d["key"]: DimensionScore(key=d["key"], name=d["name"], max_score=d["max_score"], score=d["max_score"]) for d in DIMENSIONS}

    # 逐 problem 扣分
    seen_problems: set[str] = set()
    for diag in diagnoses:
        pid = diag["problem_id"]
        if pid not in _PROBLEM_DIMENSION_MAP or pid in seen_problems:
            continue
        seen_problems.add(pid)
        severity = diag["severity"]
        factor = _SEVERITY_FACTOR.get(severity, 0.3)
        for mapping in _PROBLEM_DIMENSION_MAP[pid]:
            dim_key = mapping["dimension"]
            fraction = mapping["fraction"]
            dim = dim_map.get(dim_key)
            if dim is None:
                continue
            deduction = dim.max_score * fraction * factor
            dim.score = max(0.0, dim.score - deduction)
            dim.deductions.append({
                "problem_id": pid,
                "problem": diag["problem"],
                "severity": severity,
                "deduction": round(deduction, 1),
                "evidence": diag["evidence_text"],
                "training_advice": diag["training_advice"],
                "window_index": diag["window_index"],
            })

    total = sum(d.score for d in dim_map.values())

    has_expert = bool(result.reference_available.get("expert_template", False))
    is_experimental = not has_expert

    # 置信度：窗口数越多越可信
    confidence = min(0.95, 0.5 + 0.1 * len(result.windows))

    return ScoreResult(
        total_score=total,
        dimensions=list(dim_map.values()),
        has_expert_template=has_expert,
        is_experimental=is_experimental,
        confidence=confidence,
    )
