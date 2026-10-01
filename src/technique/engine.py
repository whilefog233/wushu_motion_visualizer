"""Technique Engine 主入口：直拳技术诊断。

链路：analysis_id → pose.json + metrics.csv → SignalBundle → 出拳窗口检测
→ 每个窗口：事件 → 阶段 → 时序 → 错误模式判定（参考校准）→ 保存 technique/{id}.json
→ 更新 Self Baseline → 并入 coach_input.json（未来 GPT 直接读）。

设计约束：
- 不运行 MediaPipe / OpenCV；只读已有产物。
- 不依赖 Streamlit；输入输出都是普通 Python 类型。
- 不做综合评分；只做可解释诊断 + 本轮最重要的一件事。
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.models.pose_result import PoseResult
from src.storage.analysis_store import AnalysisStore
from src.technique import references
from src.technique.errors import diagnose_window
from src.technique.events import detect_events, event_value
from src.technique.models import (
    PunchWindow,
    ReferenceType,
    Severity,
    TechniqueDiagnosis,
    TechniqueResult,
)
from src.technique.phases import build_phases
from src.technique.profiles import STRAIGHT_PUNCH_ID, get_profile
from src.technique.signals import SignalBundle, build_signal_bundle, reorient_bundle, select_strike_hand
from src.technique.timing import build_timing

ENGINE_VERSION = "3.0.0"

# 出拳窗口检测参数
WINDOW_PEAK_RATIO = 0.30          # 候选峰 ≥ 全局峰值 30%
WINDOW_MIN_DURATION_MS = 150.0    # 最小窗口时长
WINDOW_MIN_GAP_FRAMES = 20        # 相邻窗口最小间隔
WINDOW_PRE_PAD = 0.30             # 峰前扩展（活动段比例）
WINDOW_POST_PAD = 0.25            # 峰后扩展


class TechniqueEngine:
    """直拳技术诊断引擎。"""

    def __init__(self, technique_id: str = STRAIGHT_PUNCH_ID):
        self.technique_id = technique_id
        self.profile = get_profile(technique_id)
        self.store = AnalysisStore()

    # ------------------------------------------------------------ 主入口
    def analyze(self, analysis_id: str, window: Optional[tuple[int, int]] = None) -> TechniqueResult:
        paths = self.store.paths(analysis_id)
        if not paths.pose_json.exists() or not paths.metrics_csv.exists():
            raise FileNotFoundError(f"analysis {analysis_id} 缺少 pose.json / metrics.csv，无法做技术诊断")

        pose = PoseResult.load(paths.pose_json)
        metrics_df = pd.read_csv(paths.metrics_csv)
        bundle = build_signal_bundle(pose, metrics_df)
        ref = references.load_reference(self.technique_id)

        result = TechniqueResult(
            technique_id=self.technique_id,
            analysis_id=analysis_id,
            engine_version=ENGINE_VERSION,
            metrics_interpretation=_metrics_interpretation(self.profile),
            reference_available={
                "self_baseline": bool(ref.get("baseline_available")),
                "personal_best": bool(ref.get("personal_best_available")),
                "expert_template": bool(ref.get("expert_template_available")),
            },
        )

        if window is not None:
            windows = [(int(window[0]), int(window[1]))]
        else:
            windows = self.detect_punch_windows(bundle)
            if not windows:
                result.notes.append("未检出清晰出拳事件（腕速峰值不足），未生成诊断。")

        for index, (frame_start, frame_end) in enumerate(windows):
            pw = self._analyze_window(bundle, ref, frame_start, frame_end, index)
            result.windows.append(pw)

        # 更新 Self Baseline（用最新窗口统计）
        for pw in result.windows:
            if pw.diagnoses is not None or True:
                stats = self._window_stats_from_window(pw)
                references.update_baseline(self.technique_id, stats, analysis_id=analysis_id)

        result.save(paths.analysis_dir / "technique" / f"{self.technique_id}.json")
        self._record_metadata(analysis_id, len(result.windows))
        self._merge_into_coach_input(analysis_id, result)
        return result

    # ------------------------------------------------------------ 窗口检测
    def detect_punch_windows(self, bundle: SignalBundle, limit: int = 6) -> list[tuple[int, int]]:
        """从腕速曲线自动检测候选直拳窗口（主手自动选择：左/右峰值更大）。"""
        df = bundle.source_df
        if df is None:
            return []
        left = pd.to_numeric(df["left_wrist_speed"], errors="coerce").to_numpy(dtype=float)
        right = pd.to_numeric(df["right_wrist_speed"], errors="coerce").to_numpy(dtype=float)
        combined = np.fmax(np.nan_to_num(left, nan=0.0), np.nan_to_num(right, nan=0.0))
        finite = combined[np.isfinite(combined)]
        if len(finite) == 0:
            return []
        global_peak = float(finite.max())
        if global_peak <= 0:
            return []
        threshold = max(float(np.percentile(finite, 60)), global_peak * WINDOW_PEAK_RATIO)

        # 找出超过阈值的活动段
        active = np.isfinite(combined) & (combined >= threshold)
        segments: list[tuple[int, int]] = []
        i = 0
        n = len(combined)
        while i < n:
            if active[i]:
                j = i
                while j + 1 < n and active[j + 1]:
                    j += 1
                segments.append((i, j))
                i = j + 1
            else:
                i += 1

        windows: list[tuple[int, int]] = []
        frames = bundle.frame_index
        for seg_start, seg_end in segments:
            seg_len = seg_end - seg_start + 1
            if seg_len < 3:
                continue
            peak_i = int(seg_start + np.nanargmax(combined[seg_start : seg_end + 1]))
            pre = max(int(seg_len * WINDOW_PRE_PAD), 4)
            post = max(int(seg_len * WINDOW_POST_PAD), 4)
            f_start = int(frames[max(0, peak_i - pre)])
            f_end = int(frames[min(n - 1, peak_i + post)])
            if (f_end - f_start) < 2:
                continue
            # 与已有窗口去重
            if windows and int(frames[peak_i]) - int(windows[-1][1]) < WINDOW_MIN_GAP_FRAMES:
                continue
            windows.append((f_start, f_end))
            if len(windows) >= limit:
                break

        # 按腕速峰值从强到弱排序（最显著的出拳排最前）
        def _strength(w: tuple[int, int]) -> float:
            mask = (bundle.frame_index >= w[0]) & (bundle.frame_index <= w[1])
            return float(np.nanmax(combined[mask])) if mask.any() else 0.0

        windows.sort(key=_strength, reverse=True)
        return windows

    # ------------------------------------------------------------ 单窗口分析
    def _analyze_window(self, bundle: SignalBundle, ref: dict, frame_start: int, frame_end: int, index: int) -> PunchWindow:
        hand = select_strike_hand(bundle, frame_start, frame_end)
        bundle = reorient_bundle(bundle, hand)
        sliced = bundle.slice(frame_start, frame_end)

        events, warnings = detect_events(bundle, frame_start, frame_end)
        phases = build_phases(events, bundle.fps)
        timing = build_timing(events, bundle.fps)
        window_stats = self._window_stats(sliced, events, timing)
        diagnoses = diagnose_window(bundle, events, timing, ref, window_stats)
        diagnoses = _sort_diagnoses(diagnoses)

        # Personal Best 曲线比较（预留：为"动作一致性/轨迹相似度"提供证据）
        pb_note = ""
        if ref.get("personal_best_available") and ref.get("personal_best"):
            pb = ref["personal_best"]
            similarity = _compare_with_pb(sliced, events, pb)
            if similarity is not None:
                pb_note = f"与个人优秀动作曲线相似度 {similarity:.2f}"
                window_stats["pb_curve_similarity"] = similarity

        # Top 3 + 本轮最重要的一件事
        top = diagnoses[:3]
        one_thing = top[0].training_advice if top else (
            "本次未发现明确技术问题；保持当前节奏，重点练动作一致性（可用多次出拳的轨迹稳定性衡量进步）。"
        )

        pw = PunchWindow(
            window_index=index,
            frame_start=frame_start,
            frame_end=frame_end,
            time_start_sec=bundle.time_at(frame_start),
            time_end_sec=bundle.time_at(frame_end),
            duration_ms=(bundle.time_at(frame_end) - bundle.time_at(frame_start)) * 1000.0,
            strike_hand=hand,
            detection_confidence=_window_confidence(sliced),
            events=events,
            phases=phases,
            timing=timing,
            diagnoses=diagnoses,
            top_issues=[f"{d.problem}｜{d.severity}置信度" for d in top],
            one_thing=one_thing,
            reference_summary={
                "baseline_available": bool(ref.get("baseline_available")),
                "personal_best_available": bool(ref.get("personal_best_available")),
                "pb_note": pb_note,
            },
        )
        return pw

    def _window_stats(self, sliced: SignalBundle, events: list, timing: list) -> dict[str, float]:
        """窗口统计（baseline 聚合与诊断消费）。"""
        from src.technique.timing import timing_value

        stats: dict[str, float] = {}
        stats["hip_shoulder_gap_ms"] = timing_value(timing, "hip_start", "shoulder_start")
        stats["hip_angular_velocity_peak"] = event_value(events, "hip_angular_velocity_peak")
        wrist_peak = event_value(events, "wrist_speed_peak")
        shoulder_peak = event_value(events, "shoulder_velocity_peak")
        stats["terminal_amplification"] = (
            wrist_peak / shoulder_peak if math.isfinite(wrist_peak) and math.isfinite(shoulder_peak) and shoulder_peak > 0 else float("nan")
        )
        recovery = timing_value(timing, "max_extension", "action_end")
        strike = timing_value(timing, "wrist_speed_peak", "max_extension")
        stats["recovery_strike_ratio"] = (
            recovery / strike if math.isfinite(recovery) and math.isfinite(strike) and strike > 0 else float("nan")
        )
        stats["head_displacement"] = float(np.nansum(sliced.head_displacement)) if len(sliced.head_displacement) else float("nan")
        stats["hip_forward_shift"] = _hip_forward_shift(sliced)
        stats["wrist_jitter"] = _wrist_jitter(sliced, events)
        return stats

    def _window_stats_from_window(self, pw: PunchWindow) -> dict[str, float]:
        stats: dict[str, float] = {}
        for link in pw.timing:
            if link.from_event == "hip_start" and link.to_event == "shoulder_start":
                stats["hip_shoulder_gap_ms"] = link.interval_ms
            elif link.from_event == "max_extension" and link.to_event == "action_end":
                stats["recovery_strike_ratio"] = link.interval_ms
        for event in pw.events:
            if event.name == "hip_angular_velocity_peak":
                stats["hip_angular_velocity_peak"] = event.value
        wrist = _event_value_list(pw.events, "wrist_speed_peak")
        shoulder = _event_value_list(pw.events, "shoulder_velocity_peak")
        if wrist and shoulder and shoulder[0] > 0:
            stats["terminal_amplification"] = wrist[0] / shoulder[0]
        return stats

    # ------------------------------------------------------------ 记录与合并
    def _record_metadata(self, analysis_id: str, window_count: int) -> None:
        self.store.update_metadata(
            analysis_id,
            technique={
                self.technique_id: {
                    "engine_version": ENGINE_VERSION,
                    "run_at": datetime.now(timezone.utc).isoformat(),
                    "window_count": window_count,
                }
            },
        )

    def _merge_into_coach_input(self, analysis_id: str, result: TechniqueResult) -> None:
        """把结构化诊断并入 coach_input.json（未来 GPT 的唯一输入）。"""
        paths = self.store.paths(analysis_id)
        if not paths.coach_input_json.exists():
            return
        try:
            with paths.coach_input_json.open("r", encoding="utf-8") as file:
                coach = json.load(file)
        except (OSError, json.JSONDecodeError):
            return
        coach["technique_diagnosis"] = {
            "technique_id": result.technique_id,
            "engine_version": result.engine_version,
            "windows": [pw.to_dict() for pw in result.windows],
            "reference_available": result.reference_available,
            "top_issues_across_windows": _global_top_issues(result),
        }
        with paths.coach_input_json.open("w", encoding="utf-8") as file:
            json.dump(coach, file, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 工具
def analyze_technique(analysis_id: str, technique_id: str = STRAIGHT_PUNCH_ID,
                      window: Optional[tuple[int, int]] = None) -> TechniqueResult:
    """核心入口：``result = analyze_technique(analysis_id)``（不依赖 Streamlit）。"""
    return TechniqueEngine(technique_id).analyze(analysis_id, window=window)


def load_technique_result(analysis_id: str, technique_id: str = STRAIGHT_PUNCH_ID) -> Optional[TechniqueResult]:
    paths = AnalysisStore().paths(analysis_id)
    path = paths.analysis_dir / "technique" / f"{technique_id}.json"
    if not path.exists():
        return None
    return TechniqueResult.load(path)


def _metrics_interpretation(profile) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in profile.important_metrics:
        result[item["metric"]] = {
            "unit": item.get("unit", ""),
            "what_it_judges": item.get("what_it_judges", ""),
            "paired_with": item.get("paired_with", ""),
            "cannot_judge_alone": item.get("cannot_judge_alone", ""),
            "training_meaning": item.get("training_meaning", ""),
        }
    return result


def _window_confidence(sliced: SignalBundle) -> float:
    conf = sliced.detection_confidence
    finite = conf[np.isfinite(conf)]
    if len(finite) == 0:
        return 0.5
    mean = float(finite.mean())
    return min(0.95, max(0.3, mean))


def _sort_diagnoses(diagnoses: list[TechniqueDiagnosis]) -> list[TechniqueDiagnosis]:
    order = {Severity.HIGH.value: 0, Severity.MEDIUM.value: 1, Severity.LOW.value: 2, Severity.INFO.value: 3}

    def _key(d: TechniqueDiagnosis) -> tuple[int, float]:
        return (order.get(d.severity, 9), -float(d.confidence))

    return sorted(diagnoses, key=_key)


def _global_top_issues(result: TechniqueResult) -> list[dict[str, Any]]:
    all_diags: list[tuple[int, TechniqueDiagnosis]] = []
    for pw in result.windows:
        for d in pw.diagnoses:
            all_diags.append((pw.window_index, d))
    order = {Severity.HIGH.value: 0, Severity.MEDIUM.value: 1, Severity.LOW.value: 2}
    all_diags.sort(key=lambda item: (order.get(item[1].severity, 9), -item[1].confidence))
    return [
        {
            "window_index": idx,
            "problem": d.problem,
            "severity": d.severity,
            "confidence": d.confidence,
            "evidence_text": d.evidence_text,
            "meaning": d.meaning,
            "training_advice": d.training_advice,
        }
        for idx, d in all_diags[:3]
    ]


def _hip_forward_shift(sliced: SignalBundle) -> float:
    x = sliced.hip_center_x
    torso = sliced.torso_length
    finite_x = x[np.isfinite(x)]
    finite_torso = torso[np.isfinite(torso)]
    if len(finite_x) < 2 or len(finite_torso) == 0:
        return float("nan")
    scale = float(np.median(finite_torso))
    if not math.isfinite(scale) or scale <= 1e-6:
        return float("nan")
    return float(finite_x.max() - finite_x.min()) / scale


def _wrist_jitter(sliced: SignalBundle, events: list) -> float:
    """腕速上升段（启动→峰值）的抖动指数：相邻差绝对值均值 / 峰值。"""
    from src.technique.events import event_frame

    f_start = event_frame(events, "wrist_start")
    f_peak = event_frame(events, "wrist_speed_peak")
    if f_start < 0 or f_peak < 0 or f_peak <= f_start:
        return float("nan")
    idx_s = int(np.searchsorted(sliced.frame_index, f_start))
    idx_p = int(np.searchsorted(sliced.frame_index, f_peak))
    segment = sliced.wrist_speed[idx_s : idx_p + 1]
    finite = segment[np.isfinite(segment)]
    if len(finite) < 3:
        return float("nan")
    peak = float(np.max(finite))
    if peak <= 1e-6:
        return float("nan")
    diffs = np.abs(np.diff(finite))
    return float(np.mean(diffs) / peak)


def _compare_with_pb(sliced: SignalBundle, events: list, pb: dict) -> Optional[float]:
    """与 Personal Best 模板比较（曲线相似度均值）。预留为证据。"""
    pb_curves = pb.get("curves") or {}
    if not pb_curves:
        return None
    similarities = []
    candidates = [
        ("hip_angular_velocity", sliced.hip_angular_velocity),
        ("shoulder_speed", sliced.shoulder_speed),
        ("elbow_angle", sliced.elbow_angle),
        ("wrist_speed", sliced.wrist_speed),
    ]
    for name, signal in candidates:
        if name not in pb_curves or not pb_curves[name]:
            continue
        curve = references.normalize_curve(signal)
        sim = references.curve_similarity(curve, pb_curves[name])
        if math.isfinite(sim):
            similarities.append(sim)
    if not similarities:
        return None
    return float(np.mean(similarities))


def _event_value_list(events: list, name: str) -> list[float]:
    return [float(e.value) for e in events if e.name == name and math.isfinite(float(e.value))]


def _build_pb_template(technique_id: str, analysis_id: str, window_index: int):
    """构建 Personal Best 模板（references.set_personal_best 调用）。"""
    from src.technique.models import PersonalBestTemplate

    store = AnalysisStore()
    paths = store.paths(analysis_id)
    result = load_technique_result(analysis_id, technique_id)
    if result is None or window_index >= len(result.windows):
        raise ValueError(f"analysis {analysis_id} 无 technique 诊断或窗口 {window_index}")
    pw = result.windows[window_index]

    pose = PoseResult.load(paths.pose_json)
    metrics_df = pd.read_csv(paths.metrics_csv)
    bundle = build_signal_bundle(pose, metrics_df)
    bundle = reorient_bundle(bundle, pw.strike_hand or "left")
    sliced = bundle.slice(pw.frame_start, pw.frame_end)

    events = pw.events
    start_time = pw.time_start_sec
    end_time = pw.time_end_sec
    template = PersonalBestTemplate(
        technique_id=technique_id,
        analysis_id=analysis_id,
        window_index=window_index,
        event_times_normalized=references.normalize_event_times(events, start_time, end_time),
        curves={
            "hip_angular_velocity": references.normalize_curve(sliced.hip_angular_velocity),
            "shoulder_speed": references.normalize_curve(sliced.shoulder_speed),
            "elbow_angle": references.normalize_curve(sliced.elbow_angle),
            "wrist_speed": references.normalize_curve(sliced.wrist_speed),
        },
        metrics={d.problem_id: _severity_score(d) for d in pw.diagnoses},
        total_issues=len(pw.diagnoses),
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    return template


def _severity_score(d: TechniqueDiagnosis) -> float:
    return {"high": 3.0, "medium": 2.0, "low": 1.0, "info": 0.0}.get(d.severity, 0.0)
