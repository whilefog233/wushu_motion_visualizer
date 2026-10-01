from __future__ import annotations

"""兼容层：肌肉视频分析旧入口。

V2 之后肌肉分析与骨架分析共用同一个 AnalysisPipeline / 统一 PoseResult，
本模块保留旧函数 ``process_muscle_video`` 的签名与返回结构，内部委托新管线。

关键变化（修复旧 bug）：
- 旧代码里 ``reuse_existing_pose`` 参数被 ``del`` 直接丢弃，从不复用姿态；
  现在任何入口都默认复用 pose.json / 同源视频缓存，不再重复运行 MediaPipe。
"""

import json
import shutil
from pathlib import Path
from typing import Callable

import pandas as pd

from src.analysis.pipeline import AnalysisPipeline, load_pipeline_config


ProgressCallback = Callable[[float, str], None] | None


def process_muscle_video(
    input_video_path: str,
    output_video_path: str | None = None,
    reuse_existing_pose: bool = False,
    progress_callback: ProgressCallback = None,
) -> dict:
    """兼容旧入口：分析并生成肌肉可视化视频。

    说明：``reuse_existing_pose`` 参数保留仅为兼容旧签名；
    V2 默认行为就是复用统一 PoseResult（同一视频只跑一次 MediaPipe）。
    """
    del reuse_existing_pose

    def adapter(stage, progress, message):
        if progress_callback:
            progress_callback(progress, message)

    pipeline = AnalysisPipeline(config=load_pipeline_config(), progress_callback=adapter)
    result = pipeline.analyze(input_video_path)

    muscle_df = pd.read_csv(result.paths["muscle_csv"]) if Path(result.paths["muscle_csv"]).exists() else pd.DataFrame()
    with Path(result.paths["muscle_json"]).open("r", encoding="utf-8") as file:
        muscle_data = json.load(file)
    summary = muscle_data.get("summary", {})

    # 导出肌肉可视化视频（复用 pose.json / muscle_metrics.csv，不重跑推理）
    from src.export.muscle_video import export_muscle_video

    exported = Path(export_muscle_video(result.analysis_id, progress_callback=progress_callback))
    final_video_path = Path(output_video_path) if output_video_path else exported
    if output_video_path and final_video_path.resolve() != exported.resolve():
        final_video_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(exported), str(final_video_path))

    return {
        "analysis_id": result.analysis_id,
        "output_video": str(final_video_path),
        "csv_path": result.paths["muscle_csv"],
        "summary": summary,
        "metrics_df": muscle_df,
        "reused_pose": result.reused_pose,
    }
