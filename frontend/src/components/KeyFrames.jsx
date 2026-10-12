import { useEffect, useMemo, useRef, useState } from 'react'
import { fileUrl } from '../api/client'
import { sampleFrames } from '../lib/frameData'
export default function KeyFrames({task,result,pose,frameIndex=0,onSeek}) {
  const total = pose?.frames?.length || result?.video?.frame_count || 0
  const fps = pose?.fps || result?.video?.fps || 0
  const frames = useMemo(() => sampleFrames(total),[total])
  const refs = useRef([])
  const [error,setError] = useState(false)
  useEffect(() => {
    setError(false)
    if (!task?.id || !frames.length || !(fps > 0)) return
    const video = document.createElement('video')
    video.muted = true; video.playsInline = true; video.preload = 'auto'
    let cancelled = false, i = 0
    const draw = () => {
      if (cancelled || i >= frames.length) return
      const canvas = refs.current[i]
      if (canvas && video.videoWidth && video.videoHeight) {
        const ctx = canvas.getContext('2d')
        const scale = Math.min(canvas.width / video.videoWidth, canvas.height / video.videoHeight)
        const w = video.videoWidth * scale, h = video.videoHeight * scale
        ctx.fillStyle = '#080614'; ctx.fillRect(0,0,canvas.width,canvas.height)
        ctx.drawImage(video,(canvas.width-w)/2,(canvas.height-h)/2,w,h)
      }
      i++; next()
    }
    const next = () => {
      if (cancelled || i >= frames.length) return
      const t = Math.min(frames[i]/fps,Math.max(0,video.duration-.001))
      if (Math.abs(video.currentTime-t)<.0001 && video.readyState>=2) draw()
      else video.currentTime=t
    }
    const failed=()=>{if(!cancelled)setError(true)}
    video.addEventListener('loadeddata',next,{once:true})
    video.addEventListener('seeked',draw); video.addEventListener('error',failed)
    video.src=fileUrl(task.id,'source.mp4')
    return ()=>{
      cancelled=true
      video.removeEventListener('loadeddata',next);video.removeEventListener('seeked',draw);video.removeEventListener('error',failed)
      video.pause();video.removeAttribute('src');video.load()
    }
  },[task?.id,frames,fps])
  const closest=frames.reduce((best,f)=>Math.abs(f-frameIndex)<Math.abs(best-frameIndex)?f:best,frames[0])
  return <div className="keyframes">
    <div className="keyframes-heading"><strong>关键帧</strong><span className="panel-sub">Key Frames</span><span>均匀采样 · 点击定位</span></div>
    {frames.length?<div className="thumbnail-track">{frames.map((f,i)=><button key={f} className={'thumbnail '+(f===closest?'active':'')} aria-label={'跳转到帧 '+f} aria-pressed={f===closest} onClick={()=>onSeek?.(f)}>
      <canvas width="240" height="144" ref={(el)=>{refs.current[i]=el}}/><span>#{f}<small>{fps?(f/fps).toFixed(2)+'s':'—'}</small></span>
    </button>)}</div>:<div className="keyframes-empty">分析完成后，显示当前视频的真实帧缩略图</div>}
    {error&&<p role="alert" className="text-warn text-xs">缩略图加载失败，仍可使用时间轴定位。</p>}
  </div>
}

