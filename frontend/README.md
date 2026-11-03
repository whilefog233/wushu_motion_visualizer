# Kungfu V4 Web UI（高保真前端）

深空紫 × 青绿 · 玻璃拟态 · 专业运动分析控制台风格。

## 方式一：立即预览（无需安装）

直接双击打开 **`preview.html`**（需联网加载 CDN）。

## 方式二：完整开发环境（推荐）

```bash
cd web-ui
npm install
npm run dev
# 打开 http://localhost:5173
```

## 目录结构

```
src/
  App.jsx                 # 页面布局组装
  data/mockData.js        # 全部 mock 数据（接后端时替换为 API 返回）
  components/
    Sidebar.jsx           # 左侧导航
    Header.jsx           # 顶部标题 + 特性卡
    UploadPanel.jsx      # 上传视频
    PipelineSteps.jsx    # 分析流程步骤
    StartButton.jsx      # 开始分析
    VideoStage.jsx       # 视频区 + 骨架叠加 + 数据浮层 + 控制栏
    KeyFrames.jsx        # 关键帧时间轴
    AnalysisTabs.jsx     # 右侧标签容器
    PoseAnalysisTab.jsx  # 姿态分析（指标/骨架/趋势图）
    PowerChainTab.jsx    # 发力链诊断（时序图 + 诊断卡）
    TechCompareTab.jsx   # 技术对比
    AIAdviceTab.jsx      # AI 建议
    ScorePanel.jsx       # 环形评分
    ActionCompare.jsx    # 正误动作对比
    SkeletonFigure.jsx   # 发光骨架 SVG（复用组件）
    Icons.jsx            # 图标库
```

## 接入真实数据

1. `mockData.js` 中每个导出对应一个后端接口返回结构
2. 视频区场景层替换为 `<video>` + 真实骨架坐标
3. 骨架坐标使用 MediaPipe 归一化点（0~1000 映射）
