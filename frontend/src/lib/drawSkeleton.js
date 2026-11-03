import { POSE_CONNECTIONS } from './poseSpec'
const MAJOR = new Set([11,12,13,14,15,16,23,24,25,26,27,28])
export function drawSkeleton(ctx, points, w, h, color = '#2dd4bf', angles = null) {
  ctx.clearRect(0, 0, w, h)
  if (!points?.length) return
  ctx.save()
  const visible = (i) => Number.isFinite(points[i]?.[0]) && Number.isFinite(points[i]?.[1]) && points[i]?.[2] >= .4
  const x = (i) => points[i][0] * w
  const y = (i) => points[i][1] * h
  const scale = Math.min(w, h)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = color
  ctx.lineWidth = Math.max(1.5, scale / 280)
  ctx.shadowColor = color
  ctx.shadowBlur = scale / 90
  ctx.beginPath()
  for (const [a, b] of POSE_CONNECTIONS) {
    if (!visible(a) || !visible(b)) continue
    ctx.moveTo(x(a), y(a)); ctx.lineTo(x(b), y(b))
  }
  ctx.stroke()
  for (let i = 0; i < points.length; i++) {
    if (!visible(i)) continue
    const r = Math.max(1.2, scale / (MAJOR.has(i) ? 145 : 260))
    ctx.fillStyle = MAJOR.has(i) ? '#cafff4' : color
    ctx.beginPath(); ctx.arc(x(i), y(i), r, 0, Math.PI * 2); ctx.fill()
    if (MAJOR.has(i)) {
      ctx.lineWidth = Math.max(1, scale / 700)
      ctx.beginPath(); ctx.arc(x(i), y(i), r * 1.8, 0, Math.PI * 2); ctx.stroke()
    }
  }
  ctx.shadowBlur = 0
  if (angles) {
    const size = Math.max(13, scale / 34)
    ctx.font = '600 ' + size + 'px monospace'
    ctx.textBaseline = 'middle'
    for (const [joint, key] of [[13,'left_elbow_angle'],[14,'right_elbow_angle'],[25,'left_knee_angle'],[26,'right_knee_angle']]) {
      if (!visible(joint) || !Number.isFinite(angles[key])) continue
      const label = angles[key].toFixed(1) + '°'
      const width = ctx.measureText(label).width + size * .8
      const px = Math.max(4, Math.min(w - width - 4, x(joint) + size * .65))
      const py = Math.max(size, Math.min(h - size, y(joint) - size))
      ctx.fillStyle = 'rgba(9,7,25,.85)'
      ctx.fillRect(px, py - size * .75, width, size * 1.5)
      ctx.fillStyle = '#99f6e4'
      ctx.fillText(label, px + size * .4, py)
    }
  }
  ctx.restore()
}

