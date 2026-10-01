from __future__ import annotations

"""肌肉参与度分析（纯数据阶段，不调用 MediaPipe）。

复用统一 PoseResult / metrics.csv，对每一帧估计 8 组肌群参与度，
输出 muscle.json（统计 + 峰值时刻）与 muscle_metrics.csv（逐帧明细）。
"""

import math
from collections import Counter
from typing import Any, Mapping

import pandas as pd

from muscle_analysis.muscle_estimator import MUSCLE_LABELS, MuscleEngagementEstimator
from src.analysis.power_chain import hint_from_scores, score_power_chain


def analyze_muscle(metrics_df: pd.DataFrame, smoothing_alpha: float = 0.28, baseline: float = 0.05) -> dict[str, Any]:
    """基于逐帧指标估计肌肉参与度，返回 {metrics_df, summary}。"""
    estimator = MuscleEngagementEstimator(smoothing_alpha=smoothing_alpha, baseline=baseline)
    rows: list[dict[str, Any]] = []
    for _, row in metrics_df.iterrows():
        frame_index = int(row.get("frame_index", 0))
        timestamp_sec = float(row.get("timestamp_sec", 0.0))
        engagement = estimator.estimate(None, row.to_dict(), frame_index=frame_index, timestamp_sec=timestamp_sec)
        top_muscles = estimator.get_top_muscles(engagement, top_k=3)
        scores = score_power_chain(row.to_dict())
        hint = hint_from_scores(scores)
        row_out: dict[str, Any] = {"frame": frame_index, "time_sec": timestamp_sec}
        row_out.update(engagement)
        row_out["top1_muscle"] = top_muscles[0][0] if top_muscles else ""
        row_out["top2_muscle"] = top_muscles[1][0] if len(top_muscles) > 1 else ""
        row_out["top3_muscle"] = top_muscles[2][0] if len(top_muscles) > 2 else ""
        row_out["power_chain_hint"] = hint
        rows.append(row_out)

    muscle_df = pd.DataFrame(rows)
    summary = _build_summary(muscle_df, estimator)
    return {"metrics_df": muscle_df, "summary": summary}


def _build_summary(muscle_df: pd.DataFrame, estimator: MuscleEngagementEstimator) -> dict[str, Any]:
    muscle_columns = list(MUSCLE_LABELS.keys())
    muscle_statistics = []
    for name in muscle_columns:
        series = pd.to_numeric(muscle_df.get(name, pd.Series(dtype=float)), errors="coerce").dropna()
        muscle_statistics.append(
            {
                "muscle": name,
                "label": MUSCLE_LABELS[name],
                "mean": float(series.mean()) if not series.empty else float("nan"),
                "max": float(series.max()) if not series.empty else float("nan"),
            }
        )
    hint_counter = Counter(str(v) for v in muscle_df.get("power_chain_hint", []) if str(v).strip())
    peak_moments = estimator.detect_peak_moments()
    return {
        "total_frames": int(len(muscle_df)),
        "dominant_power_chain_hint": hint_counter.most_common(1)[0][0] if hint_counter else "暂无数据",
        "power_chain_hint_counts": dict(hint_counter),
        "muscle_statistics": muscle_statistics,
        "peak_moments": peak_moments,
    }


def muscle_stats_table(muscle_summary: Mapping[str, Any]) -> pd.DataFrame:
    """UI 用：肌群统计表。"""
    rows = []
    for item in muscle_summary.get("muscle_statistics", []):
        rows.append(
            {
                "肌群": item.get("label", item.get("muscle", "")),
                "平均参与度": round(float(item.get("mean", float("nan"))), 3) if math.isfinite(float(item.get("mean", float("nan")))) else None,
                "峰值参与度": round(float(item.get("max", float("nan"))), 3) if math.isfinite(float(item.get("max", float("nan")))) else None,
            }
        )
    return pd.DataFrame(rows).sort_values("峰值参与度", ascending=False, na_position="last")
