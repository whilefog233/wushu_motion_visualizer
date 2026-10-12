# 武术 AI 教练系统 V3 重构报告

> 版本：V3.0.0 ｜ 日期：2026-10-01 ｜ 基线：V2（REFACTOR_REPORT.md 已完成）
>
> V3 目标：把系统从"动作数据可视化"升级为**武术技术诊断系统**。第一版只重点支持**直拳 / 冲拳**。
> 核心标准只有一个——系统最后必须能回答：**这个数据说明我的动作哪里有问题，我下一轮训练具体应该改什么？**

---

## 1. 新增了什么模块

```
src/technique/                  # V3 技术诊断引擎（纯 Python，零 Streamlit 依赖）
├── __init__.py                 # 公开 API：analyze_technique / load_technique_result / get_profile
├── models.py                   # TechniqueProfile / KeyEvent / Phase / TimingLink /
│                               #   DiagnosisEvidence / TechniqueDiagnosis / PunchWindow / TechniqueResult
├── profiles.py                 # 直拳 TechniqueProfile（阶段/事件/指标意义/错误模式/判定规则）
├── signals.py                  # SignalBundle：从 pose.json + metrics.csv 组装帧对齐信号
├── events.py                   # 关键事件检测（启动/峰值/回收/结束）
├── phases.py                   # 5 阶段切分（由事件对构成）
├── timing.py                   # 发力链毫秒间隔（髋→肩→肘→腕）
├── errors.py                   # 11 种错误模式诊断
├── references.py               # Self Baseline / Personal Best / Expert Template
└── engine.py                   # analyze_technique 主入口 + 出拳窗口检测 + coach_input 合并

tests/test_technique_v3.py      # 8 个单元/集成测试
```

UI 侧（app.py）：暗黑+金色主题重绘；删除本地视频下拉框（只保留文件上传）；新增「直拳技术诊断 · V3」展示区块（Top3 问题 + 本轮最重要的一件事 + 窗口详情 + 一键运行诊断按钮）。

---

## 2. 直拳如何分阶段

`profiles.py` 定义 5 个阶段，由关键事件对切分（`phases.py`）：

| 阶段 | 起止事件 | 训练含义 |
|---|---|---|
| 准备阶段 | window_start → hip_start | 站架稳定、重心下沉 |
| 启动阶段 | hip_start → wrist_start | 髋先启动，动力链开始传导 |
| 加速阶段 | wrist_start → wrist_speed_peak | 肩/肘/腕依次加速 |
| 最大伸展 / 击打阶段 | wrist_speed_peak → max_extension | 末端速度最大，拳到位 |
| 回收阶段 | recovery_start → action_end | 主动回撤、复位防守 |

阶段本身只提供结构，判定问题靠阶段内的时序与峰值，不靠阶段名称。

---

## 3. 有哪些关键事件

`events.py` 对每个窗口检测 10 个关键事件：

| 事件 | 检测方法 |
|---|---|
| hip_start（髋启动） | 髋角速度突破基线（均值 + max(2.5σ, 信号幅值 2% 噪声带)，持续 ≥3 帧） |
| shoulder_start（肩启动） | 肩移动速度首次突破基线 |
| wrist_start（腕启动） | 主手腕速度首次突破基线 |
| hip_angular_velocity_peak | 髋角速度峰值（prominence 过滤） |
| shoulder_velocity_peak | 肩速度峰值 |
| elbow_extension_peak | 肘角速度峰值 |
| wrist_speed_peak | 主手腕速度峰值 |
| max_extension（最大伸展） | 肘角最大伸展帧 |
| recovery_start（回收开始） | 腕速回落到峰值的 40% |
| action_end（动作结束） | 肘角回到起始 + 25% 伸展范围 |

启动检测的关键细节：**基线窗口只取窗口前 ≤10 帧**（取前 25% 会把启动段算进基线，导致"肩早于髋"这类问题信号被污染）；事件排序**不做强制单调化**——肩启动可以合法地早于髋启动，这正是问题信号，不能抹掉。

---

## 4. 有哪些错误模式（11 种）

`errors.py` 的 `diagnose_window` 串行执行 11 种判定：

1. shoulder_starts_early 肩启动过早
2. insufficient_hip 髋参与不足
3. arm_dominant 手臂主导发力
4. chain_order_mixed 发力链顺序混乱
5. elbow_flare 肘部外翻
6. excessive_forward_shift 身体过度前冲
7. insufficient_end_speed 末端速度不足
8. slow_recovery 回收过慢
9. excessive_head_motion 头部晃动过大
10. poor_stability 动作稳定性差
11. left_right_asymmetry 左右侧差异明显

每种诊断固定输出：`problem / severity / confidence / reference_type / evidence / evidence_text / meaning / training_advice`。
**禁止只输出 True/False**；每条必须有可读证据和"为什么是问题"的解释。

---

## 5. 每个错误如何判断（判定逻辑摘要）

| 问题 | 判断信号 | 无基线时（结构规则） | 有基线时 |
|---|---|---|---|
| 肩启动过早 | hip_start 与 shoulder_start 帧差 | shoulder_start 早于 hip_start ≥15ms 即报 | 与基线 hip_shoulder_gap_ms 偏差按 σ 分级 |
| 髋参与不足 | 髋角速度峰值 | 髋/肘峰值比 < 0.25（髋贡献过小） | 髋峰值低于基线 1σ 以上 |
| 手臂主导发力 | 髋峰值 vs 肘峰值 | hip_to_elbow_peak_ratio < 0.35 | 与基线偏差分级 |
| 发力链顺序混乱 | hip/shoulder/elbow/wrist 峰帧序 | 任何相邻峰值逆序即报 | 结构规则为主 |
| 肘部外翻 | 肘到肩-腕连线垂直距离/肩宽 | 加速-击打段均值 > 0.45 肩宽 | 与基线偏差分级 |
| 身体过度前冲 | 窗口内髋中心前移量/躯干长度 | 前冲 > 0.6 个躯干长 | 与基线偏差分级 |
| 末端速度不足 | 腕峰值 vs 髋/肩速度峰值 | 末端放大比 < 1.5 | 与基线偏差分级 |
| 回收过慢 | 回收时长/击打时长 | 回收 > 击打 × 2.5 | 与基线 recovery_strike_ratio 偏差分级 |
| 头部晃动过大 | 窗口内鼻尖累计位移/肩宽 | 累计 > 0.8 肩宽 | 与基线 head_displacement 偏差分级 |
| 动作稳定性差 | 腕速上升段抖动指数 + 跨窗口 CV | 抖动指数 > 0.15 | 与基线 wrist_jitter 偏差分级 |
| 左右侧差异 | 主手 vs 对侧腕峰值比 | 比值 < 0.5 或 > 2.0 | 与基线偏差分级 |

严重度分级：相对偏差 **≥2σ=high / ≥1σ=medium / 其他=low**（`diagnosis_rules.severity_by_deviation`）。
置信度：结构规则 ≈0.5-0.6；Self Baseline ≈0.75；Personal Best ≈0.8（`_confidence_for`）。

**没有写死任何绝对标准**（如"髋角速度必须 > X"）。所有阈值都是相对参考或结构规则（如"肩不应早于髋"），并且每种结构规则都说明自己是"实验性规则"（见第 9 节）。

---

## 6. 使用了哪些数据

全部**只读** `data/analyses/{analysis_id}/` 下已有产物，**不重复运行 MediaPipe**：

- `pose.json`：补充信号（肩速度、鼻速度、肘外翻、头部位移、肩宽尺度）——从逐帧 landmarks 现算
- `metrics.csv`：髋角速度 / 肘角速度 / 肘角 / 腕速（px、normalized、world）/ 髋中心 x / 肩宽 / 躯干长 / 置信度 / 躯干旋转速度
- `data/analyses/._technique_refs/straight_punch/`：baseline.json / personal_best.json / expert_template.json
- 输出：`technique/straight_punch.json`（TechniqueResult）+ 合并进 `coach_input.json`（新增 `technique_diagnosis` 段，**不删旧字段**，兼容）

---

## 7. 如何生成训练建议

每个错误模式在 `profiles.py` 的 `common_errors` 里带 `advice_template` 与 `meaning_template`，由 `errors.py` 用本次证据数值填充。建议是**动作指令级**的：

> 问题：肩部启动过早
> 证据：髋峰值时间 0.61s，肩峰值时间 0.64s，髋肩间隔 30ms，个人优秀动作平均 90ms
> 含义：肩部过早参与，髋—肩动力传递阶段被压缩，动作更依赖肩臂。
> 建议：下一轮暂时降低出拳速度，重点练习髋先启动、肩稍后跟进。

页面最终展示：**本次最值得改的 3 个问题**（跨窗口按严重度聚合）+ **本轮训练最重要的一件事**（取问题最重窗口的 Top1 建议）。

---

## 8. 哪些判断目前有可靠依据

- **发力链时序**（髋→肩→肘→腕 的启动/峰值毫秒间隔）：直接来自关节运动学信号，可复算、可解释，是 V3 最有依据的部分。
- **时序顺序类结构规则**（肩早于髋、峰序倒挂）：基于运动学因果链（身体核心先于末端），有生物力学常识支撑。
- **左右差异 / 头部晃动 / 前冲量**：归一化后（肩宽/躯干长）跨视频可比，数值可靠。
- **Self Baseline**：用户自己的滚动基线（最近 10 窗口），"进步/退步"判断相对自身历史，可靠且不伪造绝对标准。

## 9. 哪些仍然只是实验性规则

- **结构规则的绝对阈值**（如 0.8 肩宽、×2.5 回收比、0.35 髋肘比、0.45 肘外翻）：这些数值目前**没有公开研究标定**，属于"合理初值 + 待标注验证"。代码里 `diagnosis_rules.no_absolute_standards=True` 且每条结构规则诊断 confidence 被压到 ≤0.6，明确标注实验性质。
- **肌肉分析（V2 muscle.json）**：仍是启发式估计，不参与 V3 诊断。
- **动作稳定性抖动指数**：与 0.15 阈值的对应关系未标定。
- **Personal Best 曲线相似度**：`normalize_curve` / `curve_similarity` 接口已实现，但没有真实 PB 样本验证阈值。

**诚实边界**：V3 不做"综合评分 85 分"——没有足够依据给指标分配权重；不做"真实米/秒"——world 坐标未标定，归一化单位（×肩宽/×躯干长）才是跨视频可比口径。

---

## 10. 下一步：专家模板与教练标注

已预留 `expert_template.json` schema（`references.py`）：

```json
{
  "technique_id": "straight_punch",
  "template": {
    "event_times_normalized": {"hip_start": 0.0, "shoulder_start": 0.12, "...": 0.0},
    "curves": {"hip_angular_velocity": [...101], "shoulder_speed": [...], "elbow_angle": [...], "wrist_speed": [...]},
    "metrics": {"hip_shoulder_gap_ms": 90, "terminal_amplification": 2.1},
    "coach_annotations": []
  }
}
```

接入路径：教练给 10-20 次示范动作 → `set_expert_template()` → `load_reference()` 自动把 `expert_template_available` 置真 → 诊断优先与专家模板比（confidence 提升到 ~0.85），并输出曲线差异证据。

未来 AI Coach（GPT/Gemini）的正确接线方式（已定，未接 API）：

```
视频 → MediaPipe（一次） → pose.json / metrics.csv
  → Technique Engine → technique/straight_punch.json（结构化诊断）
  → 合并 coach_input.json（technique_diagnosis 段）
  → GPT / Gemini 只负责把结构化诊断翻译成自然教练语言（不自己判断动作）
```

---

## 11. 测试与验证结果

**自动化测试（36 passed / 0 failed）**：

| 套件 | 数量 | 内容 |
|---|---|---|
| V2 回归（tests/） | 28 | 视频分析、导出、缓存复用、worker、肌肉、发力链 |
| V3 新增（test_technique_v3.py） | 8 | 事件时序、峰值间隔、5 阶段、错误模式、曲线归一化、PB、集成三连 |

**真实数据验证**（`20261001_124339_0e62e2cb`，竖屏 1080×1920，794 帧 / 30fps）：

- `analyze_technique` 端到端跑通，检出 **6 个出拳窗口**，全部输出结构化诊断（示例见下）
- 修复过程发现并解决：`head_displacement` 未按窗口切片（曾输出 110 个肩宽的异常值）、基线窗口污染启动检测、事件强制单调化抹掉"肩早于髋"信号
- 第二次运行起 Self Baseline 自动生效（髋参与不足 215.5deg/s = 基线 58%）

```
window 0（帧 255-263，左拳，267ms）
  ├─ 手臂主导发力 [high]  hip_to_elbow_peak_ratio = 0.06（髋 215.5°/s vs 肘 3369.9°/s）
  ├─ 身体过度前冲 [medium]  前冲 0.71 个躯干长度
  ├─ 髋参与不足 [low·self_baseline]  髋峰值 = 基线 58%
  └─ 左右侧差异明显 [low]  主手/对侧峰值比 0.59
本轮最重要的一件事：降低出拳速度 30%，每拳从髋启动开始……
```

**Streamlit UI 验证**（AppTest 无头渲染）：初始页、历史分析全量渲染（含 V3 区块）、"运行直拳技术诊断"按钮点击生成，三场景均无异常；服务已重启于 http://localhost:8501。

**性能**（沿用 V2 performance.json，26.7s 视频）：总处理 33.26s，其中 **MediaPipe 推理 32.28s（96.5%）**——当前最大瓶颈是姿态推理本身，指标/肌肉/发力链/技术诊断总计 <1s。V3 技术诊断本身不产生新的推理开销。

---

## 12. 文件变更清单

**新增**：`src/technique/`（10 个文件）、`tests/test_technique_v3.py`、`V3_REPORT.md`

**修改**：`app.py`（暗黑+金色主题、删除本地视频下拉框、新增 V3 诊断区块、关于页更新）、`src/technique/errors.py`（baseline 样本不足守卫、head_motion 改用窗口统计）、`src/technique/events.py`（基线窗口缩至 ≤10 帧、自适应噪声带、取消强制单调化）、`src/technique/engine.py`（NaN 处理）、`src/technique/profiles.py`（中文引号修复）

**未改动**：实时摄像头模块、V2 全部产物格式、旧输出目录、导出功能、worker.py
