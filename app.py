from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st
import yaml

from src.analysis.pipeline import AnalysisStage, AnalysisStatus, analyze_video, load_analysis_result, load_pipeline_config
from src.analysis.muscle import muscle_stats_table
from src.export.exporters import save_frame_image
from src.storage.analysis_store import AnalysisStore
from src.utils.paths import INPUT_DIR, ensure_project_dirs
from src.utils.video_utils import split_side_by_side_frame
from src.video.realtime_processor import build_realtime_components
from src.video.video_reader import VideoReader
from src.visualization.charts import make_metric_figure, make_trajectory_figure
from src.visualization.draw_dashboard import build_metric_groups
from src.visualization.draw_pose import compose_side_by_side, create_skeleton_canvas, draw_pose_landmarks, draw_overlay_text


CONFIG_PATH = Path("configs/default.yaml")


def load_config() -> dict:
    ensure_project_dirs()
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def inject_styles() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Noto+Sans+SC:wght@400;500;700&display=swap');

:root {
  --bg: #0b0e13;
  --bg-soft: #121822;
  --panel: #141a23;
  --panel-soft: #1b2330;
  --card: rgba(24, 32, 45, 0.86);
  --line: rgba(255,255,255,0.08);
  --accent: #d4af37;
  --accent-bright: #f0c95c;
  --accent-soft: rgba(212,175,55,0.14);
  --text: #ece7da;
  --muted: #8d97a8;
  --danger: #e05d5d;
  --ok: #7cc47c;
}

.stApp {
  background:
    radial-gradient(1100px 480px at 88% -8%, rgba(212,175,55,0.14), transparent 60%),
    radial-gradient(900px 520px at -10% 110%, rgba(30,45,70,0.55), transparent 62%),
    linear-gradient(180deg, #0b0e13 0%, #0e141d 55%, #0b0e13 100%);
  color: var(--text);
  font-family: "DM Sans", "Noto Sans SC", "Microsoft YaHei", sans-serif;
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0d1118 0%, #131a25 100%);
  border-right: 1px solid rgba(212,175,55,0.14);
}

[data-testid="stSidebar"] * {
  color: #ece7da !important;
}

.block-container {
  padding-top: 1.25rem;
  padding-bottom: 3rem;
  max-width: 1380px;
}

/* ---------- Hero ---------- */
.wmv-hero {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 1.6rem;
  align-items: center;
  padding: 2rem 2.1rem 2rem;
  border-radius: 26px;
  background:
    linear-gradient(135deg, rgba(19,25,36,0.96) 0%, rgba(24,32,46,0.92) 70%),
    radial-gradient(560px 300px at 92% 8%, rgba(212,175,55,0.22), transparent 55%);
  color: #f2eee2;
  margin-bottom: 1.2rem;
  box-shadow: 0 26px 60px rgba(0,0,0,0.42);
  border: 1px solid rgba(212,175,55,0.16);
}

.wmv-hero::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 40%, rgba(212,175,55,0.10) 78%, transparent 96%);
  pointer-events: none;
}

.wmv-hero-kicker {
  font-size: 0.78rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--accent-bright);
  opacity: 0.85;
  margin-bottom: 0.55rem;
}

.wmv-hero-title {
  font-size: 2.35rem;
  font-weight: 700;
  line-height: 1.04;
  margin: 0;
  letter-spacing: 0.01em;
}

.wmv-hero-copy {
  margin-top: 0.8rem;
  max-width: 860px;
  color: rgba(242,238,226,0.74);
  font-size: 0.98rem;
  line-height: 1.72;
}

.wmv-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1.05rem;
}

.wmv-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0.42rem 0.78rem;
  border-radius: 999px;
  background: rgba(212,175,55,0.10);
  border: 1px solid rgba(212,175,55,0.22);
  color: #f0c95c;
  font-size: 0.84rem;
  white-space: nowrap;
}

.wmv-chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-bright);
  box-shadow: 0 0 8px rgba(240,201,92,0.8);
}

.wmv-section-label {
  margin: 1rem 0 0.5rem;
  font-size: 0.8rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-bright);
  opacity: 0.9;
}

/* ---------- Panels & stats ---------- */
.wmv-panel {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1.05rem 1.1rem 1.1rem;
  box-shadow: 0 16px 34px rgba(0,0,0,0.28);
}

.wmv-panel-dark {
  background: linear-gradient(180deg, #10151e 0%, #161e2b 100%);
  color: #ece7da;
  border: 1px solid rgba(212,175,55,0.18);
}

.wmv-mini-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.7rem;
  margin-top: 0.7rem;
}

.wmv-stat {
  padding: 0.8rem 0.85rem;
  border-radius: 16px;
  background: rgba(255,255,255,0.035);
  border: 1px solid var(--line);
}

.wmv-panel-dark .wmv-stat {
  background: rgba(255,255,255,0.05);
  border-color: rgba(255,255,255,0.07);
}

.wmv-stat-label {
  color: var(--muted);
  font-size: 0.78rem;
  margin-bottom: 0.22rem;
}

.wmv-panel-dark .wmv-stat-label {
  color: rgba(236,231,218,0.58);
}

.wmv-stat-value {
  font-size: 1.32rem;
  font-weight: 700;
  line-height: 1.1;
  color: var(--text);
}

.wmv-panel-dark .wmv-stat-value {
  color: #f2eee2;
}

.wmv-note {
  padding: 0.9rem 1rem;
  border-left: 4px solid var(--accent);
  background: var(--accent-soft);
  border-radius: 0 16px 16px 0;
  color: #e9d98e;
  margin-top: 0.8rem;
  font-size: 0.92rem;
}

.wmv-divider {
  height: 1px;
  background: linear-gradient(90deg, rgba(212,175,55,0.34), transparent);
  margin: 0.85rem 0 1.05rem;
}

.stButton > button,
.stDownloadButton > button {
  border-radius: 999px;
  border: 1px solid rgba(212,175,55,0.3);
  background: linear-gradient(180deg, #d4af37 0%, #b8942a 100%);
  color: #141a23;
  font-weight: 700;
  min-height: 2.9rem;
  box-shadow: 0 10px 22px rgba(212,175,55,0.22);
}

.stButton > button:hover,
.stDownloadButton > button:hover {
  border-color: rgba(240,201,92,0.55);
  color: #141a23;
  box-shadow: 0 12px 26px rgba(212,175,55,0.3);
}

.stTabs [data-baseweb="tab-list"] {
  gap: 0.45rem;
}

.stTabs [data-baseweb="tab"] {
  border-radius: 999px;
  background: rgba(255,255,255,0.05);
  border: 1px solid transparent;
  padding: 0.42rem 0.9rem;
}

.stTabs [aria-selected="true"] {
  background: linear-gradient(180deg, #d4af37 0%, #b8942a 100%) !important;
  color: #141a23 !important;
  font-weight: 700;
  border-color: transparent;
}

[data-testid="stMetric"] {
  background: var(--card);
  border: 1px solid var(--line);
  padding: 0.8rem 0.95rem;
  border-radius: 18px;
}

/* ---------- V3 诊断卡片 ---------- */
.wmv-sev-high   { color: var(--danger); }
.wmv-sev-medium { color: #e8a33d; }
.wmv-sev-low    { color: var(--accent-bright); }

.wmv-dx-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-left: 4px solid var(--accent);
  border-radius: 16px;
  padding: 0.85rem 1rem 0.85rem 1.05rem;
  margin: 0.55rem 0;
}

.wmv-dx-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.wmv-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.wmv-badge-high   { background: rgba(224,93,93,0.16); color: #f09090; border: 1px solid rgba(224,93,93,0.35); }
.wmv-badge-medium { background: rgba(232,163,61,0.16); color: #f0b45f; border: 1px solid rgba(232,163,61,0.35); }
.wmv-badge-low    { background: rgba(212,175,55,0.14); color: #f0c95c; border: 1px solid rgba(212,175,55,0.32); }

.wmv-dx-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
}

.wmv-dx-evidence {
  margin-top: 0.5rem;
  padding: 0.6rem 0.75rem;
  background: rgba(255,255,255,0.04);
  border-radius: 10px;
  font-size: 0.86rem;
  color: var(--muted);
  line-height: 1.6;
}

.wmv-dx-advice {
  margin-top: 0.45rem;
  font-size: 0.9rem;
  color: #e9d98e;
  line-height: 1.65;
}

.wmv-one-thing {
  padding: 1.05rem 1.2rem;
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(212,175,55,0.16), rgba(212,175,55,0.05));
  border: 1px solid rgba(212,175,55,0.4);
  margin: 0.9rem 0;
}

.wmv-one-thing-label {
  font-size: 0.75rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent-bright);
  margin-bottom: 0.35rem;
}

.wmv-one-thing-text {
  font-size: 1.06rem;
  font-weight: 600;
  color: #f2eee2;
  line-height: 1.7;
}

@media (max-width: 900px) {
  .wmv-hero {
    grid-template-columns: 1fr;
  }
  .wmv-hero-title {
    font-size: 1.75rem;
  }
  .wmv-mini-grid {
    grid-template-columns: 1fr;
  }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(title: str, subtitle: str, chips: list[str], kicker: str = "Wushu Motion Visualizer") -> None:
    chip_html = "".join(f"<span class='wmv-chip'><span class='wmv-chip-dot'></span>{chip}</span>" for chip in chips)
    st.markdown(
        f"""
<section class="wmv-hero">
  <div>
    <div class="wmv-hero-kicker">{kicker}</div>
    <h1 class="wmv-hero-title">{title}</h1>
    <p class="wmv-hero-copy">{subtitle}</p>
  </div>
  <div class="wmv-chip-row">{chip_html}</div>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_section_label(label: str) -> None:
    st.markdown(f"<div class='wmv-section-label'>{label}</div>", unsafe_allow_html=True)


def render_panel_start(dark: bool = False) -> None:
    class_name = "wmv-panel wmv-panel-dark" if dark else "wmv-panel"
    st.markdown(f"<div class='{class_name}'>", unsafe_allow_html=True)


def render_panel_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def bgr_to_rgb(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def save_uploaded_video(uploaded_file) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = Path(uploaded_file.name).name.replace(" ", "_")
    target_path = INPUT_DIR / f"{timestamp}_{safe_name}"
    target_path.write_bytes(uploaded_file.getbuffer())
    return target_path


def list_local_videos() -> list[Path]:
    ensure_project_dirs()
    return sorted([path for path in INPUT_DIR.glob("*.mp4") if path.is_file()], key=lambda item: item.stat().st_mtime, reverse=True)


def _load_binary(path: Path) -> bytes:
    return path.read_bytes()


def _show_image(frame, caption: str) -> None:
    st.markdown(f"**{caption}**")
    st.image(bgr_to_rgb(frame), use_column_width=True)


def _fmt_value(value, unit: str = "", precision: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NaN"
    if pd.isna(number):
        return "NaN"
    suffix = f" {unit}" if unit else ""
    return f"{number:.{precision}f}{suffix}"


def _pose_connections():
    import mediapipe as mp

    return list(mp.solutions.pose.POSE_CONNECTIONS)


# =====================================================================
# 视频分析页面（V2：统一 pipeline + 历史 analysis + 按需导出视频）
# =====================================================================


def _prepare_selected_input(uploaded_file) -> Path | None:
    video_input_path = st.session_state.get("video_input_path")

    if uploaded_file is not None:
        upload_signature = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get("video_upload_signature") != upload_signature:
            st.session_state.video_upload_signature = upload_signature
            st.session_state.video_input_path = save_uploaded_video(uploaded_file)
            st.session_state.analysis_id = None
            st.session_state.video_current_frame = 0
            # 内容去重：同一视频（字节一致）之前分析过，直接打开已有结果，不再重跑
            from src.utils.video_utils import video_fingerprint

            fingerprint = video_fingerprint(st.session_state.video_input_path)
            existing = AnalysisStore().find_analysis_by_fingerprint(fingerprint)
            if existing:
                st.session_state.analysis_id = existing
                st.info(f"该视频之前已分析过，直接打开已有结果（`{existing}`），不再重复识别。")
        return st.session_state.video_input_path

    return video_input_path


def _run_analysis(video_path: Path) -> None:
    progress_bar = st.progress(0, text="准备开始分析...")
    status_text = st.empty()

    def progress_callback(stage: AnalysisStage, progress: float, message: str) -> None:
        progress_bar.progress(min(progress, 1.0), text=f"{stage.value} · {message}")
        status_text.caption(f"阶段：{stage.value}")

    try:
        result = analyze_video(
            video_path,
            config=load_config(),
            progress_callback=progress_callback,
        )
        st.session_state.analysis_id = result.analysis_id
        st.session_state.video_current_frame = 0
        progress_bar.progress(1.0, text="分析完成")
        if result.reused_pose:
            st.info("本次分析复用了已有姿态结果（MediaPipe 未重复执行）。")
    except Exception as exc:
        st.session_state.analysis_id = None
        progress_bar.empty()
        st.error(f"视频分析失败：{type(exc).__name__}: {exc}")
        st.info("请确认视频文件可以被本机播放器打开，并尽量使用常见的 mp4/H.264 编码。")


def _render_frame_inspector(result) -> None:
    total_frames = result.frame_count
    fps = result.fps
    metrics_df: pd.DataFrame = result.metrics_df
    pose = result.pose

    selected_frame = st.slider(
        "当前帧",
        min_value=0,
        max_value=max(0, total_frames - 1),
        value=min(st.session_state.get("video_current_frame", 0), max(0, total_frames - 1)),
        step=1,
    )
    st.session_state.video_current_frame = selected_frame

    source = result.source_path
    frame = None
    if source is not None and source.exists():
        try:
            with VideoReader(source, max_side=max(pose.width, pose.height) if pose else None) as reader:
                frame = reader.read_at(selected_frame)
        except Exception:
            frame = None

    if frame is None:
        st.error("无法读取源视频帧。")
        return

    landmarks = pose.frame_landmarks(selected_frame) if pose else {}
    skeleton = create_skeleton_canvas(frame.shape, (18, 18, 18))
    skeleton = draw_pose_landmarks(skeleton, landmarks, _pose_connections())
    side_by_side = compose_side_by_side(frame, skeleton)
    original_frame, skeleton_frame = split_side_by_side_frame(side_by_side)

    frame_metrics = metrics_df.loc[metrics_df["frame_index"] == selected_frame]
    metrics = frame_metrics.iloc[0].to_dict() if not frame_metrics.empty else {}
    if not metrics_df.empty:
        final_metrics = metrics_df.iloc[-1].to_dict()
        for key, value in final_metrics.items():
            if "peak" in key:
                metrics[key] = value

    viewer_col, inspector_col = st.columns([1.7, 1.05], gap="large")
    with viewer_col:
        image_left, image_right = st.columns(2)
        with image_left:
            render_panel_start()
            _show_image(original_frame, "原始画面")
            render_panel_end()
        with image_right:
            render_panel_start(dark=True)
            _show_image(skeleton_frame, "骨架画面")
            render_panel_end()

    with inspector_col:
        render_panel_start()
        st.markdown("**当前帧摘要**")
        left_knee = metrics.get("left_knee_angle", float("nan"))
        right_knee = metrics.get("right_knee_angle", float("nan"))
        torso_tilt = metrics.get("torso_tilt_angle", float("nan"))
        motion_intensity = metrics.get("motion_intensity", float("nan"))
        st.markdown(
            f"""
<div class="wmv-mini-grid">
  <div class="wmv-stat"><div class="wmv-stat-label">左膝</div><div class="wmv-stat-value">{_fmt_value(left_knee, "deg")}</div></div>
  <div class="wmv-stat"><div class="wmv-stat-label">右膝</div><div class="wmv-stat-value">{_fmt_value(right_knee, "deg")}</div></div>
  <div class="wmv-stat"><div class="wmv-stat-label">躯干倾斜</div><div class="wmv-stat-value">{_fmt_value(torso_tilt, "deg")}</div></div>
</div>
<div class="wmv-mini-grid">
  <div class="wmv-stat"><div class="wmv-stat-label">motion_intensity</div><div class="wmv-stat-value">{_fmt_value(motion_intensity)}</div></div>
  <div class="wmv-stat"><div class="wmv-stat-label">当前帧</div><div class="wmv-stat-value">{selected_frame}</div></div>
  <div class="wmv-stat"><div class="wmv-stat-label">时间</div><div class="wmv-stat-value">{selected_frame / fps:.2f}s</div></div>
</div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("导出当前帧截图", use_container_width=True):
            screenshot_dir = result.analysis_dir / "exports"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            paths = {
                "original_frame.png": original_frame,
                "skeleton_frame.png": skeleton_frame,
                "side_by_side_frame.png": side_by_side,
            }
            saved = []
            for filename, image in paths.items():
                target = screenshot_dir / filename
                save_frame_image(image, target)
                saved.append(str(target))
            st.success("截图已保存到: " + ", ".join(saved))
        render_panel_end()

    _render_metric_panel(metrics, selected_frame, fps)


def _render_metric_panel(metrics: dict, frame_index: int, fps: float) -> None:
    st.subheader("当前帧数据面板")
    groups = build_metric_groups(metrics, frame_index, fps)
    tabs = st.tabs(list(groups.keys()))
    for tab, (title, dataframe) in zip(tabs, groups.items()):
        with tab:
            st.dataframe(dataframe, use_container_width=True, hide_index=True)


def _render_charts(metrics_df: pd.DataFrame, selected_frame: int) -> None:
    render_section_label("曲线与轨迹")
    chart_tab, trajectory_tab, normalized_tab = st.tabs(["角度与强度曲线", "轨迹图", "归一化速度"])
    with chart_tab:
        st.plotly_chart(make_metric_figure(metrics_df, selected_frame), use_container_width=True)
    with trajectory_tab:
        st.plotly_chart(make_trajectory_figure(metrics_df), use_container_width=True)
    with normalized_tab:
        import plotly.graph_objects as go

        figure = go.Figure()
        for column in ["wrist_speed_normalized", "hip_speed_normalized"]:
            if column in metrics_df.columns:
                figure.add_trace(
                    go.Scatter(
                        x=metrics_df["frame_index"],
                        y=metrics_df[column],
                        mode="lines",
                        name=column,
                    )
                )
        figure.update_layout(
            template="plotly_dark",
            height=320,
            margin=dict(l=24, r=24, t=36, b=24),
            title="归一化速度（身体尺度/秒，不受远近影响）",
            legend=dict(orientation="h"),
            xaxis_title="Frame",
        )
        st.plotly_chart(figure, use_container_width=True)


def _render_muscle_summary(result) -> None:
    render_section_label("肌肉与发力链")
    muscle = result.muscle or {}
    summary = muscle.get("summary", {})
    power_chain = result.power_chain or {}
    if not summary:
        st.caption("无肌肉分析数据。")
        return

    col1, col2 = st.columns([1.2, 1.0], gap="large")
    with col1:
        render_panel_start()
        st.markdown("**主要参与肌群统计表**")
        stats_df = muscle_stats_table(summary)
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
        render_panel_end()
    with col2:
        render_panel_start()
        st.markdown("**发力链分析**")
        st.write(summary.get("dominant_power_chain_hint", "暂无数据"))
        hint_counts = summary.get("power_chain_hint_counts", {})
        if hint_counts:
            hint_df = pd.DataFrame([{"提示": hint, "出现次数": count} for hint, count in hint_counts.items()]).sort_values(
                "出现次数", ascending=False
            )
            st.dataframe(hint_df, use_container_width=True, hide_index=True)
        render_panel_end()

    st.markdown("**峰值时刻分析**")
    render_panel_start()
    peak_moments = summary.get("peak_moments", [])
    if peak_moments:
        peak_df = pd.DataFrame(
            [
                {
                    "帧": item.get("frame"),
                    "时间(s)": round(float(item.get("time_sec", 0.0)), 3),
                    "峰值分数": round(float(item.get("score", 0.0)), 3),
                    "主要肌群": item.get("top_muscles", ""),
                    "发力链提示": item.get("power_chain_hint", ""),
                }
                for item in peak_moments
            ]
        )
        st.dataframe(peak_df, use_container_width=True, hide_index=True)
    else:
        st.caption("当前视频未提取到稳定的峰值时刻。")
    render_panel_end()

    stage_distribution = power_chain.get("stage_distribution", {})
    if stage_distribution:
        st.markdown("**发力链阶段分布**")
        st.dataframe(
            pd.DataFrame([{"阶段": stage, "帧数": count} for stage, count in stage_distribution.items()]).sort_values(
                "帧数", ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_exports(result) -> None:
    render_section_label("导出")
    render_panel_start()
    st.markdown("**视频导出（按需生成，分析阶段默认不生成 MP4）**")
    export_col1, export_col2 = st.columns(2)
    with export_col1:
        if st.button("导出骨架视频", use_container_width=True):
            with st.spinner("正在生成骨架视频..."):
                from src.export.skeleton_video import export_skeleton_video

                try:
                    path = export_skeleton_video(result.analysis_id)
                    st.session_state.skeleton_video_path = str(path)
                    st.success("骨架视频已生成")
                except Exception as exc:
                    st.error(f"导出失败：{exc}")
    with export_col2:
        if st.button("导出肌肉可视化视频", use_container_width=True):
            with st.spinner("正在生成肌肉可视化视频..."):
                from src.export.muscle_video import export_muscle_video

                try:
                    path = export_muscle_video(result.analysis_id)
                    st.session_state.muscle_video_path = str(path)
                    st.success("肌肉可视化视频已生成")
                except Exception as exc:
                    st.error(f"导出失败：{exc}")

    skeleton_path = st.session_state.get("skeleton_video_path")
    if skeleton_path and Path(skeleton_path).exists():
        st.success(f"骨架视频已导出：`{skeleton_path}`")
        st.video(str(Path(skeleton_path)))
        with open(Path(skeleton_path), "rb") as file_handle:
            st.download_button(
                "下载骨架视频（保存到本地）",
                data=file_handle.read(),
                file_name=Path(skeleton_path).name,
                mime="video/mp4",
                use_container_width=True,
            )
    muscle_path = st.session_state.get("muscle_video_path")
    if muscle_path and Path(muscle_path).exists():
        st.success(f"肌肉可视化视频已导出：`{muscle_path}`")
        st.video(str(Path(muscle_path)))
        with open(Path(muscle_path), "rb") as file_handle:
            st.download_button(
                "下载肌肉可视化视频（保存到本地）",
                data=file_handle.read(),
                file_name=Path(muscle_path).name,
                mime="video/mp4",
                use_container_width=True,
            )

    st.markdown("**数据文件下载**")
    paths = result.paths
    download_specs = {
        "pose.json": paths.get("pose_json"),
        "metrics.csv": paths.get("metrics_csv"),
        "analysis.json": paths.get("analysis_json"),
        "muscle.json": paths.get("muscle_json"),
        "power_chain.json": paths.get("power_chain_json"),
        "coach_input.json": paths.get("coach_input_json"),
        "summary.md": paths.get("summary_md"),
    }
    existing = {label: Path(path) for label, path in download_specs.items() if path and Path(path).exists()}
    columns = st.columns(min(4, len(existing)))
    for index, (label, path) in enumerate(existing.items()):
        with columns[index % len(columns)]:
            st.download_button(
                label=label,
                data=_load_binary(path),
                file_name=path.name,
                mime="application/octet-stream",
                use_container_width=True,
            )
    render_panel_end()


def _severity_weight(severity: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(severity, 0)


def _render_issue_card(diagnosis, window_index: int | None = None) -> None:
    badge_class = {
        "high": "wmv-badge-high",
        "medium": "wmv-badge-medium",
        "low": "wmv-badge-low",
    }.get(diagnosis.severity, "wmv-badge-low")
    sev_label = {"high": "高", "medium": "中", "low": "低"}.get(diagnosis.severity, diagnosis.severity)
    window_tag = f" · 窗口 {window_index}" if window_index is not None else ""
    st.markdown(
        f"""
<div class="wmv-dx-card">
  <div class="wmv-dx-head">
    <span class="wmv-badge {badge_class}">{sev_label}置信度</span>
    <span class="wmv-dx-title">{diagnosis.problem}</span>
    <span style="color:var(--muted);font-size:0.8rem">{diagnosis.reference_type}{window_tag}</span>
  </div>
  <div class="wmv-dx-evidence">{diagnosis.evidence_text or '无证据文本'}</div>
  <div class="wmv-dx-advice">👉 {diagnosis.training_advice or '暂无建议'}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_window_detail(window) -> None:
    render_panel_start()
    st.markdown(f"**事件时间线**（{window.strike_hand}手 · 置信度 {window.detection_confidence:.2f}）")
    if window.events:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "事件": event.label or event.name,
                        "帧": event.frame_index,
                        "时间(s)": round(event.time_sec, 3) if event.time_sec == event.time_sec else None,
                        "数值": round(event.value, 2) if event.value == event.value else None,
                        "单位": event.unit,
                        "说明": event.description,
                    }
                    for event in window.events
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("未检测到关键事件。")

    if window.timing:
        st.markdown("**发力链时序（毫秒间隔）**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "链路": link.label,
                        "间隔(ms)": round(link.interval_ms, 1) if link.interval_ms == link.interval_ms else None,
                        "期望顺序": link.expected_order,
                        "符合": "✓" if link.order_ok is True else ("✗" if link.order_ok is False else "—"),
                        "说明": link.note,
                    }
                    for link in window.timing
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    if window.phases:
        st.markdown("**动作阶段**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "阶段": phase.label or phase.name,
                        "起止": f"{phase.frame_start} → {phase.frame_end}",
                        "时长(ms)": round(phase.duration_ms, 1) if phase.duration_ms == phase.duration_ms else None,
                    }
                    for phase in window.phases
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    if window.diagnoses:
        st.markdown("**该窗口全部诊断**")
        for diagnosis in window.diagnoses:
            _render_issue_card(diagnosis)
    else:
        st.caption("该窗口未检出明确技术问题。")
    render_panel_end()


def _render_technique_analysis(analysis_id: str) -> None:
    """V3 直拳技术诊断区块：只读 technique/straight_punch.json，不重复运行 MediaPipe。"""
    render_section_label("直拳技术诊断 · V3")
    paths = AnalysisStore().paths(analysis_id)
    technique_dir = paths.analysis_dir / "technique"
    result_file = technique_dir / "straight_punch.json"

    if not result_file.exists():
        render_panel_start(dark=True)
        st.markdown("**该分析还没有直拳技术诊断。**")
        st.caption("诊断只读取已有的 pose.json / metrics.csv，不会重复运行 MediaPipe，几秒即可完成。")
        if st.button("运行直拳技术诊断", type="primary"):
            with st.spinner("正在检测出拳窗口、关键事件与错误模式..."):
                try:
                    from src.technique.engine import analyze_technique

                    analyze_technique(analysis_id)
                    st.rerun()
                except Exception as exc:
                    st.error(f"技术诊断失败：{type(exc).__name__}: {exc}")
        render_panel_end()
        return

    from src.technique.models import TechniqueResult

    result = TechniqueResult.load(result_file)
    refs = result.reference_available or {}
    overview_cols = st.columns(4)
    overview_cols[0].metric("出拳窗口", f"{len(result.windows)}")
    overview_cols[1].metric("Self Baseline", "已建立" if refs.get("baseline_available") else "样本不足(≥3)")
    overview_cols[2].metric("Personal Best", "已记录" if refs.get("personal_best_available") else "未设置")
    overview_cols[3].metric("Expert 模板", "接口已预留" if refs.get("expert_template_available") else "未接入")

    windows = result.windows
    if not windows:
        st.info("未检测到直拳窗口：视频中可能没有直拳动作，或手腕速度峰值不够明显。")
        return

    # 本轮最重要的一件事：跨窗口取问题最重窗口的建议
    best_window = max(windows, key=lambda w: sum(_severity_weight(d.severity) for d in w.diagnoses))
    one_thing = best_window.one_thing or "本次未发现明确技术问题；保持当前节奏，重点练动作一致性（多次出拳轨迹是否稳定）。"
    st.markdown(
        f"<div class='wmv-one-thing'><div class='wmv-one-thing-label'>本轮训练最重要的一件事</div>"
        f"<div class='wmv-one-thing-text'>{one_thing}</div></div>",
        unsafe_allow_html=True,
    )

    # Top 3：跨窗口按严重度聚合
    all_dx: list[tuple[int, object]] = []
    for window in windows:
        for diagnosis in window.diagnoses:
            all_dx.append((window.window_index, diagnosis))
    all_dx.sort(key=lambda pair: (_severity_weight(pair[1].severity), pair[1].confidence), reverse=True)
    st.markdown("**本次最值得改的 3 个问题**")
    for window_index, diagnosis in all_dx[:3]:
        _render_issue_card(diagnosis, window_index=window_index)

    # 窗口详情
    st.markdown("**出拳窗口详情**")
    labels = [
        f"窗口 {w.window_index} · 帧 {w.frame_start}-{w.frame_end} · {w.strike_hand}手 · {w.duration_ms:.0f}ms"
        for w in windows
    ]
    selected_label = st.selectbox("选择窗口", options=labels, label_visibility="collapsed")
    _render_window_detail(windows[labels.index(selected_label)])


def _render_analysis_result(result) -> None:
    total_frames = result.frame_count
    fps = result.fps
    metrics_df: pd.DataFrame = result.metrics_df

    _render_technique_analysis(result.analysis_id)

    render_section_label("概览")
    metric_cols = st.columns(4)
    metric_cols[0].metric("总帧数", f"{total_frames}")
    metric_cols[1].metric("视频 FPS", f"{fps:.1f}")
    metric_cols[2].metric("状态", result.status.value)
    metric_cols[3].metric("姿态复用", "是" if result.reused_pose else "否")

    if result.performance:
        perf = result.performance
        render_section_label("性能")
        perf_cols = st.columns(4)
        perf_cols[0].metric("总处理时间", f"{perf.get('total_processing_time_sec', 0):.2f}s")
        perf_cols[1].metric("MediaPipe 推理", f"{perf.get('pose_inference_time_sec') or 0:.2f}s")
        perf_cols[2].metric("姿态推理 FPS", f"{perf.get('pose_processing_fps') or 0:.1f}")
        perf_cols[3].metric("平均处理 FPS", f"{perf.get('average_processing_fps') or 0:.1f}")

    render_section_label("逐帧检查")
    render_panel_start()
    _render_frame_inspector(result)
    render_panel_end()

    _render_charts(metrics_df, st.session_state.get("video_current_frame", 0))
    _render_muscle_summary(result)
    _render_exports(result)


def render_video_analysis_page(config: dict) -> None:
    render_hero(
        title="武术 AI 教练系统",
        subtitle="上传一段出拳视频，系统一次姿态推理后完成：骨架 / 指标 / 肌肉 / 发力链分析，并给出直拳技术诊断——哪里有问题、为什么、下一轮具体怎么改。分析默认只生成数据，视频导出按需进行。",
        chips=["一次推理多模块复用", "直拳技术诊断 V3", "Self Baseline 对照", "结果按需导出"],
        kicker="Martial Arts AI Coach · V3",
    )

    store = AnalysisStore()
    history = store.list_analyses()
    history_ids = [item["analysis_id"] for item in history]

    render_section_label("输入")
    left_col, right_col = st.columns([1.2, 1.0], gap="large")

    with left_col:
        render_panel_start()
        st.markdown("**上传视频**")
        uploaded_file = st.file_uploader("上传 mp4 视频（支持横屏 / 竖屏）", type=["mp4"])
        video_input_path = _prepare_selected_input(uploaded_file)
        if video_input_path is not None:
            st.caption(f"当前输入文件：`{video_input_path.name}`")
        analyze_clicked = st.button("开始分析", type="primary", use_container_width=True, disabled=video_input_path is None)
        render_panel_end()

        render_panel_start()
        st.markdown("**历史分析（直接读取已有结果）**")
        history_options = ["（新建分析）"] + history_ids
        selected_history = st.selectbox(
            "选择 analysis_id",
            options=history_options,
            format_func=lambda aid: aid if aid == "（新建分析）" else f"{aid}  ·  {next((h['source_filename'] for h in history if h['analysis_id'] == aid), '')}",
        )
        render_panel_end()

    with right_col:
        render_panel_start(dark=True)
        st.markdown("**分析流程**")
        st.markdown(
            """
1. MediaPipe Pose 只执行一次，产出统一 `pose.json`
2. 骨架 / 指标 / 肌肉 / 发力链全部复用同一结果
3. 直拳技术诊断：关键事件 → 发力链时序 → 错误模式 → 训练建议
4. 默认不生成完整 MP4，导出由你主动触发
            """
        )
        st.markdown(
            "<div class='wmv-note'>同一视频再次分析会自动复用已有姿态结果；技术诊断只读数据、不重跑推理。</div>",
            unsafe_allow_html=True,
        )
        render_panel_end()

    # 历史加载优先于新分析按钮
    if selected_history != "（新建分析）":
        if st.session_state.get("analysis_id") != selected_history:
            st.session_state.analysis_id = selected_history
        try:
            result = load_analysis_result(selected_history)
            _render_analysis_result(result)
            return
        except Exception as exc:
            st.error(f"读取历史分析失败：{exc}")

    if analyze_clicked and video_input_path is not None:
        _run_analysis(video_input_path)

    analysis_id = st.session_state.get("analysis_id")
    if not analysis_id:
        st.info("上传一个 mp4 视频后点击“开始分析”，或直接打开一条历史分析。")
        return

    try:
        result = load_analysis_result(analysis_id)
    except Exception as exc:
        st.error(f"加载分析结果失败：{exc}")
        return

    if result.status == AnalysisStatus.FAILED:
        st.error(f"该分析此前失败：{result.error}")
        st.info("请重新点击“开始分析”，管线会从已有缓存继续。")
        return

    _render_analysis_result(result)


# =====================================================================
# 实时摄像头页面（本阶段不重构）
# =====================================================================


def _release_camera() -> None:
    capture = st.session_state.get("camera_capture")
    if capture is not None:
        capture.release()
    processor = st.session_state.get("camera_processor")
    if processor is not None:
        processor.pose_backend.close()
    st.session_state.camera_capture = None
    st.session_state.camera_processor = None
    st.session_state.camera_running = False
    st.session_state.active_camera_index = None


def render_realtime_page(config: dict) -> None:
    render_hero(
        title="实时摄像头工作台",
        subtitle="本机摄像头实时显示原始画面、主骨架和数据面板。轨迹默认关闭，只在你需要时显示短残影。",
        chips=["单人检测", "720p 默认", "主骨架优先", "实时数据刷新"],
        kicker="Realtime Camera",
    )

    render_section_label("控制")
    control_left, control_right = st.columns([1.2, 1.0], gap="large")
    with control_left:
        render_panel_start()
        camera_index_options = [0, 1, 2, 3]
        default_camera_index = int(st.session_state.get("camera_index", config["app"].get("default_camera_index", 0)))
        if default_camera_index not in camera_index_options:
            camera_index_options.append(default_camera_index)
            camera_index_options = sorted(set(camera_index_options))
        selected_camera_index = st.selectbox(
            "摄像头索引",
            options=camera_index_options,
            index=camera_index_options.index(default_camera_index),
            help="电脑内置摄像头通常是 0，手机通过 DroidCam / Iriun 接入后通常可尝试 1。",
        )
        st.session_state.camera_index = selected_camera_index
        show_live_trajectory = st.checkbox("显示短轨迹残影（约 1 秒后自然消失）", value=False)
        if st.session_state.get("camera_running", False):
            active_camera_index = st.session_state.get("active_camera_index", selected_camera_index)
            if active_camera_index != selected_camera_index:
                st.warning(f"当前正在使用摄像头索引 {active_camera_index}。如果要切换到 {selected_camera_index}，请先停止再重新开始。")
        start_col, stop_col, clear_col, shot_col = st.columns(4)
        with start_col:
            start_clicked = st.button("开始摄像头", type="primary", use_container_width=True)
        with stop_col:
            stop_clicked = st.button("停止摄像头", use_container_width=True)
        with clear_col:
            clear_clicked = st.button("清空轨迹", use_container_width=True)
        with shot_col:
            shot_clicked = st.button("截图保存当前帧", use_container_width=True)
        render_panel_end()

    with control_right:
        render_panel_start(dark=True)
        st.markdown("**实时模式说明**")
        st.markdown(
            """
- 左边始终保留原始画面  
- 右边只强调主骨架和当前帧数据  
- 速度单位使用 `px/s`，适合看变化趋势  
- `motion_intensity` 是运动强度参考，不代表真实肌肉发力
            """
        )
        render_panel_end()

    if start_clicked and not st.session_state.get("camera_running", False):
        try:
            capture = cv2.VideoCapture(int(selected_camera_index))
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, config["app"]["default_camera_width"])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config["app"]["default_camera_height"])
        except Exception as exc:
            st.error(f"摄像头初始化失败：{type(exc).__name__}: {exc}")
            return
        if not capture.isOpened():
            st.error(f"摄像头打开失败。请检查索引 {selected_camera_index} 是否正确，或确认手机摄像头驱动是否已接入 Windows。")
            capture.release()
            return
        st.session_state.camera_capture = capture
        st.session_state.camera_processor = build_realtime_components(config)
        st.session_state.camera_running = True
        st.session_state.active_camera_index = int(selected_camera_index)
        st.session_state.realtime_history = []

    if stop_clicked:
        _release_camera()

    processor = st.session_state.get("camera_processor")
    if clear_clicked and processor is not None:
        processor.clear_trajectories()
        st.session_state.realtime_history = []

    if not st.session_state.get("camera_running", False):
        st.info("点击“开始摄像头”后，页面会持续刷新并显示实时双画面、角度、速度和 motion_intensity。")
        return

    capture = st.session_state.get("camera_capture")
    if capture is None or processor is None:
        st.warning("摄像头状态异常，已重置。")
        _release_camera()
        return

    success, frame = capture.read()
    if not success:
        st.error("摄像头读取失败，已停止。")
        _release_camera()
        return

    try:
        result = processor.process_frame(frame, show_trajectories=show_live_trajectory)
    except Exception as exc:
        st.error(f"实时帧处理失败：{type(exc).__name__}: {exc}")
        _release_camera()
        return
    st.session_state.last_realtime_result = result
    history = st.session_state.get("realtime_history", [])
    history.append(result["metrics"])
    recent_seconds = config["app"]["recent_seconds_for_live_chart"]
    max_rows = int(max(result["fps"], 20.0) * recent_seconds)
    st.session_state.realtime_history = history[-max_rows:]

    metrics_col = st.columns(5)
    metrics_col[0].metric("实时 FPS", f"{result['fps']:.1f}")
    metrics_col[1].metric("当前帧", f"{int(result['metrics']['frame_index'])}")
    metrics_col[2].metric("左手腕速度", _fmt_value(result["metrics"].get("left_wrist_speed"), "px/s"))
    metrics_col[3].metric("motion_intensity", _fmt_value(result["metrics"].get("motion_intensity")))
    metrics_col[4].metric("摄像头索引", f"{st.session_state.get('active_camera_index', selected_camera_index)}")

    st.caption(
        "当前实时源："
        f" 摄像头索引 {st.session_state.get('active_camera_index', selected_camera_index)}"
        "。如果手机已被 DroidCam / Iriun 识别为摄像头，可优先尝试 1。"
    )

    frame_col_left, frame_col_right = st.columns(2)
    with frame_col_left:
        render_panel_start()
        _show_image(result["original_frame"], "原始画面")
        render_panel_end()
    with frame_col_right:
        render_panel_start(dark=True)
        _show_image(result["skeleton_frame"], "骨架画面")
        render_panel_end()

    if shot_clicked:
        from src.utils.paths import make_output_run_dir

        run_dir = make_output_run_dir("camera_snapshot")
        screenshot_dir = run_dir / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_paths = {
            "original_frame": screenshot_dir / "original_frame.png",
            "skeleton_frame": screenshot_dir / "skeleton_frame.png",
            "side_by_side_frame": screenshot_dir / "side_by_side_frame.png",
        }
        save_frame_image(result["original_frame"], screenshot_paths["original_frame"])
        save_frame_image(result["skeleton_frame"], screenshot_paths["skeleton_frame"])
        save_frame_image(result["side_by_side_frame"], screenshot_paths["side_by_side_frame"])
        st.success("截图已保存到: " + ", ".join(str(path) for path in screenshot_paths.values()))

    _render_metric_panel(result["metrics"], int(result["metrics"]["frame_index"]), float(result["fps"]))

    history_df = pd.DataFrame(st.session_state.get("realtime_history", []))
    if not history_df.empty:
        trend_tab, trajectory_tab = st.tabs(["最近趋势", "轨迹图"])
        with trend_tab:
            st.plotly_chart(make_metric_figure(history_df, int(history_df["frame_index"].iloc[-1])), use_container_width=True)
        with trajectory_tab:
            st.plotly_chart(make_trajectory_figure(history_df), use_container_width=True)

    time.sleep(0.03)
    st.rerun()


# =====================================================================
# 关于页面
# =====================================================================


def render_about_page() -> None:
    render_hero(
        title="系统说明与部署说明",
        subtitle="这一页面向教练、项目汇报和后续云部署。重点说明系统定位、每项实时数据的计算方式、数据的训练意义，以及部署时应该怎么取舍。",
        chips=["系统定位", "公式说明", "指标作用", "云服务器部署"],
        kicker="About & Deployment",
    )

    overview_tab, metrics_tab, usage_tab, deploy_tab = st.tabs(["系统定位", "计算方式", "指标作用", "云部署建议"])

    with overview_tab:
        render_panel_start()
        st.markdown(
            """
### 系统定位

本系统是“武术 AI 教练系统”（V3：从动作可视化升级为武术技术诊断）。不是通用动作评分器。

系统负责做的事情：

- 实时提取人体关键点并绘制主骨架
- 展示角度、速度（px / normalized / world）、重心、轨迹、`motion_intensity`
- 一次 MediaPipe 推理，多模块复用统一 PoseResult
- 直拳技术诊断：动作阶段、关键事件、发力链时序、11 种错误模式、训练建议
- 参考系统：Self Baseline（和自己比）/ Personal Best（个人优秀动作）/ Expert Template（预留接口）
- 支持视频离线分析（数据与视频导出分离）和本机摄像头实时分析
- 为未来 AI Coach（GPT / Gemini）预留结构化诊断输入（coach_input.json）

系统明确不做的事情：

- 不做“综合评分”（没有足够依据给指标分配权重）
- 不伪造绝对标准（不写死“拳速必须达到 X”这类阈值）
- 不识别真实肌肉发力（肌肉参与度为启发式估计）
- 不训练深度学习模型
            """
        )
        st.markdown(
            "<div class='wmv-note'>V3 的核心变化：新增 src/technique 技术诊断引擎，直拳可独立分析；核心逻辑仍与 Streamlit 完全解耦，可通过 worker.py 独立运行，为迁移到 Vercel / Web Site + Python Worker 做好准备。</div>",
            unsafe_allow_html=True,
        )
        render_panel_end()

    with metrics_tab:
        render_panel_start()
        st.markdown(
            """
### 关键点来源

系统基于 `MediaPipe Pose` 提取 33 个人体关键点。每一帧都会得到关键点的归一化坐标、像素坐标与 world 坐标。

### 速度的三套口径（V2 新增）

- `*_speed`（px/s）：保留旧口径，受人物远近影响
- `*_speed_normalized`（身体尺度/秒）：以肩宽/髋宽/躯干长度中位数为尺度基准，降低远近影响
- `*_speed_world`：MediaPipe world 坐标速度（近似米制，未标定，仅作参考）

### 角度计算

通用函数：`calculate_angle(point_a, point_b, point_c)`，以 `point_b` 为顶点计算夹角，任意点缺失或异常返回 `NaN`。

### motion_intensity

```text
motion_intensity =
0.25 * left_wrist_speed + 0.25 * right_wrist_speed +
0.20 * left_ankle_speed + 0.20 * right_ankle_speed + 0.10 * hip_center_speed
```
            """
        )
        render_panel_end()

    with usage_tab:
        render_panel_start()
        st.markdown(
            """
### 这些指标在训练观察里有什么用

#### 角度类

- 肘、肩、髋、膝、踝角度：帮助教练观察关节展开程度、收折程度、姿态是否稳定
- 躯干倾斜角：帮助看身体前倾、侧倾和重心转移趋势

#### 速度类

- 手腕速度：适合看出刀、架刀、收刀这些上肢变化的快慢
- 归一化速度：人物远近变化时仍然可比
- 脚踝速度：适合看步法切换和下肢发起节奏
- 髋部中心速度：适合看整体身体推进或撤收的节奏

#### 发力链

- 下肢驱动 / 髋部传递 / 躯干连接 / 上肢释放的阶段分布
- 帮助观察一次发力的起点与传导顺序（启发式标签，非精确测量）

### 页面解读建议

- 主判断依据永远是原始视频和主骨架
- 实时数字用于辅助，不建议脱离画面单独解释
- 对单帧丢点要容忍，出现 `NaN` 不代表动作错误
            """
        )
        render_panel_end()

    with deploy_tab:
        render_panel_start(dark=True)
        st.markdown(
            """
### 云服务器部署建议（面向 V2 架构）

#### 推荐结构

```text
Next.js / Vercel Site
        ↓ API
Python Worker（本项目的 src/analysis 核心）
        ↓ MediaPipe / OpenCV / 动作分析
返回 JSON（analysis.json / coach_input.json）
```

#### 当前已经为迁移做好的准备

- 核心分析 `analyze_video(video_path)` 完全脱离 Streamlit，只用普通 Python 类型
- `worker.py` 可独立运行：`python worker.py --input xxx.mp4`
- 进度状态（PREPARING → COMPLETED / FAILED）统一在 `src/models/analysis.py` 定义
- 所有结果统一保存在 `data/analyses/{analysis_id}/`，网站层直接读文件即可

#### 关于实时摄像头

当前实时摄像头模式使用 `cv2.VideoCapture(0)`，读取的是服务器本机摄像头，适合本地运行；公网多人使用时需改为浏览器采集 + 服务端推理架构（下一阶段再做）。
            """
        )
        render_panel_end()


def main() -> None:
    st.set_page_config(page_title="wushu_motion_visualizer", layout="wide")
    inject_styles()
    config = load_config()

    st.sidebar.title("武术 AI 教练系统")
    st.sidebar.caption("武术动作分析 · 直拳技术诊断 · V3")
    page = st.sidebar.radio("模式选择", options=["视频分析", "实时摄像头", "关于系统"])

    if page != "实时摄像头" and st.session_state.get("camera_running", False):
        _release_camera()

    if page == "视频分析":
        render_video_analysis_page(config)
    elif page == "实时摄像头":
        render_realtime_page(config)
    else:
        render_about_page()


if __name__ == "__main__":
    main()
