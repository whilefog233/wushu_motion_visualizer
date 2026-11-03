
const STANDARD_STEPS = [
  '准备：重心微沉，护手持稳，目视目标',
  '启动：先转髋、送重心，肩自然被带出',
  '加速：肘沿直线伸展，拳面旋转向前',
  '击打：腕部最后弹出，末端速度达到峰值',
  '回收：沿原路线快速弹回护手位',
]

function buildFromResult(result) {
  const tech = result.technique
  const flat = tech.windows.flatMap((w) => w.diagnoses || [])
  const order = { high: 3, medium: 2, low: 1, positive: 0 }
  const problems = flat
    .filter((d) => d.severity !== 'positive')
    .sort((a, b) => order[b.severity] - order[a.severity])
  const positives = flat.filter((d) => d.severity === 'positive')
  const top = problems[0]

  const summary = [
    `本次动作总分 ${result.score?.total_score ?? '--'}。`,
    top ? `最主要问题是「${top.problem}」。` : '未发现明显结构性问题。',
    positives[0] ? `同时，${positives[0].problem}。` : '',
  ].join('')

  return {
    summary,
    priorityDrill: top ? top.training_advice : '保持当前动作，尝试逐步提升出拳速度。',
    standard: STANDARD_STEPS,
    nextSession: problems.slice(0, 3).map((p) => p.training_advice).filter(Boolean),
    confidence: result.score?.confidence ?? null,
    limitations: !result.score?.has_expert_template
      ? '无专家模板，评分为实验性估计；速度为像素/归一化单位，非真实物理速度。'
      : '结论基于与专家模板的结构差异。',
  }
}

export default function AIAdviceTab({ result }) {
  if (!result?.technique?.windows?.length) return <div className="empty-analysis">暂无可用诊断建议，请先分析视频。</div>
  const a = buildFromResult(result)

  return (
    <div className="space-y-3">
      <div className="glass-strong p-4">
        <p className="text-[13px] font-semibold text-mint-300">本次动作总评</p>
        <p className="mt-2 text-[13px] leading-relaxed text-ink-100">{a.summary}</p>
        <p className="mt-2 font-mono text-[11px] text-ink-500">建议来源：现有技术诊断规则 · 置信度 {a.confidence == null ? '暂无' : Math.round(a.confidence * 100) + '%'}</p>
      </div>

      <div className="rounded-xl border border-mint-500/35 bg-gradient-to-r from-mint-500/15 to-transparent p-4">
        <p className="text-[12.5px] font-semibold text-mint-300">本轮最重要的一件事</p>
        <p className="mt-1.5 text-[13.5px] font-medium">{a.priorityDrill}</p>
      </div>

      <div className="glass p-4">
        <p className="mb-3 text-[12.5px] font-semibold">标准动作应该怎样完成</p>
        <ol className="space-y-2">
          {a.standard.map((s, i) => (
            <li key={i} className="flex gap-2.5 text-[12.5px] leading-relaxed text-ink-300">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-mint-500/15 font-mono text-[10px] text-mint-300">{i + 1}</span>
              {s}
            </li>
          ))}
        </ol>
      </div>

      <div className="glass p-4">
        <p className="mb-3 text-[12.5px] font-semibold">下一轮具体怎么练</p>
        <ul className="space-y-2">
          {a.nextSession.map((s, i) => (
            <li key={i} className="flex items-start gap-2 text-[12.5px] leading-relaxed text-ink-300">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-mint-400" />{s}
            </li>
          ))}
        </ul>
      </div>

      <p className="rounded-lg border border-white/[.08] bg-white/[.03] px-3 py-2 text-[10.5px] leading-relaxed text-ink-500">
        能力边界：{a.limitations} 系统不测量真实拳力/肌电，不做医学判断，不替代专业教练。
      </p>
    </div>
  )
}
