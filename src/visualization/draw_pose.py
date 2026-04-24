from __future__ import annotations

from collections import deque
from typing import Iterable, Mapping

import cv2
import mediapipe as mp
import numpy as np


TRACK_COLORS = {
    "left_wrist": (0, 200, 255),
    "right_wrist": (255, 140, 0),
    "left_ankle": (80, 220, 120),
    "right_ankle": (220, 80, 160),
    "hip_center": (220, 220, 220),
}


def _point_to_int(point: Mapping[str, float] | None) -> tuple[int, int] | None:
    if not point:
        return None
    x = point.get("pixel_x")
    y = point.get("pixel_y")
    if x is None or y is None:
        return None
    if not np.isfinite([x, y]).all():
        return None
    return int(x), int(y)


def create_skeleton_canvas(frame_shape: tuple[int, int, int], background_bgr: tuple[int, int, int]) -> np.ndarray:
    canvas = np.zeros(frame_shape, dtype=np.uint8)
    canvas[:, :] = background_bgr
    return canvas


def draw_pose_landmarks(
    canvas: np.ndarray,
    landmarks: Mapping[str, Mapping[str, float]],
    connections: Iterable[tuple[mp.solutions.pose.PoseLandmark, mp.solutions.pose.PoseLandmark]],
) -> np.ndarray:
    landmark_names = [landmark.name.lower() for landmark in mp.solutions.pose.PoseLandmark]
    for connection in connections:
        start_landmark = connection[0]
        end_landmark = connection[1]
        start_name = start_landmark.name.lower() if hasattr(start_landmark, "name") else landmark_names[int(start_landmark)]
        end_name = end_landmark.name.lower() if hasattr(end_landmark, "name") else landmark_names[int(end_landmark)]
        start = _point_to_int(landmarks.get(start_name))
        end = _point_to_int(landmarks.get(end_name))
        if start is None or end is None:
            continue
        cv2.line(canvas, start, end, (0, 210, 255), 2, lineType=cv2.LINE_AA)

    for name, point in landmarks.items():
        pixel = _point_to_int(point)
        if pixel is None:
            continue
        radius = 5 if "wrist" in name or "ankle" in name else 4
        color = TRACK_COLORS.get(name, (255, 255, 255))
        cv2.circle(canvas, pixel, radius, color, -1, lineType=cv2.LINE_AA)
    return canvas


def draw_trajectories(
    canvas: np.ndarray,
    trajectory_buffers: Mapping[str, deque[tuple[float, float]]],
    radius: int = 2,
) -> np.ndarray:
    for name, points in trajectory_buffers.items():
        if len(points) < 2:
            continue
        base_color = TRACK_COLORS.get(name, (255, 255, 255))
        int_points = []
        for x, y in points:
            if not np.isfinite([x, y]).all():
                continue
            int_points.append((int(x), int(y)))

        point_count = len(int_points)
        if point_count < 2:
            continue

        overlay = canvas.copy()
        for index, point in enumerate(int_points):
            fade_ratio = (index + 1) / point_count
            faded_color = tuple(int(channel * fade_ratio) for channel in base_color)
            cv2.circle(overlay, point, radius, faded_color, -1, lineType=cv2.LINE_AA)
            if index > 0:
                cv2.line(overlay, int_points[index - 1], point, faded_color, 1, lineType=cv2.LINE_AA)
        canvas = cv2.addWeighted(overlay, 0.5, canvas, 0.5, 0)
    return canvas


def draw_overlay_text(
    frame: np.ndarray,
    lines: list[str],
    origin: tuple[int, int] = (16, 28),
    line_height: int = 24,
) -> np.ndarray:
    x, y = origin
    for index, line in enumerate(lines):
        location = (x, y + index * line_height)
        cv2.putText(frame, line, location, cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 20, 20), 3, cv2.LINE_AA)
        cv2.putText(frame, line, location, cv2.FONT_HERSHEY_SIMPLEX, 0.62, (235, 235, 235), 1, cv2.LINE_AA)
    return frame


def compose_side_by_side(original_frame: np.ndarray, skeleton_frame: np.ndarray) -> np.ndarray:
    if original_frame.shape[0] != skeleton_frame.shape[0]:
        skeleton_frame = cv2.resize(skeleton_frame, (skeleton_frame.shape[1], original_frame.shape[0]))
    return np.concatenate([original_frame, skeleton_frame], axis=1)
