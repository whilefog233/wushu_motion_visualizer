from __future__ import annotations

"""肌肉参与度可视化视频导出（按需）。

复用 pose.json（骨架）与 muscle_metrics.csv（逐帧参与度），
不重新运行 MediaPipe，也不重新做肌肉估计。
"""

import shutil
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

from muscle_analysis.muscle_renderer import MuscleRenderer
from src.models.pose_result import PoseResult
from src.storage.analysis_store import AnalysisStore
from src.utils.video_utils import make_video_writer, transcode_to_browser_mp4
from src.video.video_reader import VideoReader

ProgressCallback = Optional[Callable[[float, str], None]]


def _pose_connections() -> list[tuple[object, object]]:
    import mediapipe as mp

    return list(mp.solutions.pose.POSE_CONNECTIONS)


def export_muscle_video(analysis_id: str, progress_callback: ProgressCallback = None, ffmpeg_transcode: bool = True) -> Path:
    """生成肌肉参与度可视化视频到 exports/，返回导出文件路径。"""
    store = AnalysisStore()
    paths = store.paths(analysis_id)
    if not paths.pose_json.exists() or not paths.muscle_csv.exists():
        raise FileNotFoundError(f"analysis {analysis_id} 缺少 pose.json / muscle_metrics.csv，无法导出肌肉视频")

    pose = PoseResult.load(paths.pose_json)
    muscle_df = pd.read_csv(paths.muscle_csv)
    muscle_df = muscle_df.set_index("frame")

    source_path = paths.source_video
    if not source_path.exists() and store.load_metadata(analysis_id).get("source_abs_path"):
        source_path = Path(store.load_metadata(analysis_id)["source_abs_path"])

    paths.exports_dir.mkdir(parents=True, exist_ok=True)
    output_path = paths.export_file("muscle_video.mp4")
    raw_output_path = paths.export_file("muscle_video_raw.mp4")
    connections = _pose_connections()
    renderer = MuscleRenderer()

    muscle_columns = ["quadriceps", "hamstrings", "glutes", "calves", "erector_spinae", "obliques", "deltoids", "forearms"]

    started = time.perf_counter()
    # max_side 语义是「最长边上限」：分析时 PoseExtractor 按最长边缩放，
    # 导出必须用同一基准（max(宽,高)），竖屏视频用 pose.width 会导致帧被二次缩放错位。
    with VideoReader(source_path, max_side=max(pose.width, pose.height)) as reader:
        if reader.width != pose.width or reader.height != pose.height:
            raise RuntimeError(f"源视频尺寸与 pose.json 不一致（{reader.width}x{reader.height} vs {pose.width}x{pose.height}）")
        fps = reader.fps if reader.fps > 0 else pose.fps
        writer = make_video_writer(raw_output_path, fps, (pose.width, pose.height))
        if not writer.isOpened():
            raise RuntimeError(f"无法创建视频写入器：{raw_output_path}")
        written = 0
        try:
            for frame_index, frame in enumerate(reader.iter_frames()):
                if frame_index >= pose.frame_count:
                    break
                landmarks = pose.frame_landmarks(frame_index)
                engagement = {}
                if frame_index in muscle_df.index:
                    row = muscle_df.loc[frame_index]
                    engagement = {column: float(row.get(column, 0.0)) for column in muscle_columns}
                top_muscles = _top_muscles(muscle_df, frame_index)
                hint = str(muscle_df.loc[frame_index].get("power_chain_hint", "")) if frame_index in muscle_df.index else ""
                visualized = renderer.render_frame(
                    original_frame=frame,
                    landmarks=landmarks,
                    connections=connections,
                    engagement=engagement,
                    power_chain_text=hint,
                    top_muscles=top_muscles,
                )
                if visualized.shape[0] != pose.height or visualized.shape[1] != pose.width:
                    raise RuntimeError(
                        f"渲染帧尺寸与写入器不一致（{visualized.shape} vs 期望 {(pose.height, pose.width)}），"
                        "通常由源视频尺寸与 pose.json 不匹配导致"
                    )
                writer.write(visualized)
                written += 1
                if progress_callback and pose.frame_count > 0:
                    progress_callback(min((frame_index + 1) / pose.frame_count, 1.0), f"导出肌肉视频 {frame_index + 1}/{pose.frame_count}")
        finally:
            writer.release()
    if written == 0:
        raw_output_path.unlink(missing_ok=True)
        raise RuntimeError("导出失败：没有写入任何帧")

    if ffmpeg_transcode and transcode_to_browser_mp4(raw_output_path, output_path):
        raw_output_path.unlink(missing_ok=True)
    else:
        shutil.move(str(raw_output_path), str(output_path))

    elapsed = round(time.perf_counter() - started, 4)
    _append_export_performance(paths, elapsed)
    return output_path


def _top_muscles(muscle_df: pd.DataFrame, frame_index: int) -> list[tuple[str, float]]:
    if frame_index not in muscle_df.index:
        return []
    row = muscle_df.loc[frame_index]
    columns = ["quadriceps", "hamstrings", "glutes", "calves", "erector_spinae", "obliques", "deltoids", "forearms"]
    items = []
    for column in columns:
        try:
            value = float(row.get(column, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        if np.isfinite(value):
            items.append((column, value))
    items.sort(key=lambda item: item[1], reverse=True)
    return items[:3]


def _append_export_performance(paths, elapsed: float) -> None:
    import json

    performance_path = paths.performance_json
    if not performance_path.exists():
        return
    with performance_path.open("r", encoding="utf-8") as file:
        performance = json.load(file)
    performance["export_muscle_video_time_sec"] = elapsed
    with performance_path.open("w", encoding="utf-8") as file:
        json.dump(performance, file, ensure_ascii=False, indent=2)
