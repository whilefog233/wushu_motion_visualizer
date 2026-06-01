import math

import pandas as pd
import pytest

from src.analysis.motion_intensity import compute_motion_intensity
from src.analysis.smoothing import smooth_metric_dict, smooth_scalar
from src.export.exporters import build_summary


def test_motion_intensity_matches_weighted_formula_when_all_values_exist():
    value = compute_motion_intensity(
        left_wrist_speed=100,
        right_wrist_speed=200,
        left_ankle_speed=300,
        right_ankle_speed=400,
        hip_center_speed=500,
    )

    assert value == pytest.approx(0.25 * 100 + 0.25 * 200 + 0.20 * 300 + 0.20 * 400 + 0.10 * 500)


def test_motion_intensity_ignores_missing_values_and_reweights():
    value = compute_motion_intensity(
        left_wrist_speed=float("nan"),
        right_wrist_speed=200,
        left_ankle_speed=float("nan"),
        right_ankle_speed=float("nan"),
        hip_center_speed=float("nan"),
    )

    assert value == 200


def test_motion_intensity_returns_nan_when_every_signal_is_missing():
    value = compute_motion_intensity(float("nan"), float("nan"), float("nan"), float("nan"), float("nan"))

    assert math.isnan(value)


def test_smooth_scalar_handles_nan_inputs():
    assert smooth_scalar(float("nan"), 10.0, 0.5) == 10.0
    assert math.isnan(smooth_scalar(5.0, float("nan"), 0.5))
    assert smooth_scalar(10.0, 20.0, 0.25) == 12.5


def test_smooth_metric_dict_handles_empty_previous_values():
    smoothed = smooth_metric_dict({}, {"left_wrist_speed": 10.0}, alpha=0.35)

    assert smoothed["left_wrist_speed"] == 10.0


def test_build_summary_has_stable_top_level_shape():
    metrics_df = pd.DataFrame(
        [
            {"frame_index": 0, "left_knee_angle": 100, "right_knee_angle": 110, "left_elbow_angle": 120, "motion_intensity": 10, "hip_height": 300},
            {"frame_index": 1, "left_knee_angle": 130, "right_knee_angle": 140, "left_elbow_angle": 150, "motion_intensity": 20, "hip_height": 280},
        ]
    )

    summary = build_summary(metrics_df, average_fps=30.0)

    assert summary["total_frames"] == 2
    assert summary["average_fps"] == 30.0
    assert summary["left_knee_angle"]["min"] == 100.0
    assert summary["left_knee_angle"]["max"] == 130.0
