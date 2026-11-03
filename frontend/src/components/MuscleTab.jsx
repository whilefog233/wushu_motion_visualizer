// 肌群分区配色
const GROUP = {
  quadriceps: '#8b7bff', hamstrings: '#8b7bff', glutes: '#a99cff', calves: '#a99cff',
  erector_spinae: '#3ff0cf', obliques: '#3ff0cf',
  deltoids: '#5b8cff', forearms: '#7ff5e2',
}

function MuscleBars({ stats }) {
  return (
    <div className="rounded-xl border border-white/[.07] bg-white/[.025] p-4">
      <p className="mb-1 text-[12.5px] font-semibold">肌群参与估计 · 平均 / 峰值</p>
      <p className="mb-3 text-[10px] text-ink-700">为关节运动推算的相对激活度（0~1），非真实肌电。</p>
      <div className="space-y-2">
        {stats.map((m) => {
          const c = GROUP[m.muscle] || '#3ff0cf'
          return (
            <div key={m.muscle} className="flex items-center gap-2.5">
              <span className="w-16 shrink-0 text-[11px] text-ink-300">{m.label}</span>
              <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-white/[.06]">
                <div className="h-full rounded-full" style={{ width: `${m.mean * 100}%`, background: `${c}aa` }} />
                {/* 峰值标记 */}
                <span className="absolute top-[-2px] h-[14px] w-[2px]" style={{ left: `${m.max * 100}%`, background: c, boxShadow: `0 0 5px ${c}` }} />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-[10.5px]" style={{ color: c }}>
                {m.mean.toFixed(2)}/{m.max.toFixed(2)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function HintDistribution({ counts }) {
  const entries = Object.entries(counts).map(([k, v]) => [k.replace('发力链提示：', ''), v])
  const total = entries.reduce((a, [, v]) => a + v, 0) || 1
  const colors = ['#8b7bff', '#5b8cff', '#3ff0cf', '#7ff5e2', '#a99cff']
  return (
    <div className="rounded-xl border border-white/[.07] bg-white/[.025] p-4">
      <p className="mb-3 text-[12.5px] font-semibold">发力来源分布</p>
      <div className="space-y-2">
        {entries.map(([label, v], i) => (
          <div key={label} className="flex items-center gap-2.5">
            <span className="w-[150px] shrink-0 truncate text-[10.5px] text-ink-300">{label}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[.06]">
              <div className="h-full rounded-full" style={{ width: `${(v / total) * 100}%`, background: colors[i % colors.length] }} />
            </div>
            <span className="w-10 text-right font-mono text-[10.5px] text-ink-500">{v}帧</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function PeakMoments({ moments, onSeek }) {
  return (
    <div className="rounded-xl border border-white/[.07] bg-white/[.025] p-4">
      <p className="mb-3 text-[12.5px] font-semibold">整体发力峰值时刻 · 点击跳转</p>
      <div className="grid grid-cols-3 gap-2.5">
        {moments.map((m) => (
          <button
            key={m.frame}
            onClick={() => onSeek?.(m.frame)}
            className="rounded-lg border border-white/[.08] bg-white/[.03] p-2.5 text-left transition hover:border-mint-500/50"
          >
            <p className="font-mono text-[11px] text-mint-300">{m.time_sec.toFixed(2)}s · 帧{m.frame}</p>
            <p className="mt-1 text-[10.5px] leading-snug text-ink-300">{m.top_muscles}</p>
          </button>
        ))}
      </div>
    </div>
  )
}

export default function MuscleTab({ result, onSeek }) {
  const summary = result?.muscle?.summary
  if (!summary) {
    return <p className="px-1 py-8 text-center text-[12.5px] text-ink-500">上传并分析后显示肌肉参与估计。</p>
  }
  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-mint-500/25 bg-mint-500/[.06] px-3.5 py-2.5 text-[11.5px] text-mint-300">
        {summary.dominant_power_chain_hint}
      </div>
      <MuscleBars stats={summary.muscle_statistics || []} />
      <HintDistribution counts={summary.power_chain_hint_counts || {}} />
      <PeakMoments moments={summary.peak_moments || []} onSeek={onSeek} />
      <p className="text-[10px] leading-relaxed text-ink-700">
        说明：肌肉数据由关节角度、角速度与动作阶段推算，用于判断主要参与部位与发力来源，不代表真实肌电（EMG），不做医学判断。
      </p>
    </div>
  )
}
