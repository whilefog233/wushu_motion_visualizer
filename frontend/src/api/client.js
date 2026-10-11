// 前端 API 客户端：同源访问，不带 API Key（服务端对同源页面放行）

import { JOINT_NAMES } from '../lib/poseSpec'

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

// 上传视频，创建分析任务（XHR 以便返回上传进度），返回 { analysis_id, status, stage }
export function uploadVideo(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/v1/analyses')
    xhr.responseType = 'json'
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response)
      else {
        const msg = xhr.response?.detail || `上传失败 (${xhr.status})`
        reject(new Error(msg))
      }
    }
    xhr.onerror = () => reject(new Error('网络错误，上传失败'))
    const fd = new FormData()
    fd.append('video', file)
    xhr.send(fd)
  })
}

export const getStatus = (id) =>
  fetch(`/api/v1/analyses/${id}`).then(handle)

// 列出全部分析任务（历史页）
export const listAnalyses = () =>
  fetch('/api/v1/analyses').then(handle)

export const getResult = (id) =>
  fetch(`/api/v1/analyses/${id}/result`).then(handle)

// 拉取 metrics.csv 并解析为 { columns, rows }
export async function getMetrics(id) {
  const res = await fetch(`/api/v1/analyses/${id}/files/metrics.csv`)
  if (!res.ok) throw new Error('metrics.csv 不可用')
  const text = await res.text()
  const lines = text.trim().split(/\r?\n/)
  const columns = lines[0].split(',').map((s) => s.trim())
  const rows = lines.slice(1).map((line) => {
    const cells = line.split(',')
    const obj = {}
    columns.forEach((c, i) => {
      const v = cells[i]?.trim()
      obj[c] = v === '' || v == null ? null : Number(v)
    })
    return obj
  })
  return { columns, rows }
}

export const fileUrl = (id, name) =>
  `/api/v1/analyses/${id}/files/${encodeURIComponent(name)}`

// 拉取 pose.json 并转换为紧凑骨架数据（每帧 33 点 [x,y,visibility]）
export async function getPose(id) {
  const res = await fetch(`/api/v1/analyses/${id}/files/pose.json`)
  if (!res.ok) throw new Error('pose.json 不可用')
  const data = await res.json()
  const frames = (data.frames || []).map((f) =>
    JOINT_NAMES.map((name) => {
      const p = f.landmarks?.[name]
      return p ? [p.x, p.y, p.visibility ?? 1] : [0, 0, 0]
    }),
  )
  return {
    fps: data.fps,
    frame_count: data.frame_count,
    width: data.width,
    height: data.height,
    duration: data.duration,
    frames,
  }
}

export async function checkHealth() {
  try {
    const r = await fetch('/health')
    return r.ok ? r.json() : null
  } catch {
    return null
  }
}
