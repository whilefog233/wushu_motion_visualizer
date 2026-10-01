"""肌肉分析算法模块。

说明：``process_muscle_video`` 在 V2 中作为兼容入口保留（内部委托
AnalysisPipeline），为打破循环依赖，不再在包初始化时急切导入。
"""

from .muscle_estimator import MuscleEngagementEstimator
from .muscle_renderer import MuscleRenderer
from .opensim_adapter import OpenSimAdapter

__all__ = [
    "MuscleEngagementEstimator",
    "MuscleRenderer",
    "OpenSimAdapter",
    "process_muscle_video",
]


def process_muscle_video(*args, **kwargs):
    """延迟加载的兼容入口，见 muscle_analysis.video_muscle_pipeline。"""
    from .video_muscle_pipeline import process_muscle_video as _impl

    return _impl(*args, **kwargs)
