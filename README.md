# wushu_motion_visualizer

基于 `MediaPipe Pose + OpenCV + Streamlit` 的本地运行“武术动作骨架实时可视化分析系统”。

这个项目的目标很明确：  
不是做“AI 自动武术教练”，而是做一个**让教练和训练者同时观察原始动作、骨架变化和实时数据**的可视化分析工具。

系统重点是：

- 左侧看原始视频或摄像头画面
- 右侧看骨架画面
- 右侧或下方看实时角度、速度、重心、轨迹、`motion_intensity`
- 由人类教练判断动作质量，不做自动评分

---

## 1. 项目定位

### 这是什么

`wushu_motion_visualizer` 是一个面向武术训练场景的骨架数据可视化系统，适合：

- 刀术、剑术、拳术、棍术等动作回看
- 教练逐帧检查步型、身法、手法
- 本地训练辅助观察
- 后续扩展为云端“上传视频分析”工具

### 这不是什么

本项目**不是**：

- 自动动作评分系统
- 动作对错自动判断系统
- 真实肌肉发力识别系统
- 真实呼吸识别系统
- 生物力学精确测量系统

换句话说，本系统做的是**骨架可视化 + 运动数据展示**，不是代替教练做判断。

---

## 2. 核心能力

### 视频分析模式

上传 `mp4` 后，系统会：

1. 逐帧提取人体关键点
2. 左边显示原始画面
3. 右边显示骨架画面
4. 生成 side-by-side 分析视频
5. 提供逐帧滑块查看
6. 显示当前帧的角度、速度、峰值、峰值时间等数据
7. 输出可选导出文件

### 实时摄像头模式

本机摄像头实时运行时，系统会：

1. 打开默认摄像头
2. 左边显示原始画面
3. 右边显示骨架画面
4. 实时刷新 FPS 和当前帧数据
5. 可选显示短轨迹残影
6. 支持截图保存当前帧

---

## 3. 当前展示的数据

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

- `Kinetic Chain Stage` 当前是**启发式时序阶段标签**
- 它表达的是“当前更像是下肢驱动、髋部传递、躯干旋转还是上肢释放”
- 它**不是**真实“力量传导”的精确测量

---

## 4. 主要参数的计算方式

### 4.1 关键点来源

系统基于 `MediaPipe Pose` 提取 33 个关键点。  
每帧关键点包含：

- 归一化坐标：`x / y / z`
- 关键点可见性：`visibility`
- 像素坐标：`pixel_x / pixel_y`

后续大部分计算都基于像素坐标完成。

### 4.2 角度计算

统一使用：

```python
calculate_angle(point_a, point_b, point_c)
```

含义：以 `point_b` 为顶点，计算 `a-b-c` 的夹角。

例如：

- 左肘角度：`left_shoulder - left_elbow - left_wrist`
- 右膝角度：`right_hip - right_knee - right_ankle`

如果任意点缺失、异常或重合，则返回 `NaN`。

### 4.3 躯干倾斜角

步骤：

1. 计算肩部中心点
2. 计算髋部中心点
3. 构造髋部中心指向肩部中心的向量
4. 计算该向量相对竖直方向的偏转角

得到：

- `torso_tilt_angle`

### 4.4 速度计算

速度来自相邻帧关键点位移：

```text
speed = distance(current_point, previous_point) * fps
```

单位当前使用：

- `px/s`

它适合看相对变化和节奏，不等于真实世界物理速度。

### 4.5 角速度

角速度来自角度差分：

```text
angular_velocity = (current_angle - previous_angle) * fps
```

单位可理解为：

- `deg/s`

### 4.6 角加速度

角加速度来自角速度差分：

```text
angular_acceleration = (current_angular_velocity - previous_angular_velocity) * fps
```

单位可理解为：

- `deg/s²`

### 4.7 粗略重心估计

当前版本不是精确质心模型，而是视觉关键点粗略估计：

- 优先使用左右肩、左右髋的加权中心
- 若这些关键点不全，则回退为所有可见关键点的平均中心

输出字段：

- `center_of_mass_x`
- `center_of_mass_y`

### 4.8 motion_intensity

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

### 4.9 Kinetic Chain Stage

当前做法是启发式：

1. 计算下肢、髋部、躯干、上肢当前活跃度
2. 用当前值相对历史峰值做归一化
3. 哪一段当前更活跃，就给出对应阶段标签

当前可能输出：

- `Lower-limb drive`
- `Hip transfer`
- `Torso rotation`
- `Upper-limb release`
- `Transition / Hold`

请注意：

- 这适合看**动作链的时序趋势**
- 不应宣传为“准确测量力量传导”

---

## 5. 界面说明

### 视频分析页面

页面包含：

- 输入区
- 分析结果视频播放器
- 当前帧滑块
- 当前帧双画面对照
- 当前帧数据面板
- 曲线图
- 轨迹图
- 导出区

### 实时摄像头页面

页面包含：

- 开始/停止摄像头
- 是否显示短轨迹残影
- 原始画面
- 骨架画面
- 实时数据面板
- 最近若干秒的趋势图

### 关于系统页面

页面包含：

- 系统定位
- 参数计算方式
- 数据在训练观察中的用途
- 云服务器部署建议

---

## 6. 项目结构

```text
wushu_motion_visualizer/
  app.py
  requirements.txt
  README.md
  configs/
    default.yaml
  src/
    pose/
      mediapipe_backend.py
    analysis/
      kinematics.py
      metrics.py
      motion_intensity.py
      smoothing.py
    video/
      offline_processor.py
      realtime_processor.py
      video_player.py
    visualization/
      draw_pose.py
      draw_dashboard.py
      charts.py
    export/
      exporters.py
    utils/
      paths.py
      video_utils.py
      time_utils.py
  data/
    input/
    output/
    cache/
```

---

## 7. 安装

推荐环境：

- Windows 11
- Python `3.10` 或 `3.11`

安装依赖：

```bash
python -m pip install -r requirements.txt
```

如果你的 `pip` 启动器异常，优先使用 `python -m pip`，不要直接用 `pip install`。

---

## 8. 运行

本地启动：

```bash
python -m streamlit run app.py
```

浏览器打开本地页面后即可使用。

---

## 9. 输出文件

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

实时截图保存在：

```text
data/output/camera_snapshot_时间戳/screenshots/
```

---

## 10. 云服务器部署建议

### 推荐先部署什么

优先部署“视频上传分析”版本。

这条路径最稳：

1. 用户上传 `mp4`
2. 服务端离线分析
3. 返回分析页面和导出文件

### 启动命令

```bash
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

### 服务器侧建议

- 使用 `Nginx` 反向代理
- 放行对应公网端口
- 限制上传文件大小
- 定期清理 `data/output`
- 如并发变高，再把分析任务移到后台队列

### 为什么当前不建议直接把实时摄像头模式开放给公网用户

当前实时模式使用：

```python
cv2.VideoCapture(0)
```

这读取的是**服务器本机摄像头**，不是访问者浏览器摄像头。

所以：

- 本地运行没问题
- 公网多人访问时不适合直接沿用这一版

如果以后要做“浏览器直接打开自己摄像头实时分析”，需要额外改成：

1. 浏览器采集摄像头
2. 前端上传图像帧或视频流
3. 服务端推理
4. 页面回传结果

这属于下一阶段架构。

---

## 11. 注意事项

- 单帧出现 `NaN` 通常表示该帧关键点检测不稳定，不代表动作错误
- `px/s` 适合看相对快慢，不是绝对物理速度
- `center_of_mass_x / center_of_mass_y` 是粗略估计，不是真实质心
- `motion_intensity` 不是肌肉发力值
- `Kinetic Chain Stage` 不是精确力量传导测量

---

## 12. 常见问题

### 为什么网页里有时视频能加载但不能播？

浏览器对 `mp4` 编码兼容性较敏感。当前版本已经把导出视频转成浏览器更友好的 `H.264`。

### 为什么有些帧没有数值？

因为关键点可能暂时丢失，系统会返回 `NaN` 或“未检测到”，而不是崩溃。

### 为什么没有自动评分？

这是有意为之。第一版只做稳定的骨架和运动数据可视化，动作质量判断交给教练。

---

## 13. 后续可扩展方向

- 更好的历史任务管理页面
- 峰值时序链路图
- 更清晰的动力链趋势可视化
- 云端视频任务队列
- 浏览器端摄像头实时分析架构
