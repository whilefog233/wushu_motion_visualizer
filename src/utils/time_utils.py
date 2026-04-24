from __future__ import annotations


def frame_to_seconds(frame_index: int, fps: float) -> float:
    if fps <= 0:
        return 0.0
    return float(frame_index) / float(fps)


def format_seconds(seconds: float) -> str:
    total_ms = max(0, int(seconds * 1000))
    mins, ms_remaining = divmod(total_ms, 60_000)
    secs, ms = divmod(ms_remaining, 1000)
    return f"{mins:02d}:{secs:02d}.{ms:03d}"
