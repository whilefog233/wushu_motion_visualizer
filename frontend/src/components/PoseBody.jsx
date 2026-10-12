import { useEffect, useRef } from 'react'
import { drawSkeleton } from '../lib/drawSkeleton'

function FrameCanvas({ pose, frameIndex, color, mirror }) {
  const ref = useRef(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas || !pose) return
    const ctx = canvas.getContext('2d')
    let pts = pose.frames[Math.min(frameIndex, pose.frames.length - 1)]
    if (mirror && pts) pts = pts.map((p) => [1 - p[0], p[1], p[2]])
    drawSkeleton(ctx, pts, pose.width, pose.height, color)
  }, [pose, frameIndex, color, mirror])

  if (!pose?.frames?.length) return <div className="pose-placeholder">暂无骨架</div>
  return (
    <canvas
      ref={ref}
      width={pose.width}
      height={pose.height}
      className="h-[150px] w-[72px] rounded-lg object-contain"
    />
  )
}

export default function PoseBody({ pose, frameIndex = 0 }) {
  return (
    <div className="pose-body flex flex-col p-3.5">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-mint-500/15 text-mint-400">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="5" r="2.2" /><path d="M12 7.5V14M8 10h8M9 21l3-7 3 7" /></svg>
        </span>
        <span className="panel-title">骨架分析</span>
        <span className="panel-sub">Pose Analysis</span>
      </div>

      <div className="flex items-center justify-center gap-3">
        <div className="flex flex-col items-center gap-1.5">
          <FrameCanvas pose={pose} frameIndex={frameIndex} color="#3ff0cf" />
          <span className="text-[10px] text-ink-500">原视角 · 当前帧</span>
        </div>
        <div className="flex flex-col items-center gap-1.5">
          <FrameCanvas pose={pose} frameIndex={frameIndex} color="#2a9d8f" mirror />
          <span className="text-[10px] text-ink-500">镜像</span>
        </div>
      </div>

      <p className="mt-3 text-center font-mono text-[11px] text-mint-300">
        {pose ? `帧 #${frameIndex} / ${pose.frame_count}` : '上传分析后显示真实骨架'}
      </p>
    </div>
  )
}
