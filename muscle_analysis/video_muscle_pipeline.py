from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
import shutil
from typing import Callable

import cv2
import numpy as np
import pandas as pd
import yaml

from muscle_analysis.muscle_estimator import MUSCLE_LABELS, MuscleEngagementEstimator
from muscle_analysis.muscle_renderer import MuscleRenderer
from src.analysis.kinematics import midpoint
from src.analysis.metrics import compute_frame_metrics, initialize_peak_state, update_peak_metrics
from src.export.exporters import write_metrics_csv, write_summary_json
from src.pose.mediapipe_backend import MediaPipePoseBackend, PoseBackendConfig
from src.utils.paths import PROJECT_ROOT
from src.utils.video_utils import make_video_writer, resize_with_aspect_ratio, transcode_to_browser_mp4


ProgressCallback = Callable[[float, str], None] | None
MUSCLE_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "muscle_visualized"
CONFIG_PATH = PROJECT_ROOT / "configs" / "default.yaml"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _safe_diff(current: float, previous: float, fps: float) -> float:
    if fps <= 0 or not np.isfinite([current, previous]).all():
        return float("nan")
    return float((current - previous) * fps)


def _line_angle(point_a: dict[str, float] | None, point_b: dict[str, float] | None) -> float:
    if point_a is None or point_b is None:
        return float("nan")
    x1, y1 = point_a.get("pixel_x"), point_a.get("pixel_y")
    x2, y2 = point_b.get("pixel_x"), point_b.get("pixel_y")
    if x1 is None or y1 is None or x2 is None or y2 is None or not np.isfinite([x1, y1, x2, y2]).all():
        return float("nan")
    return float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))


def _angle_wrap_diff(current: float, previous: float) -> float:
    if not np.isfinite([current, previous]).all():
        return float("nan")
    delta = current - previous
    while delta > 180.0:
        delta -= 360.0
    while delta < -180.0:
        delta += 360.0
    return float(delta)


def _add_additional_metrics(metrics: dict[str, float], previous_metrics: dict[str, float] | None, fps: float) -> dict[str, float]:
    previous_metrics = previous_metrics or {}
    metrics["left_ankle_angular_velocity"] = _safe_diff(
        float(metrics.get("left_ankle_angle", float("nan"))),
        float(previous_metrics.get("left_ankle_angle", float("nan"))),
        fps,
    )
    metrics["right_ankle_angular_velocity"] = _safe_diff(
        float(metrics.get("right_ankle_angle", float("nan"))),
        float(previous_metrics.get("right_ankle_angle", float("nan"))),
        fps,
    )
    metrics["left_shoulder_angular_velocity"] = _safe_diff(
        float(metrics.get("left_shoulder_angle", float("nan"))),
        float(previous_metrics.get("left_shoulder_angle", float("nan"))),
        fps,
    )
    metrics["right_shoulder_angular_velocity"] = _safe_diff(
        float(metrics.get("right_shoulder_angle", float("nan"))),
        float(previous_metrics.get("right_shoulder_angle", float("nan"))),
        fps,
    )
    metrics["left_hip_angular_acceleration"] = _safe_diff(
        float(metrics.get("hip_angular_velocity", float("nan"))),
        float(previous_metrics.get("hip_angular_velocity", float("nan"))),
        fps,
    )
    return metrics


def _build_pose_backend(config: dict) -> MediaPipePoseBackend:
    pose_config = config.get("pose", {})
    return MediaPipePoseBackend(
        PoseBackendConfig(
            model_complexity=pose_config.get("model_complexity", 1),
            enable_segmentation=False,
            min_detection_confidence=pose_config.get("min_detection_confidence", 0.5),
            min_tracking_confidence=pose_config.get("min_tracking_confidence", 0.5),
            smooth_landmarks=pose_config.get("smooth_landmarks", True),
        )
    )


def _ensure_output_dir() -> Path:
    MUSCLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return MUSCLE_OUTPUT_DIR


def _default_output_paths(input_video_path: Path) -> tuple[Path, Path, Path]:
    output_dir = _ensure_output_dir()
    stem = input_video_path.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_video_path = output_dir / f"{stem}_{timestamp}_muscle_visualized.mp4"
    raw_video_path = output_dir / f"{stem}_{timestamp}_muscle_visualized_raw.mp4"
    csv_path = output_dir / f"{stem}_{timestamp}_muscle_metrics.csv"
    return output_video_path, raw_video_path, csv_path


def _build_summary(
    metrics_df: pd.DataFrame,
    estimator: MuscleEngagementEstimator,
    output_video_path: Path,
    csv_path: Path,
    fps: float,
) -> dict[str, object]:
    muscle_columns = list(MUSCLE_LABELS.keys())
    muscle_summary_rows = []
    for name in muscle_columns:
        series = pd.to_numeric(metrics_df.get(name, pd.Series(dtype=float)), errors="coerce").dropna()
        muscle_summary_rows.append(
            {
                "muscle": name,
                "label": MUSCLE_LABELS[name],
                "mean": float(series.mean()) if not series.empty else float("nan"),
                "max": float(series.max()) if not series.empty else float("nan"),
            }
        )

    hint_counter = Counter(str(value) for value in metrics_df.get("power_chain_hint", []) if str(value).strip())
    peak_moments = estimator.detect_peak_moments()
    return {
        "output_video": str(output_video_path),
        "csv_path": str(csv_path),
        "total_frames": int(len(metrics_df)),
        "fps": float(fps),
        "dominant_power_chain_hint": hint_counter.most_common(1)[0][0] if hint_counter else "暂无数据",
        "power_chain_hint_counts": dict(hint_counter),
        "muscle_statistics": muscle_summary_rows,
        "peak_moments": peak_moments,
    }


def process_muscle_video(
    input_video_path: str,
    output_video_path: str | None = None,
    reuse_existing_pose: bool = False,
    progress_callback: ProgressCallback = None,
) -> dict:
    del reuse_existing_pose
    backend: MediaPipePoseBackend | None = None
    capture: cv2.VideoCapture | None = None
    writer: cv2.VideoWriter | None = None
    raw_output_path: Path | None = None
    output_path: Path | None = None
    csv_path: Path | None = None

    try:
        config = _load_config()
        input_path = Path(input_video_path)
        if not input_path.exists():
            return {"error": f"输入视频不存在: {input_path}"}

        capture = cv2.VideoCapture(str(input_path))
        if not capture.isOpened():
            return {"error": f"无法打开视频: {input_path}"}

        fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        success, first_frame = capture.read()
        if not success:
            return {"error": "视频中没有可读取帧。"}

        max_video_side = int(config.get("app", {}).get("max_video_side", 1280))
        first_frame = resize_with_aspect_ratio(first_frame, max_video_side)
        frame_height, frame_width = first_frame.shape[:2]

        if output_video_path is None:
            output_path, raw_output_path, csv_path = _default_output_paths(input_path)
        else:
            output_path = Path(output_video_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            raw_output_path = output_path.with_name(f"{output_path.stem}_raw{output_path.suffix}")
            csv_path = output_path.with_name(f"{output_path.stem}_metrics.csv")

        writer = make_video_writer(raw_output_path, fps, (frame_width, frame_height))
        backend = _build_pose_backend(config)
        estimator = MuscleEngagementEstimator()
        renderer = MuscleRenderer()

        metrics_rows: list[dict[str, object]] = []
        previous_landmarks: dict[str, dict[str, float]] | None = None
        previous_metrics: dict[str, float] | None = None
        previous_smoothed_speeds: dict[str, float] | None = None
        peak_state = initialize_peak_state()
        frame_index = 0
        current_frame = first_frame

        while True:
            frame = resize_with_aspect_ratio(current_frame, max_video_side)
            pose_result = backend.process(frame)
            landmarks = pose_result["landmarks"]
            metrics, previous_smoothed_speeds = compute_frame_metrics(
                landmarks=landmarks,
                previous_landmarks=previous_landmarks,
                fps=fps,
                previous_metrics=previous_metrics,
                previous_smoothed_speeds=previous_smoothed_speeds,
                speed_smoothing_alpha=float(config.get("analysis", {}).get("speed_smoothing_alpha", 0.35)),
            )

            metrics["torso_rotation_angle"] = _line_angle(landmarks.get("left_shoulder"), landmarks.get("right_shoulder"))
            previous_rotation_angle = float(previous_metrics.get("torso_rotation_angle", float("nan"))) if previous_metrics else float("nan")
            rotation_delta = _angle_wrap_diff(float(metrics["torso_rotation_angle"]), previous_rotation_angle)
            metrics["torso_rotation_velocity"] = float(rotation_delta * fps) if np.isfinite(rotation_delta) and fps > 0 else float("nan")
            metrics = _add_additional_metrics(metrics, previous_metrics, fps)
            metrics, peak_state = update_peak_metrics(metrics, peak_state, frame_index / fps if fps > 0 else 0.0, frame_index)

            engagement = estimator.estimate(landmarks, metrics, frame_index=frame_index, timestamp_sec=frame_index / fps if fps > 0 else 0.0)
            top_muscles = estimator.get_top_muscles(engagement, top_k=3)
            power_chain_hint = estimator.analyze_power_chain(metrics)
            visualized_frame = renderer.render_frame(
                original_frame=frame,
                landmarks=landmarks,
                connections=pose_result["connections"],
                engagement=engagement,
                power_chain_text=power_chain_hint,
                top_muscles=top_muscles,
            )
            writer.write(visualized_frame)

            row = {"frame": frame_index, "time_sec": frame_index / fps if fps > 0 else 0.0}
            row.update(metrics)
            row.update(engagement)
            row["top1_muscle"] = top_muscles[0][0] if len(top_muscles) > 0 else ""
            row["top2_muscle"] = top_muscles[1][0] if len(top_muscles) > 1 else ""
            row["top3_muscle"] = top_muscles[2][0] if len(top_muscles) > 2 else ""
            row["power_chain_hint"] = power_chain_hint
            metrics_rows.append(row)

            if progress_callback and total_frames > 0:
                progress_callback(min((frame_index + 1) / total_frames, 1.0), f"肌肉可视化处理中 {frame_index + 1}/{total_frames}")

            previous_landmarks = landmarks
            previous_metrics = metrics.copy()
            frame_index += 1
            success, next_frame = capture.read()
            if not success:
                break
            current_frame = next_frame

        metrics_df = pd.DataFrame(metrics_rows)
        write_metrics_csv(
            metrics_df[
                [
                    "frame",
                    "time_sec",
                    "quadriceps",
                    "hamstrings",
                    "glutes",
                    "calves",
                    "erector_spinae",
                    "obliques",
                    "deltoids",
                    "forearms",
                    "top1_muscle",
                    "top2_muscle",
                    "top3_muscle",
                    "power_chain_hint",
                ]
            ],
            csv_path,
        )

        summary = _build_summary(metrics_df, estimator, output_path, csv_path, fps)
        write_summary_json(summary, output_path.with_name(f"{output_path.stem}_summary.json"))

        return {
            "output_video": str(output_path),
            "csv_path": str(csv_path),
            "summary": summary,
            "metrics_df": metrics_df,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        if capture is not None:
            capture.release()
        if writer is not None:
            writer.release()
        if backend is not None:
            backend.close()
        if raw_output_path is not None and output_path is not None and raw_output_path.exists():
            if transcode_to_browser_mp4(raw_output_path, output_path):
                raw_output_path.unlink(missing_ok=True)
            else:
                output_path.unlink(missing_ok=True)
                shutil.move(str(raw_output_path), str(output_path))
