from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st
import yaml

from src.export.exporters import save_frame_image
from src.utils.paths import INPUT_DIR, ensure_project_dirs, make_output_run_dir
from src.utils.video_utils import read_frame_at_index, split_side_by_side_frame
from src.video.offline_processor import build_offline_components
from src.video.realtime_processor import build_realtime_components
from src.visualization.charts import make_metric_figure, make_trajectory_figure
from src.visualization.draw_dashboard import build_metric_groups


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
  --bg: #f6f2ea;
  --panel: #11150f;
  --panel-soft: #1b2119;
  --card: rgba(255,255,255,0.82);
  --line: rgba(17,21,15,0.08);
  --accent: #d85f2f;
  --accent-soft: rgba(216,95,47,0.12);
  --text: #10140f;
  --muted: #5f685f;
}

.stApp {
  background:
    radial-gradient(circle at top right, rgba(216,95,47,0.16), transparent 22%),
    linear-gradient(180deg, #faf6ef 0%, #f2ede3 100%);
  color: var(--text);
  font-family: "DM Sans", "Noto Sans SC", "Microsoft YaHei", sans-serif;
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #11150f 0%, #1a2018 100%);
  border-right: 1px solid rgba(255,255,255,0.06);
}

[data-testid="stSidebar"] * {
  color: #f5f1e8 !important;
}

.block-container {
  padding-top: 1.25rem;
  padding-bottom: 3rem;
  max-width: 1380px;
}

.wmv-hero {
  padding: 1.4rem 1.6rem 1.6rem;
  border-radius: 28px;
  background:
    linear-gradient(135deg, rgba(17,21,15,0.96) 0%, rgba(26,32,24,0.94) 72%),
    radial-gradient(circle at top right, rgba(216,95,47,0.28), transparent 35%);
  color: #f6f1e8;
  margin-bottom: 1rem;
  box-shadow: 0 22px 54px rgba(17,21,15,0.18);
}

.wmv-hero-kicker {
  font-size: 0.82rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(246,241,232,0.7);
  margin-bottom: 0.5rem;
}

.wmv-hero-title {
  font-size: 2.2rem;
  font-weight: 700;
  line-height: 1.02;
  margin: 0;
}

.wmv-hero-copy {
  margin-top: 0.75rem;
  max-width: 820px;
  color: rgba(246,241,232,0.78);
  font-size: 1rem;
  line-height: 1.7;
}

.wmv-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 1rem;
}

.wmv-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.75rem;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
  color: #f6f1e8;
  font-size: 0.88rem;
}

.wmv-section-label {
  margin: 0.7rem 0 0.45rem;
  font-size: 0.82rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}

.wmv-panel {
  background: rgba(255,255,255,0.74);
  border: 1px solid rgba(17,21,15,0.08);
  border-radius: 24px;
  padding: 1rem 1.05rem 1.05rem;
  box-shadow: 0 14px 28px rgba(31,37,29,0.06);
}

.wmv-panel-dark {
  background: linear-gradient(180deg, #151913 0%, #1d231c 100%);
  color: #f6f1e8;
  border: 1px solid rgba(255,255,255,0.05);
}

.wmv-mini-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 0.7rem;
}

.wmv-stat {
  padding: 0.85rem 0.9rem;
  border-radius: 18px;
  background: rgba(255,255,255,0.62);
  border: 1px solid rgba(17,21,15,0.06);
}

.wmv-panel-dark .wmv-stat {
  background: rgba(255,255,255,0.05);
  border-color: rgba(255,255,255,0.06);
}

.wmv-stat-label {
  color: var(--muted);
  font-size: 0.8rem;
  margin-bottom: 0.25rem;
}

.wmv-panel-dark .wmv-stat-label {
  color: rgba(246,241,232,0.6);
}

.wmv-stat-value {
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.1;
}

.wmv-note {
  padding: 0.9rem 1rem;
  border-left: 4px solid var(--accent);
  background: var(--accent-soft);
  border-radius: 0 16px 16px 0;
  color: #71452f;
  margin-top: 0.8rem;
}

.wmv-divider {
  height: 1px;
  background: linear-gradient(90deg, rgba(17,21,15,0.14), transparent);
  margin: 0.8rem 0 1rem;
}

.stButton > button,
.stDownloadButton > button {
  border-radius: 999px;
  border: 1px solid rgba(17,21,15,0.08);
  background: linear-gradient(180deg, #d85f2f 0%, #c14f23 100%);
  color: white;
  font-weight: 700;
  min-height: 2.9rem;
  box-shadow: 0 10px 20px rgba(216,95,47,0.2);
}

.stButton > button:hover,
.stDownloadButton > button:hover {
  border-color: rgba(17,21,15,0.08);
  color: white;
}

.stTabs [data-baseweb="tab-list"] {
  gap: 0.45rem;
}

.stTabs [data-baseweb="tab"] {
  border-radius: 999px;
  background: rgba(17,21,15,0.05);
  padding: 0.45rem 0.9rem;
}

.stTabs [aria-selected="true"] {
  background: #11150f !important;
  color: #f6f1e8 !important;
}

[data-testid="stMetric"] {
  background: rgba(255,255,255,0.74);
  border: 1px solid rgba(17,21,15,0.06);
  padding: 0.8rem 0.95rem;
  border-radius: 20px;
}

@media (max-width: 900px) {
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
    chip_html = "".join(f"<span class='wmv-chip'>{chip}</span>" for chip in chips)
    st.markdown(
        f"""
<section class="wmv-hero">
  <div class="wmv-hero-kicker">{kicker}</div>
  <h1 class="wmv-hero-title">{title}</h1>
  <p class="wmv-hero-copy">{subtitle}</p>
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


def _render_metric_panel(metrics: dict, frame_index: int, fps: float) -> None:
    st.subheader("当前帧数据面板")
    groups = build_metric_groups(metrics, frame_index, fps)
    tabs = st.tabs(list(groups.keys()))
    for tab, (title, dataframe) in zip(tabs, groups.items()):
        with tab:
            st.dataframe(dataframe, use_container_width=True, hide_index=True)


def _save_current_screenshots(run_dir: Path, frame_bundle: dict[str, object]) -> dict[str, Path]:
    screenshot_dir = run_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "original_frame": screenshot_dir / "original_frame.png",
        "skeleton_frame": screenshot_dir / "skeleton_frame.png",
        "side_by_side_frame": screenshot_dir / "side_by_side_frame.png",
    }
    save_frame_image(frame_bundle["original_frame"], paths["original_frame"])
    save_frame_image(frame_bundle["skeleton_frame"], paths["skeleton_frame"])
    save_frame_image(frame_bundle["side_by_side_frame"], paths["side_by_side_frame"])
    return paths


def _render_video_exports(result: dict) -> None:
    render_section_label("导出")
    render_panel_start()
    st.markdown("**分析结果文件**")
    export_paths = {
        "下载 side_by_side_video.mp4": result["side_by_side_video_path"],
        "下载 keypoints.json": result["keypoints_json_path"],
        "下载 metrics.csv": result["metrics_csv_path"],
        "下载 summary.json": result["summary_json_path"],
        "下载 summary.md": result["summary_md_path"],
    }
    columns = st.columns(len(export_paths))
    for column, (label, path) in zip(columns, export_paths.items()):
        with column:
            st.download_button(
                label=label,
                data=_load_binary(path),
                file_name=Path(path).name,
                mime="application/octet-stream",
                use_container_width=True,
            )
    render_panel_end()


def _prepare_selected_input(uploaded_file, selected_local_video_name: str | None) -> Path | None:
    video_input_path = st.session_state.get("video_input_path")

    if uploaded_file is not None:
        upload_signature = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get("video_upload_signature") != upload_signature:
            st.session_state.video_upload_signature = upload_signature
            st.session_state.video_input_path = save_uploaded_video(uploaded_file)
            st.session_state.analysis_result = None
            st.session_state.video_current_frame = 0
        return st.session_state.video_input_path

    if selected_local_video_name:
        candidate_path = INPUT_DIR / selected_local_video_name
        if video_input_path != candidate_path:
            st.session_state.video_input_path = candidate_path
            st.session_state.analysis_result = None
            st.session_state.video_current_frame = 0
        return candidate_path

    return video_input_path


def render_video_analysis_page(config: dict) -> None:
    render_hero(
        title="视频分析工作台",
        subtitle="先生成稳定的 side-by-side 分析结果，再逐帧查看原画面、骨架画面和当前帧指标。这里强调观察，不做自动评分。",
        chips=["离线处理", "双画面对照", "逐帧检查", "适合后续云部署"],
        kicker="Video Analysis",
    )

    local_videos = list_local_videos()
    local_video_names = [path.name for path in local_videos]

    render_section_label("输入")
    left_col, right_col = st.columns([1.2, 1.0], gap="large")

    with left_col:
        render_panel_start()
        st.markdown("**选择分析视频**")
        uploaded_file = st.file_uploader("上传 mp4 视频", type=["mp4"])
        selected_local_video_name = st.selectbox(
            "或直接选择 data/input 中的本地视频",
            options=[""] + local_video_names,
            format_func=lambda name: "请选择本地视频" if name == "" else name,
        )
        video_input_path = _prepare_selected_input(uploaded_file, selected_local_video_name if selected_local_video_name else None)
        if video_input_path is not None:
            st.caption(f"当前输入文件：`{video_input_path}`")
        analyze_clicked = st.button("开始分析", type="primary", use_container_width=True, disabled=video_input_path is None)
        render_panel_end()

    with right_col:
        render_panel_start(dark=True)
        st.markdown("**这一步会得到什么**")
        st.markdown(
            """
- 左侧原视频、右侧骨架视频的对照结果  
- 每一帧的角度、速度、重心和 `motion_intensity`  
- 便于逐帧检查的滑块与曲线图  
- 可选导出的视频、CSV、JSON、摘要报告
            """
        )
        st.markdown(
            "<div class='wmv-note'>如果后续部署到云服务器，这个页面最适合先做成“上传视频并生成分析结果”的多人访问版本。</div>",
            unsafe_allow_html=True,
        )
        render_panel_end()

    if analyze_clicked and video_input_path is not None:
        progress_bar = st.progress(0, text="准备开始分析...")
        processor = build_offline_components(config)
        try:
            result = processor.process(
                video_input_path,
                progress_callback=lambda progress, text: progress_bar.progress(min(progress, 1.0), text=text),
            )
            st.session_state.analysis_result = result
            st.session_state.video_current_frame = 0
            progress_bar.progress(1.0, text="分析完成")
        finally:
            processor.pose_backend.close()

    result = st.session_state.get("analysis_result")
    if not result:
        st.info("先上传视频或选择 data/input 中的本地 mp4，再点击“开始分析”。")
        return

    total_frames = int(result["total_frames"])
    fps = float(result["fps"])
    metrics_df: pd.DataFrame = result["metrics_df"]

    render_section_label("概览")
    metric_cols = st.columns(4)
    metric_cols[0].metric("总帧数", f"{total_frames}")
    metric_cols[1].metric("视频 FPS", f"{fps:.1f}")
    metric_cols[2].metric("当前输出目录", "已生成")
    metric_cols[3].metric("当前模式", "离线分析")

    render_section_label("分析结果视频")
    render_panel_start(dark=True)
    st.video(_load_binary(result["side_by_side_video_path"]))
    render_panel_end()

    render_section_label("逐帧检查")
    selected_frame = st.slider(
        "当前帧",
        min_value=0,
        max_value=max(0, total_frames - 1),
        value=min(st.session_state.get("video_current_frame", 0), max(0, total_frames - 1)),
        step=1,
    )
    st.session_state.video_current_frame = selected_frame

    side_by_side_frame = read_frame_at_index(result["side_by_side_video_path"], selected_frame)
    if side_by_side_frame is None:
        st.error("无法读取生成后的 side-by-side 视频帧。")
        return

    original_frame, skeleton_frame = split_side_by_side_frame(side_by_side_frame)
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
            screenshot_paths = _save_current_screenshots(
                result["run_dir"],
                {
                    "original_frame": original_frame,
                    "skeleton_frame": skeleton_frame,
                    "side_by_side_frame": side_by_side_frame,
                },
            )
            st.success("截图已保存到: " + ", ".join(str(path) for path in screenshot_paths.values()))
        render_panel_end()

    _render_metric_panel(metrics, selected_frame, fps)

    render_section_label("曲线与轨迹")
    chart_tab, trajectory_tab = st.tabs(["角度与强度曲线", "轨迹图"])
    with chart_tab:
        st.plotly_chart(make_metric_figure(metrics_df, selected_frame), use_container_width=True)
    with trajectory_tab:
        st.plotly_chart(make_trajectory_figure(metrics_df), use_container_width=True)

    _render_video_exports(result)


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
        show_live_trajectory = st.checkbox("显示短轨迹残影（约 1 秒后自然消失）", value=False)
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
        capture = cv2.VideoCapture(0)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, config["app"]["default_camera_width"])
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config["app"]["default_camera_height"])
        if not capture.isOpened():
            st.error("摄像头打开失败，请检查是否被其他程序占用。")
            return
        st.session_state.camera_capture = capture
        st.session_state.camera_processor = build_realtime_components(config)
        st.session_state.camera_running = True
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

    result = processor.process_frame(frame, show_trajectories=show_live_trajectory)
    st.session_state.last_realtime_result = result
    history = st.session_state.get("realtime_history", [])
    history.append(result["metrics"])
    recent_seconds = config["app"]["recent_seconds_for_live_chart"]
    max_rows = int(max(result["fps"], 20.0) * recent_seconds)
    st.session_state.realtime_history = history[-max_rows:]

    metrics_col = st.columns(4)
    metrics_col[0].metric("实时 FPS", f"{result['fps']:.1f}")
    metrics_col[1].metric("当前帧", f"{int(result['metrics']['frame_index'])}")
    metrics_col[2].metric("左手腕速度", _fmt_value(result["metrics"].get("left_wrist_speed"), "px/s"))
    metrics_col[3].metric("motion_intensity", _fmt_value(result["metrics"].get("motion_intensity")))

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
        run_dir = make_output_run_dir("camera_snapshot")
        screenshot_paths = _save_current_screenshots(
            run_dir,
            {
                "original_frame": result["original_frame"],
                "skeleton_frame": result["skeleton_frame"],
                "side_by_side_frame": result["side_by_side_frame"],
            },
        )
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

本系统是“武术动作骨架实时可视化分析系统”，不是“AI 自动武术教练”。

系统负责做的事情：

- 实时提取人体关键点并绘制主骨架
- 展示角度、速度、重心、轨迹、`motion_intensity`
- 让教练在同一界面同时观察原始动作和骨架变化
- 支持视频离线分析和本机摄像头实时分析

系统明确不做的事情：

- 不自动判断动作对错
- 不自动评分
- 不识别真实肌肉发力
- 不识别真实呼吸
- 不训练深度学习模型

这意味着页面里的数据更像“训练观察仪表板”，它帮助人看动作，而不是替人做动作判断。
            """
        )
        st.markdown(
            "<div class='wmv-note'>如果之后部署到云服务器，最推荐先开放“视频上传分析”能力。浏览器端多人实时摄像头分析需要单独改成前端采集摄像头并上传流的架构。</div>",
            unsafe_allow_html=True,
        )
        render_panel_end()

    with metrics_tab:
        render_panel_start()
        st.markdown(
            """
### 关键点来源

系统基于 `MediaPipe Pose` 提取 33 个人体关键点。每一帧都会得到关键点的归一化坐标，再换算到像素坐标用于绘图和计算。

### 角度计算

通用函数：

```python
calculate_angle(point_a, point_b, point_c)
```

含义：以 `point_b` 为顶点，计算 `a-b-c` 的夹角。若任意点缺失或坐标异常，则返回 `NaN`。

主要角度定义：

- 左肘：`left_shoulder - left_elbow - left_wrist`
- 右肘：`right_shoulder - right_elbow - right_wrist`
- 左肩：`left_elbow - left_shoulder - left_hip`
- 右肩：`right_elbow - right_shoulder - right_hip`
- 左髋：`left_shoulder - left_hip - left_knee`
- 右髋：`right_shoulder - right_hip - right_knee`
- 左膝：`left_hip - left_knee - left_ankle`
- 右膝：`right_hip - right_knee - right_ankle`
- 左踝：`left_knee - left_ankle - left_foot_index`
- 右踝：`right_knee - right_ankle - right_foot_index`

### 躯干倾斜角

先求肩部中心和髋部中心，再构造从髋部中心指向肩部中心的向量。该向量相对竖直方向的偏转角，就是 `torso_tilt_angle`。

### 速度计算

速度来自相邻帧的关键点像素位移：

```text
speed = distance(current_point, previous_point) * fps
```

当前版本计算：

- `left_wrist_speed`
- `right_wrist_speed`
- `left_ankle_speed`
- `right_ankle_speed`
- `hip_center_speed`

为了减小抖动，速度会经过简单指数平滑。

### 粗略重心估计

第一版不是生物力学精确质心，而是视觉关键点粗略估计：

- 优先使用左右肩、左右髋的加权中心
- 若这些关键点缺失，则回退为所有可见关键点的平均中心

输出字段：

- `center_of_mass_x`
- `center_of_mass_y`

### motion_intensity

```text
motion_intensity =
0.25 * left_wrist_speed +
0.25 * right_wrist_speed +
0.20 * left_ankle_speed +
0.20 * right_ankle_speed +
0.10 * hip_center_speed
```

它是“运动强度趋势指标”，不是肌肉发力值。
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

#### 位置类

- 髋部中心坐标、髋部高度：帮助看起伏、沉降、腾起和步型转换
- 双脚距离、肩宽、两手距离：帮助看架子开合和动作幅度
- 粗略重心位置：帮助看身体整体是否偏前、偏后、偏左、偏右

#### 速度类

- 手腕速度：适合看出刀、架刀、收刀、挑刀这些上肢变化的快慢
- 脚踝速度：适合看步法切换和下肢发起节奏
- 髋部中心速度：适合看整体身体推进或撤收的节奏

#### 轨迹类

- 手腕轨迹：适合看器械和上肢的运动路径
- 脚踝轨迹：适合看步法路径
- 髋部中心轨迹：适合看整体移动趋势

#### motion_intensity

- 用于快速观察当前这一段动作是“爆发”还是“过渡”
- 适合和视频、骨架一起看节奏峰值
- 不应用来判断动作标准与否

### 页面解读建议

- 主判断依据永远是原始视频和主骨架
- 实时数字用于辅助，不建议脱离画面单独解释
- 对单帧丢点要容忍，出现 `NaN` 不代表动作错误，只代表该帧检测不稳
            """
        )
        render_panel_end()

    with deploy_tab:
        render_panel_start(dark=True)
        st.markdown(
            """
### 云服务器部署建议

#### 最适合先部署的能力

先部署“视频分析模式”，让用户上传 mp4，服务端离线处理，再返回结果页面和导出文件。

#### 启动方式

```bash
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

#### 服务器侧还要做的事

- 放行 `8501` 端口，或放在 `Nginx` 后面走 80/443
- 给 `data/input`、`data/output` 预留磁盘空间
- 对上传文件大小做限制
- 定期清理旧输出目录，避免磁盘越积越满
- 如果多人并发上传较多，建议把分析任务移到后台队列

#### 推荐的公网结构

1. `Nginx` 反向代理域名
2. Streamlit 负责前端页面
3. 本地磁盘或对象存储保存输出文件
4. 后续如并发增加，再拆成“Web 层 + 分析任务层”

#### 关于实时摄像头

当前实时摄像头模式使用 `cv2.VideoCapture(0)`，读取的是服务器本机摄像头。

这意味着：

- 本地运行时很好用
- 直接部署到云服务器后，不适合给公网用户直接使用

如果以后要做“用户浏览器打开网页后，用自己的摄像头实时分析”，需要改成：

1. 浏览器采集摄像头
2. 前端把帧或视频流发送给服务端
3. 服务端推理后回传结果

这一块是下一阶段架构，不建议和当前离线分析版混在一起做。
            """
        )
        render_panel_end()


def _fmt_value(value, unit: str = "", precision: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NaN"
    if pd.isna(number):
        return "NaN"
    suffix = f" {unit}" if unit else ""
    return f"{number:.{precision}f}{suffix}"


def main() -> None:
    st.set_page_config(page_title="wushu_motion_visualizer", layout="wide")
    inject_styles()
    config = load_config()

    st.sidebar.title("wushu_motion_visualizer")
    st.sidebar.caption("本地可运行的武术动作骨架可视化分析系统")
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
