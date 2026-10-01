from __future__ import annotations

"""骨架视频导出（按需，独立于 analyze_video）。

分析阶段默认只生成数据（pose.json / metrics.csv / analysis.json ...），
用户主动点击“导出骨架视频”时才生成 MP4，保存到 analysis 目录的 exports/。
"""

import shutil
import time
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from src.models.pose_result import PoseResult
from src.storage.analysis_store import AnalysisPaths, AnalysisStore
from src.utils.video_utils import make_video_writer, transcode_to_browser_mp4
from src.video.video_reader import VideoReader
from src.visualization.draw_dashboard import build_overlay_lines
from src.visualization.draw_pose import compose_side_by_side, create_skeleton_canvas, draw_pose_landmarks, draw_overlay_text

ProgressCallback = Optional[Callable[[float, str], None]]


def _pose_connections() -> list[tuple[object, object]]:
    import mediapipe as mp

    return list(mp.solutions.pose.POSE_CONNECTIONS)


def export_skeleton_video(
    analysis_id: str,
    show_overlay: bool = True,
    show_trajectories: bool = False,
    progress_callback: ProgressCallback = None,
    ffmpeg_transcode: bool = True,
) -> Path:
    """按 analysis_id 生成 side-by-side 骨架视频，返回导出文件路径。"""
    store = AnalysisStore()
    paths = store.paths(analysis_id)
    if not paths.pose_json.exists():
        raise FileNotFoundError(f"analysis {analysis_id} 缺少 pose.json，无法导出骨架视频")

    pose = PoseResult.load(paths.pose_json)
    source_path = paths.source_video
    if not source_path.exists() and store.load_metadata(analysis_id).get("source_abs_path"):
        source_path = Path(store.load_metadata(analysis_id)["source_abs_path"])

    metrics_df = None
    if show_overlay and paths.metrics_csv.exists():
        metrics_df = pd.read_csv(paths.metrics_csv)

    paths.exports_dir.mkdir(parents=True, exist_ok=True)
    output_path = paths.export_file("skeleton_video.mp4")
    raw_output_path = paths.export_file("skeleton_video_raw.mp4")
    connections = _pose_connections()

    started = time.perf_counter()
    # max_side 语义是「最长边上限」：分析时 PoseExtractor 按最长边缩放，
    # 导出必须用同一基准（max(宽,高)），竖屏视频用 pose.width 会导致帧被二次缩放错位。
    with VideoReader(source_path, max_side=max(pose.width, pose.height)) as reader:
        if reader.width != pose.width or reader.height != pose.height:
            raise RuntimeError(f"源视频尺寸与 pose.json 不一致（{reader.width}x{reader.height} vs {pose.width}x{pose.height}）")
        fps = reader.fps if reader.fps > 0 else pose.fps
        writer = make_video_writer(raw_output_path, fps, (pose.width * 2, pose.height))
        if not writer.isOpened():
            raise RuntimeError(f"无法创建视频写入器：{raw_output_path}")
        written = 0
        try:
            for frame_index, frame in enumerate(reader.iter_frames()):
                if frame_index >= pose.frame_count:
                    break
                landmarks = pose.frame_landmarks(frame_index)
                skeleton = create_skeleton_canvas(frame.shape, (18, 18, 18))
                skeleton = draw_pose_landmarks(skeleton, landmarks, connections)
                if show_overlay and metrics_df is not None:
                    row = metrics_df[metrics_df["frame_index"] == frame_index]
                    metrics = row.iloc[0].to_dict() if not row.empty else {}
                    skeleton = draw_overlay_text(skeleton, build_overlay_lines(metrics, frame_index, fps))
                side_by_side = compose_side_by_side(frame, skeleton)
                if side_by_side.shape[0] != pose.height or side_by_side.shape[1] != pose.width * 2:
                    raise RuntimeError(
                        f"渲染帧尺寸与写入器不一致（{side_by_side.shape} vs 期望 {(pose.height, pose.width * 2)}），"
                        "通常由源视频尺寸与 pose.json 不匹配导致"
                    )
                writer.write(side_by_side)
                written += 1
                if progress_callback and pose.frame_count > 0:
                    progress_callback(min((frame_index + 1) / pose.frame_count, 1.0), f"导出骨架视频 {frame_index + 1}/{pose.frame_count}")
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
    store.update_metadata(analysis_id, **{})  # 触发 updated_at 刷新
    _append_export_performance(paths, elapsed)
    return output_path


def _append_export_performance(paths: AnalysisPaths, elapsed: float) -> None:
    """把导出耗时写入 performance.json 的 export_video_time_sec。"""
    performance_path = paths.performance_json
    if not performance_path.exists():
        return
    import json

    with performance_path.open("r", encoding="utf-8") as file:
        performance = json.load(file)
    performance["export_video_time_sec"] = elapsed
    with performance_path.open("w", encoding="utf-8") as file:
        json.dump(performance, file, ensure_ascii=False, indent=2)
