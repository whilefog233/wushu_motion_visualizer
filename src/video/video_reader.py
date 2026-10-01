from __future__ import annotations

"""统一视频读取器。

解决旧代码里反复 ``VideoCapture() → seek → read → release`` 的问题：
一个流程内只打开一次 VideoCapture，顺序迭代或按帧号跳读都复用同一个对象。
"""

from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np

from src.utils.video_utils import resize_with_aspect_ratio


class VideoReader:
    """可复用的 OpenCV 视频读取封装。

    用法::

        with VideoReader(path, max_side=1280) as reader:
            for frame in reader.iter_frames():
                ...

        frame = reader.read_at(100)   # 同一 capture 对象上跳读
    """

    def __init__(self, video_path: str | Path, max_side: int | None = None):
        self.video_path = Path(video_path)
        self.max_side = max_side
        self.capture = cv2.VideoCapture(str(self.video_path))
        if not self.capture.isOpened():
            raise RuntimeError(f"无法打开视频: {self.video_path}")

        self.fps: float = float(self.capture.get(cv2.CAP_PROP_FPS) or 25.0)
        self.frame_count: int = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.source_width: int = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self.source_height: int = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        # width/height 表示 read() 实际返回的帧尺寸（应用 max_side 缩放之后）
        self.width, self.height = self._output_size(self.source_width, self.source_height, max_side)

    @staticmethod
    def _output_size(src_width: int, src_height: int, max_side: int | None) -> tuple[int, int]:
        if max_side is None or max(src_height, src_width) <= max_side:
            return src_width, src_height
        scale = max_side / float(max(src_height, src_width))
        return max(1, int(src_width * scale)), max(1, int(src_height * scale))

    @property
    def duration(self) -> float:
        if self.fps <= 0:
            return 0.0
        return self.frame_count / self.fps

    # ------------------------------------------------------------------ 基础读帧
    def read(self) -> Optional[np.ndarray]:
        """读取下一帧并返回（按需缩放），读到结尾返回 None。"""
        success, frame = self.capture.read()
        if not success:
            return None
        return self._maybe_resize(frame)

    def read_at(self, frame_index: int) -> Optional[np.ndarray]:
        """跳读到指定帧（同一 capture 上 seek 一次）。"""
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(frame_index)))
        return self.read()

    def iter_frames(self, start: int = 0, end: Optional[int] = None) -> Iterator[np.ndarray]:
        """按顺序迭代帧，复用同一个 capture 对象。"""
        if start > 0:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, int(start))
        index = start
        while True:
            if end is not None and index >= int(end):
                break
            frame = self.read()
            if frame is None:
                break
            yield frame
            index += 1

    def _maybe_resize(self, frame: np.ndarray) -> np.ndarray:
        if self.max_side is None:
            return frame
        return resize_with_aspect_ratio(frame, self.max_side)

    # ------------------------------------------------------------------ 生命周期
    def close(self) -> None:
        self.capture.release()

    def __enter__(self) -> "VideoReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
