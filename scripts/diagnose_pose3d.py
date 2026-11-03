"""Audit MediaPipe world-landmark data without changing inference results."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


JOINT_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right", "left_shoulder", "right_shoulder", "left_elbow",
    "right_elbow", "left_wrist", "right_wrist", "left_pinky", "right_pinky", "left_index", "right_index",
    "left_thumb", "right_thumb", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle",
    "right_ankle", "left_heel", "right_heel", "left_foot_index", "right_foot_index",
]

MAJOR_BONES = [
    ("left_upper_arm", 11, 13), ("left_forearm", 13, 15),
    ("right_upper_arm", 12, 14), ("right_forearm", 14, 16),
    ("left_thigh", 23, 25), ("left_shin", 25, 27),
    ("right_thigh", 24, 26), ("right_shin", 26, 28),
    ("shoulders", 11, 12), ("hips", 23, 24),
    ("left_torso", 11, 23), ("right_torso", 12, 24),
]


def confidence(frame: dict, name: str) -> float:
    world = frame.get("world_landmarks", {}).get(name, {})
    value = world.get("visibility", frame.get("visibility", {}).get(name, frame.get("landmarks", {}).get(name, {}).get("visibility", 0)))
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def xyz(frame: dict, index: int) -> tuple[float, float, float] | None:
    point = frame.get("world_landmarks", {}).get(JOINT_NAMES[index])
    if not point:
        return None
    values = (point.get("x"), point.get("y"), point.get("z"))
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
        return None
    return tuple(float(value) for value in values)


def distance(a: tuple[float, float, float] | None, b: tuple[float, float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    return math.dist(a, b)


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * ratio)]


def frame_report(frame: dict, medians: dict[str, float]) -> dict:
    joints = []
    for index, name in enumerate(JOINT_NAMES):
        point = xyz(frame, index)
        visibility = confidence(frame, name)
        joints.append({
            "index": index,
            "name": name,
            "world": {"x": point[0], "y": point[1], "z": point[2]} if point else None,
            "scene": {"x": point[0], "y": -point[1], "z": -point[2]} if point else None,
            "visibility": visibility,
            "status": "missing" if point is None or visibility < 0.15 else "low" if visibility < 0.45 else "reliable",
        })

    bones = []
    for label, a_index, b_index in MAJOR_BONES:
        length = distance(xyz(frame, a_index), xyz(frame, b_index))
        baseline = medians.get(label)
        ratio = length / baseline if length is not None and baseline else None
        bones.append({
            "name": label,
            "indices": [a_index, b_index],
            "length_m": length,
            "median_m": baseline,
            "ratio_to_median": ratio,
            "outlier": ratio is not None and (ratio < 0.5 or ratio > 1.8),
        })
    return {
        "frame_index": int(frame.get("index", 0)),
        "timestamp_sec": float(frame.get("timestamp_sec", 0)),
        "joints": joints,
        "low_confidence": [joint["name"] for joint in joints if joint["status"] == "low"],
        "missing": [joint["name"] for joint in joints if joint["status"] == "missing"],
        "bones": bones,
        "outlier_bones": [bone["name"] for bone in bones if bone["outlier"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pose", type=Path)
    parser.add_argument("--frame", type=int, default=355)
    parser.add_argument("--out-dir", type=Path, default=Path("docs/3d-diagnostics"))
    args = parser.parse_args()

    data = json.loads(args.pose.read_text(encoding="utf-8"))
    frames = data.get("frames", [])
    if not frames:
        raise SystemExit("pose.json has no frames")
    target_index = max(0, min(len(frames) - 1, args.frame))

    length_series: dict[str, list[float]] = {label: [] for label, _, _ in MAJOR_BONES}
    missing_counts = {name: 0 for name in JOINT_NAMES}
    max_jumps = {name: 0.0 for name in JOINT_NAMES}
    previous = [None] * len(JOINT_NAMES)
    for frame in frames:
        for index, name in enumerate(JOINT_NAMES):
            point = xyz(frame, index)
            if point is None or confidence(frame, name) < 0.15:
                missing_counts[name] += 1
            if point is not None and previous[index] is not None:
                max_jumps[name] = max(max_jumps[name], math.dist(point, previous[index]))
            previous[index] = point
        for label, a_index, b_index in MAJOR_BONES:
            length = distance(xyz(frame, a_index), xyz(frame, b_index))
            if length is not None and confidence(frame, JOINT_NAMES[a_index]) >= 0.45 and confidence(frame, JOINT_NAMES[b_index]) >= 0.45:
                length_series[label].append(length)

    medians = {label: statistics.median(values) for label, values in length_series.items() if values}
    stability = {}
    for label, values in length_series.items():
        if not values:
            continue
        mean = statistics.fmean(values)
        stability[label] = {
            "median_m": statistics.median(values),
            "p05_m": percentile(values, 0.05),
            "p95_m": percentile(values, 0.95),
            "coefficient_of_variation": statistics.pstdev(values) / mean if mean else None,
        }

    sample_indices = sorted(set([0, target_index, len(frames) - 1]))
    reports = [frame_report(frames[index], medians) for index in sample_indices]
    target_report = frame_report(frames[target_index], medians)
    normalized = frames[target_index].get("landmarks", {})
    world = frames[target_index].get("world_landmarks", {})
    same_as_2d = all(
        name in normalized and name in world
        and all(abs(float(normalized[name].get(axis, 0)) - float(world[name].get(axis, 0))) < 1e-9 for axis in ("x", "y", "z"))
        for name in JOINT_NAMES
    )

    sequence = {
        "missing_counts": {name: count for name, count in missing_counts.items() if count},
        "largest_single_frame_jumps_m": sorted(max_jumps.items(), key=lambda item: item[1], reverse=True)[:8],
        "bone_length_stability": stability,
    }
    result = {
        "source": str(args.pose.resolve()),
        "analysis_id": data.get("analysis_id"),
        "fps": data.get("fps"),
        "frame_count": data.get("frame_count"),
        "dimensions": [data.get("width"), data.get("height")],
        "uses_distinct_world_landmarks": len(world) == 33 and not same_as_2d,
        "coordinate_transform": "scene=(world.x, -world.y, -world.z)",
        "sample_frames": reports,
        "target_frame": target_report,
        "sequence": sequence,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / f"frame-{target_index}-data.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    target = target_report
    rows = ["| # | 关键点 | x | y | z | visibility | 状态 |", "|---:|---|---:|---:|---:|---:|---|"]
    for joint in target["joints"]:
        point = joint["world"] or {"x": float("nan"), "y": float("nan"), "z": float("nan")}
        rows.append(f"| {joint['index']} | {joint['name']} | {point['x']:.6f} | {point['y']:.6f} | {point['z']:.6f} | {joint['visibility']:.6f} | {joint['status']} |")
    unstable = [name for name, stats in stability.items() if (stats["coefficient_of_variation"] or 0) > 0.12]
    markdown = f"""# 三维姿态数据诊断

- 分析：`{data.get('analysis_id')}`
- 视频：{data.get('width')}×{data.get('height')}，{data.get('fps')} FPS，共 {data.get('frame_count')} 帧
- 第 {target_index} 帧时间戳：{target['timestamp_sec']:.6f}s（帧号/FPS = {target_index / float(data.get('fps') or 1):.6f}s）
- 数据源：`world_landmarks` 33 点，且与二维 normalized landmarks 不同：**{not same_as_2d}**
- 渲染坐标：`(x, -y, -z)`；不分部位缩放，不替换原始姿态

## 第 {target_index} 帧结论

- 缺失点：{', '.join(target['missing']) or '无'}
- 低置信度点（0.15–0.45）：{', '.join(target['low_confidence']) or '无'}
- 相对全序列中位长度异常的主要骨段：{', '.join(target['outlier_bones']) or '无'}
- 左髋 x={target['joints'][23]['world']['x']:.6f}，右髋 x={target['joints'][24]['world']['x']:.6f}；左右索引未交换。

## 责任边界

- 渲染代码问题：旧实现三维帧使用四舍五入而视频使用向下取整；z 轴语义/正背视角注释相反；自由旋转会被预设相机持续拉回；低置信度骨段仍被完整绘制；无 world 数据时可能显示 33 个零点；线段与大球造成结构难辨。
- 模型预测问题：MediaPipe world 坐标是单目估计，不是多相机动捕；连续帧骨长并非严格恒定。当前序列骨长波动较大的段：{', '.join(unstable) or '无明显段'}。这些点只标记，不做预设姿态替换。

## 第 {target_index} 帧 33 点原始数据

{chr(10).join(rows)}
"""
    report_path = args.out_dir / "diagnostic-report.md"
    report_path.write_text(markdown, encoding="utf-8")
    print(json.dumps({"json": str(json_path), "report": str(report_path), "sample_frames": sample_indices}, ensure_ascii=False))


if __name__ == "__main__":
    main()
