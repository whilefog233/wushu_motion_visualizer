"""关键事件检测：直拳动作周期内的 10 个事件。

原则：
- 启动检测用"相对基线"（窗口前段信号均值 + kσ），不写死绝对阈值。
- 峰值检测带 prominence 过滤，避免局部小峰干扰。
- 事件必须落到帧索引，并带 confidence（信号质量）。
"""

from __future__ import annotations

import math

import numpy as np

from src.technique.models import KeyEvent
from src.technique.signals import SignalBundle

ONSET_MULTIPLIER = 2.5   # 基线均值 + 2.5σ
ONSET_MIN_FRAMES = 3     # 启动需持续 ≥3 帧（防单帧噪声）
PEAK_PROMINENCE = 0.25   # 峰值显著性（相对峰值的比例）


def detect_onset_index(
    signal: np.ndarray,
    start: int,
    end: int,
    baseline: tuple[float, float],
    min_frames: int = ONSET_MIN_FRAMES,
) -> int:
    """信号首次突破基线的帧索引（相对窗口内绝对索引）。找不到返回 -1。

    阈值 = 基线均值 + max(2.5σ, 最小噪声带)。最小噪声带取信号幅值的 2%，
    避免 std≈0（信号过于干净）时阈值退化为均值、任何浮点噪声都触发误检。
    这是自适应噪声带，不是绝对性能标准。
    """
    mean, std = baseline
    finite = signal[np.isfinite(signal)]
    signal_scale = float(np.nanmax(np.abs(finite))) if len(finite) else 0.0
    if not math.isfinite(signal_scale):
        signal_scale = 0.0
    min_band = max(0.02 * signal_scale, 1e-9)
    threshold = mean + max(ONSET_MULTIPLIER * std, min_band)
    run = 0
    for i in range(start, end + 1):
        value = float(signal[i]) if i < len(signal) else float("nan")
        if math.isfinite(value) and value > threshold:
            run += 1
            if run >= min_frames:
                return i - run + 1
        else:
            run = 0
    return -1


def detect_peak_index(signal: np.ndarray, start: int, end: int, prominence_ratio: float = PEAK_PROMINENCE) -> int:
    """窗口内峰值帧索引（含显著性过滤），找不到返回 -1。"""
    if end < start:
        return -1
    segment = signal[start : end + 1]
    finite = segment[np.isfinite(segment)]
    if len(finite) == 0:
        return -1
    peak_value = float(finite.max())
    if peak_value <= 0 or not math.isfinite(peak_value):
        # 负向信号（如角速度可能为负）取绝对值峰值
        abs_segment = np.abs(segment)
        abs_finite = abs_segment[np.isfinite(abs_segment)]
        if len(abs_finite) == 0:
            return -1
        peak_value = float(abs_finite.max())
        positions = np.where(np.abs(segment) == peak_value)[0]
        return start + int(positions[-1]) if len(positions) else -1
    threshold = peak_value * (1 - prominence_ratio)
    positions = np.where(segment >= threshold)[0]
    return start + int(positions[-1]) if len(positions) else -1


def baseline_stats(signal: np.ndarray, start: int, end: int) -> tuple[float, float]:
    """窗口前段（准备阶段）的基线统计：均值与标准差。"""
    if end < start:
        return 0.0, 1.0
    segment = signal[start : end + 1]
    finite = segment[np.isfinite(segment)]
    if len(finite) == 0:
        return 0.0, 1.0
    return float(finite.mean()), float(finite.std())


def detect_events(bundle: SignalBundle, frame_start: int, frame_end: int) -> tuple[list[KeyEvent], list[KeyEvent]]:
    """检测窗口内全部关键事件。

    返回 (events, warnings)：events 为按时间排序的事件列表；warnings 为检测问题说明。
    """
    warnings: list[KeyEvent] = []
    fps = bundle.fps if bundle.fps > 0 else 30.0
    n = len(bundle.frame_index)
    idx_start = int(np.searchsorted(bundle.frame_index, frame_start))
    idx_end = int(np.searchsorted(bundle.frame_index, frame_end, side="right")) - 1
    idx_end = max(idx_start, min(idx_end, n - 1))
    if idx_end - idx_start < 5:
        warnings.append(KeyEvent(name="insufficient_window", label="窗口过短", frame_index=frame_start,
                                 time_sec=bundle.time_at(frame_start), description="窗口内有效帧太少，事件不可靠"))
        return [], warnings

    # 基线：窗口前段（固定 ≤10 帧）作为准备段——窗口起止由峰检测给出，
    # 前 25% 可能已包含启动段，会污染基线统计（启动点落在基线内则检测失真）。
    base_len = min(10, max(4, (idx_end - idx_start) // 8))
    base_start = idx_start
    base_end = idx_start + base_len

    def _time(i: int) -> float:
        return float(bundle.timestamps[i]) if 0 <= i < n else float("nan")

    def _make(name: str, label: str, i: int, signal: np.ndarray, unit: str = "", description: str = "") -> KeyEvent:
        return KeyEvent(
            name=name,
            label=label,
            frame_index=int(bundle.frame_index[i]) if 0 <= i < n else -1,
            time_sec=_time(i) if 0 <= i < n else float("nan"),
            value=float(signal[i]) if 0 <= i < n and len(signal) > i and math.isfinite(signal[i]) else float("nan"),
            unit=unit,
            description=description,
            confidence=0.7,
        )

    events: list[KeyEvent] = []

    # ---- 1. 髋启动 / 肩启动 / 腕启动（相对基线）
    hip_base = baseline_stats(bundle.hip_angular_velocity, idx_start, base_end)
    sh_base = baseline_stats(bundle.shoulder_speed, idx_start, base_end)
    wr_base = baseline_stats(bundle.wrist_speed, idx_start, base_end)

    hip_start_i = detect_onset_index(bundle.hip_angular_velocity, idx_start + 1, idx_end, hip_base)
    sh_start_i = detect_onset_index(bundle.shoulder_speed, idx_start + 1, idx_end, sh_base)
    wr_start_i = detect_onset_index(bundle.wrist_speed, idx_start + 1, idx_end, wr_base)

    hip_start_i = _clamp(hip_start_i, idx_start, idx_end)
    sh_start_i = _clamp(sh_start_i, idx_start, idx_end)
    wr_start_i = _clamp(wr_start_i, idx_start, idx_end)

    if hip_start_i < 0:
        hip_start_i = idx_start + 2
        warnings.append(_make("hip_start_low_signal", "髋启动信号弱", idx_start + 2, bundle.hip_angular_velocity,
                              description="髋角速度未明显突破基线，事件按窗口起点估计"))
    if sh_start_i < 0:
        sh_start_i = idx_start + 3
        warnings.append(_make("shoulder_start_low_signal", "肩启动信号弱", idx_start + 3, bundle.shoulder_speed,
                              description="肩速度未明显突破基线，事件按窗口起点估计"))
    if wr_start_i < 0:
        wr_start_i = idx_start + 3
        warnings.append(_make("wrist_start_low_signal", "手腕启动信号弱", idx_start + 3, bundle.wrist_speed,
                              description="腕速度未明显突破基线，事件按窗口起点估计"))

    events.append(_make("window_start", "动作开始", idx_start, bundle.wrist_speed, description="分析窗口起点"))
    events.append(_make("hip_start", "髋启动", hip_start_i, bundle.hip_angular_velocity, unit="deg/s",
                        description="髋角速度首次突破基线噪声带"))
    events.append(_make("shoulder_start", "肩启动", sh_start_i, bundle.shoulder_speed, unit="px/s",
                        description="肩线速度首次突破基线噪声带"))
    events.append(_make("wrist_start", "手腕启动", wr_start_i, bundle.wrist_speed, unit="px/s",
                        description="主手手腕速度首次突破基线噪声带"))

    # ---- 2. 峰值事件（在启动点之后搜索）
    search_start = max(idx_start, min(hip_start_i, sh_start_i, wr_start_i))
    hip_peak_i = detect_peak_index(bundle.hip_angular_velocity, search_start, idx_end)
    sh_peak_i = detect_peak_index(bundle.shoulder_speed, search_start, idx_end)
    elb_peak_i = detect_peak_index(bundle.elbow_angular_velocity, search_start, idx_end)
    wr_peak_i = detect_peak_index(bundle.wrist_speed, search_start, idx_end)
    hip_peak_i = _clamp(hip_peak_i, idx_start, idx_end)
    sh_peak_i = _clamp(sh_peak_i, idx_start, idx_end)
    elb_peak_i = _clamp(elb_peak_i, idx_start, idx_end)
    wr_peak_i = _clamp(wr_peak_i, idx_start, idx_end)

    # 最大伸展：主手肘角最大
    max_ext_i = detect_peak_index(bundle.elbow_angle, max(idx_start, elb_peak_i), idx_end)

    # 回收开始：腕速从峰值显著回落的第一个点（降到峰值的一定比例）
    rec_start_i = _detect_recovery_start(bundle.wrist_speed, wr_peak_i, idx_end)

    # 动作结束：肘角回到接近起始（肘角回落，接近窗口起始肘角值）
    end_i = _detect_action_end(bundle.elbow_angle, max_ext_i, idx_end, idx_start)

    max_ext_i = _clamp(max_ext_i, idx_start, idx_end)
    rec_start_i = _clamp(rec_start_i, idx_start, idx_end)
    end_i = _clamp(end_i, idx_start, idx_end)

    events.append(_make("hip_angular_velocity_peak", "髋角速度峰值", hip_peak_i, bundle.hip_angular_velocity, unit="deg/s",
                        description="髋旋转最快的时刻"))
    events.append(_make("shoulder_velocity_peak", "肩速度峰值", sh_peak_i, bundle.shoulder_speed, unit="px/s",
                        description="肩移动最快的时刻"))
    events.append(_make("elbow_extension_peak", "肘伸展峰值", elb_peak_i, bundle.elbow_angular_velocity, unit="deg/s",
                        description="主手肘伸展角速度峰值"))
    events.append(_make("wrist_speed_peak", "手腕速度峰值", wr_peak_i, bundle.wrist_speed, unit="px/s",
                        description="主手手腕速度峰值"))
    events.append(_make("max_extension", "最大伸展", max_ext_i, bundle.elbow_angle, unit="deg",
                        description="主手肘角最大（手臂接近伸直）"))
    events.append(_make("recovery_start", "回收开始", rec_start_i, bundle.wrist_speed, unit="px/s",
                        description="腕速从峰值显著回落，出拳结束"))
    events.append(_make("action_end", "动作结束", end_i, bundle.elbow_angle, unit="deg",
                        description="肘角回到接近起始，动作周期结束"))

    # 兜底：确保事件单调递增
    events = _enforce_monotonic(events)
    return events, warnings


def _detect_recovery_start(signal: np.ndarray, peak_i: int, idx_end: int) -> int:
    """回收开始：腕速降到峰值 40% 以下的第一个点。"""
    if peak_i < 0 or peak_i >= idx_end:
        return idx_end
    peak_value = float(signal[peak_i])
    if not math.isfinite(peak_value) or peak_value <= 0:
        return idx_end
    threshold = peak_value * 0.4
    for i in range(peak_i + 1, idx_end + 1):
        value = float(signal[i]) if i < len(signal) else float("nan")
        if math.isfinite(value) and value <= threshold:
            return i
    return idx_end


def _detect_action_end(elbow_angle: np.ndarray, max_ext_i: int, idx_end: int, idx_start: int) -> int:
    """动作结束：肘角回落到接近起始值的点（起始值 + 20% 伸展范围）。"""
    if max_ext_i < 0:
        return idx_end
    start_angle = float(elbow_angle[idx_start]) if idx_start < len(elbow_angle) and math.isfinite(elbow_angle[idx_start]) else float("nan")
    max_angle = float(elbow_angle[max_ext_i]) if max_ext_i < len(elbow_angle) and math.isfinite(elbow_angle[max_ext_i]) else float("nan")
    if not math.isfinite(start_angle) or not math.isfinite(max_angle) or max_angle <= start_angle:
        return idx_end
    range_ = max_angle - start_angle
    return_threshold = start_angle + 0.25 * range_
    for i in range(max_ext_i + 1, idx_end + 1):
        value = float(elbow_angle[i]) if i < len(elbow_angle) else float("nan")
        if math.isfinite(value) and value <= return_threshold:
            return i
    return idx_end


def _clamp(index: int, lo: int, hi: int) -> int:
    if index < 0:
        return -1
    return max(lo, min(hi, index))


def _enforce_monotonic(events: list[KeyEvent]) -> list[KeyEvent]:
    """按帧索引排序，保留检测到的时序原值。

    注意：肩启动可以合法地早于髋启动（这正是"肩启动过早"问题的信号），
    因此这里不做"向后推帧"的强制单调化，否则会抹掉问题信息。
    帧索引为 -1（检测失败）的事件保留，由时序层按无效处理。
    """
    return sorted(events, key=lambda e: (e.frame_index if e.frame_index >= 0 else 10**9))


def event_time(events: list[KeyEvent], name: str) -> float:
    for event in events:
        if event.name == name:
            return float(event.time_sec)
    return float("nan")


def event_frame(events: list[KeyEvent], name: str) -> int:
    for event in events:
        if event.name == name:
            return int(event.frame_index)
    return -1


def event_value(events: list[KeyEvent], name: str) -> float:
    for event in events:
        if event.name == name:
            return float(event.value)
    return float("nan")
