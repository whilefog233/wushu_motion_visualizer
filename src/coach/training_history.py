"""历史训练对比：基于 analysis 目录下的 ai_coach.json / technique 结果做趋势分析。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.storage.analysis_store import AnalysisStore


def list_recent_trainings(limit: int = 10) -> list[dict[str, Any]]:
    """列出最近 N 次有评分结果的训练，按时间倒序。"""
    store = AnalysisStore()
    items: list[dict[str, Any]] = []
    for summary in store.list_analyses():
        aid = summary["analysis_id"]
        coach_path = store.paths(aid).analysis_dir / "ai_coach.json"
        if not coach_path.exists():
            continue
        try:
            coach = json.loads(coach_path.read_text(encoding="utf-8"))
            score = coach.get("score", {})
            items.append({
                "analysis_id": aid,
                "created_at": summary.get("created_at", ""),
                "total_score": score.get("total_score"),
                "is_experimental": score.get("is_experimental", True),
            })
        except Exception:  # noqa: BLE001
            continue
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


def compare_with_previous(current_analysis_id: str, lookback: int = 3) -> dict[str, Any]:
    """对比当前训练与最近 N 次的趋势。"""
    recent = list_recent_trainings(limit=lookback + 1)
    current = next((x for x in recent if x["analysis_id"] == current_analysis_id), None)
    if current is None:
        return {"note": "当前训练无评分数据，无法对比"}
    previous = [x for x in recent if x["analysis_id"] != current_analysis_id]
    if not previous:
        return {"current_score": current.get("total_score"), "note": "暂无历史数据，这是第一次训练"}

    prev_scores = [p["total_score"] for p in previous if p.get("total_score") is not None]
    avg_prev = sum(prev_scores) / len(prev_scores) if prev_scores else None
    delta = (current.get("total_score") - avg_prev) if avg_prev is not None and current.get("total_score") is not None else None

    return {
        "current_score": current.get("total_score"),
        "avg_previous": round(avg_prev, 1) if avg_prev else None,
        "delta": round(delta, 1) if delta is not None else None,
        "trend": "进步" if delta and delta > 0.5 else ("退步" if delta and delta < -0.5 else "持平"),
        "history": previous,
    }
