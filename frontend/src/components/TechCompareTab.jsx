function summarize(result) {
  const windows = result.technique?.windows || []
  const gaps = []
  const recoveries = []
  let orderBad = 0
  let timingRows = 0
  const hands = { left: 0, right: 0 }

  windows.forEach((w) => {
    const evs = w.events || []
    const t = (n) => evs.find((e) => e.name === n)?.time_sec
    const hp = t('hip_angular_velocity_peak')
    const sp = t('shoulder_velocity_peak')
    if (hp != null && sp != null) gaps.push((sp - hp) * 1000)
    const me = t('max_extension')
    const ae = t('action_end')
    if (me != null && ae != null) recoveries.push(ae - me)
    ;(w.timing || []).forEach((tm) => {
      if (tm.order_ok === null) return
      timingRows += 1
      if (tm.order_ok === false) orderBad += 1
    })
    if (w.strike_hand) hands[w.strike_hand] = (hands[w.strike_hand] || 0) + 1
  })

  const avg = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null)
  return {
    n: windows.length,
    gap: avg(gaps),
    gapN: gaps.length,
    recovery: avg(recoveries),
    recN: recoveries.length,
    orderBad,
    timingRows,
    hands,
  }
}

const fmt = (v, d) => (v == null ? '--' : v.toFixed(d))

export default function TechCompareTab({ result }) {
  if (!result?.technique?.windows?.length) {
    return <p className="px-1 py-8 text-center text-[12.5px] text-ink-500">上传并分析后显示技术对照。</p>
  }
  const s = summarize(result)
  const hasExpert = result.score?.has_expert_template

  const rows = [
    {
      name: '发力链顺序',
      expect: '髋→肩→肘→腕 依次',
      cur: s.timingRows ? `${s.timingRows - s.orderBad}/${s.timingRows} 处顺序正确` : '--',
      ok: s.orderBad === 0,
    },
    {
      name: '髋→肩 峰值间隔',
      expect: '峰值依次、间隔为正',
      cur: s.gap != null ? `${fmt(s.gap, 0)}ms（${s.gapN} 段）` : '--',
      ok: s.gap != null && s.gap > 0,
    },
    {
      name: '回收时间',
      expect: '击打后快速回收',
      cur: s.recovery != null ? `${fmt(s.recovery, 2)}s（${s.recN} 段）` : '--',
      ok: s.recovery != null && s.recovery <= 0.35,
    },
    {
      name: '识别动作 / 出拳手',
      expect: '—',
      cur: `${s.n} 段 · 左${s.hands.left || 0} 右${s.hands.right || 0}`,
      ok: true,
    },
  ]

  return (
    <div className="space-y-3">
      <div className="glass p-4">
        <p className="mb-3 text-[12.5px] font-semibold">逐项对照（汇总本次全部动作窗口）</p>
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-left text-ink-500">
              <th className="pb-2 font-normal">指标</th>
              <th className="pb-2 font-normal">结构期望</th>
              <th className="pb-2 font-normal">本次实测</th>
              <th className="pb-2 text-right font-normal">状态</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="border-t border-white/[.06]">
                <td className="py-2.5 text-ink-300">{r.name}</td>
                <td className="py-2.5 text-mint-300/85">{r.expect}</td>
                <td className={`py-2.5 font-mono ${r.ok ? 'text-ink-100' : 'text-danger'}`}>{r.cur}</td>
                <td className="py-2.5 text-right">
                  <span className={`rounded-full px-2 py-0.5 text-[10px] ${r.ok ? 'bg-mint-500/12 text-mint-300' : 'bg-danger/12 text-danger'}`}>
                    {r.ok ? '符合' : '待改进'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p className={`mt-3 rounded-lg px-3 py-2 text-[10.5px] leading-relaxed ${
          hasExpert ? 'border border-mint-500/30 bg-mint-500/[.08] text-mint-300'
          : 'border border-warn/25 bg-warn/[.07] text-warn'}`}>
          {hasExpert
            ? '已加载专家模板，以上为与专家动作的差异对照。'
            : '无专家模板，以上为基于结构规则与个人基线的实验性参考，“结构期望”不是权威评分标准，仅用于定位发力顺序问题。'}
        </p>
      </div>
    </div>
  )
}
