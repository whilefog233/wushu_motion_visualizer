from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import perf_counter

import cv2

from src.analysis.kinematics import midpoint
from src.analysis.metrics import compute_frame_metrics, initialize_peak_state, update_peak_metrics
from src.pose.mediapipe_backend import MediaPipePoseBackend, PoseBackendConfig
from src.utils.video_utils import resize_with_aspect_ratio
from src.visualization.draw_dashboard import build_overlay_lines
from src.visualization.draw_pose import compose_side_by_side, create_skeleton_canvas, draw_overlay_text, draw_pose_landmarks, draw_trajectories


@dataclass
class RealtimeProcessorConfig:
    max_video_side: int = 1280
    skeleton_background_bgr: tuple[int, int, int] = (18, 18, 18)
    trajectory_seconds: int = 5
    show_trajectory_overlay: bool = False
    speed_smoothing_alpha: float = 0.35


class RealtimePoseProcessor:
    def __init__(self, pose_backend: MediaPipePoseBackend, config: RealtimeProcessorConfig):
        self.pose_backend = pose_backend
        self.config = config
        self.previous_landmarks = None
        self.previous_metrics = None
        self.previous_smoothed_speeds = None
        self.previous_time = None
        self.start_time = None
        self.frame_index = 0
        self.current_fps = 0.0
        self.peak_state = initialize_peak_state()
        trajectory_maxlen = max(30, int(config.trajectory_seconds * 30))
        self.trajectory_buffers = {
            "left_wrist": deque(maxlen=trajectory_maxlen),
            "right_wrist": deque(maxlen=trajectory_maxlen),
            "left_ankle": deque(maxlen=trajectory_maxlen),
            "right_ankle": deque(maxlen=trajectory_maxlen),
            "hip_center": deque(maxlen=trajectory_maxlen),
        }

    def process_frame(self, frame, show_trajectories: bool | None = None):
        frame = resize_with_aspect_ratio(frame, self.config.max_video_side)
        now = perf_counter()
        if self.start_time is None:
            self.start_time = now
        if self.previous_time is not None:
            delta = max(1e-6, now - self.previous_time)
            instant_fps = 1.0 / delta
            self.current_fps = 0.2 * instant_fps + 0.8 * self.current_fps if self.current_fps > 0 else instant_fps
        else:
            self.current_fps = 0.0
        self.previous_time = now

        pose_result = self.pose_backend.process(frame)
        landmarks = pose_result["landmarks"]
        metrics, self.previous_smoothed_speeds = compute_frame_metrics(
            landmarks=landmarks,
            previous_landmarks=self.previous_landmarks,
            fps=self.current_fps if self.current_fps > 0 else 30.0,
            previous_metrics=self.previous_metrics,
            previous_smoothed_speeds=self.previous_smoothed_speeds,
            speed_smoothing_alpha=self.config.speed_smoothing_alpha,
        )
        timestamp_sec = max(0.0, now - self.start_time)
        metrics, self.peak_state = update_peak_metrics(metrics, self.peak_state, timestamp_sec, self.frame_index)

        hip_center = midpoint(landmarks.get("left_hip"), landmarks.get("right_hip"))
        tracked_points = {
            "left_wrist": landmarks.get("left_wrist"),
            "right_wrist": landmarks.get("right_wrist"),
            "left_ankle": landmarks.get("left_ankle"),
            "right_ankle": landmarks.get("right_ankle"),
            "hip_center": hip_center,
        }
        for name, point in tracked_points.items():
            if point is None:
                continue
            x = point.get("pixel_x")
            y = point.get("pixel_y")
            if x is None or y is None:
                continue
            self.trajectory_buffers[name].append((x, y))

        skeleton = create_skeleton_canvas(frame.shape, self.config.skeleton_background_bgr)
        skeleton = draw_pose_landmarks(skeleton, landmarks, pose_result["connections"])
        should_draw_trajectories = self.config.show_trajectory_overlay if show_trajectories is None else show_trajectories
        if should_draw_trajectories:
            skeleton = draw_trajectories(skeleton, self.trajectory_buffers)
        skeleton = draw_overlay_text(skeleton, build_overlay_lines(metrics, self.frame_index, self.current_fps))
        side_by_side = compose_side_by_side(frame, skeleton)

        metrics_row = {"frame_index": self.frame_index}
        metrics_row.update(metrics)
        self.previous_landmarks = landmarks
        self.previous_metrics = metrics
        self.frame_index += 1

        return {
            "original_frame": frame,
            "skeleton_frame": skeleton,
            "side_by_side_frame": side_by_side,
            "metrics": metrics_row,
            "fps": self.current_fps,
        }

    def clear_trajectories(self) -> None:
        for buffer in self.trajectory_buffers.values():
            buffer.clear()


def build_realtime_components(app_config: dict) -> RealtimePoseProcessor:
    pose_backend = MediaPipePoseBackend(
        PoseBackendConfig(
            model_complexity=app_config["pose"]["model_complexity"],
            enable_segmentation=app_config["pose"]["enable_segmentation"],
            min_detection_confidence=app_config["pose"]["min_detection_confidence"],
            min_tracking_confidence=app_config["pose"]["min_tracking_confidence"],
            smooth_landmarks=app_config["pose"]["smooth_landmarks"],
        )
    )
    config = RealtimeProcessorConfig(
        max_video_side=app_config["app"]["max_video_side"],
        skeleton_background_bgr=tuple(app_config["visualization"]["skeleton_background_bgr"]),
        trajectory_seconds=app_config["analysis"]["trajectory_seconds"],
        show_trajectory_overlay=app_config["visualization"]["show_trajectory_overlay"],
        speed_smoothing_alpha=app_config["analysis"]["speed_smoothing_alpha"],
    )
    return RealtimePoseProcessor(pose_backend=pose_backend, config=config)
