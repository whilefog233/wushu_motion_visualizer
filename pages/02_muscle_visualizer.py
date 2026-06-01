from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app import (
    inject_styles,
    list_local_videos,
    load_config,
    render_hero,
    render_panel_end,
    render_panel_start,
    render_section_label,
    save_uploaded_video,
)
from muscle_analysis.muscle_estimator import MUSCLE_LABELS
from muscle_analysis.video_muscle_pipeline import process_muscle_video


def _load_binary(path: str | Path) -> bytes:
    return Path(path).read_bytes()


def _prepare_input(uploaded_file, selected_local_video_name: str | None) -> Path | None:
    if uploaded_file is not None:
        signature = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get("muscle_upload_signature") != signature:
            st.session_state.muscle_upload_signature = signature
            st.session_state.muscle_input_path = save_uploaded_video(uploaded_file)
            st.session_state.muscle_result = None
        return st.session_state.muscle_input_path

    if selected_local_video_name:
        local_videos = {path.name: path for path in list_local_videos()}
        selected_path = local_videos.get(selected_local_video_name)
        if selected_path is not None and st.session_state.get("muscle_input_path") != selected_path:
            st.session_state.muscle_input_path = selected_path
            st.session_state.muscle_result = None
        return selected_path
    return st.session_state.get("muscle_input_path")


def _build_stats_table(metrics_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, label in MUSCLE_LABELS.items():
        series = pd.to_numeric(metrics_df.get(key, pd.Series(dtype=float)), errors="coerce").dropna()
        rows.append(
            {
                "肌群": label,
                "平均参与度": round(float(series.mean()), 3) if not series.empty else None,
                "峰值参与度": round(float(series.max()), 3) if not series.empty else None,
            }
        )
    return pd.DataFrame(rows).sort_values("峰值参与度", ascending=False, na_position="last")


def main() -> None:
    st.set_page_config(page_title="武术动作肌肉运动可视化分析", layout="wide")
    inject_styles()
    load_config()

    render_hero(
        title="武术动作肌肉运动可视化分析",
        subtitle="本功能基于人体姿态识别、关节角速度、关键点速度峰值与躯干旋转特征，估计主要肌群参与度，用于训练教学可视化，不代表真实肌电信号或医学诊断结果。",
        chips=["轻量版肌群参与度估计", "独立页面", "不改原主流程", "适合云端视频分析"],
        kicker="Muscle Visualizer",
    )

    st.markdown(
        "<div class='wmv-note'>免责声明：本功能基于姿态识别与运动学特征估计肌肉参与度，不代表真实肌电信号或医学诊断结果。</div>",
        unsafe_allow_html=True,
    )

    local_videos = list_local_videos()
    local_video_names = [path.name for path in local_videos]

    render_section_label("输入")
    left_col, right_col = st.columns([1.15, 1.0], gap="large")

    with left_col:
        render_panel_start()
        st.markdown("**选择需要生成肌肉可视化的视频**")
        uploaded_file = st.file_uploader("上传 mp4 视频", type=["mp4"], key="muscle_uploader")
        selected_local_video_name = st.selectbox(
            "或直接选择 data/input 中的本地视频",
            options=[""] + local_video_names,
            format_func=lambda name: "请选择本地视频" if name == "" else name,
            key="muscle_local_video",
        )
        input_path = _prepare_input(uploaded_file, selected_local_video_name if selected_local_video_name else None)
        if input_path is not None:
            st.caption(f"当前输入文件：`{input_path}`")
        start_clicked = st.button(
            "开始肌肉可视化分析",
            type="primary",
            use_container_width=True,
            disabled=input_path is None,
        )
        render_panel_end()

    with right_col:
        render_panel_start(dark=True)
        st.markdown("**本页会输出什么**")
        st.markdown(
            """
- 左侧原始视频、右侧肌肉参与度可视化视频  
- 每帧主要肌群参与度 CSV  
- TOP 3 激活肌群、发力链提示  
- 峰值时间点与主要参与肌群统计表  
            """
        )
        st.markdown(
            "<div class='wmv-note'>这是教学观察版肌群可视化，不做肌电替代，不输出医学诊断结论。</div>",
            unsafe_allow_html=True,
        )
        render_panel_end()

    if start_clicked and input_path is not None:
        progress_bar = st.progress(0.0, text="准备肌肉可视化分析...")
        result = process_muscle_video(
            str(input_path),
            progress_callback=lambda progress, text: progress_bar.progress(progress, text=text),
        )
        st.session_state.muscle_result = result
        progress_bar.progress(1.0, text="处理完成")

    result = st.session_state.get("muscle_result")
    if not result:
        st.info("上传视频或选择 data/input 中的本地视频后，点击“开始肌肉可视化分析”。")
        return

    if result.get("error"):
        st.error(result["error"])
        return

    metrics_df: pd.DataFrame = result["metrics_df"]
    summary: dict = result["summary"]

    render_section_label("结果视频")
    col1, col2 = st.columns(2, gap="large")
    with col1:
        render_panel_start()
        st.markdown("**原视频**")
        st.video(_load_binary(st.session_state.get("muscle_input_path")))
        render_panel_end()
    with col2:
        render_panel_start(dark=True)
        st.markdown("**肌肉参与度可视化视频**")
        st.video(_load_binary(result["output_video"]))
        render_panel_end()

    render_section_label("统计与分析")
    stats_col, chain_col = st.columns([1.2, 1.0], gap="large")
    with stats_col:
        render_panel_start()
        st.markdown("**主要参与肌群统计表**")
        st.dataframe(_build_stats_table(metrics_df), use_container_width=True, hide_index=True)
        render_panel_end()

    with chain_col:
        render_panel_start()
        st.markdown("**发力链分析**")
        st.write(summary.get("dominant_power_chain_hint", "暂无数据"))
        hint_counts = summary.get("power_chain_hint_counts", {})
        if hint_counts:
            hint_df = pd.DataFrame(
                [{"提示": hint, "出现次数": count} for hint, count in hint_counts.items()]
            ).sort_values("出现次数", ascending=False)
            st.dataframe(hint_df, use_container_width=True, hide_index=True)
        render_panel_end()

    render_section_label("峰值时间点分析")
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

    render_section_label("导出")
    render_panel_start()
    download_col1, download_col2 = st.columns(2)
    with download_col1:
        st.download_button(
            "下载肌肉可视化视频",
            data=_load_binary(result["output_video"]),
            file_name=Path(result["output_video"]).name,
            mime="video/mp4",
            use_container_width=True,
        )
    with download_col2:
        st.download_button(
            "下载肌肉参与度 CSV",
            data=_load_binary(result["csv_path"]),
            file_name=Path(result["csv_path"]).name,
            mime="text/csv",
            use_container_width=True,
        )
    render_panel_end()


if __name__ == "__main__":
    main()
