"""后台分析任务队列：复用现有 pipeline，限制并发，状态落 metadata.json。"""

from __future__ import annotations

import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.analysis.pipeline import (
    ALGORITHM_VERSION,
    AnalysisPipelineError,
    analyze_video,
    load_analysis_result,
)
from src.storage.analysis_store import AnalysisStore

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()


def get_executor(max_workers: int = 1) -> ThreadPoolExecutor:
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="kungfu")
        return _executor


def mark_stale_running_as_failed() -> int:
    """服务重启后，把上次 RUNNING 的任务标记为 FAILED（不能假装成功）。"""
    store = AnalysisStore()
    count = 0
    for summary in store.list_analyses():
        aid = summary["analysis_id"]
        meta = store.load_metadata(aid)
        if meta.get("status") == "RUNNING":
            store.update_metadata(
                aid,
                status="FAILED",
                stage="RESTARTED",
                error="服务重启，任务中断",
            )
            count += 1
    return count


def _run_technique(analysis_id: str) -> None:
    """分析完成后跑 V3 直拳诊断，失败不影响主分析结果。"""
    try:
        from src.technique.engine import analyze_technique

        analyze_technique(analysis_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("technique diagnosis failed for %s: %s", analysis_id, exc)


def run_analysis_task(analysis_id: str, source_path: Path) -> None:
    """后台线程：完整分析 + V3 诊断，异常写回 metadata。"""
    store = AnalysisStore()
    try:
        result = analyze_video(source_path, analysis_id=analysis_id)
        _run_technique(analysis_id)
        logger.info("analysis %s done, status=%s", analysis_id, result.status.value)
    except AnalysisPipelineError as exc:
        store.update_metadata(
            analysis_id,
            status="FAILED",
            stage=exc.stage.value if hasattr(exc.stage, "value") else str(exc.stage),
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("analysis %s crashed", analysis_id)
        store.update_metadata(analysis_id, status="FAILED", stage="CRASHED", error=f"{type(exc).__name__}: {exc}")
    finally:
        # 清理上传临时文件（source.mp4 已在 analysis 目录）
        try:
            if source_path.exists() and source_path.parent.name == "api_uploads":
                source_path.unlink()
        except OSError:
            pass


def read_task_status(analysis_id: str) -> dict:
    """从 metadata.json 读任务状态（进程重启也不丢）。"""
    store = AnalysisStore()
    if not store.exists(analysis_id):
        return {}
    meta = store.load_metadata(analysis_id)
    return {
        "analysis_id": analysis_id,
        "status": meta.get("status", "UNKNOWN"),
        "stage": meta.get("stage", ""),
        "error": meta.get("error"),
        "algorithm_version": meta.get("algorithm_version", ALGORITHM_VERSION),
        "created_at": meta.get("created_at"),
        "video": meta.get("video", {}),
    }


def build_result_payload(analysis_id: str) -> dict | None:
    """组装 GET /result 返回：指标摘要 + V3 诊断 + 文件清单。"""
    store = AnalysisStore()
    if not store.exists(analysis_id):
        return None
    try:
        result = load_analysis_result(analysis_id)
    except Exception:  # noqa: BLE001
        return {"analysis_id": analysis_id, "status": "FAILED", "files": []}

    paths = store.paths(analysis_id)
    files = {}
    for label, p in {
        "metadata": paths.metadata,
        "pose": paths.pose_json,
        "metrics": paths.metrics_csv,
        "analysis": paths.analysis_json,
        "muscle": paths.muscle_json,
        "power_chain": paths.power_chain_json,
        "coach_input": paths.coach_input_json,
        "performance": paths.performance_json,
        "summary": paths.summary_md,
    }.items():
        if p.exists():
            files[label] = p.name

    # exports 目录里的文件
    if paths.exports_dir.exists():
        files["exports"] = sorted(
            f.name for f in paths.exports_dir.iterdir() if f.is_file()
        )

    # V3 直拳诊断
    technique = None
    try:
        from src.technique.engine import load_technique_result

        tech = load_technique_result(analysis_id)
        if tech is not None:
            technique = tech.to_dict() if hasattr(tech, "to_dict") else None
            if technique is None:
                # 兜底读文件
                tech_path = paths.analysis_dir / "technique" / "straight_punch.json"
                if tech_path.exists():
                    import json

                    technique = json.loads(tech_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass

    # V4 本地评分（基于 V3 诊断证据；无 V3 结果时为 None）
    score = None
    try:
        from src.coach.scoring import compute_score

        score_result = compute_score(analysis_id)
        if score_result is not None:
            score = score_result.to_dict()
    except Exception:  # noqa: BLE001
        pass

    return {
        "analysis_id": analysis_id,
        "status": result.status.value,
        "stage": result.stage.value,
        "error": result.error,
        "video": result.metadata.get("video", {}) if result.metadata else {},
        "performance": result.performance,
        "muscle": result.muscle,
        "power_chain": result.power_chain,
        "technique": technique,
        "score": score,
        "files": files,
    }
