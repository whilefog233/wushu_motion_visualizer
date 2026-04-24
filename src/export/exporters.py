from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import cv2
import pandas as pd


def write_keypoints_json(keypoints: list[dict[str, Any]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(keypoints, file, ensure_ascii=False, indent=2)


def write_metrics_csv(metrics_df: pd.DataFrame, output_path: Path) -> None:
    metrics_df.to_csv(output_path, index=False, encoding="utf-8-sig")


def build_summary(metrics_df: pd.DataFrame, average_fps: float) -> dict[str, Any]:
    summary = {
        "total_frames": int(metrics_df["frame_index"].max() + 1 if not metrics_df.empty else 0),
        "average_fps": float(average_fps),
        "left_knee_angle": _metric_stat(metrics_df, "left_knee_angle"),
        "right_knee_angle": _metric_stat(metrics_df, "right_knee_angle"),
        "left_elbow_angle": _metric_stat(metrics_df, "left_elbow_angle"),
        "motion_intensity": _metric_stat(metrics_df, "motion_intensity"),
        "hip_height": _metric_stat(metrics_df, "hip_height"),
    }
    return summary


def write_summary_json(summary: Mapping[str, Any], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)


def write_summary_markdown(summary: Mapping[str, Any], output_path: Path) -> None:
    def stat_line(title: str, stats: Mapping[str, Any]) -> list[str]:
        return [
            f"- {title} 最大值: {stats.get('max', 'NaN')}",
            f"- {title} 最小值: {stats.get('min', 'NaN')}",
            f"- {title} 平均值: {stats.get('mean', 'NaN')}",
        ]

    lines = [
        "# 分析摘要",
        "",
        f"- 视频总帧数: {summary.get('total_frames', 0)}",
        f"- 平均 FPS: {summary.get('average_fps', 0):.2f}",
        *stat_line("左膝角度", summary.get("left_knee_angle", {})),
        *stat_line("右膝角度", summary.get("right_knee_angle", {})),
        *stat_line("左肘角度", summary.get("left_elbow_angle", {})),
        f"- motion_intensity 最大值: {summary.get('motion_intensity', {}).get('max', 'NaN')}",
        (
            f"- 髋部高度变化范围: "
            f"{summary.get('hip_height', {}).get('min', 'NaN')} ~ {summary.get('hip_height', {}).get('max', 'NaN')}"
        ),
        "",
        "> 本报告仅提供骨架可视化统计摘要，不做动作对错判断。",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_frame_image(frame, output_path: Path) -> None:
    cv2.imwrite(str(output_path), frame)


def _metric_stat(metrics_df: pd.DataFrame, column: str) -> dict[str, float]:
    if column not in metrics_df.columns:
        return {"min": float("nan"), "max": float("nan"), "mean": float("nan")}
    series = pd.to_numeric(metrics_df[column], errors="coerce").dropna()
    if series.empty:
        return {"min": float("nan"), "max": float("nan"), "mean": float("nan")}
    return {
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
    }
