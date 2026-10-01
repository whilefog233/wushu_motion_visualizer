"""动作阶段切分：准备 → 启动 → 加速 → 最大伸展/击打 → 回收。

阶段边界直接使用关键事件，保证"事件 → 阶段"一致（阶段时长 = 事件间隔）。
"""

from __future__ import annotations

from src.technique.events import event_frame
from src.technique.models import KeyEvent, Phase
from src.technique.profiles import STRAIGHT_PUNCH_PROFILE


def build_phases(events: list[KeyEvent], fps: float) -> list[Phase]:
    """按 Profile 的阶段定义，从事件切出动作阶段。"""

    def _event_frame(name: str) -> int:
        return event_frame(events, name)

    def _event_time(name: str) -> float:
        from src.technique.events import event_time

        return event_time(events, name)

    phases: list[Phase] = []
    for phase_def in STRAIGHT_PUNCH_PROFILE.phases:
        start_event = phase_def["start_event"]
        end_event = phase_def["end_event"]
        f_start = _event_frame(start_event)
        f_end = _event_frame(end_event)
        if f_start < 0 or f_end < 0 or f_end < f_start:
            f_start, f_end = _fallback_boundaries(start_event, end_event, f_start, f_end, events)
        t_start = _event_time(start_event)
        t_end = _event_time(end_event)
        duration_ms = (t_end - t_start) * 1000.0 if t_start == t_start and t_end == t_end and t_end >= t_start else float("nan")
        phases.append(
            Phase(
                name=phase_def["id"],
                label=phase_def["label"],
                start_event=start_event,
                end_event=end_event,
                frame_start=f_start,
                frame_end=f_end,
                time_start_sec=t_start,
                time_end_sec=t_end,
                duration_ms=duration_ms,
            )
        )
    return phases


def _fallback_boundaries(start_event: str, end_event: str, f_start: int, f_end: int, events: list[KeyEvent]) -> tuple[int, int]:
    """事件缺失时回退到相邻事件边界，尽量不让阶段丢失。"""
    ordered_frames = [e.frame_index for e in events if e.frame_index >= 0]
    if not ordered_frames:
        return 0, 0
    lo, hi = min(ordered_frames), max(ordered_frames)
    if f_start < 0:
        f_start = lo
    if f_end < 0:
        f_end = hi
    if f_end < f_start:
        f_end = f_start
    return f_start, f_end
