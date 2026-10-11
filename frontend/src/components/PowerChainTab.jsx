import { useState } from 'react'

const CHAIN_COLORS = { lower: '#8b7bff', hip: '#5b8cff', trunk: '#3ff0cf', upper: '#7ff5e2' }
const CHAIN_LABEL = { lower: '下肢', hip: '髋', trunk: '躯干', upper: '上肢' }

const sevStyle = {
  high: { text: 'text-danger', bg: 'bg-danger/12', border: 'border-danger/35', tag: '高' },
  medium: { text: 'text-warn', bg: 'bg-warn/12', border: 'border-warn/35', tag: '中' },
  low: { text: 'text-mint-300', bg: 'bg-mint-500/10', border: 'border-mint-500/30', tag: '低' },
  positive: { text: 'text-mint-300', bg: 'bg-mint-500/10', border: 'border-mint-500/30', tag: '优' },
}

// ---------- 当前帧：四段发力实时值 ----------
function LiveChainBar({ result, frameIndex }) {
  const frames = result?.power_chain?.frames || []
  const f = frames[Math.min(frameIndex, frames.length - 1)]
  const scores = f?.scores || {}
  return (
    <div className="rounded-xl border border-white/[.07] bg-white/[.025] p-3.5">
      <p className="mb-2.5 flex items-center gap-2 text-[12.5px] font-semibold">
        当前帧发力链 · 帧 #{frameIndex}
        <span className="ml-auto font-mono text-[10.5px] font-normal text-ink-500">{f?.stage || ''}</span>
      </p>
      <div className="space-y-2">
        {Object.keys(CHAIN_COLORS).map((k) => {
          const v = scores[k] ?? 0
          return (
            <div key={k} className="flex items-center gap-2.5">
              <span className="w-9 text-[11px] text-ink-500">{CHAIN_LABEL[k]}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[.06]">
                <div
                  className="h-full rounded-full transition-all duration-150"
                  style={{ width: `${Math.min(100, v * 100)}%`, background: CHAIN_COLORS[k], boxShadow: `0 0 8px ${CHAIN_COLORS[k]}88` }}
                />
              </div>
              <span className="w-9 text-right font-mono text-[11px]" style={{ color: CHAIN_COLORS[k] }}>{v.toFixed(2)}</span>
            </div>
          )
        })}
      </div>
      <p className="mt-2 text-[10px] text-ink-700">看力量是否按 下肢→髋→躯干→上肢 依次点亮；若上肢先亮、下肢不亮，多为手臂主导。</p>
    </div>
  )
}

// ---------- 窗口选择 ----------
function WindowSelector({ windows, sel, onSel }) {
  return (
    <div className="flex flex-wrap gap-2">
      {windows.map((w) => {
        const on = w.window_index === sel
        return (
          <button
            key={w.window_index}
            onClick={() => onSel(w.window_index)}
            className={`rounded-lg border px-3 py-1.5 text-[11.5px] transition ${
              on ? 'border-mint-400 bg-mint-500/12 text-mint-300 shadow-mint-glow'
                 : 'border-white/[.09] bg-white/[.03] text-ink-500 hover:text-ink-100'
            }`}
          >
            #{w.window_index + 1} · {w.strike_hand === 'left' ? '左' : '右'}手 · {Number(w.time_start_sec).toFixed(1)}s
          </button>
        )
      })}
    </div>
  )
}

// ---------- 阶段时间轴 ----------
function PhaseBar({ win }) {
  const phases = win.phases || []
  const total = Math.max(1, ...phases.map((p) => p.duration_ms))
  return (
    <div className="rounded-xl border border-white/[.07] bg-white/[.025] p-3.5">
      <p className="mb-2.5 text-[12.5px] font-semibold">动作阶段 · 时长比例</p>
      <div className="flex h-9 gap-[2px] overflow-hidden rounded-md">
        {phases.map((p, i) => {
          const w = Math.max(6, (p.duration_ms / total) * 100)
          const colors = ['#4a3fa8', '#5b8cff', '#35b8d6', '#3ff0cf', '#2a9d8f']
          return (
            <div key={p.name} className="flex items-center justify-center overflow-hidden" style={{ width: `${w}%`, background: `${colors[i]}55` }}>
              <span className="truncate px-1 text-[9px] text-ink-100">{p.label.replace('阶段', '')}</span>
            </div>
          )
        })}
      </div>
      <div className="mt-2 grid grid-cols-5 gap-1 text-center font-mono text-[10px] text-ink-500">
        {phases.map((p) => (
          <span key={p.name}>{Math.round(p.duration_ms)}ms</span>
        ))}
      </div>
    </div>
  )
}

// ---------- 髋肩肘腕 时序图 ----------
function TimingChart({ win }) {
  const evs = win.events || []
  const base = win.time_start_sec
  const tOf = (name) => {
    const e = evs.find((x) => x.name === name)
    return e ? e.time_sec - base : null
  }
  const rows = [
    { joint: '髋', start: tOf('hip_start'), peak: tOf('hip_angular_velocity_peak'), color: '#8b7bff' },
    { joint: '肩', start: tOf('shoulder_start'), peak: tOf('shoulder_velocity_peak'), color: '#5b8cff' },
    { joint: '肘', start: null, peak: tOf('elbow_extension_peak'), color: '#3ff0cf' },
    { joint: '腕', start: tOf('wrist_start'), peak: tOf('wrist_speed_peak'), color: '#7ff5e2' },
  ].filter((r) => r.peak != null)

  const times = rows.flatMap((r) => [r.start, r.peak]).filter((v) => v != null)
  const tMax = Math.max(0.12, ...times) * 1.12
  const xAt = (t) => 56 + (t / tMax) * 452

  return (
    <div className="rounded-xl border border-white/[.07] bg-white/[.025] p-4">
      <p className="mb-3 text-[12.5px] font-semibold">发力时序 · 髋 → 肩 → 肘 → 腕（相对该动作起点）</p>
      <svg viewBox="0 0 540 180" className="w-full">
        {Array.from({ length: 5 }, (_, i) => (i / 4) * tMax).map((t) => (
          <g key={t}>
            <line x1={xAt(t)} y1="16" x2={xAt(t)} y2="140" stroke="rgba(255,255,255,.06)" strokeDasharray="3 4" />
            <text x={xAt(t)} y="156" textAnchor="middle" fontSize="9" fill="#8a8fb5">{Math.round(t * 1000)}ms</text>
          </g>
        ))}
        {rows.map((e, row) => {
          const y = 32 + row * 30
          return (
            <g key={e.joint}>
              <text x="24" y={y + 4} fontSize="12" fill={e.color} fontWeight="600">{e.joint}</text>
              {e.start != null && (
                <>
                  <line x1={xAt(e.start)} y1={y} x2={xAt(e.peak)} y2={y} stroke={e.color} strokeWidth="2.5" opacity=".5" />
                  <circle cx={xAt(e.start)} cy={y} r="4.5" fill="#0c0720" stroke={e.color} strokeWidth="2" />
                </>
              )}
              <circle cx={xAt(e.peak)} cy={y} r="6" fill={e.color} style={{ filter: `drop-shadow(0 0 5px ${e.color})` }} />
              <text x={xAt(e.peak) + 10} y={y + 4} fontSize="9" fill="#b9bede">{Math.round(e.peak * 1000)}ms</text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// ---------- 时序间隔判定表 ----------
function TimingTable({ win }) {
  const timing = win.timing || []
  const icon = (ok) => (ok === true ? <span className="text-mint-300">✓ 顺序正确</span>
    : ok === false ? <span className="text-danger">✗ 顺序异常</span>
    : <span className="text-ink-700">—</span>)
  return (
    <div className="rounded-xl border border-white/[.07] bg-white/[.025] p-4">
      <p className="mb-2 text-[12.5px] font-semibold">关键间隔判定</p>
      <table className="w-full text-[11.5px]">
        <tbody>
          {timing.map((t, i) => (
            <tr key={i} className="border-t border-white/[.05]">
              <td className="py-2 text-ink-300">{t.label}</td>
              <td className="py-2 text-right font-mono text-ink-100">{Math.round(t.interval_ms)}ms</td>
              <td className="py-2 pl-3 text-right">{icon(t.order_ok)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------- 诊断卡 ----------
function DiagnosisCard({ d }) {
  const s = sevStyle[d.severity] || sevStyle.low
  return (
    <div className={`rounded-xl border ${s.border} ${s.bg} p-3.5`}>
      <p className={`flex items-center gap-2 text-[13px] font-semibold ${s.text}`}>
        <span className={`flex h-5 w-5 items-center justify-center rounded-md border ${s.border} text-[10px]`}>{s.tag}</span>
        {d.problem}
        <span className="ml-auto font-mono text-[10px] font-normal text-ink-500">置信度 {Math.round((d.confidence ?? 0.6) * 100)}%</span>
      </p>
      {d.evidence_text && <p className="mt-2 text-[11.5px] text-ink-300"><span className="text-ink-500">证据：</span>{d.evidence_text}</p>}
      {d.meaning && <p className="mt-1 text-[11.5px] text-ink-300"><span className="text-ink-500">含义：</span>{d.meaning}</p>}
      {d.training_advice && <p className="mt-1 text-[11.5px] text-mint-300/90"><span className="text-ink-500">训练建议：</span>{d.training_advice}</p>}
    </div>
  )
}

export default function PowerChainTab({ result, frameIndex }) {
  const windows = result?.technique?.windows || []
  const [sel, setSel] = useState(0)
  if (!windows.length) {
    return <p className="px-1 py-8 text-center text-[12.5px] text-ink-500">上传并分析视频后，这里显示每一段动作的发力链诊断。</p>
  }
  const win = windows[Math.min(sel, windows.length - 1)]

  return (
    <div className="space-y-3">
      <LiveChainBar result={result} frameIndex={frameIndex} />
      <WindowSelector windows={windows} sel={win.window_index} onSel={setSel} />

      <div className="rounded-xl border border-mint-500/30 bg-gradient-to-r from-mint-500/12 to-transparent p-3.5">
        <p className="text-[11.5px] font-semibold text-mint-300">动作 #{win.window_index + 1} · 本轮最重要的一件事</p>
        <p className="mt-1 text-[12.5px] leading-relaxed">{win.one_thing}</p>
      </div>

      <PhaseBar win={win} />
      <TimingChart win={win} />
      <TimingTable win={win} />

      <p className="text-[11.5px] font-semibold text-ink-300">该动作诊断（{win.diagnoses?.length || 0} 条）</p>
      {(win.diagnoses || []).map((d, i) => (
        <DiagnosisCard key={d.problem_id || d.id || i} d={d} />
      ))}
    </div>
  )
}
