import { useState } from 'react'
import PoseAnalysisTab from './PoseAnalysisTab'
import PowerChainTab from './PowerChainTab'
import TechCompareTab from './TechCompareTab'
import MuscleTab from './MuscleTab'
import AIAdviceTab from './AIAdviceTab'

const tabs = [
  { id: 'pose', label: '姿态分析' },
  { id: 'chain', label: '发力链诊断' },
  { id: 'muscle', label: '肌肉分析' },
  { id: 'compare', label: '技术对比' },
  { id: 'ai', label: 'AI 建议' },
]

export default function AnalysisTabs({ result, metrics, pose, frameIndex, onSeek }) {
  const [tab, setTab] = useState('pose')
  const Panel = {
    pose: PoseAnalysisTab,
    chain: PowerChainTab,
    muscle: MuscleTab,
    compare: TechCompareTab,
    ai: AIAdviceTab,
  }[tab]

  return (
    <section className="glass analysis-panel flex min-w-0 flex-1 flex-col overflow-hidden">
      <div role="tablist" aria-label="分析模块" className="analysis-tablist">
        {tabs.map((t) => {
          const on = tab === t.id
          return (
            <button
              key={t.id}
              role="tab" aria-selected={on} aria-controls="analysis-tab-content" id={'tab-'+t.id}
              onClick={() => setTab(t.id)}
              className={`relative px-4 py-2.5 text-[12.5px] font-medium transition ${on ? 'text-mint-300' : 'text-ink-500 hover:text-ink-300'}`}
            >
              {t.label}
              {on && <span className="absolute inset-x-3 bottom-0 h-[2.5px] rounded-t bg-mint-400 shadow-mint-glow" />}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id="analysis-tab-content" aria-labelledby={'tab-'+tab} className="analysis-tab-content">
        <Panel result={result} metrics={metrics} pose={pose} frameIndex={frameIndex} onSeek={onSeek} />
      </div>
    </section>
  )
}
