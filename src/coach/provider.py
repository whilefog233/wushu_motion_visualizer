"""AI Coach LLM 调用层：OpenAI 兼容格式，支持 Kimi/豆包/任何 OpenAI 兼容接口。

配置全部从环境变量读取，密钥不写死、不返回给前端。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class CoachProviderConfig:
    def __init__(self) -> None:
        self.enabled: bool = _env("AI_ENABLED", "false").lower() in ("1", "true", "yes")
        self.api_key: str = _env("AI_API_KEY")
        self.base_url: str = _env("AI_BASE_URL", "https://api.moonshot.cn/v1")
        self.model: str = _env("AI_MODEL", "moonshot-v1-8k")
        self.timeout: float = float(_env("AI_TIMEOUT", "60"))

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.api_key)


def call_llm(system_prompt: str, user_prompt: str, config: CoachProviderConfig | None = None) -> str:
    """调用 OpenAI 兼容 Chat Completions 接口，返回文本。

    未配置密钥时抛 RuntimeError；网络/解析异常向上抛，由调用方捕获。
    """
    config = config or CoachProviderConfig()
    if not config.is_configured:
        raise RuntimeError("AI 未配置（AI_ENABLED 或 AI_API_KEY 缺失）")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai 包未安装，请 pip install openai") from exc

    client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=config.timeout)
    kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    # kimi 系列模型只允许 temperature=1，其他模型用 0.3 更稳定
    if "kimi" not in config.model and "moonshot" not in config.model:
        kwargs["temperature"] = 0.3
    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    return content


def parse_json_response(text: str) -> dict[str, Any]:
    """从 LLM 返回文本中提取 JSON（容忍 markdown 代码块包裹）。"""
    text = text.strip()
    if text.startswith("```"):
        # 去掉 ```json ... ``` 包裹
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)
