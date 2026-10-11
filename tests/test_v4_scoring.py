"""V4 评分与 AI Coach 冒烟测试。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.coach.scoring import DIMENSIONS, compute_score, ScoreResult  # noqa: E402
from src.coach.provider import CoachProviderConfig, parse_json_response  # noqa: E402
from src.coach.training_history import compare_with_previous  # noqa: E402


def test_dimension_sum_is_100():
    assert sum(d["max_score"] for d in DIMENSIONS) == 100


def test_provider_config_default_disabled():
    import os
    old = os.environ.pop("AI_ENABLED", None)
    old_key = os.environ.pop("AI_API_KEY", None)
    try:
        cfg = CoachProviderConfig()
        assert cfg.is_configured is False
    finally:
        if old:
            os.environ["AI_ENABLED"] = old
        if old_key:
            os.environ["AI_API_KEY"] = old_key


def test_parse_json_strips_markdown():
    raw = "```json\n{\"score\": 85}\n```"
    parsed = parse_json_response(raw)
    assert parsed["score"] == 85


def test_parse_json_plain():
    raw = '{"overall_summary": "test", "score": 70}'
    parsed = parse_json_response(raw)
    assert parsed["overall_summary"] == "test"


def test_compare_with_nonexistent():
    result = compare_with_previous("nonexistent_id")
    assert "note" in result
