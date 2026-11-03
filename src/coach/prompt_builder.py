"""AI Coach prompt 构造：把 V3 结构化数据喂给 LLM，要求输出结构化 JSON。"""

from __future__ import annotations

import json
from typing import Any

from src.coach.scoring import ScoreResult


SYSTEM_PROMPT = """你是一位武术技术诊断教练。你的任务不是自己判断动作对错，而是理解下面提供的结构化分析数据，把它翻译成清晰、具体、可执行的教练建议。

严格规则：
1. 你只能使用提供的数据，不能凭空编造指标、帧号或时间。
2. 没有数据支持的结论，必须明确说"当前数据不足"。
3. 不得声称测量了真实拳力、真实肌电、真实物理速度（单位是 px/s 或归一化单位）。
4. 不得做医学诊断，不得保证一定得高分，不得替代专业教练。
5. 所有建议必须对应 V3 诊断给出的具体证据（帧号、时间、指标数值）。
6. 输出必须是合法 JSON，不要 markdown，不要解释性文字。

输出 JSON 格式（必须严格遵守）：
{
  "overall_summary": "本次动作总体结论（2-3 句）",
  "score": 85,
  "score_breakdown": [{"dimension": "发力链顺序", "score": 16, "max": 20, "reason": "扣分原因"}],
  "top_problems": [{"problem": "问题名称", "severity": "high/medium/low", "evidence": "对应帧/时间/指标", "why": "为什么扣分"}],
  "standard_action": "标准动作应该怎样完成（具体步骤）",
  "why_score_is_lost": "主要扣分点总结",
  "training_advice": "下一轮具体怎么练（可执行动作指令）",
  "priority_drill": "本轮最重要的一项训练（一句话）",
  "comparison_with_baseline": "与个人基线相比的变化",
  "confidence": 0.8,
  "limitations": "当前结论的限制和不确定性"
}"""


def build_user_prompt(
    technique_dict: dict[str, Any],
    score_result: ScoreResult,
    baseline_summary: dict[str, Any] | None = None,
    expert_available: bool = False,
) -> str:
    """构造用户 prompt：只传关键摘要，控制 LLM 响应速度。"""
    windows = technique_dict.get("windows", [])
    # 收集所有窗口的 top 问题（去重，只取最严重的）
    all_problems: list[dict[str, Any]] = []
    seen: set[str] = set()
    sev_order = {"high": 3, "medium": 2, "low": 1}
    for w in windows:
        for d in w.get("diagnoses", []):
            pid = d.get("problem_id", "")
            if pid not in seen:
                seen.add(pid)
                all_problems.append(d)
    # 按 severity 排序，取前 3
    all_problems.sort(key=lambda x: sev_order.get(x.get("severity", "low"), 0), reverse=True)
    top_problems = all_problems[:3]

    compact = {
        "total_score": score_result.total_score,
        "dimensions": [
            {"name": d.name, "score": d.score, "max": d.max_score}
            for d in score_result.dimensions
        ],
        "top_problems": [
            {
                "problem": p.get("problem"),
                "severity": p.get("severity"),
                "evidence": p.get("evidence_text", "")[:100],
                "advice": p.get("training_advice", "")[:100],
            }
            for p in top_problems
        ],
        "window_count": len(windows),
    }

    payload = {
        "score_and_problems": compact,
        "expert_template_available": expert_available,
    }
    if not expert_available:
        payload["notice"] = "当前没有专家模板，评分属于基于个人基线和结构规则的实验性估计。"
    return "请基于以下武术动作诊断数据，给出简洁的教练解读：\n\n" + json.dumps(payload, ensure_ascii=False)
