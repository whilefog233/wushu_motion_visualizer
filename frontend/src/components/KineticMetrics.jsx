import { useMemo } from 'react'
import { finite,formatValue,rowAt } from '../lib/frameData'
const specs=[
  ['left_wrist_speed_normalized','左拳速度','norm/帧','#2dd4bf',2],
  ['right_wrist_speed_normalized','右拳速度','norm/帧','#2dd4bf',2],
  ['hip_center_speed_normalized','髋中心速度','norm/帧','#5eead4',2],
  ['motion_intensity','运动强度','强度指数','#a78bfa',2],
  ['hip_angular_velocity','髋部角速度','°/s','#a78bfa',0],
  ['torso_angular_velocity','躯干角速度','°/s','#a78bfa',0],
  ['left_elbow_angular_velocity','左肘角速度','°/s','#a78bfa',0],
  ['right_elbow_angular_velocity','右肘角速度','°/s','#a78bfa',0],
]
function Spark({rows,column,color}) {
  const path=useMemo(()=>{
    const vals=rows.map(r=>r[column]).filter(finite)
    if(vals.length<2)return ''
    const min=Math.min(...vals), span=Math.max(...vals)-min || 1
    return rows.map((r,i)=>finite(r[column])?(i===0||!finite(rows[i-1][column])?'M':'L')+(i/Math.max(1,rows.length-1)*100)+','+(30-(r[column]-min)/span*25):'').join(' ')
  },[rows,column])
  return <svg viewBox="0 0 100 36" className="sparkline" aria-label="当前帧附近的真实趋势"><path d={path} stroke={color} strokeWidth="1.8" fill="none"/></svg>
}
export default function KineticMetrics({metrics,frameIndex=0}) {
  const row=rowAt(metrics,frameIndex)
  const rows=useMemo(()=>metrics?.rows?.filter(r=>r.frame_index>=frameIndex-45&&r.frame_index<=frameIndex) || [],[metrics,frameIndex])
  return <div>
    <div className="metric-heading"><span className="heading-icon violet">ϟ</span><h3>实时运动学</h3><span>{metrics?.rows?.length?'帧 #'+frameIndex:'等待分析'}</span></div>
    {[specs.slice(0,4),specs.slice(4)].map((group,i)=><div key={i}>
      <p className="kinetic-caption">{i?'关节角速度 · 髋 → 躯干 → 肘':'末端与重心速度 · 身体尺度归一化'}</p>
      <div className="kinetic-grid">{group.map(([key,label,unit,color,d])=><div key={key} className="metric-card kinetic-card" style={{'--metric-color':color}}>
        <div className="metric-label">{label}<span className="metric-dot"/></div>
        <strong className="metric-value">{formatValue(row[key],d)}</strong>
        <span className="metric-unit">{unit}</span>
        <Spark rows={rows} column={key} color={color}/>
      </div>)}</div>
    </div>)}
    <p className="metric-note">速度来自姿态估计，并非真实物理速度；发力先后请结合动作窗口判断。</p>
  </div>
}

