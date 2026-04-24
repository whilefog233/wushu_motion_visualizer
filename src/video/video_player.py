from __future__ import annotations


def next_frame_index(current_frame: int, total_frames: int, playing: bool) -> int:
    if not playing or total_frames <= 0:
        return current_frame
    if current_frame >= total_frames - 1:
        return total_frames - 1
    return current_frame + 1
