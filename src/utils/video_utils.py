from __future__ import annotations

from pathlib import Path
from typing import Optional

import shutil
import subprocess

import cv2
import numpy as np


def resize_with_aspect_ratio(frame: np.ndarray, max_side: int) -> np.ndarray:
    height, width = frame.shape[:2]
    longest_side = max(height, width)
    if longest_side <= max_side:
        return frame
    scale = max_side / float(longest_side)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)


def make_video_writer(path: Path, fps: float, frame_size: tuple[int, int]) -> cv2.VideoWriter:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(str(path), fourcc, fps, frame_size)


def transcode_to_browser_mp4(input_path: Path, output_path: Path) -> bool:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        return False

    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0 and output_path.exists()


def read_frame_at_index(video_path: str | Path, frame_index: int) -> Optional[np.ndarray]:
    capture = cv2.VideoCapture(str(video_path))
    capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(frame_index)))
    success, frame = capture.read()
    capture.release()
    if not success:
        return None
    return frame


def split_side_by_side_frame(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    width = frame.shape[1]
    half_width = width // 2
    return frame[:, :half_width].copy(), frame[:, half_width:].copy()
