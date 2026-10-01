from __future__ import annotations

"""直拳（冲拳）技术档案：V3 第一个 TechniqueProfile。

原则：
- 阶段 / 事件 / 错误模式全部在这里集中定义，判定逻辑在 events.py / errors.py 消费。
- 不写死“髋角速度必须 > X / 拳速必须 > Y / 间隔必须 > Z 毫秒”这类绝对标准；
  所有偏差判断都相对 Self Baseline / Personal Best / Expert Template，或使用
  结构性规则（如“肩启动不应早于髋启动”）。
"""

from src.technique.models import TechniqueProfile

STRAIGHT_PUNCH_ID = "straight_punch"

STRAIGHT_PUNCH_PROFILE = TechniqueProfile(
    technique_id=STRAIGHT_PUNCH_ID,
    name="直拳 / 冲拳",
    description=(
        "第一版只支持直拳。链路：准备 → 髋启动 → 肩/肘/腕依次加速 → 最大伸展击打 → 回收。"
        "重点分析发力链时序（髋→肩→肘→腕 的启动与峰值间隔），而不是只看数值大小。"
    ),
    phases=[
        {
            "id": "preparation",
            "label": "准备阶段",
            "start_event": "window_start",
            "end_event": "hip_start",
            "description": "站姿待发，髋尚未开始转动。",
        },
        {
            "id": "initiation",
            "label": "启动阶段",
            "start_event": "hip_start",
            "end_event": "elbow_extension_peak",
            "description": "髋先启动，动力向躯干、肩、肘逐级传递。",
        },
        {
            "id": "acceleration",
            "label": "加速阶段",
            "start_event": "elbow_extension_peak",
            "end_event": "wrist_speed_peak",
            "description": "肘伸展加速，手腕速度快速上升。",
        },
        {
            "id": "strike",
            "label": "最大伸展 / 击打阶段",
            "start_event": "wrist_speed_peak",
            "end_event": "max_extension",
            "description": "腕速达到峰值，手臂接近完全伸展，命中点。",
        },
        {
            "id": "recovery",
            "label": "回收阶段",
            "start_event": "max_extension",
            "end_event": "action_end",
            "description": "出拳后回收，回到准备姿态。",
        },
    ],
    key_events=[
        {"id": "window_start", "label": "动作开始", "signal": "window", "description": "分析窗口起点。"},
        {"id": "hip_start", "label": "髋启动", "signal": "hip_angular_velocity", "description": "髋角速度首次突破基线噪声带。"},
        {"id": "shoulder_start", "label": "肩启动", "signal": "shoulder_speed", "description": "肩线速度首次突破基线噪声带。"},
        {"id": "wrist_start", "label": "手腕启动", "signal": "wrist_speed", "description": "主手手腕速度首次突破基线噪声带。"},
        {"id": "hip_angular_velocity_peak", "label": "髋角速度峰值", "signal": "hip_angular_velocity", "description": "髋旋转最快的时刻。"},
        {"id": "shoulder_velocity_peak", "label": "肩速度峰值", "signal": "shoulder_speed", "description": "肩移动最快的时刻。"},
        {"id": "elbow_extension_peak", "label": "肘伸展峰值", "signal": "elbow_angular_velocity", "description": "主手肘伸展角速度峰值。"},
        {"id": "wrist_speed_peak", "label": "手腕速度峰值", "signal": "wrist_speed", "description": "主手手腕速度峰值（击打瞬间的拳速代理）。"},
        {"id": "max_extension", "label": "最大伸展", "signal": "elbow_angle", "description": "主手肘角最大（手臂接近伸直）。"},
        {"id": "recovery_start", "label": "回收开始", "signal": "wrist_speed", "description": "腕速从峰值显著回落，出拳结束。"},
        {"id": "action_end", "label": "动作结束", "signal": "elbow_angle", "description": "肘角回到接近起始，动作周期结束。"},
    ],
    expected_sequence=[
        "hip_start",
        "shoulder_start",
        "elbow_extension_peak",
        "wrist_speed_peak",
    ],
    important_metrics=[
        {
            "metric": "hip_angular_velocity_peak",
            "unit": "deg/s",
            "what_it_judges": "髋旋转参与程度，判断是否用身体发力而非只挥手臂。",
            "paired_with": "shoulder_velocity_peak、wrist_speed_peak、hip_shoulder_gap_ms",
            "cannot_judge_alone": "绝对值受个人体型与发力习惯影响，不能只看数值大小；需与自己基线或个人最佳对比。",
            "training_meaning": "髋峰值低且肩/腕峰值正常 → 出拳可能主要靠手臂；髋峰值高但拳速没上去 → 动力传递断在中间环节。",
        },
        {
            "metric": "hip_shoulder_gap_ms",
            "unit": "ms",
            "what_it_judges": "髋启动到肩启动的间隔，判断动力传递链是否被压缩。",
            "paired_with": "shoulder_wrist_gap_ms、发力链顺序",
            "cannot_judge_alone": "间隔过短或为负（肩先动）提示肩部过早参与；但 30ms 与 90ms 哪个更优要对比个人优秀动作，不能拍脑袋定标准。",
            "training_meaning": "髋先动、肩稍后跟进的间隔越大，说明越依赖下肢/躯干发力；间隔太小说明动作偏手臂主导。",
        },
        {
            "metric": "wrist_speed_peak",
            "unit": "px/s",
            "what_it_judges": "出拳末端速度，衡量击打爆发力代理。",
            "paired_with": "shoulder_velocity_peak、末端速度放大比（wrist/shoulder 峰值比）",
            "cannot_judge_alone": "px/s 受拍摄距离影响，比较前必须用 normalized 或与同一拍摄条件下自对比。",
            "training_meaning": "末端速度低 → 动力链末端没把速度“放大”，训练重点是“松后紧”（前半程放松、击打瞬间加速）。",
        },
        {
            "metric": "elbow_extension_peak",
            "unit": "deg/s",
            "what_it_judges": "肘伸展速度峰值，判断手臂伸展的爆发性。",
            "paired_with": "wrist_speed_peak、elbow 伸展时序（相对髋肩）",
            "cannot_judge_alone": "肘伸展快但髋启动晚 → 手臂主导；肘伸展峰值出现时间比肩启动还早 → 发力链顺序混乱。",
            "training_meaning": "肘的伸展应在髋-肩之后发生；伸展过早说明“甩胳膊”，伸展过晚说明手臂没跟上身体。",
        },
        {
            "metric": "recovery_duration_ms",
            "unit": "ms",
            "what_it_judges": "回收速度（最大伸展到动作结束），判断击打后的复位效率。",
            "paired_with": "strike_duration_ms（击打时长）",
            "cannot_judge_alone": "回收慢不一定是问题——重击后顺势回防也常见；需结合下一动作衔接或个人基线。",
            "training_meaning": "回收过慢会拉长动作周期，影响连击与防守；训练重点是击打后主动缩肘回防。",
        },
        {
            "metric": "head_displacement",
            "unit": "body_scale",
            "what_it_judges": "头部晃动幅度（相对身体尺度归一化），判断出拳时是否保持头部稳定。",
            "paired_with": "hip_center_forward_shift、torso_tilt",
            "cannot_judge_alone": "小幅随动前倾属正常；过大位移或左右摆头才是问题。",
            "training_meaning": "头部晃动过大说明出拳时重心/颈部控制不足，训练重点是“出拳不丢下巴、头不探出支撑面”。",
        },
        {
            "metric": "hip_forward_shift",
            "unit": "body_scale",
            "what_it_judges": "髋部前冲距离（相对躯干长度归一化），判断是否过度前冲。",
            "paired_with": "head_displacement、torso_tilt_angle",
            "cannot_judge_alone": "直拳有适度重心前移；过大前冲会牺牲平衡与回收速度。",
            "training_meaning": "过度前冲 → 重心越出支撑面，易被反击；训练重点是击打后重心回收、保持三脚支撑。",
        },
    ],
    common_errors=[
        {
            "id": "shoulder_starts_early",
            "problem": "肩启动过早",
            "description": "肩在髋之前或几乎同时启动，髋—肩动力传递被压缩。",
            "signals": ["hip_start", "shoulder_start", "hip_shoulder_gap_ms"],
            "meaning_template": "肩部过早参与，髋—肩之间的动力传递阶段被压缩，动作可能更依赖肩臂而少用髋/躯干。",
            "advice_template": "下一轮暂时降低出拳速度，重点练习髋先启动、肩稍后跟进（可做慢速分解：髋动 30-50ms 后再送肩）。",
        },
        {
            "id": "insufficient_hip_engagement",
            "problem": "髋参与不足",
            "description": "髋角速度峰值明显低于个人基线/优秀动作，出拳偏手臂。",
            "signals": ["hip_angular_velocity_peak", "hip_shoulder_gap_ms", "wrist_speed_peak"],
            "meaning_template": "髋旋转参与不足，身体核心没有把力量送进拳头，拳速更多来自手臂挥动。",
            "advice_template": "训练中刻意强调“先转髋再送拳”，可做扶墙转髋、站架转髋出拳的慢速组合，找“脚-髋-拳”连成一条线的感觉。",
        },
        {
            "id": "arm_dominant",
            "problem": "手臂主导发力",
            "description": "腕速/肘伸展峰值相对髋贡献过高，髋-肩峰值过低。",
            "signals": ["hip_angular_velocity_peak", "shoulder_velocity_peak", "wrist_speed_peak", "elbow_extension_peak"],
            "meaning_template": "发力主要由手臂完成，身体（髋/躯干）贡献少，拳力上限低且肩部易疲劳。",
            "advice_template": "降低出拳速度 30%，每拳从髋启动开始，感受“身体先把重量送出去、手臂只是延长线”；用空击时注意肩部放松。",
        },
        {
            "id": "chain_order_mixed",
            "problem": "发力链顺序混乱",
            "description": "启动/峰值顺序偏离期望的 髋→肩→肘→腕。",
            "signals": ["hip_start", "shoulder_start", "elbow_extension_peak", "wrist_speed_peak", "chain_order"],
            "meaning_template": "发力链顺序混乱，力量传递出现“断层”（如肘先伸展、腕先加速），动作缺乏整体性，速度与力量无法叠加。",
            "advice_template": "做分节慢速训练：先转髋 → 再送肩 → 再伸肘 → 最后甩腕，每一节找到“上一节带动下一节”的感觉后再逐步加速。",
        },
        {
            "id": "elbow_flare",
            "problem": "肘部外翻",
            "description": "加速/击打阶段肘关节明显偏离肩-腕连线（外展过大）。",
            "signals": ["elbow_abduction_ratio", "elbow_angle"],
            "meaning_template": "肘部外翻使出拳轨迹变长、暴露肋部，且力量从肩-腕连线散失，击打效率下降。",
            "advice_template": "训练时让肘部沿“收肘贴肋→直线送出”的轨迹走；可对镜/录视频检查肘尖是否指向目标。",
        },
        {
            "id": "excessive_forward_shift",
            "problem": "身体过度前冲",
            "description": "髋部前移距离明显超过个人基线（相对躯干长度归一化）。",
            "signals": ["hip_forward_shift", "head_displacement", "torso_tilt_angle"],
            "meaning_template": "身体过度前冲，重心越出支撑面，出拳后回收慢、易被反击。",
            "advice_template": "出拳时保持重心在两脚之间略前即可，击打后主动把重心收回；可用“前脚掌抓地、后脚蹬”来找平衡。",
        },
        {
            "id": "insufficient_end_speed",
            "problem": "末端速度不足",
            "description": "腕速度峰值相对肩速度的“放大比”偏低，或明显低于个人最佳。",
            "signals": ["wrist_speed_peak", "shoulder_velocity_peak", "terminal_amplification"],
            "meaning_template": "末端速度不足，说明加速集中在身体/手臂中段，拳头本身没有在最后一瞬加速。",
            "advice_template": "训练“松后紧”：出拳过程中腕关节保持放松，接近目标瞬间骤然握紧加速；可做快速鞭打式空击体会末段爆发。",
        },
        {
            "id": "slow_recovery",
            "problem": "回收过慢",
            "description": "回收时长（最大伸展→结束）明显长于个人基线或占动作周期比例过大。",
            "signals": ["recovery_duration_ms", "strike_duration_ms", "recovery_ratio"],
            "meaning_template": "回收过慢拉长动作周期，影响连击节奏与防守复位。",
            "advice_template": "击打后主动“弹回”：命中瞬间肘部立刻回缩，拳沿原轨迹快速回收；可做“快出快收”节奏训练（收的速度 ≥ 出的速度）。",
        },
        {
            "id": "excessive_head_motion",
            "problem": "头部晃动过大",
            "description": "出拳过程中头部位移明显超过个人基线（相对肩宽/躯干长度归一化）。",
            "signals": ["head_displacement", "nose_speed"],
            "meaning_template": "头部晃动过大说明颈部/重心控制不足，出拳时暴露头部，易被迎击。",
            "advice_template": "出拳时下巴微收、颈部保持稳定；训练时想象“头固定在墙上”，只动手臂与身体。",
        },
        {
            "id": "poor_stability",
            "problem": "动作稳定性差",
            "description": "多次出拳之间关键指标（峰值/时序/轨迹）波动大，或单次动作内曲线抖动明显。",
            "signals": ["stability_score", "cv_of_peaks", "trajectory_similarity"],
            "meaning_template": "动作稳定性差说明技术尚未定型，每次出拳发力路径/时序都不一致，难以积累稳定质量。",
            "advice_template": "降低速度做标准化重复（10-20 次），固定“站架-转髋-送拳-回收”的节奏；每次录视频对比轨迹。",
        },
        {
            "id": "left_right_asymmetry",
            "problem": "左右侧差异明显",
            "description": "左右手腕速度峰值、左右肩启动时间等差异明显超过基线。",
            "signals": ["left_right_wrist_ratio", "left_right_shoulder_gap_diff"],
            "meaning_template": "左右侧差异明显说明双侧发力不均衡，弱侧技术被强侧掩盖。",
            "advice_template": "单侧重复训练弱侧（先空击、再轻击），把强侧的节奏“复制”给弱侧；注意双侧峰值差距目标不是一样大，而是差距收敛。",
        },
    ],
    diagnosis_rules={
        "no_absolute_standards": True,
        "reference_priority": ["self_baseline", "personal_best", "expert_template", "structural_rule"],
        "baseline_window_count": 10,
        "signal_onset": {"multiplier": 2.5, "min_frames": 3},  # 启动判定：基线均值 + 2.5σ 且持续 ≥3 帧
        "severity_by_deviation": {  # 与参考对比的偏差分级（σ 为参考标准差）
            "high": 2.0,
            "medium": 1.0,
            "low": 0.0,
        },
    },
    training_goals=[
        "先把发力链时序做对（髋→肩→肘→腕），再谈速度。",
        "每次训练固定一个最值得改的问题，不贪多。",
        "用 Self Baseline 跟踪进步：速度、时序、稳定性、回收、身体晃动、动作一致性。",
    ],
)


def get_profile(technique_id: str) -> TechniqueProfile:
    """按 technique_id 取 Profile。目前只有直拳；以后每个动作新增一个 Profile。"""
    if technique_id == STRAIGHT_PUNCH_ID:
        return STRAIGHT_PUNCH_PROFILE
    raise KeyError(f"未注册的 technique_id: {technique_id}")
