from __future__ import annotations

"""分析任务状态与阶段定义。

分析进度状态统一在这里定义，Streamlit UI 只读取展示，
未来 Web 网站 / Python Worker 也直接复用这套状态。
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import pandas as pd


class AnalysisStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AnalysisStage(str, Enum):
    PREPARING = "PREPARING"
    EXTRACTING_POSE = "EXTRACTING_POSE"
    CALCULATING_METRICS = "CALCULATING_METRICS"
    ANALYZING_MUSCLE = "ANALYZING_MUSCLE"
    ANALYZING_POWER_CHAIN = "ANALYZING_POWER_CHAIN"
    BUILDING_RESULT = "BUILDING_RESULT"
    SAVING_RESULTS = "SAVING_RESULTS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# 流水线阶段的固定执行顺序（排除 COMPLETED / FAILED）
STAGE_ORDER: list[AnalysisStage] = [
    AnalysisStage.PREPARING,
    AnalysisStage.EXTRACTING_POSE,
    AnalysisStage.CALCULATING_METRICS,
    AnalysisStage.ANALYZING_MUSCLE,
    AnalysisStage.ANALYZING_POWER_CHAIN,
    AnalysisStage.BUILDING_RESULT,
    AnalysisStage.SAVING_RESULTS,
    AnalysisStage.COMPLETED,
]


@dataclass
class AnalysisResult:
    """一次分析的最终结果（内存形态），供 UI / Worker 直接使用。"""

    analysis_id: str
    analysis_dir: Path
    status: AnalysisStatus
    stage: AnalysisStage
    paths: dict[str, Path] = field(default_factory=dict)
    pose: Any = None  # PoseResult 或 None
    metrics_df: Optional[pd.DataFrame] = None
    analysis: Optional[dict[str, Any]] = None
    muscle: Optional[dict[str, Any]] = None
    power_chain: Optional[dict[str, Any]] = None
    performance: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    reused_pose: bool = False

    @property
    def fps(self) -> float:
        return float(self.metadata.get("video", {}).get("fps", 0.0)) if self.metadata else 0.0

    @property
    def frame_count(self) -> int:
        return int(self.metadata.get("video", {}).get("frame_count", 0)) if self.metadata else 0

    @property
    def source_path(self) -> Optional[Path]:
        """源视频路径：优先 analysis 目录内的 source.mp4（自包含），其次原始绝对路径。"""
        source_video = self.paths.get("source_video")
        if source_video and Path(source_video).exists():
            return Path(source_video)
        if self.metadata and self.metadata.get("source_abs_path"):
            return Path(self.metadata["source_abs_path"])
        return None
