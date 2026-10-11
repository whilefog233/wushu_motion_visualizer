"""API 冒烟测试：不依赖真实视频，只验证接口契约和安全。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("KUNGFU_API_KEY", "testkey")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_auth_required():
    r = client.get("/api/v1/analyses/nonexistent")
    assert r.status_code == 401


def test_wrong_key():
    r = client.get("/api/v1/analyses/nonexistent", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_bad_analysis_id_format():
    r = client.get(
        "/api/v1/analyses/..%2Fetc%2Fpasswd",
        headers={"X-API-Key": "testkey"},
    )
    assert r.status_code in (400, 404)


def test_nonexistent_analysis_404():
    r = client.get(
        "/api/v1/analyses/20990101_000000_ab12cd34",
        headers={"X-API-Key": "testkey"},
    )
    assert r.status_code == 404


def test_upload_rejects_bad_extension():
    # 直接用字节内容构造上传，不依赖系统临时目录
    r = client.post(
        "/api/v1/analyses",
        files={"video": ("test.txt", b"not a video", "text/plain")},
        headers={"X-API-Key": "testkey"},
    )
    assert r.status_code == 400
