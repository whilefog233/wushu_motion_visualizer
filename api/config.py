"""API 配置：全部从环境变量读取，不写死任何密钥。"""

from __future__ import annotations

import os
from pathlib import Path

from src.utils.paths import ANALYSES_DIR, PROJECT_ROOT


class ApiConfig:
    def __init__(self) -> None:
        self.api_key: str = os.environ.get("KUNGFU_API_KEY", "")
        self.cors_origin: str = os.environ.get(
            "KUNGFU_CORS_ORIGIN",
            "https://kungfu-v3-wushu.hybrid-j9y56-1505.chatgpt.site",
        )
        self.max_concurrent: int = int(os.environ.get("KUNGFU_MAX_CONCURRENT", "1"))
        self.max_upload_mb: int = int(os.environ.get("KUNGFU_MAX_UPLOAD_MB", "200"))
        self.allowed_extensions: tuple[str, ...] = (".mp4",)
        self.host: str = "127.0.0.1"
        self.port: int = int(os.environ.get("KUNGFU_API_PORT", "8000"))
        self.analyses_dir: Path = ANALYSES_DIR
        self.project_root: Path = PROJECT_ROOT
        self.version: str = "4.0.0"

    @property
    def upload_temp_dir(self) -> Path:
        path = self.project_root / "data" / "api_uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def require_api_key(self) -> bool:
        return bool(self.api_key)


config = ApiConfig()
