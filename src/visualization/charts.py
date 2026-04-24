from __future__ import annotations

from typing import Iterable

import pandas as pd
import plotly.graph_objects as go


DEFAULT_METRIC_COLUMNS = [
    "left_knee_angle",
    "right_knee_angle",
    "left_elbow_angle",
    "right_elbow_angle",
    "torso_tilt_angle",
    "motion_intensity",
]


def make_metric_figure(metrics_df: pd.DataFrame, selected_frame: int, metric_columns: Iterable[str] | None = None) -> go.Figure:
    metric_columns = list(metric_columns or DEFAULT_METRIC_COLUMNS)
    figure = go.Figure()
    for column in metric_columns:
        if column not in metrics_df.columns:
            continue
        figure.add_trace(
            go.Scatter(
                x=metrics_df["frame_index"],
                y=metrics_df[column],
                mode="lines",
                name=column,
            )
        )
    figure.add_vline(x=selected_frame, line_dash="dash", line_color="white")
    figure.update_layout(
        template="plotly_dark",
        height=320,
        margin=dict(l=24, r=24, t=36, b=24),
        title="角度与 motion_intensity 曲线",
        legend=dict(orientation="h"),
        xaxis_title="Frame",
    )
    return figure


def make_trajectory_figure(metrics_df: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    trajectories = {
        "left_wrist": ("left_wrist_x", "left_wrist_y"),
        "right_wrist": ("right_wrist_x", "right_wrist_y"),
        "left_ankle": ("left_ankle_x", "left_ankle_y"),
        "right_ankle": ("right_ankle_x", "right_ankle_y"),
        "hip_center": ("hip_center_x", "hip_center_y"),
    }
    for name, (x_col, y_col) in trajectories.items():
        if x_col not in metrics_df.columns or y_col not in metrics_df.columns:
            continue
        figure.add_trace(
            go.Scatter(
                x=metrics_df[x_col],
                y=metrics_df[y_col],
                mode="lines+markers",
                name=name,
                marker=dict(size=4),
            )
        )

    figure.update_layout(
        template="plotly_dark",
        height=320,
        margin=dict(l=24, r=24, t=36, b=24),
        title="轨迹图",
        xaxis_title="X (px)",
        yaxis_title="Y (px)",
        yaxis=dict(autorange="reversed"),
    )
    return figure
