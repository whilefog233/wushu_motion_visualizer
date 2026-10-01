from __future__ import annotations

"""兼容层：OfflineVideoProcessor。

V2 之后核心分析全部走 :mod:`src.analysis.pipeline`，本模块保留旧类与旧 API
（``process()`` 返回同样的 dict 键），实现上委托给新的 AnalysisPipeline，
不再重复初始化 MediaPipe / 重复读取视频。

新调用方请直接使用::

    from src.analysis.pipeline import analyze_video
"""

from pathlib import Path
from typing import Callable, Optional

from src.analysis.pipeline import AnalysisPipeline, AnalysisStage, load_pipeline_config
from src.models.pose_result import PoseResult


ProgressCallback = Optional[Callable[[float, str], None]]


class OfflineProcessConfig:
    """保留旧字段名以兼容已有调用；多数字段在新管线中不再生效。"""

    def __init__(
        self,
        max_video_side: int = 1280,
        skeleton_background_bgr=(18, 18, 18),
        trajectory_seconds: int = 5,
        show_trajectory_overlay: bool = False,
        speed_smoothing_alpha: float = 0.35,
        export_side_by_side_video: bool = False,
        side_by_side_filename: str = "side_by_side_video.mp4",
        keypoints_filename: str = "keypoints.json",
        metrics_filename: str = "metrics.csv",
        summary_filename: str = "summary.json",
        report_filename: str = "summary.md",
    ):
        self.max_video_side = max_video_side
        self.skeleton_background_bgr = skeleton_background_bgr
        self.trajectory_seconds = trajectory_seconds
        self.show_trajectory_overlay = show_trajectory_overlay
        self.speed_smoothing_alpha = speed_smoothing_alpha
        self.export_side_by_side_video = export_side_by_side_video
        self.side_by_side_filename = side_by_side_filename
        self.keypoints_filename = keypoints_filename
        self.metrics_filename = metrics_filename
        self.summary_filename = summary_filename
        self.report_filename = report_filename


class OfflineVideoProcessor:
    """兼容旧接口的薄封装：所有重活交给 AnalysisPipeline。"""

    def __init__(self, pose_backend=None, config: OfflineProcessConfig | None = None, app_config: dict | None = None):
        self.pose_backend = pose_backend  # 兼容属性：V2 管线内部自建后端
        self.config = config or OfflineProcessConfig()
        self.app_config = app_config

    def process(self, input_video_path: str | Path, progress_callback: ProgressCallback = None) -> dict[str, object]:
        pipeline_config = self.app_config or load_pipeline_config()

        def adapter(stage, progress, message):
            if progress_callback:
                progress_callback(progress, message)

        result = AnalysisPipeline(config=pipeline_config, progress_callback=adapter).analyze(input_video_path)

        summary = (result.analysis or {}).get("summary", {})
        pose: Optional[PoseResult] = result.pose
        frame_width = pose.width if pose else 0
        frame_height = pose.height if pose else 0

        side_by_side_video_path = None
        if self.config.export_side_by_side_video:
            from src.export.skeleton_video import export_skeleton_video

            side_by_side_video_path = export_skeleton_video(result.analysis_id)

        paths = result.paths
        return {
            "run_dir": result.analysis_dir,
            "analysis_id": result.analysis_id,
            "input_video_path": Path(input_video_path),
            "side_by_side_video_path": side_by_side_video_path,
            "keypoints_json_path": Path(paths["pose_json"]),
            "metrics_csv_path": Path(paths["metrics_csv"]),
            "summary_json_path": Path(paths["analysis_json"]),
            "summary_md_path": Path(paths["summary_md"]),
            "metrics_df": result.metrics_df,
            "summary": summary,
            "fps": result.fps,
            "total_frames": result.frame_count,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "reused_pose": result.reused_pose,
        }


def build_offline_components(app_config: dict) -> OfflineVideoProcessor:
    return OfflineVideoProcessor(config=OfflineProcessConfig(), app_config=app_config)
