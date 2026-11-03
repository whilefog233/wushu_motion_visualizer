// Muscle V2 is a read-only interpretation of V1 muscle_metrics.csv.
// It never recalculates or replaces the eight proxy values.
export const MUSCLE_V2_VERSION = '2.0.0'
export const MUSCLES = Object.freeze([
  {key:'quadriceps', label:'股四头肌', area:'大腿前侧', color:'#68ded0', basis:'膝角速度（伸展方向）0.55 + 膝角加速度 0.18 + 髋中心速度 0.12 + 动作强度 0.08', features:['left_knee_angular_velocity','right_knee_angular_velocity','left_knee_angular_acceleration','right_knee_angular_acceleration','hip_center_speed']},
  {key:'hamstrings', label:'腘绳肌', area:'大腿后侧', color:'#a4b6ff', basis:'膝角速度（屈曲方向）0.48 + 髋角速度（负向）0.18 + 膝角加速度（负向）0.16 + 髋中心速度 0.08', features:['left_knee_angular_velocity','right_knee_angular_velocity','hip_angular_velocity','hip_center_speed']},
  {key:'glutes', label:'臀肌', area:'骨盆与臀部', color:'#d7a0f4', basis:'髋角速度 0.58 + 髋中心速度 0.22 + 髋角幅度 0.08 + 动作强度 0.05', features:['hip_angular_velocity','hip_center_speed','left_hip_angle','right_hip_angle']},
  {key:'calves', label:'小腿三头肌', area:'小腿后侧', color:'#e8b676', basis:'踝角速度 0.45 + 踝线速度 0.35 + 髋中心速度 0.08', features:['left_ankle_angular_velocity','right_ankle_angular_velocity','left_ankle_speed','right_ankle_speed']},
  {key:'erector_spinae', label:'竖脊肌', area:'背部与腰部', color:'#77c6f7', basis:'躯干倾斜角速度 0.58 + 倾斜幅度 0.18 + 髋中心速度 0.12 + 动作强度 0.05', features:['torso_angular_velocity','torso_tilt_angle','hip_center_speed']},
  {key:'obliques', label:'腹斜肌', area:'腹部两侧', color:'#b1e688', basis:'肩线旋转速度 0.62 + 旋转角度 0.16 + 动作强度 0.10', features:['torso_rotation_velocity','torso_rotation_angle','motion_intensity']},
  {key:'deltoids', label:'三角肌', area:'肩部', color:'#8f9cff', basis:'肩角速度 0.52 + 肘角速度 0.12 + 双手距离/肩宽 0.12 + 腕速度 0.08', features:['left_shoulder_angular_velocity','right_shoulder_angular_velocity','left_elbow_angular_velocity','right_elbow_angular_velocity','hand_distance','shoulder_width','left_wrist_speed','right_wrist_speed']},
  {key:'forearms', label:'前臂肌群', area:'前臂', color:'#f0a5b8', basis:'腕速度 0.60 + 肘角速度 0.16 + 动作强度 0.08', features:['left_wrist_speed','right_wrist_speed','left_elbow_angular_velocity','right_elbow_angular_velocity','motion_intensity']},
])
export const QUALITY_THRESHOLDS = Object.freeze({
  minVisibility:.15, reliableVisibility:.45, reliableMean:.72,
  minReliableJoints:10, invalidJoints:7, minFps:20,
  boneRatioLow:.5, boneRatioHigh:1.8,
  isolatedAngularJump:300, isolatedAcceleration:5000,
})
export const CRITICAL_JOINTS=[11,12,13,14,15,16,23,24,25,26,27,28]
export const BONES=[[11,13],[13,15],[12,14],[14,16],[23,25],[25,27],[24,26],[26,28],[11,12],[23,24]]
const finite = x => typeof x==='number' && Number.isFinite(x)
const median = values => { const a=values.filter(finite).sort((x,y)=>x-y); return a.length?a[Math.floor(a.length/2)]:null }
const distance = (a,b) => Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2])
const validWorld = p => p && p.length>=4 && p.slice(0,3).every(finite) && finite(p[3]) && p[3]>=QUALITY_THRESHOLDS.minVisibility

function boneBaselines(worldFrames) {
  return BONES.map(([a,b])=>median((worldFrames||[]).map(frame=>{
    const x=frame?.[a],y=frame?.[b]
    return validWorld(x)&&validWorld(y)?distance(x,y):null
  })))
}

export function assessFrameQuality(row, poseFrame, worldFrame, metricsRow, fps, baselines, previousMetrics, nextMetrics, thresholds=QUALITY_THRESHOLDS) {
  const reasons=[]
  const partialMuscleData=MUSCLES.some(m=>!finite(row?.[m.key]))
  if(!finite(row?.frame)||!finite(row?.time_sec)||partialMuscleData) reasons.push('肌群逐帧数据缺失')
  if(!(fps>0)) reasons.push('帧率未知')
  else if(fps<thresholds.minFps) reasons.push(`采样帧率 ${fps} FPS，时间分辨率较低`)
  if(!Array.isArray(poseFrame)) reasons.push('姿态可见度不可用')
  if(!Array.isArray(worldFrame)) reasons.push('三维关键点不可用，骨长未评估')
  if(!metricsRow) reasons.push('运动学依据不可用')
  let good=0, missing=0, out=0, visibility=0, observed=0
  for(const index of CRITICAL_JOINTS) {
    const p=poseFrame?.[index], v=p?.[2]
    if(!p||!finite(v)||v<thresholds.minVisibility) {missing++;continue}
    observed++;visibility+=v
    if(v>=thresholds.reliableVisibility) good++
    if(!finite(p[0])||!finite(p[1])||p[0]<0||p[0]>1||p[1]<0||p[1]>1) out++
  }
  const meanVisibility=observed?visibility/observed:null
  if(missing) reasons.push(`${missing} 个主要关键点缺失或不可见`)
  if(observed-good) reasons.push(`${observed-good} 个主要关键点可见度偏低`)
  if(out) reasons.push(`${out} 个主要关键点出画`)
  if(observed && meanVisibility<thresholds.reliableMean) reasons.push(`平均可见度 ${meanVisibility.toFixed(2)}`)
  let abnormalBones=0
  if(Array.isArray(worldFrame)) BONES.forEach(([a,b],i)=>{
    const p=worldFrame[a],q=worldFrame[b],base=baselines?.[i]
    if(!validWorld(p)||!validWorld(q)||!(base>0)) return
    const ratio=distance(p,q)/base
    if(ratio<thresholds.boneRatioLow||ratio>thresholds.boneRatioHigh) abnormalBones++
  })
  if(abnormalBones) reasons.push(`${abnormalBones} 段三维骨长异常`)
  let spikes=0
  for(const key of ['left_knee_angular_velocity','right_knee_angular_velocity','left_elbow_angular_velocity','right_elbow_angular_velocity','torso_angular_velocity']) {
    const value=metricsRow?.[key],a=previousMetrics?.[key],b=nextMetrics?.[key]
    if([value,a,b].every(finite)&&Math.abs(value-(a+b)/2)>thresholds.isolatedAngularJump&&Math.abs(value)>Math.max(Math.abs(a),Math.abs(b))*1.5) spikes++
  }
  for(const key of ['left_knee_angular_acceleration','right_knee_angular_acceleration','left_elbow_angular_acceleration','right_elbow_angular_acceleration']) {
    const value=metricsRow?.[key],a=previousMetrics?.[key],b=nextMetrics?.[key]
    if([value,a,b].every(finite)&&Math.abs(value)>thresholds.isolatedAcceleration&&Math.abs(value)>Math.max(Math.abs(a),Math.abs(b))*1.5) spikes++
  }
  if(spikes) reasons.push(`${spikes} 处孤立角速度/角加速度尖峰`)
  const invalid=!finite(row?.frame)||!finite(row?.time_sec)||MUSCLES.every(m=>!finite(row?.[m.key]))||!(fps>0)||missing>=5||out>=3
  const caution=!invalid&&(partialMuscleData||!metricsRow||!Array.isArray(worldFrame)||missing>0||observed-good>0||out>0||good<thresholds.minReliableJoints||meanVisibility===null||meanVisibility<thresholds.reliableMean||abnormalBones>0||spikes>0||fps<thresholds.minFps)
  return {status:invalid?'invalid':caution?'caution':'reliable',reasons,good,missing,out,meanVisibility,abnormalBones,spikes}
}

export function buildMuscleAnalysis(rows,metrics,pose) {
  const fps=Number(pose?.fps)||0
  const metricByFrame=new Map((metrics?.rows||[]).map(row=>[row.frame_index,row]))
  const baselines=boneBaselines(pose?.worldFrames)
  const sorted=[...(rows||[])].sort((a,b)=>a.frame-b.frame)
  const qualities=sorted.map(row=>{
    const frame=row.frame,m=metricByFrame.get(frame)
    const quality=assessFrameQuality(row,pose?.frames?.[frame],pose?.worldFrames?.[frame],m,fps,baselines,metricByFrame.get(frame-1),metricByFrame.get(frame+1))
    const poseTime=pose?.timestamps?.[frame]
    if(finite(poseTime)&&fps>0&&Math.abs(poseTime-row.time_sec)>.5/fps) {
      quality.status='invalid'
      quality.reasons.push('姿态与肌群时间戳不一致')
    }
    return quality
  })
  return {rows:sorted,qualities,metricByFrame,fps,baselines,version:MUSCLE_V2_VERSION}
}

export function summarizeMuscle(rows,key,start=0,end=Infinity,qualities=[]) {
  const samples=rows.filter(r=>r.frame>=start&&r.frame<=end&&finite(r[key]))
  if(!samples.length) return {count:0,mean:null,peak:null,peakFrame:null,peakTime:null,peakQuality:null}
  const peak=samples.reduce((best,r)=>r[key]>best[key]?r:best,samples[0])
  const i=rows.indexOf(peak)
  return {count:samples.length,mean:samples.reduce((n,r)=>n+r[key],0)/samples.length,peak:peak[key],peakFrame:peak.frame,peakTime:peak.time_sec,peakQuality:qualities[i]?.status||'unknown'}
}

// Reference only: quantify what a three-frame median would change at the
// displayed peak. V1 values and its EMA output are never overwritten.
export function median3Peak(rows,key,start=0,end=Infinity) {
  const samples=rows.filter(r=>r.frame>=start&&r.frame<=end)
  const smoothed=samples.map((r,i)=>median([samples[i-1]?.[key],r[key],samples[i+1]?.[key]]))
  let best=-1
  smoothed.forEach((v,i)=>{if(finite(v)&&(best<0||v>smoothed[best]))best=i})
  return best<0?{value:null,frame:null,time:null}:{value:smoothed[best],frame:samples[best].frame,time:samples[best].time_sec}
}

// Median-of-three is used only to locate events. Displayed curves and statistics
// remain the exact persisted V1 values.
export function detectMusclePeaks(rows,qualities,key,fps,start=0,end=Infinity) {
  if(!(fps>0)) return []
  const filtered=rows.map((r,i)=>r.frame>=start&&r.frame<=end&&qualities[i]?.status!=='invalid'&&finite(r[key])?r[key]:null)
  const smooth=filtered.map((v,i)=>v===null?null:median([filtered[i-1],v,filtered[i+1]]))
  const window=Math.max(3,Math.round(.32*fps)), separation=Math.max(3,Math.round(.25*fps))
  const candidates=[]
  for(let i=1;i<smooth.length-1;i++) {
    const v=smooth[i]
    if(v===null||qualities[i]?.status!=='reliable'||smooth[i-1]===null||smooth[i+1]===null||v<smooth[i-1]||v<=smooth[i+1]||v<.18) continue
    const left=smooth.slice(Math.max(0,i-window),i).filter(finite)
    const right=smooth.slice(i+1,Math.min(smooth.length,i+window+1)).filter(finite)
    if(left.length<2||right.length<2) continue
    const prominence=v-Math.max(Math.min(...left),Math.min(...right))
    if(prominence<.055) continue
    if(filtered[i-1]<v-.18&&filtered[i+1]<v-.18) continue
    candidates.push({frame:rows[i].frame,time:rows[i].time_sec,key,value:rows[i][key],prominence,index:i})
  }
  const accepted=[]
  for(const p of candidates.sort((a,b)=>b.prominence-a.prominence||b.value-a.value)) {
    if(accepted.some(q=>Math.abs(q.frame-p.frame)<separation)) continue
    accepted.push(p)
  }
  const max=Math.max(...accepted.map(p=>p.value),0)
  return accepted.sort((a,b)=>a.frame-b.frame).map(p=>({...p,kind:p.value>=max*.85&&p.prominence>=.10?'major':'local'}))
}

export function intervalQuality(rows,qualities,start,end) {
  const selected=rows.map((r,i)=>r.frame>=start&&r.frame<=end?qualities[i]:null).filter(Boolean)
  if(!selected.length) return {status:'invalid',counts:{reliable:0,caution:0,invalid:0},reasons:['区间内无数据']}
  const counts={reliable:0,caution:0,invalid:0}
  selected.forEach(q=>counts[q.status]++)
  const ratio=counts.invalid/selected.length
  const status=ratio>=.25?'invalid':counts.caution+counts.invalid>=selected.length*.3?'caution':'reliable'
  const reasons=[...new Set(selected.flatMap(q=>q.reasons))].slice(0,4)
  return {status,counts,reasons}
}

export function activityIntervals(rows,qualities,selected,fps,start=0,end=Infinity) {
  if(!(fps>0)||!selected.length) return []
  const values=rows.map((r,i)=>r.frame>=start&&r.frame<=end&&qualities[i]?.status==='reliable'?selected.map(k=>r[k]).filter(finite):[])
  const envelope=values.map(v=>v.length?v.reduce((a,b)=>a+b,0)/v.length:null)
  const base=median(envelope),threshold=Math.max(.25,(base||0)+.08)
  const intervals=[]
  let begin=-1
  for(let i=0;i<=rows.length;i++) {
    const active=i<rows.length&&envelope[i]!==null&&envelope[i]>=threshold
    if(active&&begin<0) begin=i
    if(!active&&begin>=0) {
      if(i-begin>=Math.max(3,Math.round(.12*fps))) {
        let peak=begin
        for(let j=begin+1;j<i;j++) if(envelope[j]>envelope[peak]) peak=j
        intervals.push({start:rows[begin].frame,end:rows[i-1].frame,peak:rows[peak].frame,peakValue:envelope[peak]})
      }
      begin=-1
    }
  }
  return intervals
}
