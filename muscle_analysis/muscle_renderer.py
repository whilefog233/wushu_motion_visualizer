from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from muscle_analysis.muscle_estimator import MUSCLE_LABELS
from src.analysis.kinematics import midpoint
from src.visualization.draw_pose import draw_pose_landmarks


MUSCLE_COLORS = {
    "quadriceps": (60, 120, 255),
    "hamstrings": (180, 80, 220),
    "glutes": (70, 90, 255),
    "calves": (70, 210, 120),
    "erector_spinae": (255, 165, 70),
    "obliques": (80, 220, 220),
    "deltoids": (255, 210, 80),
    "forearms": (190, 130, 255),
}


def _point(point: Mapping[str, float] | None) -> tuple[float, float] | None:
    if not point:
        return None
    x = point.get("pixel_x")
    y = point.get("pixel_y")
    if x is None or y is None or not np.isfinite([x, y]).all():
        return None
    return float(x), float(y)


def _line_polygon(start: tuple[float, float] | None, end: tuple[float, float] | None, thickness: float) -> np.ndarray | None:
    if start is None or end is None:
        return None
    vector = np.asarray([end[0] - start[0], end[1] - start[1]], dtype=np.float32)
    length = float(np.linalg.norm(vector))
    if length <= 1e-6:
        return None
    direction = vector / length
    normal = np.asarray([-direction[1], direction[0]], dtype=np.float32) * (thickness / 2.0)
    p1 = np.asarray(start, dtype=np.float32) + normal
    p2 = np.asarray(start, dtype=np.float32) - normal
    p3 = np.asarray(end, dtype=np.float32) - normal
    p4 = np.asarray(end, dtype=np.float32) + normal
    return np.array([p1, p2, p3, p4], dtype=np.int32)


def _torso_polygon(
    left_shoulder: tuple[float, float] | None,
    right_shoulder: tuple[float, float] | None,
    left_hip: tuple[float, float] | None,
    right_hip: tuple[float, float] | None,
) -> np.ndarray | None:
    if not all([left_shoulder, right_shoulder, left_hip, right_hip]):
        return None
    return np.array([left_shoulder, right_shoulder, right_hip, left_hip], dtype=np.int32)


class MuscleRenderer:
    def __init__(self):
        self.font_path = self._resolve_font_path()

    def render_frame(
        self,
        original_frame: np.ndarray,
        landmarks: Mapping[str, Mapping[str, float]],
        connections: Iterable[tuple[object, object]],
        engagement: Mapping[str, float],
        power_chain_text: str,
        top_muscles: list[tuple[str, float]],
    ) -> np.ndarray:
        frame = original_frame.copy()
        frame = self._apply_muscle_overlays(frame, landmarks, engagement)
        frame = draw_pose_landmarks(frame, landmarks, connections)
        frame = self._draw_text_panels(frame, top_muscles, power_chain_text)
        return frame

    def _apply_muscle_overlays(
        self,
        frame: np.ndarray,
        landmarks: Mapping[str, Mapping[str, float]],
        engagement: Mapping[str, float],
    ) -> np.ndarray:
        overlay = frame.copy()

        left_shoulder = _point(landmarks.get("left_shoulder"))
        right_shoulder = _point(landmarks.get("right_shoulder"))
        left_elbow = _point(landmarks.get("left_elbow"))
        right_elbow = _point(landmarks.get("right_elbow"))
        left_wrist = _point(landmarks.get("left_wrist"))
        right_wrist = _point(landmarks.get("right_wrist"))
        left_hip = _point(landmarks.get("left_hip"))
        right_hip = _point(landmarks.get("right_hip"))
        left_knee = _point(landmarks.get("left_knee"))
        right_knee = _point(landmarks.get("right_knee"))
        left_ankle = _point(landmarks.get("left_ankle"))
        right_ankle = _point(landmarks.get("right_ankle"))

        shoulder_width = self._distance(left_shoulder, right_shoulder)
        hip_width = self._distance(left_hip, right_hip)
        leg_width = max(16.0, (hip_width if hip_width > 0 else shoulder_width) * 0.22)
        arm_width = max(12.0, shoulder_width * 0.14 if shoulder_width > 0 else 14.0)

        region_specs = [
            ("quadriceps", _line_polygon(left_hip, left_knee, leg_width), 0.55),
            ("quadriceps", _line_polygon(right_hip, right_knee, leg_width), 0.55),
            ("hamstrings", _line_polygon(left_hip, left_knee, leg_width * 0.85), 0.38),
            ("hamstrings", _line_polygon(right_hip, right_knee, leg_width * 0.85), 0.38),
            ("calves", _line_polygon(left_knee, left_ankle, leg_width * 0.78), 0.55),
            ("calves", _line_polygon(right_knee, right_ankle, leg_width * 0.78), 0.55),
            ("forearms", _line_polygon(left_elbow, left_wrist, arm_width), 0.55),
            ("forearms", _line_polygon(right_elbow, right_wrist, arm_width), 0.55),
            ("deltoids", self._circle_polygon(left_shoulder, max(14.0, shoulder_width * 0.12)), 0.5),
            ("deltoids", self._circle_polygon(right_shoulder, max(14.0, shoulder_width * 0.12)), 0.5),
            ("glutes", self._circle_polygon(left_hip, max(18.0, hip_width * 0.18)), 0.48),
            ("glutes", self._circle_polygon(right_hip, max(18.0, hip_width * 0.18)), 0.48),
            ("erector_spinae", _torso_polygon(left_shoulder, right_shoulder, left_hip, right_hip), 0.28),
            ("obliques", _torso_polygon(left_shoulder, right_shoulder, left_hip, right_hip), 0.22),
        ]

        for muscle_name, polygon, alpha_scale in region_specs:
            if polygon is None:
                continue
            engagement_value = float(np.clip(float(engagement.get(muscle_name, 0.0)), 0.0, 1.0))
            if engagement_value <= 0.02:
                continue
            color = MUSCLE_COLORS[muscle_name]
            fill = overlay.copy()
            cv2.fillConvexPoly(fill, polygon, color, lineType=cv2.LINE_AA)
            alpha = float(np.clip(alpha_scale * engagement_value, 0.0, 0.75))
            overlay = cv2.addWeighted(fill, alpha, overlay, 1.0 - alpha, 0.0)

        return overlay

    def _circle_polygon(self, center: tuple[float, float] | None, radius: float) -> np.ndarray | None:
        if center is None:
            return None
        points = cv2.ellipse2Poly((int(center[0]), int(center[1])), (int(radius), int(radius)), 0, 0, 360, 20)
        return points.astype(np.int32)

    def _distance(self, point_a: tuple[float, float] | None, point_b: tuple[float, float] | None) -> float:
        if point_a is None or point_b is None:
            return 0.0
        return float(np.linalg.norm(np.asarray(point_a, dtype=np.float32) - np.asarray(point_b, dtype=np.float32)))

    def _draw_text_panels(self, frame: np.ndarray, top_muscles: list[tuple[str, float]], power_chain_text: str) -> np.ndarray:
        height, width = frame.shape[:2]
        top_box_width = min(380, max(260, width // 3))
        top_box_height = 120
        bottom_box_height = 56

        overlay = frame.copy()
        cv2.rectangle(overlay, (width - top_box_width - 18, 18), (width - 18, 18 + top_box_height), (12, 14, 18), -1)
        cv2.rectangle(overlay, (18, height - bottom_box_height - 18), (width - 18, height - 18), (12, 14, 18), -1)
        frame = cv2.addWeighted(overlay, 0.42, frame, 0.58, 0.0)

        text_lines = ["TOP 3 激活肌群"]
        for rank, (name, score) in enumerate(top_muscles[:3], start=1):
            label = MUSCLE_LABELS.get(name, name)
            text_lines.append(f"{rank}. {label}  {score:.2f}")
        while len(text_lines) < 4:
            text_lines.append("-")

        frame = self._draw_pil_text(
            frame,
            text_lines,
            (width - top_box_width, 30),
            line_height=28,
            font_size=24,
            fill=(245, 241, 232),
        )
        frame = self._draw_pil_text(
            frame,
            [power_chain_text],
            (34, height - bottom_box_height - 3),
            line_height=26,
            font_size=23,
            fill=(245, 241, 232),
        )
        return frame

    def _draw_pil_text(
        self,
        frame: np.ndarray,
        lines: list[str],
        origin: tuple[int, int],
        line_height: int,
        font_size: int,
        fill: tuple[int, int, int],
    ) -> np.ndarray:
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        drawer = ImageDraw.Draw(image)
        font = self._load_font(font_size)
        x, y = origin
        for index, line in enumerate(lines):
            drawer.text((x, y + index * line_height), line, font=font, fill=fill)
        return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if self.font_path:
            try:
                return ImageFont.truetype(str(self.font_path), size=size)
            except OSError:
                pass
        return ImageFont.load_default()

    def _resolve_font_path(self) -> Path | None:
        candidates = [
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None
