# 武术 AI 教练系统（Kungfu AI Coach）

基于 **MediaPipe Pose + OpenCV + FastAPI + React** 的武术动作分析、技术诊断与训练指导系统。

视频上传后，系统**只执行一次**姿态推理，产出统一 `pose.json`，骨架 / 指标 / 肌肉 / 发力链 / 直拳技术诊断 / 评分全部复用该结果；AI 教练把结构化诊断翻译成可执行的训练建议。

---

## 快速开始

### 方式一：统一服务（新 UI + API，推荐）

需要 Python 3.10+、Node 18+。

```bash
# Windows
powershell -ExecutionPolicy Bypass -File start.ps1

# Linux / macOS
bash start.sh
```

然后打开 **http://127.0.0.1:8000**。

脚本会在首次运行时自动 `npm install`、构建前端，再启动 FastAPI（同一端口同时提供网页和 API）。

手动步骤等价于：

```bash
cd frontend && npm install && npm run build && cd ..
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

### 方式二：Streamlit（旧界面，保留可用）

```bash
pip install -r requirements.txt
python -m streamlit run app.py
# http://localhost:8501
```

---

## 使用流程

1. 网页点击「选择文件」上传出拳视频（MP4，<500MB）
2. 点击「开始分析」，页面实时显示 5 步进度（上传 → 姿态推理 → 发力链 → 技术诊断 → 生成结果）
3. 分析完成后：
   - 左侧播放原视频
   - 「姿态分析」：核心角度指标、骨架分析、关节角度趋势曲线
   - 「发力链诊断」：髋→肩→肘→腕时序图 + 逐条问题诊断（证据 / 含义 / 训练建议）
   - 「技术对比」：与参考标准逐项对照
   - 「AI 建议」：总评、本轮最重要一件事、下一轮训练计划
   - 底部环形评分与正误动作对比

默认**不生成骨架视频**（耗时），需要时通过 Streamlit 的导出功能按需生成。

---

## 目录结构

```
api/            FastAPI 后端（健康检查 / 上传建任务 / 状态轮询 / 结果 / 文件下载）
frontend/       React + Tailwind 前端（Vite）
  src/
    api/          前端 API 客户端
    components/   全部 UI 组件（视频区 / 骨架 / 图表 / 评分 / 诊断）
    data/         mock 数据（未接入后端时占位）
src/            核心分析引擎（可脱离 UI 独立运行）
  pose/           MediaPipe 一次推理、PoseResult
  analysis/       指标 / 肌肉 / 发力链 / Pipeline
  technique/      V3 直拳技术诊断（阶段 / 关键事件 / 11 类错误模式）
  coach/          V4 评分 + AI Coach
  storage/        统一 analysis_id 存储
  export/         骨架视频等按需导出
pages/          Streamlit 多页面（肌肉可视化等）
muscle_analysis 肌肉渲染
deploy/         阿里云部署文件（systemd / Nginx / Docker）
docs/           版本报告与治理文档
worker.py       命令行独立分析入口
start.ps1/sh    一键启动脚本
```

---

## 独立运行分析引擎

核心引擎不依赖任何 UI / Session State，输入输出均为普通 Python 类型：

```python
from src.analysis.pipeline import analyze_video

result = analyze_video("video.mp4")          # 完整分析，返回结构化结果
```

命令行：

```bash
python worker.py --input video.mp4           # 输出 analysis_id
```

---

## 结果存储

每次分析生成唯一 `analysis_id`，所有数据集中在 `data/analyses/{analysis_id}/`：

```
source.mp4  metadata.json  pose.json  metrics.csv  analysis.json
muscle.json  power_chain.json  coach_input.json  performance.json
technique/straight_punch.json  ai_coach.json  exports/
```

已存在且算法版本未变的阶段会自动复用缓存（如 `pose.json` 存在就不重跑 MediaPipe）。

---

## AI Coach 配置（可选）

默认关闭。未配置时系统照常完成分析与本地评分。所有配置从环境变量读取，密钥只在服务端：

```bash
AI_ENABLED=true
AI_API_KEY=sk-xxx
AI_BASE_URL=https://api.moonshot.cn/v1     # Kimi（OpenAI 兼容）
AI_MODEL=moonshot-v1-8k
```

AI 只负责**解释** V3 的结构化诊断，不自行判断动作对错；调用失败自动降级，不影响分析结果。

---

## API 摘要

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 服务状态与版本 |
| POST | `/api/v1/analyses` | 上传视频、创建任务（立即返回 analysis_id） |
| GET | `/api/v1/analyses/{id}` | 查询状态 / 进度 / 错误 |
| GET | `/api/v1/analyses/{id}/result` | 指标 / V3 诊断 / 评分 / 文件清单 |
| GET | `/api/v1/analyses/{id}/files/{name}` | 下载任务文件 |

交互式文档：启动后访问 `/docs`。

外部调用可通过环境变量 `KUNGFU_API_KEY` 启用 Key 认证；同源网页请求自动放行（密钥不进前端）。

---

## 能力边界

- 速度单位为 **px/s 或归一化单位**，不是真实 m/s；不测量真实拳力、肌电
- 无专家模板时，评分与对照是基于结构规则和个人基线的**实验性参考**，不代表权威标准
- 系统不做医学诊断，不替代专业教练，不保证一定得高分

---

## 文档

- `docs/V4_REPORT.md`：V4 架构、评分模型、AI Coach 输入输出
- `docs/V3_REPORT.md`：直拳分阶段、关键事件、错误模式
- `docs/REFACTOR_REPORT.md`：V2 一次推理 / 缓存机制
- `deploy/DEPLOY_ALIYUN.md`：阿里云 2 核 8G 部署
- `LICENSE`：许可证
