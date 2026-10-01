"""发力链时序分析：髋→肩→肘→腕 的启动与峰值间隔（毫秒）。

时序是直拳诊断的核心：判断动力传递链是否被压缩、是否乱序。
所有间隔都是相对量，不做绝对"标准值"；是否"好"交给参考系统判断。
"""

from __future__ import annotations

import math

from src.technique.events import event_frame, event_time
from src.technique.models import KeyEvent, TimingLink


def build_timing(events: list[KeyEvent], fps: float) -> list[TimingLink]:
    """计算关键时序间隔（毫秒）。fps 用于帧差兜底。"""

    def _frame(name: str) -> int:
        return event_frame(events, name)

    def _time(name: str) -> float:
        return event_time(events, name)

    def _interval(a: str, b: str) -> tuple[float, bool]:
        """返回 (间隔_ms, 是否有效)。顺序为 a → b。"""
        fa, fb = _frame(a), _frame(b)
        ta, tb = _time(a), _time(b)
        if fa < 0 or fb < 0:
            return float("nan"), False
        if math.isfinite(ta) and math.isfinite(tb):
            return (tb - ta) * 1000.0, True
        if fps > 0:
            return (fb - fa) * 1000.0 / fps, True
        return float("nan"), False

    links: list[TimingLink] = []

    # ---- 启动时序
    hip_sh_gap, ok = _interval("hip_start", "shoulder_start")
    links.append(TimingLink(
        from_event="hip_start", to_event="shoulder_start", label="髋→肩 启动间隔",
        interval_ms=hip_sh_gap if ok else float("nan"),
        expected_order="髋先启动，肩稍后跟进", order_ok=_order_ok(hip_sh_gap, ok),
        note="肩早于髋（负值）提示肩启动过早" if (ok and hip_sh_gap < -15) else "",
    ))
    sh_wr_gap, ok = _interval("shoulder_start", "wrist_start")
    links.append(TimingLink(
        from_event="shoulder_start", to_event="wrist_start", label="肩→腕 启动间隔",
        interval_ms=sh_wr_gap if ok else float("nan"),
        expected_order="肩启动后手腕启动", order_ok=_order_ok(sh_wr_gap, ok),
    ))

    # ---- 峰值时序
    hip_peak_t = _time("hip_angular_velocity_peak")
    sh_peak_t = _time("shoulder_velocity_peak")
    elb_peak_t = _time("elbow_extension_peak")
    wr_peak_t = _time("wrist_speed_peak")

    def _peak_interval(a_time: float, b_time: float, a_name: str, b_name: str, label: str) -> TimingLink:
        ok = math.isfinite(a_time) and math.isfinite(b_time)
        interval = (b_time - a_time) * 1000.0 if ok else float("nan")
        return TimingLink(
            from_event=a_name, to_event=b_name, label=label,
            interval_ms=interval, expected_order="峰值按发力链顺序出现", order_ok=_order_ok(interval, ok),
        )

    links.append(_peak_interval(hip_peak_t, sh_peak_t, "hip_angular_velocity_peak", "shoulder_velocity_peak", "髋→肩 峰值间隔"))
    links.append(_peak_interval(sh_peak_t, elb_peak_t, "shoulder_velocity_peak", "elbow_extension_peak", "肩→肘 峰值间隔"))
    links.append(_peak_interval(elb_peak_t, wr_peak_t, "elbow_extension_peak", "wrist_speed_peak", "肘→腕 峰值间隔"))

    # ---- 关键总时长
    strike_ms, ok = _interval("wrist_speed_peak", "max_extension")
    links.append(TimingLink(
        from_event="wrist_speed_peak", to_event="max_extension", label="击打时长（腕峰→最大伸展）",
        interval_ms=strike_ms if ok else float("nan"), expected_order="腕峰后到达最大伸展",
    ))
    recovery_ms, ok = _interval("max_extension", "action_end")
    links.append(TimingLink(
        from_event="max_extension", to_event="action_end", label="回收时长（最大伸展→动作结束）",
        interval_ms=recovery_ms if ok else float("nan"), expected_order="回收段",
    ))
    total_ms, ok = _interval("hip_start", "action_end")
    links.append(TimingLink(
        from_event="hip_start", to_event="action_end", label="动作总时长（髋启动→结束）",
        interval_ms=total_ms if ok else float("nan"), expected_order="动作周期",
    ))
    return links


def _order_ok(interval_ms: float, valid: bool) -> bool:
    """间隔为正（顺序正确）且不过分小。小负值（>-15ms）视为测量噪声。"""
    if not valid:
        return None
    if math.isfinite(interval_ms):
        return interval_ms >= -15.0
    return None


def timing_value(links: list[TimingLink], from_event: str, to_event: str) -> float:
    for link in links:
        if link.from_event == from_event and link.to_event == to_event:
            return float(link.interval_ms)
    return float("nan")
