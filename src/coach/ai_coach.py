"""AI Coach 主入口：读 V3 诊断 → 本地评分 → 调 LLM 翻译成教练语言 → 保存结构化结果。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.coach.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from src.coach.provider import CoachProviderConfig, call_llm, parse_json_response
from src.coach.scoring import ScoreResult, compute_score
from src.storage.analysis_store import AnalysisStore
from src.technique.engine import load_technique_result

logger = logging.getLogger(__name__)


COACH_FILENAME = "ai_coach.json"


def coach_output_path(analysis_id: str) -> Path:
    return AnalysisStore().paths(analysis_id).analysis_dir / COACH_FILENAME


def _baseline_summary(analysis_id: str) -> dict[str, Any]:
    """从 technique 结果里提取基线对比摘要。"""
    result = load_technique_result(analysis_id)
    if result is None:
        return {}
    return {
        "reference_available": result.reference_available,
        "window_count": len(result.windows),
    }


def generate_coach_interpretation(
    analysis_id: str,
    config: CoachProviderConfig | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """生成 AI Coach 解读。

    流程：
    1. 读 V3 诊断
    2. 本地评分
    3. 调 LLM（未配置/失败时返回本地评分结果，不抛异常）
    4. 保存到 ai_coach.json
    """
    config = config or CoachProviderConfig()
    store = AnalysisStore()
    path = coach_output_path(analysis_id)

    if not force and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    # 1. V3 诊断
    technique = load_technique_result(analysis_id)
    if technique is None:
        result = {"error": "V3 技术诊断不存在，请先跑 analyze_technique", "analysis_id": analysis_id}
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    # 2. 本地评分
    score = compute_score(analysis_id)
    score_dict = score.to_dict() if score else {"error": "评分失败"}

    # 3. 调 LLM
    llm_result: dict[str, Any] | None = None
    llm_error: str | None = None
    if config.is_configured:
        try:
            user_prompt = build_user_prompt(
                technique.to_dict(),
                score,
                baseline_summary=_baseline_summary(analysis_id),
                expert_available=score.has_expert_template if score else False,
            )
            raw = call_llm(SYSTEM_PROMPT, user_prompt, config)
            llm_result = parse_json_response(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI Coach 调用失败: %s", exc)
            llm_error = f"{type(exc).__name__}: {exc}"
    else:
        llm_error = "AI 未配置（AI_ENABLED=false 或 AI_API_KEY 缺失），返回本地评分结果"

    output = {
        "analysis_id": analysis_id,
        "score": score_dict,
        "llm_interpretation": llm_result,
        "llm_error": llm_error,
        "ai_available": config.is_configured,
        "engine_version": "4.0.0",
    }

    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def load_coach_interpretation(analysis_id: str) -> dict[str, Any] | None:
    path = coach_output_path(analysis_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
