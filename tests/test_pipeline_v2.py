"""V2 重构集成测试。

覆盖：完整分析、MediaPipe 只跑一次、姿态/指标/肌肉缓存复用、
默认不生成 MP4、独立导出、worker 独立运行、错误恢复、旧指标兼容、
实时模块不被破坏。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.pipeline import analyze_video, load_analysis_result, load_pipeline_config  # noqa: E402
from src.storage.analysis_store import AnalysisStore  # noqa: E402

SYNTHETIC_VIDEO = PROJECT_ROOT / "data" / "input" / "synthetic_test.mp4"
CONFIG = load_pipeline_config()

pytestmark = pytest.mark.skipif(not SYNTHETIC_VIDEO.exists(), reason="缺少测试视频 synthetic_test.mp4")


@pytest.fixture(scope="module")
def store():
    return AnalysisStore()


def _cleanup_analysis(analysis_id: str) -> None:
    store = AnalysisStore()
    target = store.root / analysis_id
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)


# ------------------------------------------------------------------ 1. 完整分析
def test_new_video_completes_full_analysis(store):
    result = analyze_video(SYNTHETIC_VIDEO, config=CONFIG)
    assert result.status.value == "COMPLETED"
    assert result.metrics_df is not None and not result.metrics_df.empty
    assert result.pose is not None
    assert result.pose.frame_count == len(result.metrics_df)
    assert result.analysis_dir.name == result.analysis_id

    # 所有标准产物都在 analysis_id 目录
    expected_files = [
        "metadata.json",
        "pose.json",
        "metrics.csv",
        "analysis.json",
        "muscle.json",
        "muscle_metrics.csv",
        "power_chain.json",
        "coach_input.json",
        "performance.json",
        "summary.md",
        "source.mp4",
    ]
    for filename in expected_files:
        assert (result.analysis_dir / filename).exists(), f"缺少 {filename}"


# ------------------------------------------------------------------ 2. MediaPipe 只跑一次
def test_same_video_mediapipe_runs_once(store):
    """同一视频（全新副本）分析两次，MediaPipe 只执行一次。"""
    import src.pose.extractor as extractor_module

    # 用一份全新副本，避免被本模块更早的测试留下的同源缓存命中
    fresh_video = PROJECT_ROOT / "data" / "input" / "synthetic_test_copy_for_once.mp4"
    shutil.copy2(SYNTHETIC_VIDEO, fresh_video)

    real_extract = extractor_module.PoseExtractor.extract
    counter = {"n": 0}

    def counting_extract(self, video_path, analysis_id="", progress_callback=None):
        counter["n"] += 1
        return real_extract(self, video_path, analysis_id, progress_callback)

    extractor_module.PoseExtractor.extract = counting_extract
    first = None
    second = None
    try:
        first = analyze_video(fresh_video, config=CONFIG)
        second = analyze_video(fresh_video, config=CONFIG)
        assert counter["n"] == 1, f"MediaPipe 执行了 {counter['n']} 次，应为 1 次"
        assert first.reused_pose is False
        assert second.reused_pose is True
        assert "pose_reuse_source" in second.performance.get("reuse_sources", {})
    finally:
        extractor_module.PoseExtractor.extract = real_extract
        fresh_video.unlink(missing_ok=True)
        if first:
            _cleanup_analysis(first.analysis_id)
        if second:
            _cleanup_analysis(second.analysis_id)


# ------------------------------------------------------------------ 3. 同一 analysis_id 全缓存复用
def test_same_analysis_id_reuses_all_cache(store):
    first = analyze_video(SYNTHETIC_VIDEO, config=CONFIG)
    second = analyze_video(SYNTHETIC_VIDEO, config=CONFIG, analysis_id=first.analysis_id)
    assert second.reused_pose is True
    assert second.performance.get("reuse_sources", {}).get("metrics_reuse_source") == "cache"
    assert second.performance.get("reuse_sources", {}).get("muscle_reuse_source") == "cache"
    assert second.performance.get("reuse_sources", {}).get("power_chain_reuse_source") == "cache"
    assert second.metrics_df is not None
    assert len(second.metrics_df) == len(first.metrics_df)
    _cleanup_analysis(first.analysis_id)


# ------------------------------------------------------------------ 4. 第二次打开直接读取
def test_second_open_reads_cached_result(store):
    first = analyze_video(SYNTHETIC_VIDEO, config=CONFIG)
    loaded = load_analysis_result(first.analysis_id)
    assert loaded.status.value == "COMPLETED"
    assert loaded.metrics_df is not None and len(loaded.metrics_df) == len(first.metrics_df)
    assert loaded.muscle is not None
    assert loaded.power_chain is not None
    assert loaded.performance is not None
    _cleanup_analysis(first.analysis_id)


# ------------------------------------------------------------------ 5. 默认不生成完整 MP4
def test_analyze_default_no_mp4(store):
    result = analyze_video(SYNTHETIC_VIDEO, config=CONFIG)
    exports = result.analysis_dir / "exports"
    videos = list(exports.glob("*.mp4"))
    assert not videos, f"默认分析不应生成 MP4: {videos}"
    assert not (result.analysis_dir / "side_by_side_video.mp4").exists()
    _cleanup_analysis(result.analysis_id)


# ------------------------------------------------------------------ 6. 独立导出视频
def test_export_skeleton_video_independently(store):
    from src.export.skeleton_video import export_skeleton_video

    result = analyze_video(SYNTHETIC_VIDEO, config=CONFIG)
    video_path = export_skeleton_video(result.analysis_id)
    assert video_path.exists()
    assert video_path.suffix == ".mp4"
    assert video_path.stat().st_size > 0
    _cleanup_analysis(result.analysis_id)


def test_export_muscle_video_independently(store):
    from src.export.muscle_video import export_muscle_video

    result = analyze_video(SYNTHETIC_VIDEO, config=CONFIG)
    video_path = export_muscle_video(result.analysis_id)
    assert video_path.exists()
    assert video_path.stat().st_size > 0
    _cleanup_analysis(result.analysis_id)


# ------------------------------------------------------------------ 7. 旧指标保留 + 新指标存在
def test_old_metrics_preserved_and_new_metrics_added(store):
    result = analyze_video(SYNTHETIC_VIDEO, config=CONFIG)
    columns = set(result.metrics_df.columns)
    old_columns = {"left_wrist_speed", "right_wrist_speed", "left_ankle_speed", "hip_center_speed", "left_knee_angle"}
    assert old_columns.issubset(columns), f"旧指标缺失: {old_columns - columns}"
    new_columns = {
        "left_wrist_speed_normalized",
        "right_wrist_speed_normalized",
        "left_wrist_speed_world",
        "right_wrist_speed_world",
        "hip_center_speed_normalized",
        "hip_center_speed_world",
        "wrist_speed_px",
        "wrist_speed_normalized",
        "wrist_speed_world",
        "hip_speed_px",
        "hip_speed_normalized",
        "hip_speed_world",
        "body_scale_px",
    }
    assert new_columns.issubset(columns), f"新指标缺失: {new_columns - columns}"
    _cleanup_analysis(result.analysis_id)


# ------------------------------------------------------------------ 8. coach 接口
def test_build_coach_context(store):
    from src.coach.coach_input import build_coach_context

    result = analyze_video(SYNTHETIC_VIDEO, config=CONFIG)
    coach = build_coach_context(result.analysis_id, write_json=True)
    assert coach["analysis_id"] == result.analysis_id
    assert "video_info" in coach and "joint_angles" in coach and "speeds" in coach
    assert "power_chain" in coach and "muscle_estimate" in coach and "timeline" in coach
    assert (result.analysis_dir / "coach_input.json").exists()
    _cleanup_analysis(result.analysis_id)


# ------------------------------------------------------------------ 9. 错误恢复
def test_error_recovery_reuses_pose(store, monkeypatch):
    import src.analysis.pipeline as pipeline_module

    real_augment = pipeline_module.augment_scale_metrics

    def broken_augment(metrics_df, pose):
        raise RuntimeError("simulated metrics failure")

    pipeline_module.augment_scale_metrics = broken_augment
    try:
        with pytest.raises(Exception):
            analyze_video(SYNTHETIC_VIDEO, config=CONFIG)
    finally:
        pipeline_module.augment_scale_metrics = real_augment

    # 找到失败的分析（pose 已完成，metrics 失败）
    store = AnalysisStore()
    failed_ids = []
    for item in store.list_analyses():
        metadata = store.load_metadata(item["analysis_id"])
        if metadata.get("status") == "FAILED" and metadata.get("error", "").startswith("RuntimeError: simulated metrics failure"):
            failed_ids.append(item["analysis_id"])

    assert failed_ids, "未找到失败的分析记录"
    failed_id = failed_ids[0]
    metadata = store.load_metadata(failed_id)
    stages = metadata.get("stages", {})
    assert stages.get("pose", {}).get("completed"), "失败分析应已完成 pose 阶段"
    assert (store.paths(failed_id).pose_json).exists(), "pose.json 应保留"

    # 第二次运行同一 analysis_id：pose 复用，metrics 重新计算
    import src.pose.extractor as extractor_module

    real_extract = extractor_module.PoseExtractor.extract
    counter = {"n": 0}

    def counting_extract(self, video_path, analysis_id="", progress_callback=None):
        counter["n"] += 1
        return real_extract(self, video_path, analysis_id, progress_callback)

    extractor_module.PoseExtractor.extract = counting_extract
    try:
        result = analyze_video(SYNTHETIC_VIDEO, config=CONFIG, analysis_id=failed_id)
    finally:
        extractor_module.PoseExtractor.extract = real_extract

    assert result.status.value == "COMPLETED"
    assert counter["n"] == 0, "错误恢复后不应重新执行 MediaPipe"
    assert result.reused_pose is True
    assert result.metrics_df is not None and len(result.metrics_df) > 0
    _cleanup_analysis(failed_id)


# ------------------------------------------------------------------ 10. worker 独立运行
def test_worker_runs_independently(store):
    venv_python = Path(sys.executable)
    script = PROJECT_ROOT / "worker.py"
    completed = subprocess.run(
        [str(venv_python), str(script), "--input", str(SYNTHETIC_VIDEO), "--json"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=300,
    )
    assert completed.returncode == 0, f"worker 退出码 {completed.returncode}: {completed.stdout}\n{completed.stderr}"
    output = json.loads(completed.stdout)
    assert output["analysis_id"]
    assert output["status"] == "COMPLETED"
    assert output["reused_pose"] in (True, False)
    analysis_id = output["analysis_id"]
    store = AnalysisStore()
    assert (store.paths(analysis_id).pose_json).exists()
    _cleanup_analysis(analysis_id)


def test_worker_export_flag(store):
    venv_python = Path(sys.executable)
    script = PROJECT_ROOT / "worker.py"
    completed = subprocess.run(
        [str(venv_python), str(script), "--input", str(SYNTHETIC_VIDEO), "--export-skeleton", "--json"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=600,
    )
    assert completed.returncode == 0, f"worker 退出码 {completed.returncode}: {completed.stdout}\n{completed.stderr}"
    output = json.loads(completed.stdout)
    assert output["exports"]["skeleton_video"]
    assert Path(output["exports"]["skeleton_video"]).exists()
    _cleanup_analysis(output["analysis_id"])


# ------------------------------------------------------------------ 11. 实时模块未被破坏
def test_realtime_module_not_broken():
    from src.video.realtime_processor import RealtimePoseProcessor, build_realtime_components

    components = build_realtime_components(CONFIG)
    assert isinstance(components, RealtimePoseProcessor)
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = components.process_frame(black_frame, show_trajectories=False)
    assert "original_frame" in result and "skeleton_frame" in result and "metrics" in result
    components.pose_backend.close()


# ------------------------------------------------------------------ 12. 兼容层
def test_offline_processor_shim():
    from src.video.offline_processor import OfflineProcessConfig, OfflineVideoProcessor

    processor = OfflineVideoProcessor(config=OfflineProcessConfig(export_side_by_side_video=False), app_config=CONFIG)
    result = processor.process(SYNTHETIC_VIDEO)
    assert result["analysis_id"]
    assert result["metrics_df"] is not None
    assert result["side_by_side_video_path"] is None  # 默认不生成视频
    _cleanup_analysis(result["analysis_id"])


def test_muscle_pipeline_shim():
    from muscle_analysis.video_muscle_pipeline import process_muscle_video

    result = process_muscle_video(str(SYNTHETIC_VIDEO))
    assert result["analysis_id"]
    assert result["summary"] is not None
    assert Path(result["output_video"]).exists()
    _cleanup_analysis(result["analysis_id"])
