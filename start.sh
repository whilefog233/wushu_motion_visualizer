#!/usr/bin/env bash
# 武术 AI 教练系统 · 一键启动（Linux / macOS）
set -e
cd "$(dirname "$0")"

if [ ! -d "frontend/node_modules" ]; then
  echo "安装前端依赖..."
  (cd frontend && npm install)
fi
if [ ! -d "frontend/dist" ]; then
  echo "构建前端..."
  (cd frontend && npm run build)
fi

echo "启动服务：http://127.0.0.1:8000"
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python"
fi
$PY -m uvicorn api.main:app --host 127.0.0.1 --port 8000
