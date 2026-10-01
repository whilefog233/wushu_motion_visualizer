from __future__ import annotations

"""统一 Pose Analysis Pipeline（第一阶段：姿态提取）。

同一个视频、同一个 analysis_id 默认只执行一次完整 MediaPipe Pose 推理，
结果保存为 PoseResult，并落盘到 ``pose.json``。后续骨架分析、肌肉分析、
关节角度、速度、加速度、发力链、AI Coach 全部复用该结果。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import cv2

from src.models.pose_result import PoseResult
from src.pose.mediapipe_backend import MediaPipePoseBackend, PoseBackendConfig
from src.video.video_reader import VideoReader

# 姿态提取算法版本：影响 pose.json 缓存失效（模型配置/缩放口径变化时递增）
POSE_ALGORITHM_VERSION = "2.0.0"

ProgressCallback = Optional[Callable[[float, str], None]]


@dataclass
class PoseExtractionConfig:
    max_video_side: int = 1280
    model_complexity: int = 1
    enable_segmentation: bool = False
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    smooth_landmarks: bool = True
    store_world_landmarks: bool = True


class PoseExtractor:
    """对视频执行单次 MediaPipe Pose 推理，产出统一 PoseResult。"""

    def __init__(self, config: PoseExtractionConfig | None = None, backend: MediaPipePoseBackend | None = None):
        self.config = config or PoseExtractionConfig()
        self.backend = backend or MediaPipePoseBackend(
            PoseBackendConfig(
                model_complexity=self.config.model_complexity,
                enable_segmentation=self.config.enable_segmentation,
                min_detection_confidence=self.config.min_detection_confidence,
                min_tracking_confidence=self.config.min_tracking_confidence,
                smooth_landmarks=self.config.smooth_landmarks,
            )
        )

    def extract(self, video_path: str | Path, analysis_id: str = "", progress_callback: ProgressCallback = None) -> PoseResult:
        """单次完整推理：打开视频一次 → 逐帧 MediaPipe → PoseResult。"""
        landmarks_frames: list[dict] = []
        visibility_frames: list[dict] = []
        normalized_frames: list[dict] = []
        world_frames: list[dict] = []
        timestamps: list[float] = []

        with VideoReader(video_path, max_side=self.config.max_video_side) as reader:
            fps = reader.fps
            total_frames = reader.frame_count
            width = reader.width
            height = reader.height

            for frame_index, frame in enumerate(reader.iter_frames()):
                pose_result = self.backend.process(frame)
                landmarks_frames.append(pose_result["landmarks"])
                visibility_frames.append(
                    {name: float(point.get("visibility", float("nan"))) for name, point in pose_result["landmarks"].items()}
                )
                normalized_frames.append(
                    {
                        name: {"x": float(point["x"]), "y": float(point["y"]), "z": float(point.get("z", 0.0))}
                        for name, point in pose_result["landmarks"].items()
                    }
                )
                if self.config.store_world_landmarks:
                    world_frames.append(pose_result["world_landmarks"])
                timestamps.append(frame_index / fps if fps > 0 else 0.0)

                if progress_callback and total_frames > 0:
                    progress_callback(min((frame_index + 1) / total_frames, 1.0), f"姿态提取 {frame_index + 1}/{total_frames}")

        return PoseResult(
            analysis_id=analysis_id,
            fps=fps,
            frame_count=len(landmarks_frames),
            width=width,
            height=height,
            duration=len(landmarks_frames) / fps if fps > 0 else 0.0,
            algorithm_version=POSE_ALGORITHM_VERSION,
            landmarks=landmarks_frames,
            visibility=visibility_frames,
            normalized_landmarks=normalized_frames,
            world_landmarks=world_frames,
            timestamps=timestamps,
        )

    def close(self) -> None:
        self.backend.close()
