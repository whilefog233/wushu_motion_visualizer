export const finite = (v) => typeof v === 'number' && Number.isFinite(v)
export const formatValue = (v, d = 1) => finite(v) ? v.toFixed(d) : '—'
export function rowAt(metrics, index) {
  return metrics?.rows?.find((r) => r.frame_index === index) || {}
}
export function frameAt(time, fps, count) {
  return fps > 0 && count > 0 ? Math.max(0, Math.min(count - 1, Math.floor(time * fps + .0001))) : 0
}
export function sampleFrames(count, n = 7) {
  const size = Math.min(n, Math.max(0, count))
  return Array.from({ length: size }, (_, i) => Math.round(i * (count - 1) / Math.max(1, size - 1)))
}

