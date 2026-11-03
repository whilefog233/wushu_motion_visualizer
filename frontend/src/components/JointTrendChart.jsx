import { finite,rowAt } from '../lib/frameData'
const series=[['left_knee_angle','左膝','#2dd4bf'],['right_knee_angle','右膝','#5eead4'],['left_elbow_angle','左肘','#a78bfa'],['right_elbow_angle','右肘','#c4b5fd'],['torso_tilt_angle','躯干','#818cf8']]
export default function JointTrendChart({metrics,frameIndex=0,onSeek}) {
  const rows=metrics?.rows || []
  if(!rows.length)return <div className="trend-panel"><h3>关节角度趋势</h3><div className="chart-empty">分析后显示真实角度曲线</div></div>
  const sampled=rows.filter((_,i)=>i%Math.max(1,Math.ceil(rows.length/240))===0||i===rows.length-1)
  const minT=rows[0].timestamp_sec || 0, maxT=rows[rows.length-1].timestamp_sec || minT+1
  const values=sampled.flatMap(r=>series.map(([key])=>r[key])).filter(finite)
  const lo=Math.min(0,...values), hi=Math.max(180,...values)
  const x=t=>36+(t-minT)/(maxT-minT||1)*508
  const y=v=>12+(hi-v)/(hi-lo||1)*128
  const current=rowAt(metrics,frameIndex)
  return <div className="trend-panel"><div className="metric-heading"><h3>关节角度趋势</h3><span>点击曲线定位</span></div>
    <div className="chart-legend">{series.map(([key,name,color])=><span key={key}><i style={{background:color}}/>{name}</span>)}</div>
    <svg viewBox="0 0 560 166" className="trend-chart" role="img" aria-label="关节角度随时间变化，虚线表示当前帧" onClick={e=>{
      const rect=e.currentTarget.getBoundingClientRect()
      const target=minT+Math.max(0,Math.min(1,((e.clientX-rect.left)/rect.width*560-36)/508))*(maxT-minT)
      const row=rows.reduce((best,r)=>Math.abs(r.timestamp_sec-target)<Math.abs(best.timestamp_sec-target)?r:best,rows[0])
      onSeek?.(row.frame_index)
    }}>
      {[lo,(hi+lo)/2,hi].map(v=><g key={v}><line x1="36" x2="544" y1={y(v)} y2={y(v)} stroke="#ffffff12" strokeDasharray="3 4"/><text x="29" y={y(v)+3} textAnchor="end" fill="#9290b0" fontSize="10">{Math.round(v)}°</text></g>)}
      {series.map(([key,,color])=><path key={key} d={sampled.map((r,i)=>finite(r[key])?(i===0||!finite(sampled[i-1][key])?'M':'L')+x(r.timestamp_sec)+','+y(r[key]):'').join(' ')} fill="none" stroke={color} strokeWidth="1.6"/>)}
      {finite(current.timestamp_sec)&&<line x1={x(current.timestamp_sec)} x2={x(current.timestamp_sec)} y1="8" y2="142" stroke="#2dd4bf" strokeDasharray="4 3"/>}
      {[0,.25,.5,.75,1].map(t=><text key={t} x={x(minT+t*(maxT-minT))} y="160" textAnchor="middle" fill="#9290b0" fontSize="10">{(minT+t*(maxT-minT)).toFixed(1)}s</text>)}
    </svg>
  </div>
}

