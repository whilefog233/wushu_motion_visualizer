from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import mediapipe as mp


POSE_LANDMARK_NAMES = [landmark.name.lower() for landmark in mp.solutions.pose.PoseLandmark]


@dataclass
class PoseBackendConfig:
    model_complexity: int = 1
    enable_segmentation: bool = False
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    smooth_landmarks: bool = True


class MediaPipePoseBackend:
    def __init__(self, config: PoseBackendConfig):
        self.config = config
        self.pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=config.model_complexity,
            smooth_landmarks=config.smooth_landmarks,
            enable_segmentation=config.enable_segmentation,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )
        self.pose_connections = mp.solutions.pose.POSE_CONNECTIONS
        self.raw_pose_enum = mp.solutions.pose.PoseLandmark

    def process(self, frame_bgr: Any) -> dict[str, Any]:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.pose.process(frame_rgb)
        height, width = frame_bgr.shape[:2]

        landmarks = {}
        if results.pose_landmarks:
            for index, landmark in enumerate(results.pose_landmarks.landmark):
                name = POSE_LANDMARK_NAMES[index]
                landmarks[name] = {
                    "x": float(landmark.x),
                    "y": float(landmark.y),
                    "z": float(landmark.z),
                    "visibility": float(getattr(landmark, "visibility", float("nan"))),
                    "pixel_x": float(landmark.x * width),
                    "pixel_y": float(landmark.y * height),
                }

        return {
            "landmarks": landmarks,
            "pose_landmarks": results.pose_landmarks,
            "pose_world_landmarks": results.pose_world_landmarks,
            "connections": self.pose_connections,
        }

    def close(self) -> None:
        self.pose.close()
