"""Kungfu V3 HTTP 后端：复用现有分析 pipeline，不重写算法。

启动：
    uvicorn api.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from api.config import config
from api.security import require_api_key, safe_join_analysis_file, validate_analysis_id
from api.tasks import (
    build_result_payload,
    get_executor,
    mark_stale_running_as_failed,
    read_task_status,
    run_analysis_task,
)
from src.storage.analysis_store import AnalysisStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kungfu.api")

app = FastAPI(
    title="Kungfu V3 API",
    version=config.version,
    description="武术 AI 教练系统 V3 HTTP 后端（复用现有 pipeline，不重写算法）",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.cors_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)


@app.on_event("startup")
def _startup() -> None:
    stale = mark_stale_running_as_failed()
    if stale:
        logger.info("标记 %d 个中断任务为 FAILED", stale)
    get_executor(max_workers=config.max_concurrent)


@app.get("/health")
def health() -> dict:
    import os

    ai_key = os.environ.get("AI_API_KEY", "")
    ai_on = os.environ.get("AI_ENABLED", "").lower() in {"1", "true", "yes"} and bool(ai_key)
    return {
        "status": "ok",
        "version": config.version,
        "max_concurrent": config.max_concurrent,
        "require_auth": config.require_api_key,
        "ai_enabled": ai_on,
        "ai_model": os.environ.get("AI_MODEL", "") if ai_on else "",
    }


@app.post("/api/v1/analyses", status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(
    video: UploadFile = File(...),
    _: str = Depends(require_api_key),
) -> dict:
    # 扩展名检查
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in config.allowed_extensions:
        raise HTTPException(status_code=400, detail=f"只支持 {config.allowed_extensions}")

    # 保存上传文件到临时目录（随机名防冲突）
    tmp_name = f"{uuid.uuid4().hex}{suffix}"
    tmp_path = config.upload_temp_dir / tmp_name
    max_bytes = config.max_upload_mb * 1024 * 1024
    total = 0
    try:
        with open(tmp_path, "wb") as out:
            while chunk := await video.read(1 << 20):
                total += len(chunk)
                if total > max_bytes:
                    out.close()
                    tmp_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=f"文件超过 {config.max_upload_mb}MB")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"上传失败: {exc}") from exc

    # 创建 analysis 目录（空 metadata，等后台任务填）
    store = AnalysisStore()
    analysis_id, analysis_dir = store.create()
    store.update_metadata(analysis_id, status="RUNNING", stage="QUEUED", error=None)

    # 提交后台任务（立即返回，不等待分析完成）
    get_executor(config.max_concurrent).submit(run_analysis_task, analysis_id, tmp_path)

    return {
        "analysis_id": analysis_id,
        "status": "RUNNING",
        "stage": "QUEUED",
        "detail": "任务已提交，用 GET /api/v1/analyses/{analysis_id} 查询进度",
    }


@app.get("/api/v1/analyses")
def list_analyses(
    _: str = Depends(require_api_key),
) -> dict:
    """列出全部分析任务（按创建时间倒序），供历史页使用。"""
    store = AnalysisStore()
    items = store.list_analyses()
    return {"count": len(items), "analyses": items}


@app.get("/api/v1/analyses/{analysis_id}")
def get_analysis_status(
    analysis_id: str,
    _: str = Depends(require_api_key),
) -> dict:
    validate_analysis_id(analysis_id)
    payload = read_task_status(analysis_id)
    if not payload:
        raise HTTPException(status_code=404, detail="analysis 不存在")
    return payload


@app.get("/api/v1/analyses/{analysis_id}/result")
def get_analysis_result(
    analysis_id: str,
    _: str = Depends(require_api_key),
) -> dict:
    validate_analysis_id(analysis_id)
    payload = build_result_payload(analysis_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="analysis 不存在")
    return payload


@app.get("/api/v1/analyses/{analysis_id}/files/{filename}")
def download_file(
    analysis_id: str,
    filename: str,
    _: str = Depends(require_api_key),
):
    from fastapi.responses import FileResponse

    validate_analysis_id(analysis_id)
    store = AnalysisStore()
    paths = store.paths(analysis_id)
    target = safe_join_analysis_file(paths.analysis_dir, filename)
    media_type = "video/mp4" if target.suffix == ".mp4" else "application/octet-stream"
    return FileResponse(target, media_type=media_type, filename=target.name)


# ============================================================
# 前端托管：React build 产物（frontend/dist）由同一服务提供
# 访问 http://host:8000/ 即新 UI；/api、/health 仍为接口
# ============================================================
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

if FRONTEND_DIST.exists():
    _assets = FRONTEND_DIST / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # API / 健康检查路径即使没匹配到具体路由，也返回 404 JSON，绝不返回前端页面
        if full_path.startswith("api/") or full_path in {"health", "docs", "openapi.json"}:
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Not Found"}, status_code=404)

        # 已注册的具体路由不会进入这里
        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            try:
                candidate.relative_to(FRONTEND_DIST.resolve())
                if candidate.is_file():
                    return FileResponse(candidate)
            except ValueError:
                pass
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def no_frontend():
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {
                "detail": "前端尚未构建。请先运行: cd frontend && npm install && npm run build",
                "api_docs": "/docs",
            }
        )
