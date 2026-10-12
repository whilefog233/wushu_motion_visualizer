import { IconCheck } from './Icons'

const STAGE_RANK = {
  UPLOADING: 0, QUEUED: 1, PREPARING: 2, EXTRACTING_POSE: 3,
  CALCULATING_METRICS: 4, ANALYZING_MUSCLE: 5, ANALYZING_POWER_CHAIN: 6,
  SAVING_RESULTS: 7, COMPLETED: 8,
}

// 5 个展示节点：[名称, 完成所需 rank, active 的 rank 区间]
const NODES = [
  { name: '视频上传', doneRank: 1, active: [0, 0] },
  { name: 'AI 姿态推理', doneRank: 4, active: [1, 3] },
  { name: '发力链分析', doneRank: 7, active: [4, 6] },
  { name: '技术诊断', doneRank: 8, active: [7, 7] },
  { name: '生成结果', doneRank: 8, active: [8, 8] },
]

function stateOf(node, rank, failed) {
  if (failed) return rank >= node.doneRank ? 'done' : (rank >= node.active[0] ? 'failed' : 'wait')
  if (rank >= node.doneRank) return 'done'
  if (rank >= node.active[0] && rank <= node.active[1]) return 'active'
  return 'wait'
}

function StepNode({ state }) {
  if (state === 'done')
    return (
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-mint-500/20 text-mint-400 ring-1 ring-mint-500/60">
        <IconCheck className="h-4 w-4" />
      </span>
    )
  if (state === 'active')
    return (
      <span className="relative flex h-9 w-9 items-center justify-center">
        <span className="absolute inset-0 animate-pulseGlow rounded-full bg-mint-500/25" />
        <span className="h-9 w-9 rounded-full border-2 border-mint-400 shadow-mint-glow" />
        <span className="absolute h-3 w-3 rounded-full bg-mint-400" />
      </span>
    )
  if (state === 'failed')
    return <span className="flex h-9 w-9 items-center justify-center rounded-full border-2 border-danger/60 bg-danger/15 text-danger">!</span>
  return <span className="h-9 w-9 rounded-full border-2 border-white/15 bg-white/[.03]" />
}

export default function PipelineSteps({ task }) {
  const failed = task?.status === 'FAILED'
  const rank = failed
    ? STAGE_RANK[task.stage] ?? 0
    : task ? STAGE_RANK[task.stage] ?? (task.status === 'COMPLETED' ? 8 : 1) : -1

  const states = NODES.map((n) => stateOf(n, rank, failed))

  return (
    <section className="glass pipeline-panel p-4">
      <div className="mb-4 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-mint-500/15 text-mint-400">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M4 6h16M4 12h16M4 18h10" /></svg>
        </span>
        <span className="text-[14px] font-semibold text-ink-100">2. 分析流程</span>
      </div>

      <div className="flex items-start">
        {NODES.map((n, i) => (
          <div key={n.name} className="flex flex-1 flex-col items-center ">
            <div className="flex w-full items-center">
              {i > 0 && (
                <span className={`h-[2px] flex-1 ${states[i - 1] === 'done' ? 'bg-mint-500/60' : 'bg-white/10'}`} />
              )}
              <StepNode state={states[i]} />
              {i < NODES.length - 1 && (
                <span className={`h-[2px] flex-1 ${states[i] === 'done' ? 'bg-mint-500/60' : 'bg-white/10'}`} />
              )}
            </div>
            <span className={`mt-2 text-[12px] font-medium ${states[i] === 'active' ? 'text-mint-300' : states[i] === 'done' ? 'text-ink-300' : 'text-ink-500'}`}>
              {n.name}
            </span>
            <span className="text-[10px] text-ink-700">
              {states[i] === 'done' ? '已完成' : states[i] === 'active' ? '进行中...' : states[i] === 'failed' ? '失败' : '等待中'}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
