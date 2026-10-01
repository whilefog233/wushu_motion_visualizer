# 武术 AI 教练系统 V2 — 第一阶段重构报告

> 重构目标：把 Streamlit 项目下的“武术动作分析引擎”抽出来，做到——
> 一次姿态推理、多模块复用、结果缓存、统一 analysis_id、
> 分析与视频导出分离、UI 与核心算法分离、支持独立 Worker、
> 为 Web Site + Python Worker + AI Coach 预留接口。
>
> 本阶段未做：重写实时摄像头、接入 GPT/Gemini、大规模重做 UI、登录注册、
> 数据库、迁移 Vercel、Docker/Kubernetes、微服务。

---

## 1. 原来的架构是什么

```
Streamlit app.py / pages/02_muscle_visualizer.py
   │
   ├─ OfflineVideoProcessor.process()
   │     读视频 → MediaPipe → 逐帧指标 → 汇总 → 拼接骨架 MP4 → FFmpeg 转码
   │     输出散落在 data/output/video_analysis_*/（keypoints.json / metrics.csv / summary.json / mp4）
   │
   └─ muscle_analysis.video_muscle_pipeline.process_muscle_video()
         读视频 → 重新初始化 MediaPipe → 重新推理 → 肌肉估计 → 肌肉可视化 MP4
         参数 reuse_existing_pose 被 `del` 直接丢弃，从不复用姿态（bug）
```

主要问题：

1. **同一视频被 MediaPipe 重复推理**：视频分析跑一次，肌肉页再跑一次，各自初始化 Pose 对象。
2. **`reuse_existing_pose` 是假参数**：`muscle_analysis/video_muscle_pipeline.py` 里该参数被 `del` 丢弃，代码虽提供了参数却永远重新执行 MediaPipe。
3. **结果散落**：不同模块往 `data/output/*` 随意建目录，无统一 analysis_id，无元数据。
4. **UI 与算法耦合**：Streamlit 页面内直接堆 MediaPipe、OpenCV、指标/肌肉计算，核心逻辑无法脱离 Streamlit 单独运行。
5. **默认生成完整 MP4**：分析默认跑“读帧 → MediaPipe → 画骨架 → 拼接 → MP4 → FFmpeg 转码”，非常耗 CPU/磁盘/时间，即使只是想要数据。
6. **反复打开视频**：同一流程里多次 `VideoCapture() → seek → read → release`，再重新打开。
7. **反复转码**：每次导出都无脑 FFmpeg 二次编码。
8. **速度指标只有 px/s**：受人物离摄像头远近影响，无归一化/世界坐标口径。
9. **无进度状态机**：无 PREPARING / EXTRACTING_POSE / … / COMPLETED / FAILED 的统一状态。
10. **失败即全丢**：分析中途失败，之前已完成的数据不保留，重跑全量重来。

---

## 2. 新的架构是什么

```
上传视频 / 本地视频 / data/input
        │
        ▼
analyze_video(video_path)   ← src/analysis/pipeline.py（核心入口，不依赖 Streamlit）
        │
        ├─ PREPARING             准备 analysis 目录、复制源视频、写 metadata
        ├─ EXTRACTING_POSE       MediaPipe 只执行一次 → PoseResult → pose.json
        ├─ CALCULATING_METRICS   逐帧指标 + 归一化/世界速度 → metrics.csv
        ├─ ANALYZING_MUSCLE      复用 pose/metrics → muscle.json + muscle_metrics.csv
        ├─ ANALYZING_POWER_CHAIN 发力链 → power_chain.json
        ├─ BUILDING_RESULT       analysis.json
        └─ SAVING_RESULTS        performance.json / summary.md / coach_input.json / COMPLETED
        │
        ▼
data/analyses/{analysis_id}/
   ├─ source.mp4  metadata.json  pose.json  metrics.csv  analysis.json
   ├─ muscle.json  muscle_metrics.csv  power_chain.json  coach_input.json
   ├─ performance.json  summary.md
   └─ exports/          ← 只有用户主动“导出”才生成 MP4
        ├─ skeleton_video.mp4
        └─ muscle_video.mp4
```

外部接口：

- `worker.py --input xxx.mp4 [--export-skeleton] [--export-muscle] [--analysis-id ...] [--force]`
  完全脱离 Streamlit 运行，输出 JSON（analysis_id / status / performance）。
- `export_skeleton_video(analysis_id)` / `export_muscle_video(analysis_id)`：按需导出视频。
- `build_coach_context(analysis_id)`：输出未来 AI Coach 的结构化输入 coach_input.json。
- `load_analysis_result(analysis_id)`：只读加载已有结果（历史回看 / 网站层复用）。
- Streamlit app.py 只做：上传、启动、显示进度、读结果、画图表、展示关键帧、调用导出。

进度状态机（`src/models/analysis.py`）：

```
PREPARING → EXTRACTING_POSE → CALCULATING_METRICS → ANALYZING_MUSCLE
→ ANALYZING_POWER_CHAIN → BUILDING_RESULT → SAVING_RESULTS → COMPLETED
任意失败 → FAILED（保留已生成数据）
```

---

## 3. 修改了哪些文件

| 文件 | 改动 |
|---|---|
| `src/utils/paths.py` | 新增 `ANALYSES_DIR`（data/analyses） |
| `src/pose/mediapipe_backend.py` | `process()` 增加 `world_landmarks` 输出（不破坏旧键） |
| `src/analysis/metrics.py` | 新增 `hip_width`、`torso_length`、`torso_rotation_angle/velocity`、踝/肩角速度、髋角加速度等扩展指标 |
| `src/video/offline_processor.py` | 重写为兼容层：`process()` 委托 `AnalysisPipeline`，保留旧返回 dict 键 |
| `muscle_analysis/video_muscle_pipeline.py` | 重写为兼容层：委托 pipeline + `export_muscle_video`；`reuse_existing_pose` 参数保留仅为兼容，V2 默认即复用姿态 |
| `muscle_analysis/__init__.py` | `process_muscle_video` 改为延迟导入（打破循环依赖） |
| `app.py` | 视频分析页改为调用 `analyze_video` + `load_analysis_result`；新增历史分析选择、归一化速度图、按需导出按钮；实时摄像头页/关于页保留 |
| `pages/02_muscle_visualizer.py` | 改为复用统一 pipeline；移除重复 `set_page_config`；视频可视化改为按需导出 |
| `configs/default.yaml` | 新增 `pipeline` 配置段、`store_world_landmarks`、默认不导出视频 |
| `requirements.txt` | 固定 `mediapipe==0.10.14`、`streamlit<1.40`、`protobuf>=4.25.3,<5`；注明中文路径需用 ASCII 路径虚拟环境 |
| `README.md` | 补充 V2 结构说明（见文末） |

## 4. 新增了哪些文件

| 文件 | 作用 |
|---|---|
| `src/models/pose_result.py` | `PoseResult` dataclass：fps/frame_count/width/height/duration/timestamps/landmarks/visibility/normalized_landmarks/world_landmarks/algorithm_version，含 to_dict/from_dict/save/load |
| `src/models/analysis.py` | `AnalysisStatus` / `AnalysisStage` / `AnalysisResult` / `STAGE_ORDER` |
| `src/video/video_reader.py` | `VideoReader`：一个流程只打开一次 VideoCapture，顺序迭代/按帧跳读复用 |
| `src/pose/extractor.py` | `PoseExtractor`：单次完整 MediaPipe 推理 → PoseResult（`POSE_ALGORITHM_VERSION` 控制缓存失效） |
| `src/storage/analysis_store.py` | `AnalysisStore` / `AnalysisPaths`：统一 analysis 目录、metadata 读写、同源姿态复用查找 |
| `src/analysis/scale_normalization.py` | 身体尺度归一化：`body_scale_px`（肩宽/髋宽/躯干长度中位数）、`*_normalized`、`*_world` 速度 |
| `src/analysis/power_chain.py` | 发力链打分/提示/阶段分布（`score_power_chain` / `hint_from_scores` / `analyze_power_chain`） |
| `src/analysis/muscle.py` | 纯数据肌肉分析（复用 `MuscleEngagementEstimator`，不跑 MediaPipe） |
| `src/analysis/pipeline.py` | `AnalysisPipeline` + `analyze_video()` + `load_analysis_result()` |
| `src/export/skeleton_video.py` | `export_skeleton_video(analysis_id)` |
| `src/export/muscle_video.py` | `export_muscle_video(analysis_id)` |
| `src/coach/coach_input.py` | `CoachInput` dataclass + `build_coach_context(analysis_id)` |
| `worker.py` | 命令行独立入口 |
| `tests/test_pipeline_v2.py` | V2 集成测试（14 项） |
| `REFACTOR_REPORT.md` | 本报告 |

## 5. 删除了哪些重复逻辑

- **重复 MediaPipe 初始化/推理**：骨架分析、肌肉分析、发力链不再各自初始化 Pose 对象；统一走 `PoseExtractor`（每个 analysis 一次）。
- **假参数 `reuse_existing_pose`**：旧代码里 `del reuse_existing_pose` 从不生效；新管线默认按 (源视频签名 + 姿态算法版本) 复用 pose.json。
- **重复视频读取**：新增 `VideoReader`，pose 提取、指标计算、视频导出都复用同一个 capture 对象；UI 逐帧检查用 `read_at` 单次跳读。
- **无意义二次编码**：导出时仅当 FFmpeg 可用才转码 H.264（浏览器兼容），否则保留 mp4v 输出；分析阶段不再默认转码。
- **散落的输出路径逻辑**：统一收敛到 `data/analyses/{analysis_id}/`，由 `AnalysisPaths` 单一来源提供路径。
- **循环依赖**：`muscle_analysis/__init__` 不再急切导入 `video_muscle_pipeline`（延迟加载）。
- **未使用导入**：清理 `skeleton_video.py` 等文件的 `cv2/numpy` 等无用导入。
- **尺寸对齐修复（测试中发现）**：`VideoReader.width/height` 原来记录源视频尺寸，而实际帧经过 `max_side` 缩放，导致 pose.json 记录的像素坐标空间与真实处理帧不一致（真实 1080p 视频下骨架导出会错位）。已改为 `width/height` 表示实际返回帧尺寸（新增 `source_width/source_height` 保留源信息），并用真实视频做了骨架像素落在帧内的对齐校验。

保留（兼容层，不删）：`OfflineVideoProcessor.process()` 旧 API、`process_muscle_video()` 旧 API、
`mediapipe_backend.MediaPipePoseBackend`（实时摄像头仍用它）、`data/output/*` 旧结果目录只读不动。

## 6. MediaPipe 如何实现“只分析一次”

```
analyze_video(video_path)
  └─ _extract_pose()
       1. 本 analysis 已有 pose.json 且算法版本一致          → 直接加载（same_analysis_cache）
       2. 同源视频（文件名+大小+mtime）已有 pose.json 且版本一致 → 复制该文件（analysis:<id> 复用）
       3. 否则 → PoseExtractor.extract() 单次完整推理 → 保存 pose.json
```

- 姿态算法版本 `POSE_ALGORITHM_VERSION = "2.0.0"`（`src/pose/extractor.py`）。
- 复用只复制文件，不做推理；`performance.json` 记录 `reuse_sources`。
- 测试证据：同一视频（全新副本）分析两次，`MediaPipe 执行次数 == 1`（`tests/test_pipeline_v2.py::test_same_video_mediapipe_runs_once`）。

## 7. 缓存机制如何工作

| 产物 | 缓存条件（缺一不可） | 失效条件 |
|---|---|---|
| pose.json | 文件存在 + metadata.stages.pose.completed + 算法版本一致 | `--force` 或版本变化或源视频签名变化 |
| metrics.csv | 文件存在 + stages.metrics.completed + 版本一致 | 同上 |
| muscle.json | 文件存在 + stages.muscle.completed + 版本一致 | 同上 |
| power_chain.json | 文件存在 + stages.power_chain.completed + 版本一致 | 同上 |

- 每个阶段完成即写 `metadata.json`（stages.{key}.completed/algorithm_version/duration_sec/reused/completed_at）。
- 失败时 `status=FAILED`、记录 `stage` 与 `error`，已生成产物全部保留；重跑同一 analysis_id 时从缓存继续。
- 测试证据：`test_same_analysis_id_reuses_all_cache`、`test_error_recovery_reuses_pose`。

## 8. performance.json 测试结果（真实视频）

测试视频：`data/input/20260424_123913_20230418_#刀术组合#武术.mp4`，1920×1080 / 30fps / 802 帧 / 26.7s。
姿态推理帧统一缩放到 1280×720（与 pose.json 像素坐标一致）。

```
analysis_id: 20261001_114115_c31f1496
video_length_sec:            26.7333
total_processing_time_sec:   21.3528
pose_inference_time_sec:     20.6143   ← 占 96.5%
metrics_calc_time_sec:        0.3620
muscle_analysis_time_sec:     0.2446
power_chain_time_sec:         0.0971
export_video_time_sec:       19.9008   （骨架视频导出，802 帧 2560×720，含对齐校验）
pose_processing_fps:         38.91
average_processing_fps:      37.56
reused_pose:                 false
```

合成测试视频（12 帧）二次分析：总耗时 0.08s（姿态全部复用），首次完整分析约 0.30s。

## 9. 当前最主要的性能瓶颈

1. **MediaPipe Pose CPU 推理（≈96% 分析耗时）**：26.7s 视频单线程推理约 20.9s（38fps）。
   - 迁移到服务器后可换 GPU/更小模型（model_complexity=0）或按帧抽取（如 15fps）分析。
2. **导出骨架视频（34.8s）**：纯 Python 逐帧画骨架 + OpenCV 编码 3840×1080。
   - 可降到 model_complexity=0 模型、输出更小分辨率、或导出时用 `--no-overlay`。
3. 肌肉/发力链/指标均为毫秒级（合计 <0.8s），不是瓶颈。

## 10. 第二阶段迁移到 Next.js / Vercel + Python Worker 还要改什么

当前已具备：`analyze_video()` 纯 Python 输入输出、`worker.py` CLI、统一分析目录、统一状态机、`coach_input.json`。

迁移清单：

1. **API 层**：Vercel Next.js 加 `/api/analyze`（上传 → 返回 analysis_id）、`/api/analysis/{id}`（读 analysis.json/coach_input.json）、`/api/export/{id}`（触发导出）。Python Worker 接收任务即可复用现有 pipeline。
2. **持久化**：把 `data/analyses/{id}` 落到对象存储（S3/R2）或数据库；`AnalysisStore` 目前是本地文件实现，需抽接口（已按目录/文件组织，便于替换）。
3. **异步任务**：Worker 当前是同步 `analyze_video()`；上线需套一层任务队列（如 Celery/ARQ/Cloud Tasks），把进度状态写回 metadata.json（状态机已就绪）。
4. **MediaPipe 部署**：服务端 CPU 推理可接受；高并发需 GPU 或切换 Tasks API（mediapipe.tasks，需下载 `.task` 模型文件）；当前 0.10.14 legacy API 在中文路径下会加载失败，部署路径保持 ASCII。
5. **实时摄像头**：公网场景改为浏览器端采集（WebRTC/MediaPipe JS）或推流到 Worker，再复用同一套指标逻辑（本阶段未动）。
6. **AI Coach**：`build_coach_context(analysis_id)` 已输出结构化 JSON，第二阶段直接把它喂给 GPT/Gemini，无需改分析引擎。
7. **视频存储**：上传转存/过期策略、导出任务排队，避免 Worker 重复转码。

---

## 附：如何运行

```bash
# 1) 创建虚拟环境（路径必须为纯 ASCII，mediapipe C++ 在中文路径下会失败）
python -m venv C:\Users\<你>\kungfu_venv
C:\Users\<你>\kungfu_venv\Scripts\pip install -r requirements.txt

# 2) 独立分析（不依赖 Streamlit）
C:\Users\<你>\kungfu_venv\Scripts\python worker.py --input data\input\xxx.mp4
C:\Users\<你>\kungfu_venv\Scripts\python worker.py --input data\input\xxx.mp4 --export-skeleton --json

# 3) Streamlit UI
C:\Users\<你>\kungfu_venv\Scripts\streamlit run app.py

# 4) 测试
C:\Users\<你>\kungfu_venv\Scripts\python -m pytest tests -q
```

> 本机测试环境：`C:\Users\27947\kungfu_venv`（Python 3.10.4 + mediapipe 0.10.14）。
> 全部 28 项测试通过（13 项旧测试 + 15 项 V2 测试）；Streamlit AppTest 页面级测试通过。
