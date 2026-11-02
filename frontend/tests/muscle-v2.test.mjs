import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {JOINT_NAMES} from '../src/lib/poseSpec.js'
import {frameAt} from '../src/lib/frameData.js'
import {MUSCLES,assessFrameQuality,buildMuscleAnalysis,detectMusclePeaks,intervalQuality,median3Peak,summarizeMuscle} from '../src/lib/muscleV2.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const analysisDir=path.join(root,'data/analyses/20261009_182949_b583b9ef')
const csvPath=path.join(analysisDir,'muscle_metrics.csv')
const sample=fs.existsSync(csvPath)
const values=(v=.5)=>Object.fromEntries(MUSCLES.map(m=>[m.key,v]))

test('eight V1 proxies keep their names',()=>{
  assert.deepEqual(MUSCLES.map(m=>m.key),['quadriceps','hamstrings','glutes','calves','erector_spinae','obliques','deltoids','forearms'])
})

test('quality detects visibility, missing points, out-of-frame, low FPS and spikes',()=>{
  const row={frame:3,time_sec:.1,...values()}
  const pose=Array.from({length:33},()=>[.5,.5,1])
  const world=Array.from({length:33},(_,i)=>[i*.05,0,0,1])
  const base=Array(10).fill(.1)
  assert.equal(assessFrameQuality(row,pose,world,{},30,base).status,'reliable')
  const low=pose.map(p=>[...p]);low[11][2]=.2
  assert.equal(assessFrameQuality(row,low,world,{},30,base).status,'caution')
  const missing=pose.map(p=>[...p]);[11,12,13,14,15].forEach(i=>{missing[i][2]=0})
  assert.equal(assessFrameQuality(row,missing,world,{},30,base).status,'invalid')
  const outside=pose.map(p=>[...p]);outside[11][0]=1.2
  assert.equal(assessFrameQuality(row,outside,world,{},30,base).status,'caution')
  assert.equal(assessFrameQuality(row,pose,world,{},15,base).status,'caution')
  assert.equal(assessFrameQuality(row,pose,world,{},0,base).status,'invalid')
  const spike=assessFrameQuality(row,pose,world,{left_elbow_angular_velocity:900,left_elbow_angular_acceleration:8000},30,base,{left_elbow_angular_velocity:20,left_elbow_angular_acceleration:10},{left_elbow_angular_velocity:25,left_elbow_angular_acceleration:15})
  assert.equal(spike.status,'caution')
  assert(spike.spikes>0)
  world[13]=[4,0,0,1]
  assert(assessFrameQuality(row,pose,world,{},30,base).abnormalBones>0)
})

test('peak detector excludes isolated impulses and invalid samples',()=>{
  const sequence=[.05,.06,.07,.92,.07,.08,.20,.40,.55,.48,.30,.12,.06]
  const rows=sequence.map((v,i)=>({frame:i,time_sec:i/30,...values(v)}))
  const q=rows.map(()=>({status:'reliable',reasons:[]}))
  const peaks=detectMusclePeaks(rows,q,'deltoids',30)
  assert(peaks.some(p=>p.frame>=7&&p.frame<=9))
  assert(!peaks.some(p=>p.frame===3))
  assert(median3Peak(rows,'deltoids').value<.92)
  q[8].status='invalid'
  assert(!detectMusclePeaks(rows,q,'deltoids',30).some(p=>p.frame===8))
  assert.equal(intervalQuality(rows,q,7,9).counts.invalid,1)
  assert.equal(frameAt((8+.5)/30,30,13),8)
})

test('short clips and absent values do not invent events',()=>{
  const rows=[{frame:0,time_sec:0,...values(null)},{frame:1,time_sec:.033,...values(.2)}]
  const q=rows.map(()=>({status:'invalid',reasons:['missing']}))
  assert.equal(detectMusclePeaks(rows,q,'forearms',30).length,0)
  assert.equal(summarizeMuscle(rows,'forearms').count,1)
  assert.equal(intervalQuality(rows,q,0,1).status,'invalid')
})

test('real 713-frame sample matches persisted V1 summary exactly', {skip:!sample},()=>{
  const [header,...lines]=fs.readFileSync(csvPath,'utf8').replace(/^\uFEFF/,'').trim().split(/\r?\n/)
  const names=header.split(',')
  const numeric=new Set(['frame','time_sec',...MUSCLES.map(m=>m.key)])
  const rows=lines.map(line=>{const cells=line.split(',');return Object.fromEntries(names.map((n,i)=>[n,numeric.has(n)?Number(cells[i]):cells[i]]))})
  const stored=JSON.parse(fs.readFileSync(path.join(analysisDir,'muscle.json'),'utf8')).summary
  const raw=JSON.parse(fs.readFileSync(path.join(analysisDir,'pose.json'),'utf8'))
  const pose={fps:raw.fps,timestamps:raw.frames.map(f=>f.timestamp_sec),frames:raw.frames.map(f=>JOINT_NAMES.map(name=>{const p=f.landmarks?.[name];return p?[p.x,p.y,p.visibility??0]:[0,0,0]})),worldFrames:raw.frames.map(f=>JOINT_NAMES.map(name=>{const p=f.world_landmarks?.[name];return p?[p.x,p.y,p.z,p.visibility??f.visibility?.[name]??0]:[0,0,0,0]}))}
  const [metricsHeader,...metricsLines]=fs.readFileSync(path.join(analysisDir,'metrics.csv'),'utf8').trim().split(/\r?\n/)
  const metricNames=metricsHeader.split(',').map(s=>s.trim())
  const metrics={rows:metricsLines.map(line=>{const cells=line.split(',');return Object.fromEntries(metricNames.map((n,i)=>[n,cells[i]===''?null:Number(cells[i])]))})}
  const analysis=buildMuscleAnalysis(rows,metrics,pose)
  assert.equal(analysis.rows.length,713)
  assert.equal(analysis.rows[355].frame,355)
  assert(Math.abs(analysis.rows[355].time_sec-355/30)<1e-9)
  for(const m of MUSCLES) {
    const stat=summarizeMuscle(rows,m.key,0,712,analysis.qualities)
    const expected=stored.muscle_statistics.find(s=>s.muscle===m.key)
    assert(Math.abs(stat.mean-expected.mean)<1e-10,m.key+' mean')
    assert(Math.abs(stat.peak-expected.max)<1e-10,m.key+' peak')
    assert.equal(rows[stat.peakFrame].time_sec,stat.peakTime)
  }
  assert(analysis.qualities.some(q=>q.status==='reliable'))
  assert(analysis.qualities.some(q=>q.status!=='reliable'))
  assert(detectMusclePeaks(rows,analysis.qualities,'deltoids',30).every(p=>analysis.qualities[p.index].status==='reliable'))
  const shifted={...pose,timestamps:[...pose.timestamps]};shifted.timestamps[355]+=.1
  assert.equal(buildMuscleAnalysis([rows[355]],metrics,shifted).qualities[0].status,'invalid')
  console.log(JSON.stringify({qualityCounts:analysis.qualities.reduce((a,q)=>(a[q.status]++,a),{reliable:0,caution:0,invalid:0}),frame355:analysis.qualities[355],deltoids:summarizeMuscle(rows,'deltoids',0,712,analysis.qualities),forearms:summarizeMuscle(rows,'forearms',0,712,analysis.qualities),median3:{deltoids:median3Peak(rows,'deltoids'),forearms:median3Peak(rows,'forearms')},detected:{deltoids:detectMusclePeaks(rows,analysis.qualities,'deltoids',30).length,forearms:detectMusclePeaks(rows,analysis.qualities,'forearms',30).length}},null,2))
})
