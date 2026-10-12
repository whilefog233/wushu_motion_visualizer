# 武术 AI 教练系统 · 一键启动（Windows）
# 作用：首次自动构建前端，然后启动统一服务（新 UI + API，同一端口）

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# 1. 前端依赖与构建（仅首次 / 前端有改动时）
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "安装前端依赖..." -ForegroundColor Cyan
    Push-Location frontend; npm install; Pop-Location
}
if (-not (Test-Path "frontend\dist")) {
    Write-Host "构建前端..." -ForegroundColor Cyan
    Push-Location frontend; npm run build; Pop-Location
}

# 2. 启动统一服务（FastAPI 托管新 UI + API）
# 优先使用依赖齐全的虚拟环境，避免误用 PATH 上缺依赖的 Python
$candidates = @(
    Join-Path $root ".venv\Scripts\python.exe",
    "C:\Users\27947\kungfu_venv\Scripts\python.exe"
)
$py = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) { $py = "python" }

Write-Host "使用 Python: $py" -ForegroundColor DarkGray
Write-Host "启动服务：http://127.0.0.1:8000" -ForegroundColor Green
& $py -m uvicorn api.main:app --host 127.0.0.1 --port 8000
