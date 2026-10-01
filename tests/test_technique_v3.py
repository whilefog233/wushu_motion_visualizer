"""V3 技术诊断引擎测试：合成直拳信号 + synthetic 视频集成。"""

import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

from src.technique.events import detect_events, event_frame, event_time, event_value
from src.technique.models import Severity
from src.technique.phases import build_phases
from src.technique.signals import SignalBundle
from src.technique.timing import build_timing, timing_value

FPS = 30.0


def _make_bundle(
    hip_peak_frame: int = 40,
    shoulder_peak_frame: int = 48,
    elbow_peak_frame: int = 56,
    wrist_peak_frame: int = 64,
    shoulder_start_offset: float = 5.0,   # 相对髋启动的帧偏移（负=肩先启动）
    n: int = 120,
) -> SignalBundle:
    """构造一个模拟直拳的合成信号包（启动帧 = 阶跃帧，精确可控）。"""
    frames = np.arange(n)
    timestamps = frames / FPS

    def _gauss_peak(center: int, width: float = 4.0, height: float = 1.0) -> np.ndarray:
        return height * np.exp(-((frames - center) ** 2) / (2 * width**2))

    rng = np.random.default_rng(7)
    noise = rng.normal(0, 0.005, n)  # 很低的基线噪声

    hip_start = hip_peak_frame - 12
    shoulder_start = int(hip_start + shoulder_start_offset)
    wrist_start = shoulder_start + 6

    def _step_rise(onset: int) -> np.ndarray:
        """在 onset 帧阶跃到 0.15，再缓升（模拟启动后加速）。"""
        signal = np.zeros(n)
        signal[onset:] = 0.15 + 0.05 * np.minimum(1.0, np.arange(n - onset) / 10.0)
        return signal

    hip_ang_vel = noise.copy()
    hip_ang_vel += _step_rise(hip_start)
    hip_ang_vel += _gauss_peak(hip_peak_frame, 4.0, 1.0)

    shoulder_speed = np.zeros(n)
    shoulder_speed[:shoulder_start] = 0.02  # 常量基线（无噪声），启动判定清晰
    shoulder_speed += _step_rise(shoulder_start)
    shoulder_speed += _gauss_peak(shoulder_peak_frame, 4.0, 0.8)

    elbow_ang_vel = _gauss_peak(elbow_peak_frame, 4.0, 1.2)

    wrist_speed = np.zeros(n)
    wrist_speed[:wrist_start] = 0.02
    wrist_speed += _step_rise(wrist_start)
    wrist_speed += _gauss_peak(wrist_peak_frame, 4.0, 1.5)

    elbow_angle = 90 + 80 * _sigmoid(frames, center=elbow_peak_frame, slope=0.25)
    elbow_angle -= 70 * _sigmoid(frames, center=elbow_peak_frame + 8, slope=0.5)

    bundle = SignalBundle(
        frame_index=frames,
        timestamps=timestamps,
        fps=FPS,
        hip_angular_velocity=hip_ang_vel,
        shoulder_speed=shoulder_speed,
        elbow_angular_velocity=elbow_ang_vel,
        elbow_angle=elbow_angle,
        wrist_speed=wrist_speed,
        wrist_speed_normalized=wrist_speed,
        hip_center_x=np.zeros(n),
        head_displacement=np.zeros(n),
        nose_speed=np.zeros(n),
        elbow_abduction=np.full(n, 0.2),
        torso_tilt=np.zeros(n),
        torso_rotation_velocity=np.zeros(n),
        shoulder_width=np.full(n, 40.0),
        torso_length=np.full(n, 60.0),
        detection_confidence=np.full(n, 0.9),
        body_scale_px=40.0,
        body_scale_world=40.0,
        source_df=pd.DataFrame(
            {
                "frame_index": frames,
                "timestamp_sec": timestamps,
                "left_wrist_speed": wrist_speed,
                "right_wrist_speed": wrist_speed * 0.9,
            }
        ),
    )
    return bundle


def _sigmoid(x: np.ndarray, center: float, slope: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-slope * (x - center)))


# ---------------------------------------------------------------- 事件与时序
class TestEventDetection:
    def test_detects_chain_order(self):
        bundle = _make_bundle()
        events, warnings = detect_events(bundle, 5, 115)
        hip_start = event_frame(events, "hip_start")
        shoulder_start = event_frame(events, "shoulder_start")
        wrist_peak = event_frame(events, "wrist_speed_peak")
        assert hip_start >= 0 and shoulder_start >= 0 and wrist_peak >= 0
        assert hip_start <= shoulder_start <= wrist_peak
        # 期望：髋先启动，肩后启动
        assert event_time(events, "hip_start") <= event_time(events, "shoulder_start")

    def test_peak_timing_intervals(self):
        bundle = _make_bundle()
        events, _ = detect_events(bundle, 5, 115)
        timing = build_timing(events, FPS)
        gap = timing_value(timing, "hip_angular_velocity_peak", "shoulder_velocity_peak")
        assert math.isfinite(gap)
        assert gap > 0  # 髋峰早于肩峰

    def test_phases_cover_window(self):
        bundle = _make_bundle()
        events, _ = detect_events(bundle, 5, 115)
        phases = build_phases(events, FPS)
        assert len(phases) == 5
        names = [p.name for p in phases]
        assert names == ["preparation", "initiation", "acceleration", "strike", "recovery"]
        for p in phases:
            assert p.frame_start >= 0 and p.frame_end >= p.frame_start


# ---------------------------------------------------------------- 错误模式
class TestErrorPatterns:
    def test_shoulder_starts_early_detected(self):
        # 肩启动比髋早 8 帧 → 应检出"肩启动过早"
        bundle = _make_bundle(shoulder_start_offset=-8.0)
        events, _ = detect_events(bundle, 5, 115)
        timing = build_timing(events, FPS)
        from src.technique.errors import diagnose_window

        diagnoses = diagnose_window(bundle, events, timing, {}, {})
        problems = [d.problem_id for d in diagnoses]
        assert "shoulder_starts_early" in problems
        diag = next(d for d in diagnoses if d.problem_id == "shoulder_starts_early")
        # 每个诊断必须有意义与建议
        assert diag.meaning and diag.training_advice
        assert diag.evidence
        assert diag.severity in {s.value for s in Severity}

    def test_arm_dominant_detected(self):
        # 髋峰值很小、肘峰值很大 → 手臂主导
        bundle = _make_bundle(hip_peak_frame=40)
        bundle.hip_angular_velocity = np.full(120, 0.01)
        bundle.hip_angular_velocity[30:50] = 0.15
        events, _ = detect_events(bundle, 5, 115)
        timing = build_timing(events, FPS)
        from src.technique.errors import diagnose_window

        diagnoses = diagnose_window(bundle, events, timing, {}, {})
        problems = [d.problem_id for d in diagnoses]
        assert "arm_dominant" in problems

    def test_no_diagnosis_without_evidence(self):
        # 干净信号：结构规则不应报任何问题
        bundle = _make_bundle()
        events, _ = detect_events(bundle, 5, 115)
        timing = build_timing(events, FPS)
        from src.technique.errors import diagnose_window

        diagnoses = diagnose_window(bundle, events, timing, {}, {})
        assert diagnoses == []


# ---------------------------------------------------------------- 参考系统
class TestReferences:
    def test_baseline_roundtrip(self, monkeypatch):
        import shutil
        import tempfile

        from src.technique import references

        tmp = Path(tempfile.mkdtemp(prefix="v3_refs_"))

        class _StubStore:
            root = tmp

        monkeypatch.setattr(references, "AnalysisStore", _StubStore)
        try:
            references.update_baseline("straight_punch", {"hip_shoulder_gap_ms": 80.0, "hip_angular_velocity_peak": 300.0}, analysis_id="a")
            references.update_baseline("straight_punch", {"hip_shoulder_gap_ms": 120.0, "hip_angular_velocity_peak": 340.0}, analysis_id="b")
            references.update_baseline("straight_punch", {"hip_shoulder_gap_ms": 100.0, "hip_angular_velocity_peak": 320.0}, analysis_id="c")
            baseline = references.load_baseline("straight_punch")
            gap = baseline.get("hip_shoulder_gap_ms", {})
            assert gap.get("count") == 3
            assert gap.get("mean") == pytest.approx(100.0, abs=0.01)
            ref = references.load_reference("straight_punch")
            assert ref["baseline_available"] is True
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_normalize_curve(self):
        from src.technique import references

        signal = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        curve = references.normalize_curve(signal, samples=11)
        assert len(curve) == 11
        assert max(curve) <= 1.0 + 1e-9 and min(curve) >= 0.0 - 1e-9


# ---------------------------------------------------------------- 集成（真实 synthetic 视频）
@pytest.fixture(scope="module")
def analysis():
    from src.analysis.pipeline import analyze_video

    video = Path(__file__).resolve().parents[1] / "data" / "input" / "synthetic_test.mp4"
    result = analyze_video(str(video))
    yield result
    import shutil

    shutil.rmtree(result.analysis_dir, ignore_errors=True)

    def test_full_technique_pipeline(self, analysis):
        from src.technique.engine import analyze_technique, load_technique_result

        result = analyze_technique(analysis.analysis_id)
        assert result.technique_id == "straight_punch"
        assert result.engine_version.startswith("3.")
        # 保存的文件可重新加载
        loaded = load_technique_result(analysis.analysis_id)
        assert loaded is not None
        assert loaded.analysis_id == analysis.analysis_id

    def test_diagnosis_has_meaning(self, analysis):
        from src.technique.engine import analyze_technique

        result = analyze_technique(analysis.analysis_id)
        for window in result.windows:
            for diagnosis in window.diagnoses:
                assert diagnosis.meaning
                assert diagnosis.training_advice
                assert diagnosis.evidence_text
                assert diagnosis.reference_type in {
                    "self_baseline",
                    "personal_best",
                    "expert_template",
                    "structural_rule",
                }

    def test_coach_input_merged(self, analysis):
        from src.technique.engine import analyze_technique

        analyze_technique(analysis.analysis_id)
        from src.storage.analysis_store import AnalysisStore

        paths = AnalysisStore().paths(analysis.analysis_id)
        import json

        coach = json.loads(paths.coach_input_json.read_text(encoding="utf-8"))
        assert "technique_diagnosis" in coach
        assert coach["technique_diagnosis"]["technique_id"] == "straight_punch"
