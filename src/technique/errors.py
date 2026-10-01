"""Common Error Pattern 错误模式库：直拳 11 种技术问题判定。

原则（对应 V3 要求）：
- 每个判定必须输出 problem / severity / confidence / evidence / meaning / training_advice。
- 优先用 Self Baseline / Personal Best 参考；没有参考时只用"结构规则"
  （发力链时序顺序、几何形状等非性能标准），并把 confidence 压低、注明依据类型。
- 不输出 True / False 式结论；每个问题都要解释"为什么"。
"""

from __future__ import annotations

import math

import numpy as np

from src.technique.events import event_time, event_value
from src.technique.models import DiagnosisEvidence, KeyEvent, ReferenceType, Severity, TechniqueDiagnosis, TimingLink
from src.technique.profiles import STRAIGHT_PUNCH_PROFILE
from src.technique.signals import SignalBundle


def _fmt(value: float, digits: int = 1) -> str:
    if not math.isfinite(value):
        return "N/A"
    return f"{value:.{digits}f}"


def _ev(metric: str, value: float, unit: str, reference_label: str, reference_value: float, note: str = "", deviation: str = "") -> DiagnosisEvidence:
    return DiagnosisEvidence(metric=metric, value=value, unit=unit, reference_label=reference_label,
                             reference_value=reference_value, note=note, deviation=deviation)


def _confidence_for(reference_type: str, base: float = 0.7) -> float:
    if reference_type == ReferenceType.SELF_BASELINE.value:
        return min(0.85, base + 0.05)
    if reference_type == ReferenceType.PERSONAL_BEST.value:
        return min(0.9, base + 0.1)
    if reference_type == ReferenceType.EXPERT_TEMPLATE.value:
        return min(0.85, base + 0.05)
    return min(0.6, base - 0.1)  # structural_rule


def _severity_by_deviation(deviation_sigma: float) -> str:
    if not math.isfinite(deviation_sigma):
        return Severity.LOW.value
    if deviation_sigma >= 2.0:
        return Severity.HIGH.value
    if deviation_sigma >= 1.0:
        return Severity.MEDIUM.value
    return Severity.LOW.value


def _ref_mean(ref: dict, key: str) -> float:
    item = ref.get(key) or {}
    value = item.get("mean")
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else float("nan")


def _ref_std(ref: dict, key: str) -> float:
    item = ref.get(key) or {}
    value = item.get("std")
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else float("nan")


def _deviation_sigma(observed: float, ref: dict, key: str) -> float:
    mean = _ref_mean(ref, key)
    std = _ref_std(ref, key)
    if not math.isfinite(mean) or not math.isfinite(std) or std <= 1e-9:
        return float("nan")
    return abs(observed - mean) / std


def diagnose_window(
    bundle: SignalBundle,
    events: list[KeyEvent],
    timing: list[TimingLink],
    ref: dict,
    window_stats: dict,
) -> list[TechniqueDiagnosis]:
    """对一个直拳窗口做全部 11 种错误模式判定。ref 为参考数据字典。"""
    diagnoses: list[TechniqueDiagnosis] = []

    # 参考一致性：Self Baseline 只有样本 ≥3 才有效（与 UI 的 baseline_available 口径一致）。
    # 样本不足时清除基线字段，让所有判定回落到结构规则，避免声称"与个人基线比较"却只有 1-2 次样本。
    if not ref.get("baseline_available"):
        ref = {key: value for key, value in ref.items() if not str(key).startswith("baseline_")}

    _run_shoulder_starts_early(diagnoses, events, timing, ref)
    _run_insufficient_hip(diagnoses, events, ref)
    _run_arm_dominant(diagnoses, events, ref)
    _run_chain_order_mixed(diagnoses, events, ref)
    _run_elbow_flare(diagnoses, bundle, events, ref)
    _run_excessive_forward_shift(diagnoses, bundle, events, window_stats, ref)
    _run_insufficient_end_speed(diagnoses, events, ref)
    _run_slow_recovery(diagnoses, timing, ref)
    _run_excessive_head_motion(diagnoses, window_stats, ref)
    _run_poor_stability(diagnoses, window_stats, ref)
    _run_left_right_asymmetry(diagnoses, bundle, events, ref)

    return diagnoses


# ---------------------------------------------------------------- 各错误模式
def _run_shoulder_starts_early(diagnoses: list[TechniqueDiagnosis], events: list[KeyEvent], timing: list[TimingLink], ref: dict) -> None:
    gap = _timing_value(timing, "hip_start", "shoulder_start")
    if not math.isfinite(gap):
        return
    # 结构规则：肩启动明显早于髋（<-15ms 视为测量噪声外）
    structurally_early = gap < -15.0
    # 参考规则：间隔明显小于个人基线
    baseline_gap = _ref_mean(ref, "hip_shoulder_gap_ms")
    deviation = float("nan")
    if math.isfinite(baseline_gap) and baseline_gap > 0:
        deviation = _deviation_sigma(gap, ref, "hip_shoulder_gap_ms")
        ref_based = gap < baseline_gap - 1.0 * _ref_std(ref, "hip_shoulder_gap_ms")
    else:
        ref_based = False

    if not structurally_early and not ref_based:
        return
    if structurally_early and gap < -60:
        severity = Severity.HIGH.value
    elif structurally_early or (ref_based and deviation >= 2.0):
        severity = Severity.MEDIUM.value
    else:
        severity = Severity.LOW.value

    reference_type = ReferenceType.SELF_BASELINE.value if math.isfinite(baseline_gap) else ReferenceType.STRUCTURAL_RULE.value
    evidence = [
        _ev("hip_shoulder_gap_ms", gap, "ms",
            f"个人基线（{_ref_count(ref, 'hip_shoulder_gap_ms')} 次）" if math.isfinite(baseline_gap) else "结构规则",
            baseline_gap if math.isfinite(baseline_gap) else float("nan"),
            note="负值=肩先于髋启动"),
    ]
    if math.isfinite(baseline_gap):
        evidence[0].deviation = f"本次 {_fmt(gap)}ms，基线 {_fmt(baseline_gap)}ms（均值）"
    else:
        evidence[0].deviation = f"本次 {_fmt(gap)}ms（肩先于髋 {_fmt(abs(gap))}ms）"
    diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "shoulder_starts_early", severity, reference_type, evidence,
                            hip_shoulder_gap_ms=gap, baseline_gap=baseline_gap if math.isfinite(baseline_gap) else None))


def _run_insufficient_hip(diagnoses: list[TechniqueDiagnosis], events: list[KeyEvent], ref: dict) -> None:
    hip_peak = event_value(events, "hip_angular_velocity_peak")
    if not math.isfinite(hip_peak) or hip_peak <= 0:
        return
    baseline_hip = _ref_mean(ref, "hip_angular_velocity_peak")
    if math.isfinite(baseline_hip) and baseline_hip > 0:
        ratio = hip_peak / baseline_hip
        deviation = _deviation_sigma(hip_peak, ref, "hip_angular_velocity_peak")
        if ratio >= 0.85:
            return
        severity = _severity_by_deviation(deviation) if math.isfinite(deviation) else (Severity.HIGH.value if ratio < 0.6 else Severity.MEDIUM.value)
        reference_type = ReferenceType.SELF_BASELINE.value
        evidence = [
            _ev("hip_angular_velocity_peak", hip_peak, "deg/s",
                f"个人基线（{_ref_count(ref, 'hip_angular_velocity_peak')} 次）", baseline_hip,
                deviation=f"本次 {_fmt(hip_peak)}deg/s，为基线的 {_fmt(ratio * 100, 0)}%"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "insufficient_hip_engagement", severity, reference_type, evidence,
                                hip_peak=hip_peak, baseline_hip=baseline_hip))
    # 无参考：不主动报（避免伪造标准），仅提示需要更多数据


def _run_arm_dominant(diagnoses: list[TechniqueDiagnosis], events: list[KeyEvent], ref: dict) -> None:
    hip_peak = event_value(events, "hip_angular_velocity_peak")
    elbow_peak = event_value(events, "elbow_extension_peak")
    wrist_peak = event_value(events, "wrist_speed_peak")
    if not math.isfinite(hip_peak) or not math.isfinite(elbow_peak) or hip_peak <= 0 or elbow_peak <= 0:
        return
    # 结构规则：髋角速度峰值明显低于肘伸展峰值 → 身体没跟上手臂
    ratio = hip_peak / elbow_peak
    if ratio >= 0.75:
        return
    severity = Severity.HIGH.value if ratio < 0.4 else (Severity.MEDIUM.value if ratio < 0.55 else Severity.LOW.value)
    evidence = [
        _ev("hip_to_elbow_peak_ratio", ratio, "ratio", "结构规则（髋峰值/肘峰值）", 0.75,
            deviation=f"髋峰值 {_fmt(hip_peak)}deg/s，肘峰值 {_fmt(elbow_peak)}deg/s，比值 {_fmt(ratio, 2)}"),
    ]
    diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "arm_dominant", severity, ReferenceType.STRUCTURAL_RULE.value, evidence,
                            hip_peak=hip_peak, elbow_peak=elbow_peak))


def _run_chain_order_mixed(diagnoses: list[TechniqueDiagnosis], events: list[KeyEvent], ref: dict) -> None:
    expected = ["hip_start", "shoulder_start", "elbow_extension_peak", "wrist_speed_peak"]
    frames = []
    for name in expected:
        f = next((e.frame_index for e in events if e.name == name), -1)
        frames.append((name, f))
    violations = []
    for i in range(len(frames) - 1):
        name_a, fa = frames[i]
        name_b, fb = frames[i + 1]
        if fa >= 0 and fb >= 0 and fb < fa:
            violations.append(f"{name_a}→{name_b}")
    if not violations:
        return
    severity = Severity.MEDIUM.value if len(violations) >= 2 else Severity.LOW.value
    evidence = [
        _ev("chain_order", len(violations), "violations", "期望顺序 髋→肩→肘→腕", 0,
            deviation="、".join(violations)),
    ]
    diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "chain_order_mixed", severity, ReferenceType.STRUCTURAL_RULE.value, evidence))


def _run_elbow_flare(diagnoses: list[TechniqueDiagnosis], bundle: SignalBundle, events: list[KeyEvent], ref: dict) -> None:
    idx = _index_of(bundle)
    if len(idx) == 0 or len(bundle.elbow_abduction) == 0:
        return
    # 加速→击打段（肘峰值→腕峰→最大伸展区间）的肘外翻均值
    f_elbow = _event_frame(events, "elbow_extension_peak")
    f_ext = _event_frame(events, "max_extension")
    start_i = _frame_to_idx(bundle, f_elbow) if f_elbow >= 0 else 0
    end_i = _frame_to_idx(bundle, f_ext) if f_ext >= 0 else len(idx) - 1
    segment = bundle.elbow_abduction[start_i : end_i + 1]
    finite = segment[np.isfinite(segment)]
    if len(finite) == 0:
        return
    mean_abduction = float(finite.mean())
    if not math.isfinite(mean_abduction) or mean_abduction < 0.45:
        return
    severity = Severity.HIGH.value if mean_abduction > 0.7 else (Severity.MEDIUM.value if mean_abduction > 0.55 else Severity.LOW.value)
    evidence = [
        _ev("elbow_abduction_ratio", mean_abduction, "×肩宽", "结构规则（肘偏离肩-腕连线）", 0.45,
            deviation=f"加速-击打段肘平均偏离连线 {_fmt(mean_abduction, 2)} 个肩宽"),
    ]
    diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "elbow_flare", severity, ReferenceType.STRUCTURAL_RULE.value, evidence,
                            elbow_abduction=mean_abduction))


def _run_excessive_forward_shift(diagnoses: list[TechniqueDiagnosis], bundle: SignalBundle, events: list[KeyEvent], window_stats: dict, ref: dict) -> None:
    shift = window_stats.get("hip_forward_shift")  # 相对躯干长度
    if shift is None or not math.isfinite(shift):
        return
    baseline_shift = _ref_mean(ref, "hip_forward_shift")
    if math.isfinite(baseline_shift) and baseline_shift > 0:
        deviation = _deviation_sigma(shift, ref, "hip_forward_shift")
        if shift < baseline_shift + _ref_std(ref, "hip_forward_shift"):
            return
        severity = _severity_by_deviation(deviation) if math.isfinite(deviation) else (Severity.MEDIUM.value if shift > baseline_shift * 1.3 else Severity.LOW.value)
        reference_type = ReferenceType.SELF_BASELINE.value
        evidence = [
            _ev("hip_forward_shift", shift, "×躯干长", f"个人基线（{_ref_count(ref, 'hip_forward_shift')} 次）", baseline_shift,
                deviation=f"本次 {_fmt(shift, 2)}，基线 {_fmt(baseline_shift, 2)}"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "excessive_forward_shift", severity, reference_type, evidence,
                                shift=shift, baseline_shift=baseline_shift))
    elif shift > 0.35:  # 结构规则：前冲超过 35% 躯干长度
        evidence = [
            _ev("hip_forward_shift", shift, "×躯干长", "结构规则（重心越出支撑面风险）", 0.35,
                deviation=f"本次前冲 {_fmt(shift, 2)} 个躯干长度"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "excessive_forward_shift", Severity.MEDIUM.value,
                                ReferenceType.STRUCTURAL_RULE.value, evidence, shift=shift))


def _run_insufficient_end_speed(diagnoses: list[TechniqueDiagnosis], events: list[KeyEvent], ref: dict) -> None:
    wrist_peak = event_value(events, "wrist_speed_peak")
    shoulder_peak = event_value(events, "shoulder_velocity_peak")
    if not math.isfinite(wrist_peak) or not math.isfinite(shoulder_peak) or shoulder_peak <= 0:
        return
    amplification = wrist_peak / shoulder_peak
    if amplification < 1.1:
        return
    baseline_amp = _ref_mean(ref, "terminal_amplification")
    if math.isfinite(baseline_amp) and baseline_amp > 0 and amplification < baseline_amp * 0.85:
        deviation = _deviation_sigma(amplification, ref, "terminal_amplification")
        severity = _severity_by_deviation(deviation)
        evidence = [
            _ev("terminal_amplification", amplification, "ratio", f"个人基线（{_ref_count(ref, 'terminal_amplification')} 次）", baseline_amp,
                deviation=f"本次放大比 {_fmt(amplification, 2)}（腕峰/肩峰），基线 {_fmt(baseline_amp, 2)}"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "insufficient_end_speed", severity, ReferenceType.SELF_BASELINE.value, evidence,
                                amplification=amplification, baseline_amp=baseline_amp))
    elif amplification < 1.2:  # 结构规则：腕速不到肩速 1.2 倍 → 末端没有加速
        evidence = [
            _ev("terminal_amplification", amplification, "ratio", "结构规则（末端应放大速度）", 1.2,
                deviation=f"腕峰 {_fmt(wrist_peak)}px/s，肩峰 {_fmt(shoulder_peak)}px/s，放大比 {_fmt(amplification, 2)}"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "insufficient_end_speed", Severity.MEDIUM.value,
                                ReferenceType.STRUCTURAL_RULE.value, evidence, amplification=amplification))


def _run_slow_recovery(diagnoses: list[TechniqueDiagnosis], timing: list[TimingLink], ref: dict) -> None:
    recovery = _timing_value(timing, "max_extension", "action_end")
    strike = _timing_value(timing, "wrist_speed_peak", "max_extension")
    if not math.isfinite(recovery) or not math.isfinite(strike) or strike <= 0:
        return
    ratio = recovery / strike
    baseline_ratio = _ref_mean(ref, "recovery_strike_ratio")
    if math.isfinite(baseline_ratio) and baseline_ratio > 0:
        deviation = _deviation_sigma(ratio, ref, "recovery_strike_ratio")
        if ratio < baseline_ratio + _ref_std(ref, "recovery_strike_ratio"):
            return
        severity = _severity_by_deviation(deviation)
        evidence = [
            _ev("recovery_strike_ratio", ratio, "ratio", f"个人基线（{_ref_count(ref, 'recovery_strike_ratio')} 次）", baseline_ratio,
                deviation=f"回收 {_fmt(recovery)}ms / 击打 {_fmt(strike)}ms = {_fmt(ratio, 2)}，基线 {_fmt(baseline_ratio, 2)}"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "slow_recovery", severity, ReferenceType.SELF_BASELINE.value, evidence,
                                recovery_ms=recovery, strike_ms=strike, ratio=ratio, baseline_ratio=baseline_ratio))
    elif ratio > 2.5:  # 结构规则：回收时间超过击打 2.5 倍
        evidence = [
            _ev("recovery_strike_ratio", ratio, "ratio", "结构规则", 2.5,
                deviation=f"回收 {_fmt(recovery)}ms，击打 {_fmt(strike)}ms，比值 {_fmt(ratio, 2)}"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "slow_recovery", Severity.MEDIUM.value,
                                ReferenceType.STRUCTURAL_RULE.value, evidence, recovery_ms=recovery, strike_ms=strike, ratio=ratio))


def _run_excessive_head_motion(diagnoses: list[TechniqueDiagnosis], window_stats: dict, ref: dict) -> None:
    """头部晃动过大：窗口内鼻尖累计位移（肩宽归一化）。"""
    total = window_stats.get("head_displacement")
    if total is None or not math.isfinite(total) or total <= 0:
        return
    baseline_head = _ref_mean(ref, "head_displacement")
    if math.isfinite(baseline_head) and baseline_head > 0:
        deviation = _deviation_sigma(total, ref, "head_displacement")
        if total < baseline_head + _ref_std(ref, "head_displacement"):
            return
        severity = _severity_by_deviation(deviation)
        evidence = [
            _ev("head_displacement", total, "×肩宽", f"个人基线（{_ref_count(ref, 'head_displacement')} 次）", baseline_head,
                deviation=f"本次头部累计位移 {_fmt(total, 2)} 个肩宽，基线 {_fmt(baseline_head, 2)}"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "excessive_head_motion", severity, ReferenceType.SELF_BASELINE.value, evidence,
                                head=total, baseline_head=baseline_head))
    elif total > 0.8:  # 结构规则：头部累计位移超过 0.8 个肩宽
        evidence = [
            _ev("head_displacement", total, "×肩宽", "结构规则（头部稳定要求）", 0.8,
                deviation=f"本次头部累计位移 {_fmt(total, 2)} 个肩宽"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "excessive_head_motion", Severity.MEDIUM.value,
                                ReferenceType.STRUCTURAL_RULE.value, evidence, head=total))


def _run_poor_stability(diagnoses: list[TechniqueDiagnosis], window_stats: dict, ref: dict) -> None:
    """稳定性：本次窗口内信号抖动 + 与基线对比。多窗口 CV 在 engine 层补充。"""
    jitter = window_stats.get("wrist_jitter")
    if jitter is None or not math.isfinite(jitter):
        return
    baseline_jitter = _ref_mean(ref, "wrist_jitter")
    if math.isfinite(baseline_jitter) and baseline_jitter > 0:
        deviation = _deviation_sigma(jitter, ref, "wrist_jitter")
        if jitter < baseline_jitter + _ref_std(ref, "wrist_jitter"):
            return
        severity = _severity_by_deviation(deviation)
        evidence = [
            _ev("wrist_jitter", jitter, "ratio", f"个人基线（{_ref_count(ref, 'wrist_jitter')} 次）", baseline_jitter,
                deviation=f"本次腕速抖动指数 {_fmt(jitter, 3)}，基线 {_fmt(baseline_jitter, 3)}"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "poor_stability", severity, ReferenceType.SELF_BASELINE.value, evidence,
                                jitter=jitter, baseline_jitter=baseline_jitter))
    elif jitter > 0.15:  # 结构规则：上升段抖动过大
        evidence = [
            _ev("wrist_jitter", jitter, "ratio", "结构规则（加速应平滑）", 0.15,
                deviation=f"本次腕速上升段抖动指数 {_fmt(jitter, 3)}"),
        ]
        diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "poor_stability", Severity.LOW.value,
                                ReferenceType.STRUCTURAL_RULE.value, evidence, jitter=jitter))


def _run_left_right_asymmetry(diagnoses: list[TechniqueDiagnosis], bundle: SignalBundle, events: list[KeyEvent], ref: dict) -> None:
    df = bundle.source_df
    if df is None:
        return
    # 用主手/另一侧腕速峰值比
    peak = event_value(events, "wrist_speed_peak")
    if not math.isfinite(peak) or peak <= 0:
        return
    side = bundle.strike_hand or "left"
    other_col = "left_wrist_speed" if side == "right" else "right_wrist_speed"
    other = pd_to_numeric(df[other_col]).max() if other_col in df.columns else float("nan")
    if not math.isfinite(other) or other <= 0:
        return
    ratio = peak / other
    if 0.6 <= ratio <= 1.4:
        return
    severity = Severity.MEDIUM.value if ratio < 0.45 or ratio > 1.8 else Severity.LOW.value
    evidence = [
        _ev("left_right_wrist_ratio", ratio, "ratio", "结构规则（双侧差异）", 1.0,
            deviation=f"主手（{side}）峰值 {_fmt(peak)}px/s，对侧 {_fmt(other)}px/s，比值 {_fmt(ratio, 2)}"),
    ]
    diagnoses.append(_build(STRAIGHT_PUNCH_PROFILE, "left_right_asymmetry", severity, ReferenceType.STRUCTURAL_RULE.value, evidence,
                            ratio=ratio))


# ---------------------------------------------------------------- 工具
def _build(profile, problem_id: str, severity: str, reference_type: str, evidence: list[DiagnosisEvidence],
           **context) -> TechniqueDiagnosis:
    error_def = next((e for e in profile.common_errors if e["id"] == problem_id), None)
    if error_def is None:
        raise ValueError(f"未知错误模式: {problem_id}")
    confidence = _confidence_for(reference_type)
    meaning = error_def["meaning_template"]
    advice = error_def["advice_template"]
    for key, value in context.items():
        if isinstance(value, float) and math.isfinite(value):
            meaning = meaning.replace(f"{{{key}}}", _fmt(value))
            advice = advice.replace(f"{{{key}}}", _fmt(value))
    evidence_text = "；".join(
        f"{e.metric}: {e.deviation or _fmt(e.value)}{(' ' + e.unit) if e.unit and e.unit != 'ratio' else ''}" for e in evidence
    )
    return TechniqueDiagnosis(
        problem_id=problem_id,
        problem=error_def["problem"],
        severity=severity,
        confidence=confidence,
        reference_type=reference_type,
        evidence=evidence,
        evidence_text=evidence_text,
        meaning=meaning,
        training_advice=advice,
    )


def _timing_value(timing: list[TimingLink], from_event: str, to_event: str) -> float:
    for link in timing:
        if link.from_event == from_event and link.to_event == to_event:
            return float(link.interval_ms)
    return float("nan")


def _index_of(bundle: SignalBundle) -> np.ndarray:
    return np.arange(len(bundle.frame_index))


def _frame_to_idx(bundle: SignalBundle, frame: int) -> int:
    idx = np.searchsorted(bundle.frame_index, frame)
    return int(idx)


def _event_frame(events: list[KeyEvent], name: str) -> int:
    for event in events:
        if event.name == name:
            return int(event.frame_index)
    return -1


def _ref_count(ref: dict, key: str) -> int:
    item = ref.get(key) or {}
    return int(item.get("count", 0))


def pd_to_numeric(series):
    import pandas as pd

    return pd.to_numeric(series, errors="coerce")
