"""API 认证与路径安全。"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from api.config import config

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# analysis_id 格式：20261001_124339_ab12cd34
_ANALYSIS_ID_RE = re.compile(r"^\d{8}_\d{6}_[a-f0-9]{8}$")


def _is_same_origin(request: Request) -> bool:
    """判断请求是否来自服务器自己托管的前端页面（同源）。

    浏览器同源请求的 Origin/Referer 主机与当前请求主机一致；
    这样网站自身页面不需要在前端保存 API Key，外部跨域调用仍必须带 Key。
    """
    host = request.headers.get("host", "")
    source = request.headers.get("origin") or request.headers.get("referer") or ""
    if not host or not source:
        return False
    # 提取 source 的主机部分
    try:
        from urllib.parse import urlparse

        parsed = urlparse(source)
        return bool(parsed.netloc) and parsed.netloc == host
    except Exception:  # noqa: BLE001
        return False


async def require_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> str:
    """校验 X-API-Key。

    - 未配置 KUNGFU_API_KEY：放行（本地开发）
    - 同源前端页面请求：放行（密钥不进前端）
    - 其他请求：必须携带正确 X-API-Key
    """
    if not config.require_api_key:
        return "dev"
    if _is_same_origin(request):
        return "same-origin"
    if api_key is None or api_key != config.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或缺失的 API Key",
        )
    return api_key


def validate_analysis_id(analysis_id: str) -> str:
    """校验 analysis_id 格式，防止路径穿越。"""
    if not _ANALYSIS_ID_RE.match(analysis_id):
        raise HTTPException(status_code=400, detail="analysis_id 格式非法")
    return analysis_id


def safe_join_analysis_file(analysis_dir: Path, filename: str) -> Path:
    """安全拼接 analysis 目录下的文件路径，拒绝 ../、绝对路径、符号链接外逃逸。"""
    if not filename or filename.startswith("/") or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="文件名非法")
    candidate = (analysis_dir / filename).resolve()
    analysis_root = analysis_dir.resolve()
    if not str(candidate).startswith(str(analysis_root)):
        raise HTTPException(status_code=400, detail="路径越界")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return candidate
