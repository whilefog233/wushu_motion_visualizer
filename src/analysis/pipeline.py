from __future__ import annotations

"""统一 AnalysisPipeline。

核心目标：一次姿态推理、多模块复用、结果缓存、统一 analysis_id、
分析与视频导出分离、UI 与核心算法分离、支持独立 Worker。

流程::

    prepare_video()
        ↓
    extract_pose()          ← MediaPipe 只执行一次（pose.json 缓存 / 同源复用）
        ↓
    calculate_metrics()     ← metrics.csv 缓存
        ↓
    analyze_muscle()        ← muscle.json 缓存
        ↓
    analyze_power_chain()   ← power_chain.json 缓存
        ↓
    build_analysis_result() ← analysis.json
        ↓
    save_results()          ← performance.json / summary.md / metadata COMPLETED

任意阶段失败时保留已生成数据，重跑时从已有缓存继续。
"""

import json
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from src.analysis.metrics import compute_frame_metrics, initialize_peak_state, update_peak_metrics
from src.analysis.muscle import analyze_muscle
from src.analysis.power_chain import analyze_power_chain
from src.analysis.scale_normalization import augment_scale_metrics, normalized_speed_summary
from src.export.exporters import build_summary, write_metrics_csv, write_summary_json, write_summary_markdown
from src.models.analysis import AnalysisResult, AnalysisStage, AnalysisStatus
from src.models.pose_result import PoseResult
from src.pose.extractor import POSE_ALGORITHM_VERSION, PoseExtractionConfig, PoseExtractor
from src.storage.analysis_store import AnalysisPaths, AnalysisStore, utc_now_iso
from src.utils.paths import PROJECT_ROOT

# 整个分析流水线的算法版本：任一阶段的算法口径变化时递增，使相关缓存失效
ALGORITHM_VERSION = "2.0.0"

ProgressCallback = Optional[Callable[[AnalysisStage, float, str], None]]

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "default.yaml"


class AnalysisPipelineError(RuntimeError):
    """携带失败阶段信息的分析异常。"""

    def __init__(self, stage: AnalysisStage, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


def load_pipeline_config(config_path: Path | None = None) -> dict[str, Any]:
    import yaml

    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


class AnalysisPipeline:
    """分阶段、带缓存与错误恢复的统一分析流水线。"""

    def __init__(self, config: dict[str, Any] | None = None, progress_callback: ProgressCallback = None):
        self.config = config if config is not None else load_pipeline_config()
        self.progress_callback = progress_callback
        self.store = AnalysisStore()
        self._analysis_id: str = ""
        self._paths: AnalysisPaths | None = None
        self._performance: dict[str, Any] = {}
        self._reused_pose = False

    # ------------------------------------------------------------------ 主入口
    def analyze(self, video_path: str | Path, analysis_id: str | None = None, force: bool = False) -> AnalysisResult:
        """完整分析一个视频。同一 analysis_id 默认只执行一次 MediaPipe。"""
        video_path = Path(video_path)
        if not video_path.exists():
            raise AnalysisPipelineError(AnalysisStage.PREPARING, f"输入视频不存在: {video_path}")

        self._analysis_id = self._prepare_video(video_path, analysis_id)
        self._paths = self.store.paths(self._analysis_id)
        self._performance = {"reused_pose": False}
        self._started_at = time.perf_counter()

        try:
            pose = self._extract_pose(video_path, force=force)
            metrics_df = self._calculate_metrics(pose, force=force)
            muscle = self._analyze_muscle(force=force)
            power_chain = self._analyze_power_chain(force=force)
            analysis = self._build_analysis_result(pose, metrics_df, muscle, power_chain)
            performance = self._save_results(pose, metrics_df, analysis, muscle, power_chain)

            metadata = self.store.update_metadata(
                self._analysis_id,
                status=AnalysisStatus.COMPLETED.value,
                stage=AnalysisStage.COMPLETED.value,
                error=None,
            )
            self._notify(AnalysisStage.COMPLETED, 1.0, "分析完成")
            return AnalysisResult(
                analysis_id=self._analysis_id,
                analysis_dir=self._paths.analysis_dir,
                status=AnalysisStatus.COMPLETED,
                stage=AnalysisStage.COMPLETED,
                paths=self._paths.as_dict(),
                pose=pose,
                metrics_df=metrics_df,
                analysis=analysis,
                muscle=muscle,
                power_chain=power_chain,
                performance=performance,
                metadata=metadata,
                reused_pose=self._reused_pose,
            )
        except AnalysisPipelineError:
            raise
        except Exception as exc:
            self._mark_failed(AnalysisStage.BUILDING_RESULT, exc)
            raise AnalysisPipelineError(AnalysisStage.BUILDING_RESULT, f"{type(exc).__name__}: {exc}") from exc

    # ------------------------------------------------------------------ 各阶段
    def _prepare_video(self, video_path: Path, analysis_id: str | None) -> str:
        self._notify(AnalysisStage.PREPARING, 0.0, "准备视频")
        analysis_id = analysis_id or self.store.create(analysis_id)[0]
        if not self.store.exists(analysis_id):
            self.store.create(analysis_id)
        self._paths = self.store.paths(analysis_id)
        source = self.store.copy_source(video_path, analysis_id)

        video_info = self._read_video_info(source)
        from src.utils.video_utils import video_fingerprint

        metadata = {
            "analysis_id": analysis_id,
            "source_filename": video_path.name,
            "source_abs_path": str(video_path),
            "source_signature": self.store.source_signature(video_path),
            "video_fingerprint": video_fingerprint(source),
            "created_at": utc_now_iso(),
            "status": AnalysisStatus.RUNNING.value,
            "stage": AnalysisStage.PREPARING.value,
            "algorithm_version": ALGORITHM_VERSION,
            "video": video_info,
            "stages": {},
            "error": None,
        }
        existing = self.store.load_metadata(analysis_id)
        if existing:
            metadata["created_at"] = existing.get("created_at", metadata["created_at"])
            metadata["stages"] = existing.get("stages", {})
        self.store.save_metadata(analysis_id, metadata)
        return analysis_id

    def _extract_pose(self, video_path: Path, force: bool = False) -> PoseResult:
        self._notify(AnalysisStage.EXTRACTING_POSE, 0.0, "检查姿态缓存")
        paths = self._paths
        version = POSE_ALGORITHM_VERSION
        pose_stage = self.store.load_metadata(self._analysis_id).get("stages", {}).get("pose", {})

        # 1) 本 analysis 已有 pose.json 且版本一致 → 直接加载（不重新推理）
        if not force and pose_stage.get("completed") and pose_stage.get("algorithm_version") == version and paths.pose_json.exists():
            pose = PoseResult.load(paths.pose_json)
            pose.analysis_id = self._analysis_id
            self._reused_pose = True
            self._performance["pose_reuse_source"] = "same_analysis_cache"
            self._notify(AnalysisStage.EXTRACTING_POSE, 1.0, "姿态结果已缓存")
            return pose

        # 2) 同源视频的 pose.json 复用（同一个视频默认只跑一次完整 MediaPipe）
        if not force:
            reusable_id = self.store.find_reusable_pose(
                self.store.source_signature(video_path), version, exclude_analysis_id=self._analysis_id
            )
            if reusable_id:
                source_pose_path = self.store.paths(reusable_id).pose_json
                shutil.copy2(str(source_pose_path), str(paths.pose_json))
                pose = PoseResult.load(paths.pose_json)
                pose.analysis_id = self._analysis_id
                pose.save(paths.pose_json)
                self._reused_pose = True
                self._performance["pose_reuse_source"] = f"analysis:{reusable_id}"
                self._mark_stage_done("pose", duration_sec=0.0, reused=True)
                self._notify(AnalysisStage.EXTRACTING_POSE, 1.0, f"复用 {reusable_id} 的姿态结果")
                return pose

        # 3) 真正执行 MediaPipe（单次完整推理）
        self._notify(AnalysisStage.EXTRACTING_POSE, 0.0, "执行 MediaPipe Pose")
        pose_config = self.config.get("pose", {})
        extractor = PoseExtractor(
            PoseExtractionConfig(
                max_video_side=int(self.config.get("app", {}).get("max_video_side", 1280)),
                model_complexity=int(pose_config.get("model_complexity", 1)),
                enable_segmentation=bool(pose_config.get("enable_segmentation", False)),
                min_detection_confidence=float(pose_config.get("min_detection_confidence", 0.5)),
                min_tracking_confidence=float(pose_config.get("min_tracking_confidence", 0.5)),
                smooth_landmarks=bool(pose_config.get("smooth_landmarks", True)),
                store_world_landmarks=bool(pose_config.get("store_world_landmarks", True)),
            )
        )
        started = time.perf_counter()
        try:
            pose = extractor.extract(
                video_path,
                analysis_id=self._analysis_id,
                progress_callback=lambda p, msg: self._notify(AnalysisStage.EXTRACTING_POSE, p, msg),
            )
        finally:
            extractor.close()
        pose.algorithm_version = version
        pose.save(paths.pose_json)
        self._performance["pose_inference_time_sec"] = round(time.perf_counter() - started, 4)
        self._mark_stage_done("pose", duration_sec=self._performance["pose_inference_time_sec"], reused=False)
        self._notify(AnalysisStage.EXTRACTING_POSE, 1.0, "姿态提取完成")
        return pose

    def _calculate_metrics(self, pose: PoseResult, force: bool = False) -> pd.DataFrame:
        self._notify(AnalysisStage.CALCULATING_METRICS, 0.0, "检查指标缓存")
        paths = self._paths
        stages = self.store.load_metadata(self._analysis_id).get("stages", {})
        metrics_stage = stages.get("metrics", {})
        if not force and metrics_stage.get("completed") and metrics_stage.get("algorithm_version") == ALGORITHM_VERSION and paths.metrics_csv.exists():
            metrics_df = pd.read_csv(paths.metrics_csv)
            self._performance["metrics_reuse_source"] = "cache"
            self._notify(AnalysisStage.CALCULATING_METRICS, 1.0, "指标结果已缓存")
            return metrics_df

        self._notify(AnalysisStage.CALCULATING_METRICS, 0.0, "计算逐帧指标")
        started = time.perf_counter()
        alpha = float(self.config.get("analysis", {}).get("speed_smoothing_alpha", 0.35))
        rows: list[dict[str, float]] = []
        previous_landmarks = None
        previous_metrics = None
        previous_smoothed_speeds = None
        peak_state = initialize_peak_state()

        for frame_index, landmarks in enumerate(pose.landmarks):
            metrics, previous_smoothed_speeds = compute_frame_metrics(
                landmarks=landmarks,
                previous_landmarks=previous_landmarks,
                fps=pose.fps,
                previous_metrics=previous_metrics,
                previous_smoothed_speeds=previous_smoothed_speeds,
                speed_smoothing_alpha=alpha,
            )
            metrics, peak_state = update_peak_metrics(
                metrics, peak_state, pose.timestamps[frame_index] if frame_index < len(pose.timestamps) else 0.0, frame_index
            )
            row = {"frame_index": frame_index, "timestamp_sec": pose.timestamps[frame_index] if frame_index < len(pose.timestamps) else 0.0}
            row.update(metrics)
            rows.append(row)
            previous_landmarks = landmarks
            previous_metrics = metrics

        metrics_df = pd.DataFrame(rows)
        metrics_df = augment_scale_metrics(metrics_df, pose)
        write_metrics_csv(metrics_df, paths.metrics_csv)
        self._performance["metrics_calc_time_sec"] = round(time.perf_counter() - started, 4)
        self._mark_stage_done("metrics", duration_sec=self._performance["metrics_calc_time_sec"])
        self._notify(AnalysisStage.CALCULATING_METRICS, 1.0, "指标计算完成")
        return metrics_df

    def _analyze_muscle(self, force: bool = False) -> dict[str, Any]:
        self._notify(AnalysisStage.ANALYZING_MUSCLE, 0.0, "检查肌肉分析缓存")
        paths = self._paths
        stages = self.store.load_metadata(self._analysis_id).get("stages", {})
        muscle_stage = stages.get("muscle", {})
        if not force and muscle_stage.get("completed") and muscle_stage.get("algorithm_version") == ALGORITHM_VERSION and paths.muscle_json.exists():
            with paths.muscle_json.open("r", encoding="utf-8") as file:
                self._performance["muscle_reuse_source"] = "cache"
                self._notify(AnalysisStage.ANALYZING_MUSCLE, 1.0, "肌肉分析已缓存")
                return json.load(file)

        self._notify(AnalysisStage.ANALYZING_MUSCLE, 0.0, "估计肌肉参与度")
        started = time.perf_counter()
        metrics_df = pd.read_csv(paths.metrics_csv)
        pipeline_cfg = self.config.get("pipeline", {})
        result = analyze_muscle(
            metrics_df,
            smoothing_alpha=float(pipeline_cfg.get("muscle_smoothing_alpha", 0.28)),
            baseline=float(pipeline_cfg.get("muscle_baseline", 0.05)),
        )
        muscle = {"summary": result["summary"]}
        # 逐帧明细单独存 muscle_metrics.csv（体积较大，不塞进 JSON）
        result["metrics_df"].to_csv(paths.muscle_csv, index=False, encoding="utf-8-sig")
        with paths.muscle_json.open("w", encoding="utf-8") as file:
            json.dump(muscle, file, ensure_ascii=False, indent=2)
        self._performance["muscle_analysis_time_sec"] = round(time.perf_counter() - started, 4)
        self._mark_stage_done("muscle", duration_sec=self._performance["muscle_analysis_time_sec"])
        self._notify(AnalysisStage.ANALYZING_MUSCLE, 1.0, "肌肉分析完成")
        return muscle

    def _analyze_power_chain(self, force: bool = False) -> dict[str, Any]:
        self._notify(AnalysisStage.ANALYZING_POWER_CHAIN, 0.0, "检查发力链缓存")
        paths = self._paths
        stages = self.store.load_metadata(self._analysis_id).get("stages", {})
        pc_stage = stages.get("power_chain", {})
        if not force and pc_stage.get("completed") and pc_stage.get("algorithm_version") == ALGORITHM_VERSION and paths.power_chain_json.exists():
            with paths.power_chain_json.open("r", encoding="utf-8") as file:
                self._performance["power_chain_reuse_source"] = "cache"
                self._notify(AnalysisStage.ANALYZING_POWER_CHAIN, 1.0, "发力链分析已缓存")
                return json.load(file)

        self._notify(AnalysisStage.ANALYZING_POWER_CHAIN, 0.0, "分析发力链")
        started = time.perf_counter()
        metrics_df = pd.read_csv(paths.metrics_csv)
        power_chain = analyze_power_chain(metrics_df)
        with paths.power_chain_json.open("w", encoding="utf-8") as file:
            json.dump(power_chain, file, ensure_ascii=False, indent=2)
        self._performance["power_chain_time_sec"] = round(time.perf_counter() - started, 4)
        self._mark_stage_done("power_chain", duration_sec=self._performance["power_chain_time_sec"])
        self._notify(AnalysisStage.ANALYZING_POWER_CHAIN, 1.0, "发力链分析完成")
        return power_chain

    def _build_analysis_result(
        self,
        pose: PoseResult,
        metrics_df: pd.DataFrame,
        muscle: dict[str, Any],
        power_chain: dict[str, Any],
    ) -> dict[str, Any]:
        self._notify(AnalysisStage.BUILDING_RESULT, 0.0, "组装分析结果")
        summary = build_summary(metrics_df, average_fps=pose.fps)
        muscle_summary = muscle.get("summary", {})
        analysis = {
            "analysis_id": self._analysis_id,
            "algorithm_version": ALGORITHM_VERSION,
            "video": {
                "duration_sec": pose.duration,
                "fps": pose.fps,
                "frame_count": pose.frame_count,
                "width": pose.width,
                "height": pose.height,
            },
            "summary": summary,
            "normalized_speed": normalized_speed_summary(metrics_df),
            "muscle": {
                "dominant_power_chain_hint": muscle_summary.get("dominant_power_chain_hint", ""),
                "muscle_statistics": muscle_summary.get("muscle_statistics", []),
                "peak_moments": muscle_summary.get("peak_moments", []),
            },
            "power_chain": {
                "dominant_hint": power_chain.get("dominant_hint", ""),
                "hint_counts": power_chain.get("hint_counts", {}),
                "stage_distribution": power_chain.get("stage_distribution", {}),
            },
            "pose_reused": self._reused_pose,
        }
        write_summary_json(analysis, self._paths.analysis_json)
        self._mark_stage_done("result")
        return analysis

    def _save_results(
        self,
        pose: PoseResult,
        metrics_df: pd.DataFrame,
        analysis: dict[str, Any],
        muscle: dict[str, Any],
        power_chain: dict[str, Any],
    ) -> dict[str, Any]:
        self._notify(AnalysisStage.SAVING_RESULTS, 0.0, "保存结果")
        paths = self._paths
        total_time = round(time.perf_counter() - self._started_at, 4)

        performance = {
            "analysis_id": self._analysis_id,
            "video_length_sec": round(pose.duration, 4),
            "total_processing_time_sec": total_time,
            "pose_inference_time_sec": self._performance.get("pose_inference_time_sec"),
            "metrics_calc_time_sec": self._performance.get("metrics_calc_time_sec"),
            "muscle_analysis_time_sec": self._performance.get("muscle_analysis_time_sec"),
            "power_chain_time_sec": self._performance.get("power_chain_time_sec"),
            "export_video_time_sec": self._performance.get("export_video_time_sec"),
            "pose_processing_fps": round(pose.frame_count / self._performance["pose_inference_time_sec"], 2)
            if self._performance.get("pose_inference_time_sec")
            else None,
            "average_processing_fps": round(pose.frame_count / total_time, 2) if total_time > 0 else None,
            "reused_pose": self._reused_pose,
            "reuse_sources": {k: v for k, v in self._performance.items() if k.endswith("_reuse_source")},
        }
        with paths.performance_json.open("w", encoding="utf-8") as file:
            json.dump(performance, file, ensure_ascii=False, indent=2)

        # 兼容旧输出：summary.md 摘要
        write_summary_markdown(analysis.get("summary", {}), paths.summary_md)

        # 为未来 AI Coach 预生成结构化输入
        try:
            from src.coach.coach_input import build_coach_context

            build_coach_context(self._analysis_id, write_json=True)
        except Exception as exc:  # coach_input 是辅助产物，失败不阻断主流程
            self._notify(AnalysisStage.SAVING_RESULTS, 0.9, f"coach_input 生成失败: {exc}")

        self._mark_stage_done("save", duration_sec=0.0)
        return performance

    # ------------------------------------------------------------------ 元数据辅助
    def _mark_stage_done(self, stage_key: str, duration_sec: float = 0.0, reused: bool = False) -> None:
        metadata = self.store.load_metadata(self._analysis_id)
        stages = metadata.setdefault("stages", {})
        stages[stage_key] = {
            "completed": True,
            "algorithm_version": ALGORITHM_VERSION,
            "duration_sec": round(float(duration_sec), 4),
            "reused": bool(reused),
            "completed_at": utc_now_iso(),
        }
        metadata["stage"] = AnalysisStage.COMPLETED.value if stage_key == "save" else stage_key.upper()
        self.store.save_metadata(self._analysis_id, metadata)

    def _mark_failed(self, stage: AnalysisStage, exc: Exception) -> None:
        try:
            self.store.update_metadata(
                self._analysis_id,
                status=AnalysisStatus.FAILED.value,
                stage=stage.value,
                error=f"{type(exc).__name__}: {exc}",
            )
        except Exception:
            pass

    def _notify(self, stage: AnalysisStage, progress: float, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(stage, min(max(progress, 0.0), 1.0), message)

    @staticmethod
    def _read_video_info(source_path: Path) -> dict[str, Any]:
        from src.video.video_reader import VideoReader

        with VideoReader(source_path) as reader:
            return {
                "duration": round(reader.duration, 4),
                "fps": reader.fps,
                "frame_count": reader.frame_count,
                "width": reader.source_width,
                "height": reader.source_height,
            }


def analyze_video(
    video_path: str | Path,
    config: dict[str, Any] | None = None,
    analysis_id: str | None = None,
    force: bool = False,
    progress_callback: ProgressCallback = None,
) -> AnalysisResult:
    """核心入口：``result = analyze_video(video_path)``。

    不依赖 Streamlit，只使用 Path / dict / list / dataclass / JSON / DataFrame，
    未来可直接迁移到服务器 Worker。
    """
    pipeline = AnalysisPipeline(config=config, progress_callback=progress_callback)
    return pipeline.analyze(video_path, analysis_id=analysis_id, force=force)


def load_analysis_result(analysis_id: str) -> AnalysisResult:
    """只读加载已有分析结果（第二次打开 analysis 时直接读取，不重新计算）。"""
    store = AnalysisStore()
    if not store.exists(analysis_id):
        raise AnalysisPipelineError(AnalysisStage.PREPARING, f"analysis 不存在: {analysis_id}")
    paths = store.paths(analysis_id)
    metadata = store.load_metadata(analysis_id)

    pose = PoseResult.load(paths.pose_json) if paths.pose_json.exists() else None
    metrics_df = pd.read_csv(paths.metrics_csv) if paths.metrics_csv.exists() else None
    analysis = _load_json(paths.analysis_json)
    muscle = _load_json(paths.muscle_json)
    power_chain = _load_json(paths.power_chain_json)
    performance = _load_json(paths.performance_json)

    return AnalysisResult(
        analysis_id=analysis_id,
        analysis_dir=paths.analysis_dir,
        status=AnalysisStatus(metadata.get("status", AnalysisStatus.FAILED.value))
        if metadata.get("status") in {s.value for s in AnalysisStatus}
        else AnalysisStatus.FAILED,
        stage=AnalysisStage(metadata.get("stage", AnalysisStage.FAILED.value))
        if metadata.get("stage") in {s.value for s in AnalysisStage}
        else AnalysisStage.FAILED,
        paths=paths.as_dict(),
        pose=pose,
        metrics_df=metrics_df,
        analysis=analysis,
        muscle=muscle,
        power_chain=power_chain,
        performance=performance,
        metadata=metadata,
        error=metadata.get("error"),
    )


def _load_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
