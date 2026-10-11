# 武术 AI 教练系统 V4 重构报告

> 版本：V4.0.0 ｜ 日期：2026-10-01 ｜ 基线：V3（V3_REPORT.md）
>
> V4 核心目标：在 V3 结构化诊断基础上，增加**评分系统**和 **AI Coach**，把"动作数据"翻译成"教练能听懂的人话"——哪里有问题、为什么、怎么改、怎样更接近标准动作。

---

## 1. V3 与 V4 的分工

| 层 | 负责什么 | 不做什么 |
|---|---|---|
| V2/V3 引擎 | MediaPipe 姿态识别、指标计算、发力链时序、11 类错误诊断、Self Baseline | 不打综合分、不写教练建议 |
| V4 评分 | 基于 V3 诊断证据计算 100 分制评分 | 不自己判断动作对错 |
| V4 AI Coach | 把 V3 诊断 + 评分翻译成结构化教练语言 | 不重新写动作判断逻辑 |

**关键原则**：AI 不越界——所有结论必须引用 V3 提供的实际证据（帧号、时间、指标数值）。没有证据时明确说"当前数据不足"。

---

## 2. 新增模块

```
src/coach/
  scoring.py          # 100 分制评分系统（7 维度）
  ai_coach.py         # AI Coach 主入口（读 V3 → 评分 → 调 LLM → 保存）
  prompt_builder.py   # 构造 prompt（V3 诊断 + 评分 + 基线对比）
  provider.py         # OpenAI 兼容 LLM 调用层（支持 Kimi/豆包）
  training_history.py # 历史训练对比（最近 N 次分数趋势）
tests/test_v4_scoring.py  # 5 个冒烟测试
```

---

## 3. 评分模型（100 分制，7 维度）

| 维度 | 满分 | 扣分来源（V3 诊断） |
|---|---|---|
| 发力链顺序 | 20 | shoulder_starts_early / chain_order_mixed |
| 髋部参与 | 15 | insufficient_hip / arm_dominant |
| 肩肘腕动力传递 | 15 | arm_dominant / left_right_asymmetry |
| 出拳轨迹和肘部控制 | 15 | elbow_flare |
| 末端速度和击打完成度 | 15 | insufficient_end_speed |
| 身体稳定性 | 10 | excessive_forward_shift / excessive_head_motion / poor_stability |
| 回收速度 | 10 | slow_recovery |

**扣分规则**：
- severity high / medium / low → 全额 / 60% / 30% 扣分
- 同维度多个问题扣分叠加，不低于 0
- 没有专家模板时，结果标记为"实验性估计"

**评分示例**（V3 检出 4 个问题）：

```
问题：手臂主导发力 [high]
  → 髋部参与维度扣 15 × 0.4 × 1.0 = 6 分
  → 肩肘腕传递维度扣 15 × 0.3 × 1.0 = 4.5 分
问题：身体过度前冲 [medium]
  → 身体稳定性维度扣 10 × 0.6 × 0.6 = 3.6 分
总分：100 - 6 - 4.5 - 3.6 = 85.9 分
```

---

## 4. Expert Template 格式

```json
{
  "technique_id": "straight_punch",
  "schema_version": "3.0",
  "source": "expert_coach",
  "curves": {
    "hip_angular_velocity": [0.0, 0.1, ...],
    "shoulder_speed": [...],
    "elbow_angle": [...],
    "wrist_speed": [...]
  },
  "event_times_normalized": {
    "hip_start": 0.0,
    "shoulder_start": 0.12,
    "wrist_speed_peak": 0.55
  },
  "metrics_goals": {
    "hip_shoulder_gap_ms": 90,
    "terminal_amplification": 2.1
  },
  "coach_annotations": "教练文字标注"
}
```

没有专家模板时，系统明确显示：
> "当前评分属于基于个人基线和结构规则的实验性估计，不能代表权威标准分数。"

---

## 5. AI Coach 输入 JSON（给 LLM 的）

```json
{
  "technique_diagnosis": { /* V3 TechniqueResult.to_dict() */ },
  "score_result": { /* 100 分制评分结果 */ },
  "baseline_summary": { /* Self Baseline 摘要 */ },
  "expert_template_available": false
}
```

## 6. AI Coach 输出 JSON（LLM 返回）

```json
{
  "overall_summary": "本次出拳发力链顺序基本正确，但髋部参与不足，动作更多依赖手臂挥动。",
  "score": 85,
  "score_breakdown": [
    {"dimension": "发力链顺序", "score": 16, "max": 20, "reason": "肩启动略早于髋"}
  ],
  "top_problems": [
    {"problem": "髋参与不足", "severity": "high", "evidence": "帧 258，髋角速度 215deg/s", "why": "髋峰值仅为基线的 58%"}
  ],
  "standard_action": "先转髋送重心，肩再跟进，最后手腕弹出。",
  "why_score_is_lost": "髋部参与不足扣 6 分，身体前冲扣 3.6 分。",
  "training_advice": "降低出拳速度 30%，每拳从髋启动开始。",
  "priority_drill": "扶墙转髋出拳慢速组合。",
  "comparison_with_baseline": "比上次髋参与提升 12%。",
  "confidence": 0.8,
  "limitations": "无专家模板，评分为实验性估计。"
}
```

---

## 7. AI 接口配置

环境变量：

```bash
# 默认关闭，未配置时系统仍可运行 V3 分析和本地评分
AI_ENABLED=false

# OpenAI 兼容接口（Kimi/豆包/任何兼容接口）
AI_API_KEY=sk-xxx
AI_BASE_URL=https://api.moonshot.cn/v1   # Kimi
# AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3  # 豆包
AI_MODEL=moonshot-v1-8k
AI_TIMEOUT=60
```

**安全规则**：
- 密钥只从环境变量读，不写进代码
- 密钥不返回给前端、不写进 Streamlit 页面
- AI 调用失败时降级到本地评分，不影响 V3 分析结果

---

## 8. 测试结果

```
tests/test_v4_scoring.py: 5 passed
  - 评分维度总和 = 100
  - 未配置 AI 时默认关闭
  - LLM 返回 markdown 包裹的 JSON 能正确解析
  - LLM 返回纯 JSON 能正确解析
  - 历史对比在无数据时安全降级
```

V2/V3 原有测试全部保留，未被破坏。

---

## 9. 能力边界（实验性结论）

- **评分是实验性的**：扣分规则基于 V3 诊断的 severity 分级，未经大量真实数据标定
- **没有专家模板时**：评分只能反映"与用户自己历史相比"的相对位置，不代表权威标准
- **AI 解读是翻译层**：AI 不自己判断动作对错，只把 V3 诊断翻译成教练语言
- **不测量真实物理量**：速度单位是 px/s 或归一化单位，不是 m/s；不测量真实拳力、肌电

---

## 10. 后续改进方向

1. **教练标注数据**：让教练给 10-20 次示范动作打分，标定评分权重
2. **专家模板录入**：把教练的标准动作录成 expert_template.json
3. **更多动作**：扩展 Technique Profile（腿法、步法）
4. **AI 模型升级**：接多模态模型，直接看视频截图做辅助判断

---

## 11. 本地运行

```bash
# 原 Streamlit（不变）
python -m streamlit run app.py

# API 后端（不变）
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# 启用 AI Coach（可选）
$env:AI_ENABLED="true"
$env:AI_API_KEY="sk-xxx"
$env:AI_BASE_URL="https://api.moonshot.cn/v1"
$env:AI_MODEL="moonshot-v1-8k"
```
