import { useState } from 'react'

function dimColor(rate, hasDed) {
  if (!hasDed) return '#3ff0cf'
  if (rate >= 0.8) return '#3ff0cf'
  if (rate >= 0.6) return '#8b7bff'
  if (rate >= 0.4) return '#ffb547'
  return '#ff5470'
}

function Ring({ total }) {
  const r = 42
  const c = 2 * Math.PI * r
  return (
    <div className="relative h-[104px] w-[104px] shrink-0">
      <svg viewBox="0 0 104 104" className="h-full w-full -rotate-90">
        <defs>
          <linearGradient id="ringGrad2" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#7ff5e2" /><stop offset="100%" stopColor="#14e2bd" />
          </linearGradient>
        </defs>
        <circle cx="52" cy="52" r={r} fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="8" />
        <circle
          cx="52" cy="52" r={r} fill="none" stroke="url(#ringGrad2)" strokeWidth="8"
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - total / 100)}
          style={{ filter: 'drop-shadow(0 0 6px rgba(20,226,189,.6))' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-[28px] font-bold leading-none">{Math.round(total)}</span>
        <span className="text-[9.5px] text-ink-500">/ 100</span>
      </div>
    </div>
  )
}

export default function ScorePanel({ result }) {
  const score = result?.score
  const dims = score?.dimensions || []
  const firstDed = dims.findIndex((d) => d.deductions?.length)
  const [sel, setSel] = useState(firstDed >= 0 ? firstDed : 0)

  if (!score) {
    return (
      <div className="glass flex h-full items-center justify-center text-[12.5px] text-ink-500">
        分析完成后显示动作评分
      </div>
    )
  }

  const dim = dims[Math.min(sel, dims.length - 1)] || {}
  const rate = dim.max_score ? dim.score / dim.max_score : 1
  const color = dimColor(rate, dim.deductions?.length)

  return (
    <section className="glass flex h-full items-stretch gap-4 p-4">
      {/* 总分 */}
      <div className="flex flex-col items-center justify-center gap-2 border-r border-white/[.07] pr-4">
        <Ring total={score.total_score} />
        <span className={`rounded-full border px-2 py-0.5 text-[9.5px] ${
          score.has_expert_template ? 'border-mint-500/40 text-mint-300' : 'border-warn/35 text-warn'}`}>
          {score.has_expert_template ? '专家模板对照' : '实验性评分'}
        </span>
      </div>

      {/* 7 维度列表 */}
      <div className="w-[270px] shrink-0 overflow-y-auto pr-1">
        <p className="mb-1.5 text-[11.5px] font-semibold text-ink-300">评分维度 · 点击查看扣分</p>
        <div className="space-y-1.5">
          {dims.map((d, i) => {
            const r2 = d.max_score ? d.score / d.max_score : 1
            const c2 = dimColor(r2, d.deductions?.length)
            const on = i === sel
            return (
              <button
                key={d.key}
                onClick={() => setSel(i)}
                className={`w-full rounded-lg border px-2 py-1.5 text-left transition ${
                  on ? 'border-mint-500/50 bg-white/[.05]' : 'border-white/[.06] hover:bg-white/[.03]'}`}
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="truncate text-ink-300">{d.name}</span>
                  <span className="font-mono" style={{ color: c2 }}>{d.score}/{d.max_score}</span>
                </div>
                <div className="mt-1 h-1 overflow-hidden rounded-full bg-white/[.07]">
                  <div className="h-full rounded-full" style={{ width: `${r2 * 100}%`, background: c2 }} />
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* 选中维度证据 */}
      <div className="min-w-0 flex-1 overflow-y-auto rounded-lg border border-white/[.07] bg-black/20 p-3">
        <p className="text-[12px] font-semibold" style={{ color }}>
          {dim.name} <span className="font-mono text-ink-500">{dim.score}/{dim.max_score}</span>
        </p>
        {dim.deductions?.length ? (
          <div className="mt-2 space-y-2.5">
            {dim.deductions.map((dd, i) => (
              <div key={i} className="space-y-1 border-t border-white/[.06] pt-2">
                <p className="text-[11.5px] font-medium text-danger">−{dd.deduction} 分 · {dd.problem}</p>
                <p className="text-[10.5px] leading-relaxed text-ink-300"><span className="text-ink-500">证据：</span>{dd.evidence}</p>
                <p className="text-[10.5px] leading-relaxed text-mint-300/90"><span className="text-ink-500">提升：</span>{dd.training_advice}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-[11px] text-mint-300">本维度未扣分，继续保持。</p>
        )}
      </div>
    </section>
  )
}
