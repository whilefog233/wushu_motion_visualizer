from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Callable, Optional

import cv2
import pandas as pd

from src.analysis.kinematics import midpoint
from src.analysis.metrics import compute_frame_metrics, initialize_peak_state, update_peak_metrics
from src.export.exporters import (
    build_summary,
    write_keypoints_json,
    write_metrics_csv,
    write_summary_json,
    write_summary_markdown,
)
from src.pose.mediapipe_backend import MediaPipePoseBackend, PoseBackendConfig
from src.utils.paths import make_output_run_dir
from src.utils.video_utils import make_video_writer, resize_with_aspect_ratio, transcode_to_browser_mp4
from src.visualization.draw_dashboard import build_overlay_lines
from src.visualization.draw_pose import compose_side_by_side, create_skeleton_canvas, draw_overlay_text, draw_pose_landmarks, draw_trajectories


ProgressCallback = Optional[Callable[[float, str], None]]


@dataclass
class OfflineProcessConfig:
    max_video_side: int = 1280
    skeleton_background_bgr: tuple[int, int, int] = (18, 18, 18)
    trajectory_seconds: int = 5
    show_trajectory_overlay: bool = False
    speed_smoothing_alpha: float = 0.35
    export_side_by_side_video: bool = True
    side_by_side_filename: str = "side_by_side_video.mp4"
    keypoints_filename: str = "keypoints.json"
    metrics_filename: str = "metrics.csv"
    summary_filename: str = "summary.json"
    report_filename: str = "summary.md"


class OfflineVideoProcessor:
    def __init__(self, pose_backend: MediaPipePoseBackend, config: OfflineProcessConfig):
        self.pose_backend = pose_backend
        self.config = config

    def process(self, input_video_path: str | Path, progress_callback: ProgressCallback = None) -> dict[str, object]:
        input_video_path = Path(input_video_path)
        capture = cv2.VideoCapture(str(input_video_path))
        if not capture.isOpened():
            raise RuntimeError(f"无法打开视频: {input_video_path}")

        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)

        success, first_frame = capture.read()
        if not success:
            capture.release()
            raise RuntimeError("视频中没有可读取帧。")

        first_frame = resize_with_aspect_ratio(first_frame, self.config.max_video_side)
        frame_height, frame_width = first_frame.shape[:2]
        side_by_side_size = (frame_width * 2, frame_height)

        run_dir = make_output_run_dir("video_analysis")
        side_by_side_path = run_dir / self.config.side_by_side_filename
        raw_side_by_side_path = run_dir / f"{side_by_side_path.stem}_raw{side_by_side_path.suffix}"
        writer = make_video_writer(raw_side_by_side_path, fps, side_by_side_size) if self.config.export_side_by_side_video else None

        trajectory_maxlen = max(10, int(self.config.trajectory_seconds * fps))
        trajectory_buffers = {
            "left_wrist": deque(maxlen=trajectory_maxlen),
            "right_wrist": deque(maxlen=trajectory_maxlen),
            "left_ankle": deque(maxlen=trajectory_maxlen),
            "right_ankle": deque(maxlen=trajectory_maxlen),
            "hip_center": deque(maxlen=trajectory_maxlen),
        }

        metrics_rows: list[dict[str, float]] = []
        keypoint_rows: list[dict[str, object]] = []
        previous_landmarks = None
        previous_metrics = None
        previous_smoothed_speeds = None
        peak_state = initialize_peak_state()

        frame_index = 0
        current_frame = first_frame
        while True:
            frame = resize_with_aspect_ratio(current_frame, self.config.max_video_side)
            pose_result = self.pose_backend.process(frame)
            landmarks = pose_result["landmarks"]
            metrics, previous_smoothed_speeds = compute_frame_metrics(
                landmarks=landmarks,
                previous_landmarks=previous_landmarks,
                fps=fps,
                previous_metrics=previous_metrics,
                previous_smoothed_speeds=previous_smoothed_speeds,
                speed_smoothing_alpha=self.config.speed_smoothing_alpha,
            )
            metrics, peak_state = update_peak_metrics(metrics, peak_state, frame_index / fps if fps > 0 else 0.0, frame_index)

            metrics_row = {"frame_index": frame_index, "timestamp_sec": frame_index / fps if fps > 0 else 0.0}
            metrics_row.update(metrics)
            metrics_rows.append(metrics_row)

            keypoint_rows.append(
                {
                    "frame_index": frame_index,
                    "timestamp_sec": metrics_row["timestamp_sec"],
                    "landmarks": landmarks,
                }
            )

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
                trajectory_buffers[name].append((x, y))

            skeleton = create_skeleton_canvas(frame.shape, self.config.skeleton_background_bgr)
            skeleton = draw_pose_landmarks(skeleton, landmarks, pose_result["connections"])
            if self.config.show_trajectory_overlay:
                skeleton = draw_trajectories(skeleton, trajectory_buffers)
            skeleton = draw_overlay_text(skeleton, build_overlay_lines(metrics, frame_index, fps))
            side_by_side = compose_side_by_side(frame, skeleton)
            if writer is not None:
                writer.write(side_by_side)

            if progress_callback and total_frames > 0:
                progress_callback((frame_index + 1) / total_frames, f"处理中: {frame_index + 1}/{total_frames}")

            previous_landmarks = landmarks
            previous_metrics = metrics
            frame_index += 1
            success, next_frame = capture.read()
            if not success:
                break
            current_frame = next_frame

        capture.release()
        if writer is not None:
            writer.release()
            if transcode_to_browser_mp4(raw_side_by_side_path, side_by_side_path):
                raw_side_by_side_path.unlink(missing_ok=True)
            else:
                shutil.move(str(raw_side_by_side_path), str(side_by_side_path))

        metrics_df = pd.DataFrame(metrics_rows)
        summary = build_summary(metrics_df, average_fps=fps)

        keypoints_path = run_dir / self.config.keypoints_filename
        metrics_path = run_dir / self.config.metrics_filename
        summary_path = run_dir / self.config.summary_filename
        report_path = run_dir / self.config.report_filename

        write_keypoints_json(keypoint_rows, keypoints_path)
        write_metrics_csv(metrics_df, metrics_path)
        write_summary_json(summary, summary_path)
        write_summary_markdown(summary, report_path)

        return {
            "run_dir": run_dir,
            "input_video_path": input_video_path,
            "side_by_side_video_path": side_by_side_path,
            "keypoints_json_path": keypoints_path,
            "metrics_csv_path": metrics_path,
            "summary_json_path": summary_path,
            "summary_md_path": report_path,
            "metrics_df": metrics_df,
            "summary": summary,
            "fps": fps,
            "total_frames": frame_index,
            "frame_width": frame_width,
            "frame_height": frame_height,
        }


def build_offline_components(app_config: dict) -> OfflineVideoProcessor:
    pose_backend = MediaPipePoseBackend(
        PoseBackendConfig(
            model_complexity=app_config["pose"]["model_complexity"],
            enable_segmentation=app_config["pose"]["enable_segmentation"],
            min_detection_confidence=app_config["pose"]["min_detection_confidence"],
            min_tracking_confidence=app_config["pose"]["min_tracking_confidence"],
            smooth_landmarks=app_config["pose"]["smooth_landmarks"],
        )
    )
    config = OfflineProcessConfig(
        max_video_side=app_config["app"]["max_video_side"],
        skeleton_background_bgr=tuple(app_config["visualization"]["skeleton_background_bgr"]),
        trajectory_seconds=app_config["analysis"]["trajectory_seconds"],
        show_trajectory_overlay=app_config["visualization"]["show_trajectory_overlay"],
        speed_smoothing_alpha=app_config["analysis"]["speed_smoothing_alpha"],
        export_side_by_side_video=app_config["export"]["save_side_by_side_video"],
        side_by_side_filename=app_config["export"]["side_by_side_filename"],
        keypoints_filename=app_config["export"]["keypoints_filename"],
        metrics_filename=app_config["export"]["metrics_filename"],
        summary_filename=app_config["export"]["summary_filename"],
        report_filename=app_config["export"]["report_filename"],
    )
    return OfflineVideoProcessor(pose_backend=pose_backend, config=config)
