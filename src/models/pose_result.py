from __future__ import annotations

"""统一姿态推理结果模型。

MediaPipe Pose 对一个视频只执行一次，产出一个 :class:`PoseResult`，
后续所有模块（骨架分析、肌肉分析、关节角度、速度、加速度、发力链、
未来 AI Coach）全部复用这个结果或其磁盘形态 ``pose.json``。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LandmarkFrame = dict[str, dict[str, float]]


@dataclass
class PoseResult:
    """一次视频姿态推理的完整结果（索引对齐的列表结构）。"""

    analysis_id: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration: float
    algorithm_version: str
    # 每帧 [frame] -> {landmark_name: {x, y, z, visibility, pixel_x, pixel_y}}
    landmarks: list[LandmarkFrame] = field(default_factory=list)
    # 每帧 [frame] -> {landmark_name: visibility}
    visibility: list[dict[str, float]] = field(default_factory=list)
    # 每帧 [frame] -> {landmark_name: {x, y, z}}（MediaPipe 归一化坐标）
    normalized_landmarks: list[LandmarkFrame] = field(default_factory=list)
    # 每帧 [frame] -> {landmark_name: {x, y, z}}（MediaPipe world 坐标，近似米制，未标定）
    world_landmarks: list[LandmarkFrame] = field(default_factory=list)
    # 每帧时间戳（秒）
    timestamps: list[float] = field(default_factory=list)

    # ------------------------------------------------------------------ 访问辅助
    def frame_landmarks(self, index: int) -> LandmarkFrame:
        if 0 <= index < len(self.landmarks):
            return self.landmarks[index]
        return {}

    def frame_visibility(self, index: int) -> dict[str, float]:
        if 0 <= index < len(self.visibility):
            return self.visibility[index]
        return {}

    def frame_normalized(self, index: int) -> LandmarkFrame:
        if 0 <= index < len(self.normalized_landmarks):
            return self.normalized_landmarks[index]
        return {}

    def frame_world(self, index: int) -> LandmarkFrame:
        if 0 <= index < len(self.world_landmarks):
            return self.world_landmarks[index]
        return {}

    # ------------------------------------------------------------------ 序列化
    def to_dict(self) -> dict[str, Any]:
        frames = []
        for index in range(len(self.landmarks)):
            frames.append(
                {
                    "index": index,
                    "timestamp_sec": self.timestamps[index] if index < len(self.timestamps) else 0.0,
                    "landmarks": self.landmarks[index],
                    "visibility": self.visibility[index] if index < len(self.visibility) else {},
                    "normalized_landmarks": self.normalized_landmarks[index] if index < len(self.normalized_landmarks) else {},
                    "world_landmarks": self.world_landmarks[index] if index < len(self.world_landmarks) else {},
                }
            )
        return {
            "analysis_id": self.analysis_id,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "algorithm_version": self.algorithm_version,
            "frames": frames,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PoseResult":
        frames = data.get("frames", [])
        landmarks: list[LandmarkFrame] = []
        visibility: list[dict[str, float]] = []
        normalized: list[LandmarkFrame] = []
        world: list[LandmarkFrame] = []
        timestamps: list[float] = []
        for frame in frames:
            landmarks.append(frame.get("landmarks", {}))
            visibility.append(frame.get("visibility", {}))
            normalized.append(frame.get("normalized_landmarks", {}))
            world.append(frame.get("world_landmarks", {}))
            timestamps.append(float(frame.get("timestamp_sec", 0.0)))
        return cls(
            analysis_id=str(data.get("analysis_id", "")),
            fps=float(data.get("fps", 0.0)),
            frame_count=int(data.get("frame_count", len(landmarks))),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            duration=float(data.get("duration", 0.0)),
            algorithm_version=str(data.get("algorithm_version", "")),
            landmarks=landmarks,
            visibility=visibility,
            normalized_landmarks=normalized,
            world_landmarks=world,
            timestamps=timestamps,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> "PoseResult":
        with path.open("r", encoding="utf-8") as file:
            return cls.from_dict(json.load(file))
