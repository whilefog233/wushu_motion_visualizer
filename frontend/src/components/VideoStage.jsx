import { useEffect, useRef, useState } from 'react'
import { fileUrl } from '../api/client'
import { drawSkeleton } from '../lib/drawSkeleton'
import { frameAt, rowAt } from '../lib/frameData'
import { IconPlay, IconVolume, IconFullscreen, IconTarget } from './Icons'
import KeyFrames from './KeyFrames'

const STAGES = { UPLOADING:'正在上传视频', QUEUED:'排队等待中', PREPARING:'正在准备视频', EXTRACTING_POSE:'正在提取人物姿态', CALCULATING_METRICS:'正在计算动作指标', ANALYZING_MUSCLE:'正在分析肌肉参与', ANALYZING_POWER_CHAIN:'正在分析发力链', SAVING_RESULTS:'正在保存结果' }
const clock = (t) => Math.floor((t || 0) / 60).toString().padStart(2,'0') + ':' + Math.floor((t || 0) % 60).toString().padStart(2,'0')

function Player({ src, pose, metrics, result, onFrame, seekFrame }) {
  const videoRef = useRef(null), canvasRef = useRef(null), stageRef = useRef(null)
  const [showSkel, setShowSkel] = useState(true)
  const [showAngles, setShowAngles] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0), [duration, setDuration] = useState(0)
  const [rate, setRate] = useState(1), [muted, setMuted] = useState(false)
  const [error, setError] = useState('')
  const fps = pose?.fps || result?.video?.fps || 0
  const count = pose?.frames?.length || result?.video?.frame_count || 0
  const frame = frameAt(time, fps, count)

  useEffect(() => {
    const video = videoRef.current
    if (!video || !seekFrame || !(fps > 0)) return
    const seek = () => { video.currentTime = Math.max(0, Math.min(seekFrame.frame / fps, Number.isFinite(video.duration) ? video.duration : Infinity)) }
    if (video.readyState >= 1) seek()
    else video.addEventListener('loadedmetadata', seek, { once:true })
    return () => video.removeEventListener('loadedmetadata', seek)
  }, [seekFrame, fps])

  useEffect(() => {
    const video = videoRef.current, canvas = canvasRef.current
    if (!video) return
    let handle, previous = -1
    const paint = (t = video.currentTime) => {
      const idx = frameAt(t, fps, count)
      setTime(t)
      if (idx !== previous) { previous = idx; onFrame?.(idx) }
      if (canvas) {
        const ctx = canvas.getContext('2d')
        if (showSkel && pose?.frames?.length) drawSkeleton(ctx, pose.frames[idx], canvas.width, canvas.height, '#2dd4bf', showAngles ? rowAt(metrics, idx) : null)
        else ctx.clearRect(0,0,canvas.width,canvas.height)
      }
    }
    const frameCallback = typeof video.requestVideoFrameCallback === 'function'
    const tick = (_, info) => {
      paint(info?.mediaTime ?? video.currentTime)
      handle = frameCallback ? video.requestVideoFrameCallback(tick) : requestAnimationFrame(tick)
    }
    const sync = () => paint()
    video.addEventListener('seeked',sync); video.addEventListener('loadeddata',sync)
    paint()
    handle = frameCallback ? video.requestVideoFrameCallback(tick) : requestAnimationFrame(tick)
    return () => {
      if (frameCallback) video.cancelVideoFrameCallback(handle)
      else cancelAnimationFrame(handle)
      video.removeEventListener('seeked',sync); video.removeEventListener('loadeddata',sync)
    }
  }, [pose,metrics,fps,count,showSkel,showAngles,onFrame])

  const togglePlay = async () => {
    const v = videoRef.current
    if (v.paused) { try { await v.play(); setError('') } catch { setError('视频暂时无法播放，请检查文件或浏览器编码支持。') } }
    else v.pause()
  }
  const seek = (t) => { videoRef.current.currentTime = Math.max(0,Math.min(duration,t)) }
  const fullscreen = async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await stageRef.current.requestFullscreen() }
    catch { setError('当前浏览器无法进入全屏。') }
  }
  return <div className="player" ref={stageRef}>
    <div className="video-viewport">
      <video ref={videoRef} src={src} playsInline preload="metadata" onClick={togglePlay}
        onLoadedMetadata={(e) => setDuration(Number.isFinite(e.currentTarget.duration) ? e.currentTarget.duration : 0)}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
        onError={() => setError('无法加载视频，请确认源文件存在且浏览器支持该编码。')} />
      {pose?.width > 0 && pose?.height > 0 && <canvas ref={canvasRef} width={pose.width} height={pose.height} />}
      <div className="frame-overlay"><span className="live-dot" />{fps ? '帧 #' + frame + ' · ' + time.toFixed(2) + 's · ' + fps.toFixed(2) + ' FPS' : '原始视频预览'}</div>
      <div className="overlay-actions">
        <button disabled={!pose?.frames?.length} aria-pressed={showSkel} onClick={() => setShowSkel(!showSkel)}>◎ 骨架：{showSkel ? '开' : '关'}</button>
        <button disabled={!pose?.frames?.length || !metrics?.rows?.length || !showSkel} aria-pressed={showAngles} onClick={() => setShowAngles(!showAngles)}>∠ 角度：{showAngles ? '开' : '关'}</button>
      </div>
      {result && !pose?.frames?.length && <div className="video-notice">骨架数据不可用 · 原始视频仍可播放</div>}
      {error && <div className="video-notice" role="alert">{error}</div>}
    </div>
    <div className="player-controls">
      <button aria-label={playing ? '暂停' : '播放'} onClick={togglePlay}>{playing ? <span className="pause-icon">Ⅱ</span> : <IconPlay />}</button>
      <input aria-label="视频时间轴" type="range" min="0" max={duration || 1} step="0.001" value={Math.min(time,duration)} disabled={!duration} onChange={(e) => seek(Number(e.target.value))} style={{'--progress':(duration ? time / duration * 100 : 0) + '%'}} />
      <span className="player-time">{clock(time)} <span>/ {clock(duration)}</span></span>
      <button aria-label="上一帧" disabled={!fps} onClick={() => seek((frame - 1) / fps)}>‹</button>
      <button aria-label="下一帧" disabled={!fps} onClick={() => seek((frame + 1) / fps)}>›</button>
      <select aria-label="播放速度" value={rate} onChange={(e) => { const v = Number(e.target.value); setRate(v); videoRef.current.playbackRate = v }}>
        {[.25,.5,1,1.5,2].map((v) => <option key={v} value={v}>{v}×</option>)}
      </select>
      <button aria-label={muted ? '取消静音' : '静音'} aria-pressed={muted} onClick={() => { videoRef.current.muted = !muted; setMuted(!muted) }}><IconVolume />{muted && <span className="mute-mark">×</span>}</button>
      <button aria-label="全屏" onClick={fullscreen}><IconFullscreen /></button>
    </div>
  </div>
}

export default function VideoStage({ file, task, result, pose, metrics, onFrame, seekFrame, frameIndex, onSeek }) {
  const [localUrl,setLocalUrl] = useState(null)
  useEffect(() => {
    if (!file) { setLocalUrl(null); return }
    const url = URL.createObjectURL(file); setLocalUrl(url)
    return () => URL.revokeObjectURL(url)
  },[file])
  const done = result && task?.status === 'COMPLETED'
  const running = task?.status === 'RUNNING' || task?.status === 'UPLOADING'
  const src = done ? fileUrl(task.id,'source.mp4') : localUrl
  return <section className="glass video-panel">
    <div className="section-heading"><span className="heading-icon"><IconTarget /></span><h2>分析结果</h2><span className="panel-sub">Analysis Result</span><span className="section-status">{done ? '分析已完成' : file ? '视频已就绪' : '等待上传'}</span></div>
    <div className="video-content">
      {src ? <Player key={src} src={src} pose={done ? pose : null} metrics={done ? metrics : null} result={done ? result : null} onFrame={onFrame} seekFrame={seekFrame} /> :
        <div className="video-empty"><div className="empty-target"><IconPlay /></div><h3>逐帧看见动作，找到进步的方向</h3><p>上传训练视频，查看姿态与发力链分析</p><span>原始比例 · 真实姿态 · 同步回放</span></div>}
      {running && <div className="analysis-overlay" role="status"><span className="loading-ring" /><strong>{task.status === 'UPLOADING' ? '正在上传 ' + Math.round((task.uploadPct || 0) * 100) + '%' : STAGES[task.stage] || '分析中'}</strong><p>完成后可回放视频并查看逐帧数据</p></div>}
    </div>
    <KeyFrames task={done ? task : null} result={done ? result : null} pose={done ? pose : null} frameIndex={frameIndex} onSeek={onSeek} />
  </section>
}

