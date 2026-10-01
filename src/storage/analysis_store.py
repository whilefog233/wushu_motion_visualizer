from __future__ import annotations

"""统一 analysis 目录存储管理。

每次分析生成一个唯一 ``analysis_id``，该视频产生的所有数据统一保存到
``data/analyses/{analysis_id}/``，任何模块不再自行创建零散目录。
"""

import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.utils.paths import ANALYSES_DIR, ensure_project_dirs

METADATA_FILENAME = "metadata.json"


def new_analysis_id() -> str:
    """生成唯一 analysis_id（时间戳 + 短随机串，避免并发冲突）。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AnalysisPaths:
    """一个 analysis 目录内的所有标准产物路径。"""

    analysis_dir: Path

    @property
    def source_video(self) -> Path:
        return self.analysis_dir / "source.mp4"

    @property
    def metadata(self) -> Path:
        return self.analysis_dir / METADATA_FILENAME

    @property
    def pose_json(self) -> Path:
        return self.analysis_dir / "pose.json"

    @property
    def metrics_csv(self) -> Path:
        return self.analysis_dir / "metrics.csv"

    @property
    def analysis_json(self) -> Path:
        return self.analysis_dir / "analysis.json"

    @property
    def muscle_json(self) -> Path:
        return self.analysis_dir / "muscle.json"

    @property
    def muscle_csv(self) -> Path:
        return self.analysis_dir / "muscle_metrics.csv"

    @property
    def power_chain_json(self) -> Path:
        return self.analysis_dir / "power_chain.json"

    @property
    def coach_input_json(self) -> Path:
        return self.analysis_dir / "coach_input.json"

    @property
    def performance_json(self) -> Path:
        return self.analysis_dir / "performance.json"

    @property
    def summary_md(self) -> Path:
        return self.analysis_dir / "summary.md"

    @property
    def exports_dir(self) -> Path:
        return self.analysis_dir / "exports"

    def export_file(self, filename: str) -> Path:
        return self.exports_dir / filename

    def as_dict(self) -> dict[str, str]:
        return {
            "analysis_dir": str(self.analysis_dir),
            "source_video": str(self.source_video),
            "metadata": str(self.metadata),
            "pose_json": str(self.pose_json),
            "metrics_csv": str(self.metrics_csv),
            "analysis_json": str(self.analysis_json),
            "muscle_json": str(self.muscle_json),
            "muscle_csv": str(self.muscle_csv),
            "power_chain_json": str(self.power_chain_json),
            "coach_input_json": str(self.coach_input_json),
            "performance_json": str(self.performance_json),
            "summary_md": str(self.summary_md),
            "exports_dir": str(self.exports_dir),
        }


class AnalysisStore:
    """负责 analysis 目录的创建、元数据读写与列表/复用查询。"""

    def __init__(self, root: Path | None = None):
        ensure_project_dirs()
        self.root = Path(root) if root is not None else ANALYSES_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ 目录
    def create(self, analysis_id: str | None = None) -> tuple[str, Path]:
        analysis_id = analysis_id or new_analysis_id()
        analysis_dir = self.root / analysis_id
        analysis_dir.mkdir(parents=True, exist_ok=True)
        (analysis_dir / "exports").mkdir(parents=True, exist_ok=True)
        return analysis_id, analysis_dir

    def paths(self, analysis_id: str) -> AnalysisPaths:
        return AnalysisPaths(self.root / analysis_id)

    def exists(self, analysis_id: str) -> bool:
        return (self.root / analysis_id).is_dir()

    # ------------------------------------------------------------------ 源视频
    def copy_source(self, source_path: Path, analysis_id: str) -> Path:
        """把源视频放入 analysis 目录（优先硬链接省磁盘，失败则复制）。"""
        paths = self.paths(analysis_id)
        target = paths.source_video
        if target.exists():
            return target
        try:
            os.link(str(source_path), str(target))
        except OSError:
            shutil.copy2(str(source_path), str(target))
        return target

    def source_signature(self, source_path: Path) -> dict[str, Any]:
        stat = source_path.stat()
        return {"filename": source_path.name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}

    # ------------------------------------------------------------------ 元数据
    def load_metadata(self, analysis_id: str) -> dict[str, Any]:
        path = self.paths(analysis_id).metadata
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save_metadata(self, analysis_id: str, metadata: dict[str, Any]) -> None:
        path = self.paths(analysis_id).metadata
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata["updated_at"] = utc_now_iso()
        with path.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, ensure_ascii=False, indent=2)

    def update_metadata(self, analysis_id: str, **fields: Any) -> dict[str, Any]:
        metadata = self.load_metadata(analysis_id)
        metadata.update(fields)
        self.save_metadata(analysis_id, metadata)
        return metadata

    # ------------------------------------------------------------------ 列表
    def list_analyses(self) -> list[dict[str, Any]]:
        """按创建时间倒序返回全部 analysis 的元数据摘要。"""
        summaries = []
        for analysis_dir in sorted(self.root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not analysis_dir.is_dir() or analysis_dir.name.startswith("."):
                continue
            metadata = self.load_metadata(analysis_dir.name)
            if not metadata:
                continue
            summaries.append(
                {
                    "analysis_id": analysis_dir.name,
                    "source_filename": metadata.get("source_filename", analysis_dir.name),
                    "status": metadata.get("status", "UNKNOWN"),
                    "stage": metadata.get("stage", ""),
                    "created_at": metadata.get("created_at", ""),
                    "video": metadata.get("video", {}),
                }
            )
        return summaries

    # ------------------------------------------------------------------ 姿态复用
    def find_reusable_pose(self, source_signature: dict[str, Any], algorithm_version: str, exclude_analysis_id: str | None = None) -> Optional[str]:
        """查找同一源视频、同一算法版本、已完成姿态提取的 analysis_id。

        用于“同一个视频默认只运行一次完整 MediaPipe Pose”：
        新分析复用旧分析的 pose.json（仅复制文件，不做推理）。
        """
        signature_key = (source_signature.get("filename"), source_signature.get("size"), source_signature.get("mtime_ns"))
        for analysis_dir in self.root.iterdir():
            if not analysis_dir.is_dir() or analysis_dir.name.startswith("."):
                continue
            if exclude_analysis_id and analysis_dir.name == exclude_analysis_id:
                continue
            metadata = self.load_metadata(analysis_dir.name)
            stages = metadata.get("stages", {})
            pose_stage = stages.get("pose", {})
            if not pose_stage.get("completed"):
                continue
            if pose_stage.get("algorithm_version") != algorithm_version:
                continue
            source = metadata.get("source_signature")
            if not source:
                continue
            if (source.get("filename"), source.get("size"), source.get("mtime_ns")) != signature_key:
                continue
            if (analysis_dir / "pose.json").exists():
                return analysis_dir.name
        return None

    # ------------------------------------------------------------------ 内容指纹去重
    def find_analysis_by_fingerprint(self, fingerprint: str) -> Optional[str]:
        """按视频内容指纹（md5）查找已完成分析的 analysis_id。

        同一视频即使文件名/时间戳不同，只要字节一致就命中。
        老 analysis 的 metadata 没有 video_fingerprint 字段时，现场对 source.mp4
        补算一次并写回，避免以后重复计算。
        """
        for analysis_dir in self.root.iterdir():
            if not analysis_dir.is_dir() or analysis_dir.name.startswith("."):
                continue
            metadata = self.load_metadata(analysis_dir.name)
            if not metadata:
                continue
            stored = metadata.get("video_fingerprint")
            if not stored:
                source_path = analysis_dir / "source.mp4"
                if not source_path.exists():
                    continue
                try:
                    from src.utils.video_utils import video_fingerprint

                    stored = video_fingerprint(source_path)
                except Exception:
                    continue
                self.update_metadata(analysis_dir.name, video_fingerprint=stored)
            if stored == fingerprint:
                return analysis_dir.name
        return None
