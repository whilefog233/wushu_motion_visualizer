import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'

const chromePath = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const baseUrl = process.env.KUNGFU_TEST_URL || 'http://127.0.0.1:8000'
const analysisId = process.env.KUNGFU_ANALYSIS_ID || '20261009_182949_b583b9ef'
const outputDir = path.resolve('..', 'docs', 'ui-verification')
const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'kungfu-3d-chrome-'))
const port = 9333
fs.mkdirSync(outputDir, { recursive: true })

const chrome = spawn(chromePath, [
  '--headless=new', '--no-first-run', '--no-default-browser-check', '--hide-scrollbars',
  '--use-angle=swiftshader', `--remote-debugging-port=${port}`, `--user-data-dir=${profileDir}`,
  'about:blank',
], { stdio: 'ignore' })

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function json(url, options) {
  const response = await fetch(url, options)
  if (!response.ok) throw new Error(`${response.status} ${url}`)
  return response.json()
}

async function waitForDevtools() {
  for (let attempt = 0; attempt < 80; attempt++) {
    try { return await json(`http://127.0.0.1:${port}/json/version`) } catch { await delay(100) }
  }
  throw new Error('Chrome DevTools did not start')
}

function cdp(webSocketUrl) {
  const errors = []
  const socket = new WebSocket(webSocketUrl)
  let nextId = 1
  const pending = new Map()
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data)
    if(message.method==='Runtime.exceptionThrown') errors.push(message.params.exceptionDetails)
    if (!message.id || !pending.has(message.id)) return
    const { resolve, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(message.error.message))
    else resolve(message.result)
  }
  const ready = new Promise((resolve, reject) => {
    socket.onopen = resolve
    socket.onerror = reject
  })
  return {
    errors,
    ready,
    send(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = nextId++
        pending.set(id, { resolve, reject })
        socket.send(JSON.stringify({ id, method, params }))
      })
    },
    close() { socket.close() },
  }
}

async function main() {
  await waitForDevtools()
  const target = await json(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(`${baseUrl}/?id=${analysisId}`)}`, { method: 'PUT' })
  const client = cdp(target.webSocketDebuggerUrl)
  await client.ready
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  await client.send('Emulation.setDeviceMetricsOverride', { width: 1680, height: 1050, deviceScaleFactor: 1, mobile: false })

  const evaluate = async (expression, awaitPromise = false) => {
    const result = await client.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise })
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text)
    return result.result.value
  }
  const waitFor = async (expression, label, timeoutMs = 15000) => {
    const started = Date.now()
    while (Date.now() - started < timeoutMs) {
      if (await evaluate(`Boolean(${expression})`)) return
      await delay(100)
    }
    const diagnostics = await evaluate(`(() => ({body:document.body?.innerText?.slice(0,1200),canvases:document.querySelectorAll('canvas').length,video:document.querySelector('video')?.readyState,url:location.href}))()`)
    throw new Error(`Timed out waiting for ${label}: ${JSON.stringify(diagnostics)}`)
  }

  await waitFor(`document.querySelector('.skeleton3d-canvas canvas') && document.querySelector('video')?.readyState >= 2`, 'real video and WebGL canvas')
  await waitFor(`document.querySelector('.skeleton3d-wrap')?.dataset.assetStatus==='ready'`, 'validated SkinnedMesh', 30000)
  await evaluate(`document.querySelector('.video-panel').scrollIntoView({block:'start'})`)
  await delay(250)
  await evaluate(`(() => { const v=document.querySelector('video'); v.pause(); v.currentTime=355/30; return true })()`)
  await waitFor(`document.querySelector('.frame-overlay')?.textContent.includes('帧 #355 ') && document.querySelector('.s3d-frame')?.textContent.includes('帧 #355 ')`, 'frame 355 video/3D sync')

  const pageErrors = client.errors
  const state = await evaluate(`(() => ({
    overlay: document.querySelector('.frame-overlay')?.textContent,
    model: document.querySelector('.s3d-frame')?.textContent,
    quality: document.querySelector('.s3d-quality')?.textContent,
    views: [...document.querySelectorAll('.s3d-views button')].map(b=>b.textContent.trim()),
    canvas: (()=>{const c=document.querySelector('.skeleton3d-canvas canvas');return {width:c.width,height:c.height}})(),
    video: (()=>{const v=document.querySelector('video');return {width:v.videoWidth,height:v.videoHeight,time:v.currentTime,paused:v.paused}})(),
  }))()`)
  assert.match(state.overlay, /帧 #355/)
  assert.match(state.model, /帧 #355/)
  assert.deepEqual(state.views, ['正面', '左侧', '右侧', '背面', '自由', '重置'])
  assert(state.canvas.width > 300 && state.canvas.height > 300, `3D canvas too small: ${JSON.stringify(state)}`)
  assert(Math.abs(state.video.width / state.video.height - 720 / 1280) < 0.001, 'source and pose aspect ratios must match')

  const screenshot = async (name) => {
    const rect = await evaluate(`(() => { const r=document.querySelector('.skeleton3d-wrap').getBoundingClientRect(); return {x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height} })()`)
    const capture = await client.send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: true, clip: { ...rect, scale: 1 } })
    const bytes = Buffer.from(capture.data, 'base64')
    fs.writeFileSync(path.join(outputDir, name.replace('3d-', 'rig-')), bytes)
    return crypto.createHash('sha256').update(bytes).digest('hex')
  }

  const viewHashes = {}
  for (const [label, file] of [['正面', '3d-front-frame355.png'], ['左侧', '3d-left-frame355.png'], ['右侧', '3d-right-frame355.png'], ['背面', '3d-back-frame355.png']]) {
    await evaluate(`[...document.querySelectorAll('.s3d-views button')].find(b=>b.textContent.trim()==='${label}').click()`)
    await delay(500)
    viewHashes[label] = await screenshot(file)
  }
  assert.equal(new Set(Object.values(viewHashes)).size, 4, 'four camera views must render differently')

  const bodyMode = await evaluate(`(() => ({body:document.querySelector('.s3d-mode button[aria-pressed="true"]')?.textContent.trim(),label:document.querySelector('.s3d-frame')?.textContent}))()`)
  assert.equal(bodyMode.body, '科技线框')
  assert.match(bodyMode.label, /蒙皮人体/)
  const bodyHash = await screenshot('3d-body-frame355.png')
  await evaluate(`[...document.querySelectorAll('.s3d-mode button')].find(b=>b.textContent.trim()==='人体+骨架').click()`)
  await delay(350)
  const skeletonHash = await screenshot('3d-skeleton-frame355.png')
  assert.notEqual(bodyHash, skeletonHash, 'human and skeleton modes must be visually different')
  await evaluate(`[...document.querySelectorAll('.s3d-mode button')].find(b=>b.textContent.trim()==='人体实体').click()`)
  await delay(300)
  await screenshot('3d-solid-frame355.png')
  await evaluate(`[...document.querySelectorAll('.s3d-mode button')].find(b=>b.textContent.trim()==='科技线框').click()`)
  await delay(250)

  await evaluate(`[...document.querySelectorAll('.s3d-views button')].find(b=>b.textContent.trim()==='自由').click()`)
  const canvasRect = await evaluate(`(() => { const r=document.querySelector('.skeleton3d-canvas canvas').getBoundingClientRect(); return {x:r.left,y:r.top,width:r.width,height:r.height} })()`)
  const beforeFree = await screenshot('3d-free-before-drag-frame355.png')
  const x = canvasRect.x + canvasRect.width * 0.55, y = canvasRect.y + canvasRect.height * 0.5
  await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1 })
  await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: x + 110, y: y - 35, button: 'left', buttons: 1 })
  await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: x + 110, y: y - 35, button: 'left', buttons: 0, clickCount: 1 })
  await delay(500)
  const afterFree = await screenshot('3d-free-after-drag-frame355.png')
  assert.notEqual(beforeFree, afterFree, 'free orbit drag must change the rendered view')

  await evaluate(`document.querySelector('button[aria-label="下一帧"]').click()`)
  await delay(500)
  const afterNext = await evaluate(`(() => ({time:document.querySelector('video').currentTime,video:document.querySelector('.frame-overlay')?.textContent,model:document.querySelector('.s3d-frame')?.textContent}))()`)
  assert(afterNext.video?.includes('帧 #356 ') && afterNext.model?.includes('帧 #356 '), `next-frame sync failed: ${JSON.stringify(afterNext)}`)
  await evaluate(`document.querySelector('button[aria-label="上一帧"]').click()`)
  await delay(500)
  const afterPrevious = await evaluate(`(() => ({time:document.querySelector('video').currentTime,video:document.querySelector('.frame-overlay')?.textContent,model:document.querySelector('.s3d-frame')?.textContent}))()`)
  assert(afterPrevious.video?.includes('帧 #355 ') && afterPrevious.model?.includes('帧 #355 '), `previous-frame sync failed: ${JSON.stringify(afterPrevious)}`)

  await evaluate(`document.querySelector('button[aria-label="播放"]').click()`)
  await waitFor(`document.querySelector('button[aria-label="暂停"]')`, 'play state')
  await delay(650)
  await evaluate(`document.querySelector('button[aria-label="暂停"]').click()`)
  const syncedAfterPlay = await evaluate(`(() => { const a=document.querySelector('.frame-overlay').textContent.match(/#(\\d+)/)[1]; const b=document.querySelector('.s3d-frame').textContent.match(/#(\\d+)/)[1]; return {video:Number(a),model:Number(b)} })()`)
  assert.equal(syncedAfterPlay.video, syncedAfterPlay.model)
  assert(syncedAfterPlay.video > 355)

  const keyframe = await evaluate(`(() => { const thumb=document.querySelectorAll('.thumbnail')[3]; if(!thumb)return null; const label=thumb.getAttribute('aria-label'); thumb.click(); return label })()`)
  assert(keyframe, 'a real keyframe thumbnail must exist')
  await delay(500)
  const syncedAfterKeyframe = await evaluate(`(() => { const a=document.querySelector('.frame-overlay').textContent.match(/#(\\d+)/)[1]; const b=document.querySelector('.s3d-frame').textContent.match(/#(\\d+)/)[1]; return {video:Number(a),model:Number(b),time:document.querySelector('video').currentTime} })()`)
  assert.equal(syncedAfterKeyframe.video, syncedAfterKeyframe.model)
  assert.equal(syncedAfterKeyframe.video, Number(keyframe.match(/\d+/)[0]), `keyframe jump missed target: ${JSON.stringify(syncedAfterKeyframe)}`)

  await screenshot('3d-final-real-video.png')
  await evaluate(`[...document.querySelectorAll('.s3d-views button')].find(b=>b.textContent.trim()==='正面').click()`)
  for(const calibration of ['rest','bend','motion']) {
    await evaluate(`(() => { const e=document.querySelector('select[aria-label="模型校验"]');e.value='${calibration}';e.dispatchEvent(new Event('change',{bubbles:true})) })()`)
    await delay(600)
    await screenshot(`3d-calibration-${calibration}.png`)
  }
  for(const frame of [0,355,712]) {
    await evaluate(`document.querySelector('video').currentTime=(${frame}+.5)/30`)
    await waitFor(`document.querySelector('.s3d-frame').textContent.includes('帧 #${frame} ')`, `real frame ${frame}`)
    await delay(350)
    const capture = await client.send('Page.captureScreenshot', {format:'png',captureBeyondViewport:false})
    fs.writeFileSync(path.join(outputDir,`rig-video-frame${frame}.png`),Buffer.from(capture.data,'base64'))
  }
  await evaluate(`[...document.querySelectorAll('[role="tab"]')].find(b=>b.textContent.trim()==='肌肉分析').click()`)
  await waitFor(`document.querySelector('.muscle-v2')?.dataset.version==='2.0.0'`, 'muscle V2 panel')
  await evaluate(`document.querySelector('video').currentTime=(355+.5)/30`)
  await waitFor(`document.querySelector('.muscle-quality')?.textContent.includes('#355')`, 'muscle cursor frame 355')
  await evaluate(`document.querySelector('.analysis-grid').scrollIntoView({block:'start'})`)
  await delay(400)
  const muscleState=await evaluate(`(async()=>{const csv=await(await fetch('/api/v1/analyses/20261009_182949_b583b9ef/files/muscle_metrics.csv')).text();const line=csv.trim().split(/\\r?\\n/)[356].split(',');return {buttons:document.querySelectorAll('.muscle-choice').length,frame:document.querySelector('.muscle-quality')?.textContent,qualityReason:[...document.querySelectorAll('.muscle-inspector-block')].at(-1)?.querySelector('p')?.textContent,deltoidRaw:Number(line[8]),deltoidUi:document.querySelectorAll('.muscle-choice-values b')[6]?.textContent,model:document.querySelector('.s3d-frame')?.textContent,mean:document.querySelectorAll('.muscle-stat-row strong')[1]?.textContent,peak:document.querySelectorAll('.muscle-stat-row strong')[2]?.textContent,events:document.querySelectorAll('.muscle-event').length}})()`,true)
  assert.equal(muscleState.buttons,8)
  assert.match(muscleState.frame,/(可靠|需谨慎).*355/)
  assert(Math.abs(muscleState.deltoidRaw-Number(muscleState.deltoidUi))<.005,JSON.stringify(muscleState))
  assert.match(muscleState.model,/帧 #355/)
  assert(Math.abs(Number(muscleState.mean)-.5910635339799315)<.005)
  assert(Math.abs(Number(muscleState.peak)-.871114606934577)<.005)
  assert(muscleState.events>0)
  const muscleShot=await client.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
  fs.writeFileSync(path.join(outputDir,'muscle-v2-frame355-real-video.png'),Buffer.from(muscleShot.data,'base64'))
  const peakTarget=await evaluate(`(() => {const b=document.querySelector('.muscle-event');const n=Number(b.querySelector('strong small').textContent.match(/\\d+/)[0]);b.click();return n})()`)
  await waitFor(`document.querySelector('.frame-overlay')?.textContent.includes('帧 #${peakTarget} ')&&document.querySelector('.muscle-quality')?.textContent.includes('#${peakTarget}')&&document.querySelector('.s3d-frame')?.textContent.includes('帧 #${peakTarget} ')`,'peak jump synced')
  const afterPeak=await evaluate(`(() => ({video:document.querySelector('.frame-overlay')?.textContent,muscle:document.querySelector('.muscle-quality')?.textContent,model:document.querySelector('.s3d-frame')?.textContent}))()`)
  const chartRect=await evaluate(`(() => {const r=document.querySelector('.muscle-chart svg').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}})()`)
  const chartY=chartRect.y+chartRect.height*.5
  await client.send('Input.dispatchMouseEvent',{type:'mousePressed',x:chartRect.x+chartRect.width*.35,y:chartY,button:'left',buttons:1,clickCount:1})
  await client.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:chartRect.x+chartRect.width*.55,y:chartY,button:'left',buttons:1})
  await client.send('Input.dispatchMouseEvent',{type:'mouseReleased',x:chartRect.x+chartRect.width*.55,y:chartY,button:'left',buttons:0,clickCount:1})
  assert.match(await evaluate(`document.querySelector('.muscle-scope').textContent`),/选中区间/)
  const clickX=chartRect.x+chartRect.width*.65
  await client.send('Input.dispatchMouseEvent',{type:'mousePressed',x:clickX,y:chartY,button:'left',buttons:1,clickCount:1})
  await client.send('Input.dispatchMouseEvent',{type:'mouseReleased',x:clickX,y:chartY,button:'left',buttons:0,clickCount:1})
  await waitFor(`document.querySelector('.frame-overlay')?.textContent.includes('帧 #463 ')`,'curve click seeks frame 463')
  const afterChart=await evaluate(`(() => ({video:document.querySelector('.frame-overlay')?.textContent,muscle:document.querySelector('.muscle-quality')?.textContent,model:document.querySelector('.s3d-frame')?.textContent}))()`)
  assert.match(afterChart.muscle,/#463/)
  assert.match(afterChart.model,/帧 #463/)
  await evaluate(`document.querySelector('.muscle-chart-actions button').click()`)
  await evaluate(`document.querySelector('input[aria-label="视频时间轴"]').scrollIntoView({block:'center'})`)
  await delay(150)
  const sliderRect=await evaluate(`(() => {const e=document.querySelector('input[aria-label="视频时间轴"]'),r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,ratio:Number(e.value)/Number(e.max)}})()`)
  const sx=sliderRect.x+sliderRect.width*.25,sy=sliderRect.y+sliderRect.height*.5
  await client.send('Input.dispatchMouseEvent',{type:'mousePressed',x:sliderRect.x+sliderRect.width*sliderRect.ratio,y:sy,button:'left',buttons:1,clickCount:1})
  await client.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:sx,y:sy,button:'left',buttons:1})
  await client.send('Input.dispatchMouseEvent',{type:'mouseReleased',x:sx,y:sy,button:'left',buttons:0,clickCount:1})
  await waitFor(`Math.abs(Number(document.querySelector('.frame-overlay')?.textContent.match(/#(\\d+)/)?.[1])-463)>100`,'timeline actually moved')
  await waitFor(`document.querySelector('.muscle-quality')?.textContent.match(/#(\\d+)/)?.[1]===document.querySelector('.frame-overlay')?.textContent.match(/#(\\d+)/)?.[1]`,'timeline scrub synced')
  const afterScrub=await evaluate(`(() => ({video:document.querySelector('.frame-overlay')?.textContent,muscle:document.querySelector('.muscle-quality')?.textContent,model:document.querySelector('.s3d-frame')?.textContent}))()`)
  assert.equal(afterScrub.video.match(/#(\d+)/)[1],afterScrub.model.match(/#(\d+)/)[1])
  for(const label of ['姿态分析','发力链诊断','技术对比','AI 建议']) {
    await evaluate(`[...document.querySelectorAll('[role="tab"]')].find(b=>b.textContent.trim()==='${label}').click()`)
    assert((await evaluate(`document.querySelector('.analysis-tab-content')?.textContent.length`))>30,label+' tab is empty')
  }
  assert(await evaluate(`Boolean(document.querySelector('.export-panel'))`),'export panel missing')
  assert.equal(pageErrors.length,0,JSON.stringify(pageErrors))
  console.log(JSON.stringify({
    analysisId, frame355: state, viewHashes, freeOrbitChanged: beforeFree !== afterFree,
    syncedAfterPlay, syncedAfterKeyframe, keyframe, muscleState, afterPeak, afterChart, afterScrub, pageErrors, outputDir,
  }, null, 2))
  client.close()
}

try {
  await main()
} finally {
  chrome.kill()
  for (let attempt = 0; attempt < 12; attempt++) {
    await delay(250)
    try {
      fs.rmSync(profileDir, { recursive: true, force: true })
      break
    } catch (error) {
      if (error.code !== 'EBUSY' || attempt === 11) throw error
    }
  }
}
