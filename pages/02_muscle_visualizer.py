from __future__ import annotations

"""肌肉参与度分析页（V2：复用统一 AnalysisPipeline）。

不再单独运行 MediaPipe / 不再单独做肌肉估计：骨架、指标、肌肉全部来自
同一个 analysis 目录。视频可视化改为按需导出。
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from app import (
    bgr_to_rgb,
    inject_styles,
    list_local_videos,
    load_config,
    render_hero,
    render_panel_end,
    render_panel_start,
    render_section_label,
    save_uploaded_video,
)
from src.analysis.muscle import muscle_stats_table
from src.analysis.pipeline import AnalysisStage, analyze_video, load_analysis_result
from src.storage.analysis_store import AnalysisStore
from src.utils.paths import ensure_project_dirs


def _prepare_input() -> Path | None:
    ensure_project_dirs()
    st.markdown("#### 选择视频")
    uploaded_file = st.file_uploader("上传 mp4 视频", type=["mp4"], key="muscle_uploader")
    local_videos = list_local_videos()
    local_video_names = [path.name for path in local_videos]
    selected_local_video_name = st.selectbox(
        "或直接选择 data/input 中的本地视频",
        options=[""] + local_video_names,
        format_func=lambda name: "请选择本地视频" if name == "" else name,
    )

    if uploaded_file is not None:
        upload_signature = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get("muscle_upload_signature") != upload_signature:
            st.session_state.muscle_upload_signature = upload_signature
            st.session_state.muscle_input_path = save_uploaded_video(uploaded_file)
            st.session_state.muscle_analysis_id = None
        return st.session_state.muscle_input_path

    if selected_local_video_name:
        candidate_path = Path("data/input") / selected_local_video_name
        if st.session_state.get("muscle_input_path") != candidate_path:
            st.session_state.muscle_input_path = candidate_path
            st.session_state.muscle_analysis_id = None
        return candidate_path

    return st.session_state.get("muscle_input_path")


def _render_history() -> str | None:
    store = AnalysisStore()
    history = store.list_analyses()
    history_ids = [item["analysis_id"] for item in history]
    options = ["（新分析）"] + history_ids
    selected = st.selectbox(
        "或直接打开历史分析",
        options=options,
        format_func=lambda aid: aid
        if aid == "（新分析）"
        else f"{aid}  ·  {next((h['source_filename'] for h in history if h['analysis_id'] == aid), '')}",
    )
    return None if selected == "（新分析）" else selected


def main() -> None:
    # 注意：多页应用中 set_page_config 由主脚本 app.py 统一调用，
    # 页面脚本再次调用会抛 “can only be called once per app page”。
    inject_styles()
    config = load_config()

    render_hero(
        title="肌肉参与度与发力链分析",
        subtitle="复用统一 PoseResult：逐帧估计 8 组肌群参与度，给出主要发力肌群与发力链提示。视频可视化按需导出，分析默认只生成数据。",
        chips=["8 组肌群估计", "发力链提示", "峰值时刻", "复用统一姿态结果"],
        kicker="Muscle Analysis",
    )

    render_section_label("输入")
    input_panel, history_panel = st.columns([1.2, 1.0], gap="large")
    with input_panel:
        render_panel_start()
        video_input_path = _prepare_input()
        if video_input_path is not None:
            st.caption(f"当前输入文件：`{video_input_path}`")
        analyze_clicked = st.button("开始分析", type="primary", use_container_width=True, disabled=video_input_path is None)
        render_panel_end()

    with history_panel:
        render_panel_start(dark=True)
        history_analysis_id = _render_history()
        st.markdown(
            "<div class='wmv-note'>肌肉分析不再单独运行 MediaPipe，直接复用同一次分析的 pose.json。</div>",
            unsafe_allow_html=True,
        )
        render_panel_end()

    if analyze_clicked and video_input_path is not None:
        progress_bar = st.progress(0, text="准备开始分析...")

        def progress_callback(stage: AnalysisStage, progress: float, message: str) -> None:
            progress_bar.progress(min(progress, 1.0), text=f"{stage.value} · {message}")

        try:
            result = analyze_video(video_input_path, config=config, progress_callback=progress_callback)
            st.session_state.muscle_analysis_id = result.analysis_id
            progress_bar.progress(1.0, text="分析完成")
        except Exception as exc:
            st.error(f"分析失败：{type(exc).__name__}: {exc}")
            return

    analysis_id = history_analysis_id or st.session_state.get("muscle_analysis_id")
    if not analysis_id:
        st.info("请先选择视频并点击“开始分析”，或直接打开一条历史分析。")
        return

    try:
        result = load_analysis_result(analysis_id)
    except Exception as exc:
        st.error(f"读取分析结果失败：{exc}")
        return

    muscle = result.muscle or {}
    summary = muscle.get("summary", {})
    if not summary:
        st.warning("该分析没有肌肉数据。")
        return

    render_section_label("肌肉统计")
    stats_col, hint_col = st.columns([1.4, 1.0], gap="large")
    with stats_col:
        render_panel_start()
        st.markdown("**8 组肌群参与度统计（0-1，启发式估计）**")
        st.dataframe(muscle_stats_table(summary), use_container_width=True, hide_index=True)
        render_panel_end()

    with hint_col:
        render_panel_start(dark=True)
        st.markdown("**主导发力链提示**")
        st.write(summary.get("dominant_power_chain_hint", "暂无数据"))
        hint_counts = summary.get("power_chain_hint_counts", {})
        if hint_counts:
            hint_df = pd.DataFrame([{"提示": hint, "帧数": count} for hint, count in hint_counts.items()]).sort_values(
                "帧数", ascending=False
            )
            st.dataframe(hint_df, use_container_width=True, hide_index=True)
        render_panel_end()

    st.markdown("**峰值时刻**")
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

    st.markdown("**肌群参与度时序曲线**")
    render_panel_start()
    muscle_csv = Path(result.paths.get("muscle_csv", ""))
    if muscle_csv.exists():
        muscle_df = pd.read_csv(muscle_csv)
        columns = ["quadriceps", "hamstrings", "glutes", "calves", "erector_spinae", "obliques", "deltoids", "forearms"]
        existing_columns = [column for column in columns if column in muscle_df.columns]
        if existing_columns:
            import plotly.graph_objects as go

            figure = go.Figure()
            for column in existing_columns:
                figure.add_trace(go.Scatter(x=muscle_df["time_sec"], y=muscle_df[column], mode="lines", name=column))
            figure.update_layout(
                template="plotly_dark",
                height=420,
                margin=dict(l=24, r=24, t=36, b=24),
                legend=dict(orientation="h"),
                xaxis_title="时间 (s)",
                yaxis_title="参与度",
                yaxis_range=[0, 1],
            )
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.caption("muscle_metrics.csv 中没有可绘制的肌群列。")
    else:
        st.caption("未找到 muscle_metrics.csv。")
    render_panel_end()

    st.markdown("**导出肌肉可视化视频（按需生成）**")
    render_panel_start()
    if st.button("导出肌肉可视化视频", use_container_width=True):
        with st.spinner("正在生成肌肉可视化视频..."):
            try:
                from src.export.muscle_video import export_muscle_video

                path = export_muscle_video(result.analysis_id)
                st.success(f"已导出：{path}")
                st.video(str(path))
            except Exception as exc:
                st.error(f"导出失败：{exc}")
    render_panel_end()


if __name__ == "__main__":
    main()
