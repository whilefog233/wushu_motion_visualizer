import { useEffect, useMemo, useRef, useState } from 'react'
import {
  MUSCLES, MUSCLE_V2_VERSION, QUALITY_THRESHOLDS,
  activityIntervals, buildMuscleAnalysis, detectMusclePeaks,
  intervalQuality, median3Peak, summarizeMuscle,
} from '../lib/muscleV2'

const qualityText={reliable:'可靠',caution:'需谨慎',invalid:'不可分析',unknown:'未评估'}
const featureLabels={
  left_knee_angular_velocity:'左膝角速度',right_knee_angular_velocity:'右膝角速度',
  left_knee_angular_acceleration:'左膝角加速度',right_knee_angular_acceleration:'右膝角加速度',
  left_elbow_angular_velocity:'左肘角速度',right_elbow_angular_velocity:'右肘角速度',
  left_elbow_angular_acceleration:'左肘角加速度',right_elbow_angular_acceleration:'右肘角加速度',
  left_shoulder_angular_velocity:'左肩角速度',right_shoulder_angular_velocity:'右肩角速度',
  left_ankle_angular_velocity:'左踝角速度',right_ankle_angular_velocity:'右踝角速度',
  left_ankle_speed:'左踝速度',right_ankle_speed:'右踝速度',
  left_wrist_speed:'左腕速度',right_wrist_speed:'右腕速度',
  hip_angular_velocity:'髋角速度',hip_center_speed:'髋中心速度',
  left_hip_angle:'左髋角',right_hip_angle:'右髋角',
  torso_angular_velocity:'躯干倾斜角速度',torso_tilt_angle:'躯干倾斜角',
  torso_rotation_velocity:'肩线旋转速度',torso_rotation_angle:'肩线旋转角',
  hand_distance:'双手距离',shoulder_width:'肩宽',motion_intensity:'动作强度',
}
const unitFor = key => key.includes('acceleration')?'°/s²':key.includes('angular_velocity')||key==='torso_rotation_velocity'?'°/s':key.includes('angle')?'°':['hand_distance','shoulder_width'].includes(key)?'px':'px/s'
const fmt=(n,d=2)=>typeof n==='number'&&Number.isFinite(n)?n.toFixed(d):'—'

function pathsFor(rows,qualities,key,start,end) {
  let paths=[],current=[]
  const flush=()=>{if(current.length>1) paths.push(current.map(([x,y],i)=>`${i?'L':'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' '));current=[]}
  rows.forEach((r,i)=>{
    if(r.frame<start||r.frame>end) return
    const value=r[key]
    if(qualities[i]?.status==='invalid'||!Number.isFinite(value)) {flush();return}
    current.push([38+(r.frame-start)/Math.max(1,end-start)*942,226-value*190])
  })
  flush()
  return paths
}

function TrendChart({analysis,selected,frameIndex,zoom,setZoom,segment,setSegment,onSeek}) {
  const svgRef=useRef(null),dragRef=useRef(null)
  const [hover,setHover]=useState(null),[drag,setDrag]=useState(null)
  const {rows,qualities}=analysis
  const frameAtEvent=e=>{
    const rect=svgRef.current.getBoundingClientRect()
    const svgX=(e.clientX-rect.left)/rect.width*1000
    const ratio=Math.max(0,Math.min(1,(svgX-38)/942))
    return Math.max(zoom[0],Math.min(zoom[1],Math.round(zoom[0]+ratio*(zoom[1]-zoom[0]))))
  }
  const x=f=>38+(f-zoom[0])/Math.max(1,zoom[1]-zoom[0])*942
  const onMove=e=>{
    const frame=frameAtEvent(e)
    setHover(frame)
    if(dragRef.current!==null) setDrag([dragRef.current,frame])
  }
  const onUp=e=>{
    if(dragRef.current===null) return
    const from=dragRef.current,to=frameAtEvent(e)
    if(Math.abs(from-to)>=2) setSegment([Math.min(from,to),Math.max(from,to)])
    else onSeek?.(to)
    dragRef.current=null
    setDrag(null)
    e.currentTarget.releasePointerCapture?.(e.pointerId)
  }
  const hoverRow=rows.find(r=>r.frame===hover)
  const activeSelection=drag||segment
  const shown=selected.map(key=>MUSCLES.find(m=>m.key===key)).filter(Boolean)
  return <div className="muscle-chart-shell">
    <div className="muscle-chart-title"><div><strong>肌群活动时序</strong><span>原始逐帧代理值 · 拖拽选区 · 点击跳帧</span></div><div className="muscle-chart-actions"><button onClick={()=>{
      const width=Math.max(8,Math.round((zoom[1]-zoom[0])*.5))
      const center=Math.max(zoom[0],Math.min(zoom[1],frameIndex))
      const last=rows.at(-1)?.frame||0
      const start=Math.max(0,Math.min(last-width,center-Math.round(width/2)))
      setZoom([start,start+width])
    }}>放大</button><button onClick={()=>setZoom([0,rows.at(-1)?.frame||0])}>全片</button></div></div>
    <div className="muscle-chart">
      <svg ref={svgRef} viewBox="0 0 1000 260" preserveAspectRatio="none" aria-label="八类肌群逐帧活动曲线"
        onPointerDown={e=>{dragRef.current=frameAtEvent(e);e.currentTarget.setPointerCapture(e.pointerId)}}
        onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={()=>{dragRef.current=null;setDrag(null)}} onPointerLeave={()=>{if(dragRef.current===null)setHover(null)}}>
        {[0,.25,.5,.75,1].map(v=><g key={v}><line x1="38" x2="980" y1={226-v*190} y2={226-v*190} stroke="#70658a" strokeOpacity=".18"/><text x="3" y={230-v*190} fill="#9b96b6" fontSize="12">{v.toFixed(2)}</text></g>)}
        {activeSelection&&<rect x={x(activeSelection[0])} y="32" width={Math.max(1,x(activeSelection[1])-x(activeSelection[0]))} height="194" fill="#2dd4bf" fillOpacity=".10" stroke="#2dd4bf" strokeOpacity=".5"/>}
        {shown.map(m=>pathsFor(rows,qualities,m.key,zoom[0],zoom[1]).map((path,i)=><path key={m.key+i} d={path} fill="none" stroke={m.color} strokeWidth={selected.length>4?1.6:2.5} strokeOpacity=".9" vectorEffect="non-scaling-stroke"/>))}
        <line x1={x(frameIndex)} x2={x(frameIndex)} y1="32" y2="226" stroke="#e9fdf8" strokeWidth="1.5" strokeDasharray="4 4" vectorEffect="non-scaling-stroke"/>
        {hover!==null&&<line x1={x(hover)} x2={x(hover)} y1="32" y2="226" stroke="#b4a9d5" strokeOpacity=".7" strokeWidth="1" vectorEffect="non-scaling-stroke"/>}
        <text x="38" y="251" fill="#9b96b6" fontSize="12">{fmt(zoom[0]/analysis.fps,1)}s</text>
        <text x="928" y="251" fill="#9b96b6" fontSize="12">{fmt(zoom[1]/analysis.fps,1)}s</text>
      </svg>
      {hoverRow&&<div className="muscle-chart-tooltip"><b>#{hoverRow.frame} · {fmt(hoverRow.time_sec,2)}s</b>{shown.map(m=><span key={m.key}><i style={{background:m.color}}/>{m.label} {fmt(hoverRow[m.key])}</span>)}</div>}
    </div>
    <div className="muscle-chart-legend">{shown.map(m=><span key={m.key}><i style={{background:m.color}}/>{m.label}</span>)}</div>
  </div>
}

export default function MuscleTabV2({result,metrics,muscleFrames,pose,frameIndex=0,onSeek}) {
  const summary=result?.muscle?.summary
  const [selected,setSelected]=useState(['deltoids','forearms'])
  const [primary,setPrimary]=useState('deltoids')
  const [zoom,setZoom]=useState(null)
  const [segment,setSegment]=useState(null)
  const analysis=useMemo(()=>buildMuscleAnalysis(muscleFrames,metrics,pose),[muscleFrames,metrics,pose])
  const {rows,qualities}=analysis
  useEffect(()=>{setZoom(null);setSegment(null)},[muscleFrames])
  if(!summary) return <div className="muscle-empty">上传并分析视频后显示肌群相关运动学活动。</div>
  if(!rows.length) return <div className="muscle-empty"><strong>逐帧肌群数据不可用</strong><span>旧版汇总仍在，但缺少 muscle_metrics.csv，无法生成可追溯曲线。</span></div>
  const last=rows.at(-1).frame
  const view=zoom||[0,last]
  const scope=segment||[0,last]
  const selectedMuscle=MUSCLES.find(m=>m.key===primary)||MUSCLES[0]
  const currentIndex=rows.findIndex(r=>r.frame===frameIndex)
  const current=currentIndex>=0?rows[currentIndex]:null
  const currentQuality=currentIndex>=0?qualities[currentIndex]:{status:'invalid',reasons:['该帧无肌群数据']}
  const rangeQuality=intervalQuality(rows,qualities,scope[0],scope[1])
  const stats=summarizeMuscle(rows,primary,scope[0],scope[1],qualities)
  const medianPeak=median3Peak(rows,primary,scope[0],scope[1])
  const currentMetric=analysis.metricByFrame.get(frameIndex)||{}
  const around=Math.max(1,Math.round(analysis.fps*.5))
  const before=summarizeMuscle(rows,primary,Math.max(scope[0],(stats.peakFrame??0)-around),Math.max(scope[0],(stats.peakFrame??0)-1)).mean
  const after=summarizeMuscle(rows,primary,Math.min(scope[1],(stats.peakFrame??0)+1),Math.min(scope[1],(stats.peakFrame??0)+around)).mean
  const peaks=selected.flatMap(key=>detectMusclePeaks(rows,qualities,key,analysis.fps,scope[0],scope[1]))
    .sort((a,b)=>b.prominence-a.prominence||b.value-a.value).slice(0,8).sort((a,b)=>a.frame-b.frame)
  const intervals=activityIntervals(rows,qualities,selected,analysis.fps,scope[0],scope[1]).slice(0,8)
  const toggle=key=>{
    if(selected.includes(key)) {
      if(selected.length===1) return
      const next=selected.filter(k=>k!==key)
      setSelected(next)
      if(primary===key)setPrimary(next[0])
    } else {setSelected([...selected,key]);setPrimary(key)}
  }
  return <div className="muscle-v2" data-version={MUSCLE_V2_VERSION}>
    <div className="muscle-v2-head"><div><span className="muscle-overline">MUSCLE ACTIVITY / V2</span><h3>肌群相关运动学活动</h3><p>读取已保存的八类逐帧代理值；0–1 为相对指标，未经肌电标定。</p></div><span className={'muscle-quality '+currentQuality.status}>{qualityText[currentQuality.status]}<small>当前帧 #{frameIndex}</small></span></div>
    <div className="muscle-overview" aria-label="八类肌群概览">
      {MUSCLES.map(m=>{
        const s=summarizeMuscle(rows,m.key,scope[0],scope[1],qualities)
        return <button key={m.key} className={'muscle-choice '+(selected.includes(m.key)?'selected':'')} onClick={()=>toggle(m.key)} aria-pressed={selected.includes(m.key)} style={{'--muscle-color':m.color}}>
          <span className="muscle-choice-top"><i/>{m.label}<small>{m.area}</small></span>
          <span className="muscle-choice-values"><b>{currentQuality.status==='invalid'?'—':fmt(current?.[m.key])}</b><small>均 {fmt(s.mean)} · 峰 {fmt(s.peak)}</small></span>
          <span className="muscle-choice-track"><i style={{width:`${Math.max(0,Math.min(100,(current?.[m.key]||0)*100))}%`}}/></span>
        </button>
      })}
    </div>
    <div className="muscle-main">
      <div className="muscle-left">
        <TrendChart analysis={analysis} selected={selected} frameIndex={frameIndex} zoom={view} setZoom={setZoom} segment={segment} setSegment={setSegment} onSeek={onSeek}/>
        <div className="muscle-scope"><span>{segment?`选中区间 #${scope[0]}–#${scope[1]} · ${fmt(scope[0]/analysis.fps)}–${fmt(scope[1]/analysis.fps)}s`:`全片 #0–#${last}`}</span><button onClick={()=>setSegment(null)} disabled={!segment}>清除选区</button><span className={'muscle-scope-status '+rangeQuality.status}>{qualityText[rangeQuality.status]} · {rangeQuality.counts.reliable}/{rangeQuality.counts.reliable+rangeQuality.counts.caution+rangeQuality.counts.invalid} 帧可靠</span></div>
      </div>
      <aside className="muscle-inspector">
        <span className="muscle-overline">SELECTED / {selectedMuscle.area}</span>
        <h4 style={{color:selectedMuscle.color}}>{selectedMuscle.label}</h4>
        <div className="muscle-stat-row"><div><small>当前值</small><strong>{currentQuality.status==='invalid'?'—':fmt(current?.[primary])}</strong></div><div><small>区间均值</small><strong>{fmt(stats.mean)}</strong></div><div><small>原始峰值</small><strong>{fmt(stats.peak)}</strong></div></div>
        <p className="muscle-peak-time">峰值 #{stats.peakFrame??'—'} · {fmt(stats.peakTime)}s · {qualityText[stats.peakQuality]||'未评估'} <button disabled={stats.peakFrame===null} onClick={()=>onSeek?.(stats.peakFrame)}>跳转</button></p>
        <p className="muscle-peak-time">峰前 0.5s 均值 {fmt(before)} → 峰 {fmt(stats.peak)} → 峰后 0.5s 均值 {fmt(after)}</p>
        <p className="muscle-peak-time">三帧中值参考峰 {fmt(medianPeak.value)} · #{medianPeak.frame??'—'} / {fmt(medianPeak.time)}s；仅用于对照峰值衰减和时移</p>
        <div className="muscle-inspector-block"><h5>计算依据</h5><p>旧版规则：基线 0.05；{selectedMuscle.basis}。信号归一化、EMA(α=0.28)，最终裁剪至 0–1。</p></div>
        <div className="muscle-inspector-block"><h5>当前帧相关指标 <small>左右仅列运动学输入，不拆分肌群值</small></h5><div className="muscle-feature-list">{selectedMuscle.features.map(key=><div key={key}><span>{featureLabels[key]||key}</span><b>{fmt(currentMetric[key],key.includes('angle')?1:0)} <small>{unitFor(key)}</small></b></div>)}</div></div>
        <div className="muscle-inspector-block"><h5>数据质量 <span className={'muscle-quality-inline '+currentQuality.status}>{qualityText[currentQuality.status]}</span></h5><p>{currentQuality.reasons?.length?currentQuality.reasons.join('；'):'主要关节点可见度、画面边界、骨长及孤立尖峰检查通过。'}</p><p className="muscle-limit">单目姿态与经验权重只能提示相关活动，不能代表肌电激活率、肌肉力量或左右肌肉独立估计。</p></div>
      </aside>
    </div>
    <div className="muscle-bottom">
      <section><div className="muscle-section-title"><h4>活动峰值</h4><span>三帧中值定位 · 最短间隔 0.25s · 排除低质量帧</span></div><div className="muscle-events">{peaks.length?peaks.map(p=>{
        const m=MUSCLES.find(item=>item.key===p.key),source=analysis.metricByFrame.get(p.frame)||{}
        const evidence=m.features.filter(key=>typeof source[key]==='number'&&Number.isFinite(source[key])).slice(0,2)
        return <button key={p.key+p.frame} onClick={()=>onSeek?.(p.frame)} className="muscle-event"><span style={{color:m.color}}>{p.kind==='major'?'主要峰值':'局部峰值'} · {m.label}</span><strong>{fmt(p.time)}s <small>#{p.frame}</small></strong><em>代理值 {fmt(p.value)} · 峰显著度 {fmt(p.prominence)}</em><small>{evidence.map(key=>`${featureLabels[key]} ${fmt(source[key],0)} ${unitFor(key)}`).join(' · ')||'运动学依据缺失'}</small></button>
      }):<p className="muscle-empty-small">当前区间没有通过质量和峰显著度门槛的活动峰值。</p>}</div></section>
      <section><div className="muscle-section-title"><h4>活动区间</h4><span>中性运动学描述 · 非武术技术判定</span></div><div className="muscle-intervals">{intervals.length?intervals.map(w=>{
        const q=intervalQuality(rows,qualities,w.start,w.end)
        return <button key={w.start} onClick={()=>{setSegment([w.start,w.end]);onSeek?.(w.peak)}}><span>活动上升 → 高活动 → 回落</span><strong>{fmt(w.start/analysis.fps)}–{fmt(w.end/analysis.fps)}s</strong><small>峰 #{w.peak} · {qualityText[q.status]} · 点击定位</small></button>
      }):<p className="muscle-empty-small">所选范围内未形成连续的高活动区间。</p>}</div></section>
    </div>
    <p className="muscle-footnote">质量规则 V{MUSCLE_V2_VERSION}：主要关节可见度 ≥ {QUALITY_THRESHOLDS.reliableVisibility}，可靠均值 ≥ {QUALITY_THRESHOLDS.reliableMean}；骨长比 {QUALITY_THRESHOLDS.boneRatioLow}–{QUALITY_THRESHOLDS.boneRatioHigh}；低于 {QUALITY_THRESHOLDS.minFps} FPS 标记谨慎。曲线值及全片统计保留 V1 原数据，峰值定位使用三帧中值去除孤立尖峰。</p>
  </div>
}
