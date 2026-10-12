import { finite, formatValue, rowAt } from '../lib/frameData'
const specs = [
  ['left_knee_angle','左膝角度',165,180],['right_knee_angle','右膝角度',165,180],
  ['left_elbow_angle','左肘角度',150,170],['right_elbow_angle','右肘角度',150,170],
  ['torso_tilt_angle','躯干倾斜',-5,5],
]
export default function CoreMetrics({metrics,frameIndex=0}) {
  const row=rowAt(metrics,frameIndex)
  return <div>
    <div className="metric-heading"><span className="heading-icon">＋</span><h3>核心指标</h3><span>{finite(row.timestamp_sec)?'帧 #'+frameIndex+' · '+row.timestamp_sec.toFixed(2)+'s':'等待帧数据'}</span></div>
    <div className="core-grid">{specs.map(([key,label,low,high])=>{
      const value=row[key], valid=finite(value)
      const ok=valid&&value>=low&&value<=high
      const color=!valid?'#9290b0':ok?'#2dd4bf':'#fb923c'
      const fraction=valid?Math.max(0,Math.min(1,key==='torso_tilt_angle'?Math.abs(value)/90:value/180)):0
      return <div key={key} className="metric-card" style={{'--metric-color':color}}>
        <div className="metric-label">{label}<span className="metric-dot"/></div>
        <strong className="metric-value">{formatValue(value)}<small>°</small></strong>
        <svg viewBox="0 0 100 42" className="metric-gauge" aria-hidden="true">
          <path d="M12 37 A38 38 0 0 1 88 37" fill="none" stroke="rgba(139,92,246,.15)" strokeWidth="7"/>
          {valid&&<path d="M12 37 A38 38 0 0 1 88 37" fill="none" stroke={color} strokeWidth="7" pathLength="100" strokeDasharray={fraction*100+' 100'}/>}
        </svg>
        <div className="metric-footer"><span>参考 {low}°~{high}°</span><b>{!valid?'暂无':ok?'范围内':'偏离'}</b></div>
      </div>
    })}</div>
    <p className="metric-note">参考区间沿用现有规则，动作阶段不同，角度范围也会变化。</p>
  </div>
}

