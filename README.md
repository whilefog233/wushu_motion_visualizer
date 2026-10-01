# wushu_motion_visualizer

基于 `MediaPipe Pose + OpenCV + Streamlit` 的本地武术动作骨架可视化与**技术诊断**系统。

这个项目的定位很明确：

- 不是 AI 自动武术教练
- 不是自动评分系统
- 不是动作对错自动判断系统
- 不是肌电或医学诊断系统

它的核心目标是让教练、训练者在同一界面里同时观察：

- 原始视频或摄像头画面
- 骨架变化
- 角度、速度、重心、轨迹、`motion_intensity`
- 轻量版肌肉参与度可视化结果
- **V3 技术诊断**：直拳的发力链时序、常见错误模式与训练建议（解释"为什么"，不打综合分）

所有动作质量判断仍然交给人类教练完成。

---

## V2 架构（第一阶段重构）

> 详细重构说明见 [REFACTOR_REPORT.md](./REFACTOR_REPORT.md)。

V2 核心变化：

- **一次姿态推理**：同一个视频 / 同一个 `analysis_id` 默认只执行一次完整 MediaPipe Pose，产出统一 `pose.json`，骨架 / 指标 / 肌肉 / 发力链 / AI Coach 全部复用。
- **统一 analysis_id**：每次分析生成唯一 `analysis_id`，所有结果统一保存到 `data/analyses/{analysis_id}/`（source.mp4 / metadata.json / pose.json / metrics.csv / analysis.json / muscle.json / power_chain.json / coach_input.json / performance.json / exports/）。
- **UI 与核心算法分离**：核心引擎在 `src/`（`src/analysis/pipeline.py::analyze_video()`），完全脱离 Streamlit，输入输出只用普通 Python 类型。
- **分析与视频导出分离**：默认只生成数据，不生成完整 MP4；`export_skeleton_video(analysis_id)` / `export_muscle_video(analysis_id)` 按需导出。
- **独立 Worker**：`python worker.py --input xxx.mp4` 可脱离 Streamlit 完整分析。
- **AI Coach 预留**：`src/coach/` 输出结构化 `coach_input.json`，未来直接喂给 GPT / Gemini。
- **进度状态机**：PREPARING → EXTRACTING_POSE → … → COMPLETED / FAILED，UI 与未来网站共用。
- **阶段缓存与错误恢复**：已完成的阶段（带算法版本）重跑直接复用；失败保留已生成数据。

```bash
# 独立分析（无需启动 Streamlit）
python worker.py --input data/input/xxx.mp4 --export-skeleton --json
```

---

## V3 技术诊断引擎（第二阶段）

> 详细说明见 [V3_REPORT.md](./V3_REPORT.md)。

V3 把系统从"动作数据可视化"升级为**武术技术诊断系统**，第一版只重点支持**直拳 / 冲拳**：

- **动作阶段识别**：准备 → 启动 → 加速 → 最大伸展/击打 → 回收，由关键事件对自动切分。
- **关键事件与发力链时序**：髋/肩/腕启动、髋/肩/肘峰值、腕速峰值、最大伸展、回收、结束；重点分析 **髋→肩→肘→腕** 的毫秒间隔，而不是只看数值大小。
- **错误模式库**：肩启动过早、髋参与不足、手臂主导发力、发力链顺序混乱、肘部外翻、身体过度前冲、末端速度不足、回收过慢、头部晃动过大、动作稳定性差、左右侧差异。每条诊断都带 `问题 / 严重度 / 置信度 / 证据 / 含义 / 训练建议`。
- **参考系统**：Self Baseline（最近 N 次直拳滚动基线）、Personal Best、Expert Template（预留接口）。**不写死绝对标准**，无可靠依据时只输出结构规则并标注实验性质。
- **AI Coach 预留**：诊断结果合并进 `coach_input.json`，未来 GPT/Gemini 只负责把结构化诊断翻译成教练语言，不自己判断动作。

直拳分析产物落在 `data/analyses/{analysis_id}/technique/straight_punch.json`，页面上"直拳技术诊断"区块展示本次最值得改的 3 个问题与本轮最重要的一件事。

---

## 项目定位

### 这是一个什么系统

`wushu_motion_visualizer` 是一个面向武术训练场景的动作观察工具，适合：

- 刀术、剑术、拳术、棍术等套路视频回看
- 教练逐帧检查步型、身法、手法
- 本地摄像头实时辅助观察
- 后续扩展为云端视频上传分析工具

### 它不做什么

本项目当前版本明确不做：

- 自动评分
- 自动判断动作标准或不标准
- 真实肌肉发力识别
- 真实呼吸识别
- 生物力学精确肌电建模
- OpenSim 逆动力学真值模拟

---

## 当前功能

### 1. 视频分析

上传 `mp4` 视频后，系统会：

1. 逐帧做人体姿态识别（同一 `analysis_id` 只跑一次 MediaPipe，结果复用）
2. 显示原视频 / 骨架对比结果
3. 提供逐帧滑块查看
4. 显示当前帧角度、速度、重心、峰值、峰值时间等指标
5. 输出可选导出文件（骨架视频 / 肌肉可视化视频按需导出，不默认生成 MP4）

> 同一个视频重复上传会按内容指纹自动命中已有分析，直接打开历史结果，不再重复识别。

### 2. 实时摄像头

本机摄像头实时运行时，系统会：

1. 打开默认摄像头或指定索引摄像头
2. 左边显示原始画面
3. 右边显示骨架画面
4. 实时刷新 FPS 和当前帧数据
5. 支持短轨迹残影
6. 支持截图保存当前帧

### 3. 肌肉运动可视化分析

新增独立页面：`武术动作肌肉运动可视化分析`

这个页面会重新处理上传视频，并生成：

- 左侧原视频
- 右侧肌肉参与度可视化视频
- 每帧主要肌群参与度 CSV
- TOP 3 激活肌群
- 发力链提示
- 峰值时刻分析

当前肌群参与度是基于姿态与运动学特征的轻量启发式估计，不是 EMG，不是医学诊断。

页面内会明确显示免责声明：

> 本功能基于姿态识别与运动学特征估计肌肉参与度，不代表真实肌电信号或医学诊断结果。

---

## 当前展示的指标

### 角度类

- 左肩角度
- 右肩角度
- 左肘角度
- 右肘角度
- 左髋角度
- 右髋角度
- 左膝角度
- 右膝角度
- 左踝角度
- 右踝角度
- 躯干倾斜角

### 位置类

- 髋部中心坐标
- 髋部高度
- 双脚距离
- 肩宽
- 两手距离
- 粗略重心位置

### 速度类

- 左手腕速度
- 右手腕速度
- 左脚踝速度
- 右脚踝速度
- 髋部中心速度

### 时序导数类

- 左膝角速度
- 右膝角速度
- 左肘角速度
- 右肘角速度
- 髋部角速度
- 躯干角速度
- 左膝角加速度
- 右膝角加速度
- 左肘角加速度
- 右肘角加速度

### 峰值类

- 左手腕速度峰值
- 右手腕速度峰值
- 左脚踝速度峰值
- 右脚踝速度峰值
- 髋部速度峰值
- 躯干角速度峰值

### 峰值时间类

- 手腕峰值时间
- 脚踝峰值时间
- 髋部峰值时间
- 躯干峰值时间

### 趋势类

- `motion_intensity`
- `Kinetic Chain Stage`

说明：

- `Kinetic Chain Stage` 当前是启发式时序标签
- 它表示动作更像是下肢驱动、髋部传递、躯干连接还是上肢释放
- 它不是对“真实力量传导”的精确测量

### 肌肉参与度类

当前轻量版肌肉参与度可视化估计以下 8 组肌群：

- `quadriceps` 股四头肌
- `hamstrings` 腘绳肌
- `glutes` 臀肌
- `calves` 小腿三头肌
- `erector_spinae` 竖脊肌
- `obliques` 腹斜肌
- `deltoids` 三角肌
- `forearms` 前臂肌群

---

## 主要参数的计算方式

### 1. 关键点来源

系统基于 `MediaPipe Pose` 提取 33 个人体关键点。

每帧关键点包含：

- 归一化坐标：`x / y / z`
- 可见性：`visibility`
- 像素坐标：`pixel_x / pixel_y`

后续大部分计算都基于像素坐标完成。

### 2. 角度计算

统一使用：

```python
calculate_angle(point_a, point_b, point_c)
```

含义：以 `point_b` 为顶点，计算 `a-b-c` 的夹角。

例如：

- 左肘角度：`left_shoulder - left_elbow - left_wrist`
- 左膝角度：`left_hip - left_knee - left_ankle`

如果任意点缺失、异常或重合，则返回 `NaN`。

### 3. 躯干倾斜角

步骤：

1. 计算肩部中心点
2. 计算髋部中心点
3. 构造髋部中心指向肩部中心的向量
4. 计算该向量相对竖直方向的偏转角

得到：

- `torso_tilt_angle`

### 4. 速度计算

速度来自相邻帧关键点位移：

```text
speed = distance(current_point, previous_point) * fps
```

当前单位：

- `px/s`

它适合看相对变化和节奏，不等于真实世界绝对速度。

### 5. 角速度

角速度来自角度差分：

```text
angular_velocity = (current_angle - previous_angle) * fps
```

单位可理解为：

- `deg/s`

### 6. 角加速度

角加速度来自角速度差分：

```text
angular_acceleration = (current_angular_velocity - previous_angular_velocity) * fps
```

单位可理解为：

- `deg/s²`

### 7. 粗略重心估计

当前版本不是精确质心模型，而是视觉关键点粗略估计：

- 优先使用左右肩、左右髋的加权中心
- 如果这些点不全，则退化为所有可见关键点的平均中心

输出字段：

- `center_of_mass_x`
- `center_of_mass_y`

### 8. motion_intensity

公式：

```text
motion_intensity =
0.25 * left_wrist_speed +
0.25 * right_wrist_speed +
0.20 * left_ankle_speed +
0.20 * right_ankle_speed +
0.10 * hip_center_speed
```

它表示“运动强度趋势”，不是肌肉发力值。

### 9. 肌肉参与度估计

当前肌肉可视化页面使用启发式规则估计参与度，范围统一限制在 `0.0 ~ 1.0`。

当前主要规则包括：

- 膝关节伸展速度高，`quadriceps` 增强
- 膝关节屈曲趋势增强时，`hamstrings` 增强
- 髋关节伸展速度高，`glutes` 增强
- 踝部角速度或脚踝速度高，`calves` 增强
- 躯干旋转速度高，`obliques` 增强
- 躯干屈伸速度高，`erector_spinae` 增强
- 肩关节角速度高，`deltoids` 增强
- 手腕速度高，`forearms` 增强

请注意：

- 这只是教学可视化版本
- 不是肌电信号
- 不是医学肌肉激活测量

---

## 页面说明

### 视频分析页面

包含：

- 输入区
- 分析结果视频播放器
- 当前帧滑块
- 当前帧原图和骨架图
- 当前帧数据面板
- 曲线图
- 轨迹图
- 导出区

### 实时摄像头页面

包含：

- 开始 / 停止摄像头
- 摄像头索引选择
- 是否显示短轨迹残影
- 原始画面
- 骨架画面
- 实时数据面板
- 最近几秒趋势图

### 肌肉运动可视化页面

包含：

- 视频上传或本地视频选择
- 开始肌肉可视化分析按钮
- 左侧原视频
- 右侧肌肉参与度可视化视频
- 主要参与肌群统计表
- 发力链分析
- 峰值时间点分析
- CSV 下载按钮

### 关于系统页面

包含：

- 系统定位
- 指标计算方式
- 数据在训练观察中的作用
- 云服务器部署建议

---

## 项目结构

```text
wushu_motion_visualizer/
  app.py
  worker.py                # V2：独立命令行分析入口
  requirements.txt
  README.md
  THIRD_PARTY_NOTICES.md
  REFACTOR_REPORT.md       # V2：重构报告
  configs/
    default.yaml
  src/
    models/                # V2：PoseResult / AnalysisStatus / AnalysisStage
      pose_result.py
      analysis.py
    pose/
      mediapipe_backend.py
      extractor.py         # V2：统一 PoseExtractor（MediaPipe 只跑一次）
    analysis/
      kinematics.py
      metrics.py
      motion_intensity.py
      smoothing.py
      scale_normalization.py  # V2：normalized/world 速度
      power_chain.py          # V2：发力链分析
      muscle.py               # V2：纯数据肌肉分析
      pipeline.py             # V2：统一 AnalysisPipeline
    video/
      offline_processor.py    # 兼容层（委托 pipeline）
      realtime_processor.py
      video_player.py
      video_reader.py         # V2：统一视频读取
    visualization/
      draw_pose.py
      draw_dashboard.py
      charts.py
    export/
      exporters.py
      skeleton_video.py       # V2：按需导出骨架视频
      muscle_video.py         # V2：按需导出肌肉视频
    coach/
      coach_input.py          # V2：AI Coach 结构化输入
    technique/                # V3：直拳技术诊断引擎
      engine.py               #   analyze_technique 主入口
      profiles.py             #   直拳 TechniqueProfile（阶段/事件/错误模式）
      signals.py / events.py / phases.py / timing.py
      errors.py               #   11 种错误模式诊断
      references.py            #   Self Baseline / PB / Expert Template
      models.py
    storage/
      analysis_store.py       # V2：统一 analysis 目录管理
    utils/
      paths.py
      video_utils.py
      time_utils.py
  muscle_analysis/
    __init__.py
    muscle_estimator.py
    muscle_renderer.py
    video_muscle_pipeline.py  # 兼容层（委托 pipeline）
    opensim_adapter.py
  pages/
    02_muscle_visualizer.py
  data/
    input/
    output/               # 旧结果（只读兼容）
    analyses/             # V2：统一分析结果 data/analyses/{analysis_id}/
    cache/
  outputs/
    muscle_visualized/
  tests/
    test_kinematics.py
    test_kinetic_chain.py
    test_motion_metrics.py
    test_pipeline_v2.py   # V2：集成测试
```

---

## 安装

推荐环境：

- Windows 11
- Python `3.10` 或 `3.11`

### 部署步骤

```bash
# 1. 克隆仓库
git clone https://github.com/whilefog233/wushu_motion_visualizer.git
cd wushu_motion_visualizer

# 2. 创建虚拟环境（关键：路径必须纯英文，不能有中文）
#    项目在 D 盘，venv 也放 D 盘纯英文路径
python -m venv D:\kungfu_venv

# 3. 激活虚拟环境
D:\kungfu_venv\Scripts\activate

# 4. 安装依赖
python -m pip install -r requirements.txt
```

> **重要**：MediaPipe 在中文/非 ASCII 路径下初始化会失败。
> 项目目录可以有中文，但**虚拟环境必须建在纯英文路径**（如 `D:\kungfu_venv`），不要建在项目目录里。

如果你的 `pip` 启动器异常，优先使用 `python -m pip`，不要直接使用 `pip install`。

---

## 运行

本地启动：

```bash
python -m streamlit run app.py
```

如果终端输出了：

```text
http://0.0.0.0:8501
```

请不要直接在浏览器访问 `0.0.0.0`。本机正确访问方式是：

- [http://localhost:8501](http://localhost:8501)
- [http://127.0.0.1:8501](http://127.0.0.1:8501)

---

## 输出文件

### V2：统一分析结果（推荐）

V2 起，视频分析结果统一保存在：

```text
data/analyses/{analysis_id}/
  source.mp4            # 源视频（优先硬链接，省磁盘）
  metadata.json         # analysis_id / 原始文件名 / 创建时间 / 视频信息 / 状态 / 阶段 / 算法版本
  pose.json             # 统一姿态结果（fps / frame_count / width / height / duration / timestamps /
                        #   landmarks / visibility / normalized_landmarks / world_landmarks）
  metrics.csv           # 逐帧指标（旧指标 + normalized/world 速度 + 身体尺度）
  analysis.json         # 汇总（summary / normalized_speed / muscle / power_chain）
  muscle.json           # 肌肉统计（8 组肌群 + 峰值时刻 + 主导发力链提示）
  muscle_metrics.csv    # 逐帧肌肉参与度
  power_chain.json      # 发力链阶段分布与提示
  coach_input.json      # AI Coach 结构化输入（未来喂给 GPT / Gemini）
  performance.json      # 性能统计（各阶段耗时 / FPS）
  summary.md            # 文本摘要（兼容旧输出）
  exports/              # 按需导出的视频（默认分析不生成 MP4）
    skeleton_video.mp4
    muscle_video.mp4
```

### 旧版视频分析输出（兼容保留）

视频分析完成后，结果保存在：

```text
data/output/video_analysis_时间戳/
```

主要输出包括：

- `side_by_side_video.mp4`
- `keypoints.json`
- `metrics.csv`
- `summary.json`
- `summary.md`

### 实时截图输出

实时截图保存到：

```text
data/output/camera_snapshot_时间戳/screenshots/
```

### 肌肉可视化输出

肌肉可视化页面完成后，结果保存在：

```text
outputs/muscle_visualized/
```

主要输出包括：

- `xxx_时间戳_muscle_visualized.mp4`
- `xxx_时间戳_muscle_metrics.csv`
- `xxx_时间戳_muscle_visualized_summary.json`

CSV 主要字段包括：

- `frame`
- `time_sec`
- `quadriceps`
- `hamstrings`
- `glutes`
- `calves`
- `erector_spinae`
- `obliques`
- `deltoids`
- `forearms`
- `top1_muscle`
- `top2_muscle`
- `top3_muscle`
- `power_chain_hint`

---

## 云服务器部署建议

### 推荐先部署什么

优先部署“视频上传分析”版本。

这条路径最稳：

1. 用户上传 `mp4`
2. 服务端离线处理
3. 返回分析页面和导出文件

### 启动命令

```bash
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

### 服务器侧建议

- 使用 `Nginx` 反向代理
- 放行对应公网端口
- 限制上传文件大小
- 定期清理 `data/output` 和 `outputs/muscle_visualized`
- 如果并发提高，再把分析任务移到后台队列

### 为什么当前不建议直接把实时摄像头模式开放给公网用户

当前实时模式使用：

```python
cv2.VideoCapture(0)
```

这读取的是服务器本机摄像头，不是访问者浏览器摄像头。

所以：

- 本地运行没有问题
- 公网多人访问时不适合直接沿用当前实现

如果以后要做“浏览器直接打开自己摄像头实时分析”，需要改成：

1. 浏览器采集摄像头
2. 前端上传图像帧或视频流
3. 服务端推理
4. 页面回传结果

---

## 第三方参考与许可证

本项目新增的肌肉可视化模块遵循“只参考兼容许可证项目思路，不复制不明许可证代码”的原则。

当前仓库中新增了：

- [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)

其中记录了：

- OpenCap 相关项目
- OpenSim Core
- MediaPipe

以及本项目当前对这些项目的使用边界说明。

---

## 注意事项

- 单帧出现 `NaN` 通常表示该帧关键点检测不稳定，不代表动作错误
- `px/s` 适合看相对快慢，不是绝对物理速度
- `center_of_mass_x / center_of_mass_y` 是粗略估计，不是真实质心
- `motion_intensity` 不是肌肉发力值
- `Kinetic Chain Stage` 不是精确力量传导测量
- 肌肉参与度可视化不是肌电，不是医学结论

---

## 常见问题

### 为什么浏览器里有时视频能加载但不能播放

浏览器对 `mp4` 编码兼容性比较敏感。当前版本会优先尝试转为浏览器更友好的 `H.264`。

### 为什么有些帧没有数值

因为关键点可能短暂丢失，系统会返回 `NaN` 或“未检测到”，而不是崩溃。

### 为什么没有自动评分

这是有意为之。当前版本优先做稳定的骨架和运动数据可视化，动作质量判断仍交给教练。

### 为什么 `0.0.0.0:8501` 打不开

因为 `0.0.0.0` 是服务绑定地址，不是浏览器访问地址。请改用：

- `http://localhost:8501`
- `http://127.0.0.1:8501`

### 为什么肌肉可视化看起来不像医学软件

因为这版设计目标就是“教学观察可视化”，不是医学解剖重建，也不是 OpenSim 逆动力学结果。

---

## 后续可扩展方向

- 更好的任务历史管理页面
- 峰值时序链路图
- 更清晰的动力链趋势可视化
- 云端视频任务队列
- 浏览器端摄像头实时分析架构
- 预留 OpenSim / OpenCap 适配层的进一步接入
