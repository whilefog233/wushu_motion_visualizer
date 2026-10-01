"""独立分析 Worker（完全脱离 Streamlit）。

用法::

    python worker.py --input xxx.mp4
    python worker.py --input xxx.mp4 --export-skeleton
    python worker.py --input xxx.mp4 --analysis-id my_analysis --force

运行后创建 analysis_id、完成完整分析、保存结果并输出 analysis_id。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.analysis.pipeline import ALGORITHM_VERSION, AnalysisPipelineError, analyze_video, load_pipeline_config


def _progress_callback(stage, progress, message):
    sys.stdout.write(f"\r[{stage.value}] {progress * 100:5.1f}%  {message}")
    sys.stdout.flush()
    if progress >= 1.0:
        sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="武术动作分析 Worker（V2 独立入口）")
    parser.add_argument("--input", required=True, help="输入视频路径（mp4 等）")
    parser.add_argument("--analysis-id", default=None, help="指定 analysis_id（默认自动生成）")
    parser.add_argument("--force", action="store_true", help="忽略缓存强制重算全部阶段")
    parser.add_argument("--export-skeleton", action="store_true", help="分析完成后导出骨架视频")
    parser.add_argument("--export-muscle", action="store_true", help="分析完成后导出肌肉可视化视频")
    parser.add_argument("--config", default=None, help="配置文件路径（默认 configs/default.yaml）")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 结果（便于脚本调用）")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(json.dumps({"error": f"输入视频不存在: {input_path}"}))
        return 1

    config = load_pipeline_config(Path(args.config) if args.config else None)
    try:
        result = analyze_video(
            input_path,
            config=config,
            analysis_id=args.analysis_id,
            force=args.force,
            progress_callback=_progress_callback if not args.json else None,
        )
    except AnalysisPipelineError as exc:
        print(json.dumps({"error": str(exc), "stage": exc.stage.value if hasattr(exc.stage, "value") else str(exc.stage)}))
        return 1
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 1

    export_paths = {}
    if args.export_skeleton:
        from src.export.skeleton_video import export_skeleton_video

        export_paths["skeleton_video"] = str(export_skeleton_video(result.analysis_id, progress_callback=_progress_callback if not args.json else None))
    if args.export_muscle:
        from src.export.muscle_video import export_muscle_video

        export_paths["muscle_video"] = str(export_muscle_video(result.analysis_id, progress_callback=_progress_callback if not args.json else None))

    summary = {
        "analysis_id": result.analysis_id,
        "status": result.status.value,
        "analysis_dir": str(result.analysis_dir),
        "reused_pose": result.reused_pose,
        "video": result.metadata.get("video", {}) if result.metadata else {},
        "algorithm_version": ALGORITHM_VERSION,
        "exports": export_paths,
        "performance": result.performance,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("\n=== 分析完成 ===")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
