from __future__ import annotations

"""V3 技术诊断核心数据模型（纯 dataclass，可 JSON 序列化）。

设计约束：
- 不依赖 Streamlit / OpenCV / MediaPipe，只使用普通 Python 类型。
- 所有诊断必须能解释"为什么"，不允许只输出 True / False。
- 不伪造绝对标准：参考类型（self_baseline / personal_best / expert_template /
  structural_rule）必须随诊断记录。
"""

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class Severity(str, Enum):
    """问题严重程度。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReferenceType(str, Enum):
    """诊断所依据的参考类型。"""

    SELF_BASELINE = "self_baseline"      # 用户自己过去 N 次的数据基线
    PERSONAL_BEST = "personal_best"      # 用户个人优秀动作模板
    EXPERT_TEMPLATE = "expert_template"  # 专家动作模板（V3 预留接口）
    STRUCTURAL_RULE = "structural_rule"  # 结构规则（如发力链时序顺序），非绝对数值标准


@dataclass
class TechniqueProfile:
    """一个武术动作的完整技术档案（以后每个动作一个 Profile，互不共用规则）。"""

    technique_id: str
    name: str
    description: str = ""
    phases: list[dict[str, Any]] = field(default_factory=list)          # 动作阶段定义
    key_events: list[dict[str, Any]] = field(default_factory=list)      # 关键事件定义
    important_metrics: list[dict[str, Any]] = field(default_factory=list)  # 重要指标 + 训练意义
    expected_sequence: list[str] = field(default_factory=list)          # 期望的发力时序（事件 id）
    common_errors: list[dict[str, Any]] = field(default_factory=list)   # 错误模式定义
    diagnosis_rules: dict[str, Any] = field(default_factory=dict)       # 判定规则（相对参考，无绝对标准）
    training_goals: list[str] = field(default_factory=list)             # 训练目标


@dataclass
class KeyEvent:
    """关键事件：名称 / 帧 / 时间 / 数值 / 说明。"""

    name: str
    label: str = ""
    frame_index: int = -1
    time_sec: float = float("nan")
    value: float = float("nan")
    unit: str = ""
    description: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Phase:
    """动作阶段：起始事件 → 结束事件。"""

    name: str
    label: str = ""
    start_event: str = ""
    end_event: str = ""
    frame_start: int = -1
    frame_end: int = -1
    time_start_sec: float = float("nan")
    time_end_sec: float = float("nan")
    duration_ms: float = float("nan")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TimingLink:
    """发力链时序：两个事件之间的毫秒间隔。"""

    from_event: str
    to_event: str
    label: str = ""
    interval_ms: float = float("nan")
    expected_order: str = ""      # 期望顺序说明（如 髋→肩）
    order_ok: Optional[bool] = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosisEvidence:
    """一条诊断证据：必须可读、可解释。"""

    metric: str = ""
    value: float = float("nan")
    unit: str = ""
    reference_label: str = ""      # 例如 "个人优秀动作平均"
    reference_value: float = float("nan")
    deviation: str = ""            # 文本化偏差描述，如 "30ms，个人优秀动作平均 90ms"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TechniqueDiagnosis:
    """一条技术问题诊断。"""

    problem_id: str
    problem: str                        # 问题名称
    severity: str = Severity.LOW.value  # high / medium / low
    confidence: float = 0.5             # 0~1
    reference_type: str = ReferenceType.STRUCTURAL_RULE.value
    evidence: list[DiagnosisEvidence] = field(default_factory=list)
    evidence_text: str = ""             # 人话版本证据
    meaning: str = ""                   # 为什么是问题
    training_advice: str = ""           # 具体怎么改

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PunchWindow:
    """一个直拳动作周期（帧范围 + 全部分析结果）。"""

    window_index: int = 0
    frame_start: int = -1
    frame_end: int = -1
    time_start_sec: float = float("nan")
    time_end_sec: float = float("nan")
    duration_ms: float = float("nan")
    strike_hand: str = ""               # left / right
    detection_confidence: float = 0.5   # 检出置信度
    events: list[KeyEvent] = field(default_factory=list)
    phases: list[Phase] = field(default_factory=list)
    timing: list[TimingLink] = field(default_factory=list)
    diagnoses: list[TechniqueDiagnosis] = field(default_factory=list)
    top_issues: list[str] = field(default_factory=list)   # 最值得改的问题（含严重度）
    one_thing: str = ""                 # 本轮训练最重要的一件事
    reference_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TechniqueResult:
    """一次技术诊断的完整结果（一个 analysis 可能含多个出拳窗口）。"""

    technique_id: str
    analysis_id: str
    engine_version: str = "3.0.0"
    windows: list[PunchWindow] = field(default_factory=list)
    metrics_interpretation: dict[str, Any] = field(default_factory=dict)
    reference_available: dict[str, Any] = field(default_factory=dict)  # baseline/pb/expert 是否可用
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Path) -> "TechniqueResult":
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TechniqueResult":
        result = cls(
            technique_id=str(data.get("technique_id", "")),
            analysis_id=str(data.get("analysis_id", "")),
            engine_version=str(data.get("engine_version", "3.0.0")),
            metrics_interpretation=data.get("metrics_interpretation", {}),
            reference_available=data.get("reference_available", {}),
            notes=data.get("notes", []),
        )
        for window_data in data.get("windows", []):
            window = PunchWindow(**{k: v for k, v in window_data.items() if k in PunchWindow.__dataclass_fields__})
            window.events = [KeyEvent(**e) for e in window_data.get("events", [])]
            window.phases = [Phase(**p) for p in window_data.get("phases", [])]
            window.timing = [TimingLink(**t) for t in window_data.get("timing", [])]
            window.diagnoses = [_diagnosis_from_dict(d) for d in window_data.get("diagnoses", [])]
            result.windows.append(window)
        return result


def _diagnosis_from_dict(data: dict[str, Any]) -> TechniqueDiagnosis:
    diagnosis = TechniqueDiagnosis(
        problem_id=str(data.get("problem_id", "")),
        problem=str(data.get("problem", "")),
        severity=str(data.get("severity", "low")),
        confidence=float(data.get("confidence", 0.5)),
        reference_type=str(data.get("reference_type", "structural_rule")),
        evidence_text=str(data.get("evidence_text", "")),
        meaning=str(data.get("meaning", "")),
        training_advice=str(data.get("training_advice", "")),
    )
    diagnosis.evidence = [DiagnosisEvidence(**e) for e in data.get("evidence", [])]
    return diagnosis
