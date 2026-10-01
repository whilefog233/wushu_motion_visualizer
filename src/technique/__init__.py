"""武术技术诊断引擎（V3）。

核心链路：pose.json + metrics.csv → SignalBundle → 出拳窗口 → 关键事件
→ 动作阶段 → 发力链时序 → 错误模式诊断（参考校准）→ TechniqueResult。

当前只支持直拳（straight_punch）；以后每个动作一个 TechniqueProfile。
"""

from src.technique.engine import (
    ENGINE_VERSION,
    TechniqueEngine,
    analyze_technique,
    load_technique_result,
)
from src.technique.models import (
    KeyEvent,
    Phase,
    PunchWindow,
    Severity,
    TechniqueDiagnosis,
    TechniqueProfile,
    TechniqueResult,
    TimingLink,
)
from src.technique.profiles import STRAIGHT_PUNCH_ID, get_profile

__all__ = [
    "ENGINE_VERSION",
    "TechniqueEngine",
    "analyze_technique",
    "load_technique_result",
    "KeyEvent",
    "Phase",
    "PunchWindow",
    "Severity",
    "TechniqueDiagnosis",
    "TechniqueProfile",
    "TechniqueResult",
    "TimingLink",
    "STRAIGHT_PUNCH_ID",
    "get_profile",
]
