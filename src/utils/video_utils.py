from __future__ import annotations

import hashlib
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


def _resolve_ffmpeg() -> Optional[str]:
    """优先系统 PATH 的 ffmpeg；没有则回退到 imageio-ffmpeg 自带二进制。"""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def transcode_to_browser_mp4(input_path: Path, output_path: Path) -> bool:
    """转码为浏览器可播放的 H.264 + yuv420p + faststart。

    仅当确实需要（浏览器不支持的编码 / 显式导出 H.264）时才转码，
    避免无意义二次编码。返回是否转码成功。
    """
    ffmpeg_path = _resolve_ffmpeg()
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


def video_fingerprint(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """计算视频内容指纹（md5，分块流式读取，不把整个文件读进内存）。

    用于"同一视频不重复分析"：上传文件名带时间戳、mtime 不同，
    但内容字节完全一致时指纹相同。
    """
    hasher = hashlib.md5()
    with open(path, "rb") as file_handle:
        while True:
            chunk = file_handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()
