import { JOINT_NAMES } from './poseSpec.js'

export const MIN_POINT_CONFIDENCE = 0.15
export const RELIABLE_POINT_CONFIDENCE = 0.45

// MediaPipe world 坐标：x 向图像右侧，y 向下，z 越小越靠近相机。
// Three.js 场景统一为：x 向右，y 向上，z 朝向观察者。
export function toScenePoint(point) {
  if (!isFinitePoint(point)) return null
  return [point[0], -point[1], -point[2]]
}

export function isFinitePoint(point) {
  return Array.isArray(point)
    && Number.isFinite(point[0])
    && Number.isFinite(point[1])
    && Number.isFinite(point[2])
}

export function pointConfidence(point) {
  return isFinitePoint(point) && Number.isFinite(point[3])
    ? Math.max(0, Math.min(1, point[3]))
    : 0
}

const VIRTUAL_POINTS = new Set(['neck', 'pelvis'])

// 四肢和躯干严格沿用 MediaPipe 33 点左右索引；neck / pelvis 仅为左右点
// 的中点，用于把头部和脊柱组织成可读的人体，不替换任何推理结果。
export const SKELETON_BONES = Object.freeze([
  { a: 11, b: 12, region: 'shoulders', major: true },
  { a: 11, b: 23, region: 'torso', major: true },
  { a: 12, b: 24, region: 'torso', major: true },
  { a: 23, b: 24, region: 'pelvis', major: true },
  { a: 'neck', b: 'pelvis', region: 'spine', major: true },
  { a: 'neck', b: 0, region: 'head', major: true },
  { a: 'neck', b: 7, region: 'head' },
  { a: 'neck', b: 8, region: 'head' },
  { a: 11, b: 13, region: 'left-arm', major: true },
  { a: 13, b: 15, region: 'left-arm', major: true },
  { a: 12, b: 14, region: 'right-arm', major: true },
  { a: 14, b: 16, region: 'right-arm', major: true },
  { a: 15, b: 17, region: 'left-hand' },
  { a: 15, b: 19, region: 'left-hand' },
  { a: 15, b: 21, region: 'left-hand' },
  { a: 17, b: 19, region: 'left-hand' },
  { a: 16, b: 18, region: 'right-hand' },
  { a: 16, b: 20, region: 'right-hand' },
  { a: 16, b: 22, region: 'right-hand' },
  { a: 18, b: 20, region: 'right-hand' },
  { a: 23, b: 25, region: 'left-leg', major: true },
  { a: 25, b: 27, region: 'left-leg', major: true },
  { a: 24, b: 26, region: 'right-leg', major: true },
  { a: 26, b: 28, region: 'right-leg', major: true },
  { a: 27, b: 29, region: 'left-foot' },
  { a: 29, b: 31, region: 'left-foot' },
  { a: 27, b: 31, region: 'left-foot' },
  { a: 28, b: 30, region: 'right-foot' },
  { a: 30, b: 32, region: 'right-foot' },
  { a: 28, b: 32, region: 'right-foot' },
])

export const ANGLE_TRIPLETS = Object.freeze({
  11: [23, 11, 13], 12: [24, 12, 14],
  13: [11, 13, 15], 14: [12, 14, 16],
  23: [11, 23, 25], 24: [12, 24, 26],
  25: [23, 25, 27], 26: [24, 26, 28],
  27: [25, 27, 31], 28: [26, 28, 32],
})

export function virtualPoints(frame) {
  return {
    neck: midpoint(frame?.[11], frame?.[12]),
    pelvis: midpoint(frame?.[23], frame?.[24]),
  }
}

function midpoint(a, b) {
  if (!isFinitePoint(a) || !isFinitePoint(b)) return null
  return [
    (a[0] + b[0]) / 2,
    (a[1] + b[1]) / 2,
    (a[2] + b[2]) / 2,
    Math.min(pointConfidence(a), pointConfidence(b)),
  ]
}

export function endpoint(frame, virtual, key) {
  return VIRTUAL_POINTS.has(key) ? virtual[key] : frame?.[key]
}

export function distance3d(a, b) {
  if (!isFinitePoint(a) || !isFinitePoint(b)) return Number.NaN
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
}

function percentile(values, ratio) {
  if (!values.length) return 0
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.round((sorted.length - 1) * ratio)))]
}

function median(values) {
  return percentile(values, 0.5)
}

export function buildDatasetProfile(worldFrames) {
  const frames = Array.isArray(worldFrames) ? worldFrames : []
  const stride = Math.max(1, Math.floor(frames.length / 240))
  const xs = [], ys = [], zs = [], footYs = []
  const lengths = SKELETON_BONES.map(() => [])

  for (let frameIndex = 0; frameIndex < frames.length; frameIndex += stride) {
    const frame = frames[frameIndex]
    if (!Array.isArray(frame)) continue
    const virtual = virtualPoints(frame)
    frame.forEach((point, index) => {
      if (pointConfidence(point) < RELIABLE_POINT_CONFIDENCE) return
      const scenePoint = toScenePoint(point)
      if (!scenePoint) return
      xs.push(scenePoint[0]); ys.push(scenePoint[1]); zs.push(scenePoint[2])
      if ([27, 28, 29, 30, 31, 32].includes(index)) footYs.push(scenePoint[1])
    })
    SKELETON_BONES.forEach((bone, boneIndex) => {
      if (!bone.major) return
      const a = endpoint(frame, virtual, bone.a)
      const b = endpoint(frame, virtual, bone.b)
      if (pointConfidence(a) < RELIABLE_POINT_CONFIDENCE || pointConfidence(b) < RELIABLE_POINT_CONFIDENCE) return
      const length = distance3d(a, b)
      if (Number.isFinite(length) && length > 0.01) lengths[boneIndex].push(length)
    })
  }

  const minY = percentile(ys, 0.02)
  const maxY = percentile(ys, 0.98)
  const height = Math.max(1.2, maxY - minY)
  const targetY = (minY + maxY) / 2
  return {
    center: [median(xs), targetY, median(zs)],
    groundY: footYs.length ? percentile(footYs, 0.2) : minY,
    height,
    distance: Math.max(3.5, height * 2.1),
    bodyScale: lengths[0]?.length ? median(lengths[0]) : 0.34,
    boneMedians: lengths.map((samples) => samples.length ? median(samples) : null),
  }
}

export function analyzeWorldFrame(frame, profile) {
  const virtual = virtualPoints(frame)
  const lowConfidence = []
  const missing = []
  const pointStates = Array.from({ length: JOINT_NAMES.length }, () => 'reliable')

  for (let index = 0; index < JOINT_NAMES.length; index++) {
    const point = frame?.[index]
    const confidence = pointConfidence(point)
    if (!isFinitePoint(point) || confidence < MIN_POINT_CONFIDENCE) {
      missing.push(index)
      pointStates[index] = 'missing'
    } else if (confidence < RELIABLE_POINT_CONFIDENCE) {
      lowConfidence.push(index)
      pointStates[index] = 'low'
    }
  }

  const boneStates = SKELETON_BONES.map((bone, boneIndex) => {
    const a = endpoint(frame, virtual, bone.a)
    const b = endpoint(frame, virtual, bone.b)
    const confidence = Math.min(pointConfidence(a), pointConfidence(b))
    const length = distance3d(a, b)
    const baseline = profile?.boneMedians?.[boneIndex]
    const ratio = baseline && Number.isFinite(length) ? length / baseline : null
    const outlier = Boolean(bone.major && ratio != null && (ratio < 0.5 || ratio > 1.8))
    if (outlier) {
      if (Number.isInteger(bone.a) && pointStates[bone.a] === 'reliable') pointStates[bone.a] = 'outlier'
      if (Number.isInteger(bone.b) && pointStates[bone.b] === 'reliable') pointStates[bone.b] = 'outlier'
    }
    return {
      visible: isFinitePoint(a) && isFinitePoint(b) && confidence >= MIN_POINT_CONFIDENCE,
      confidence,
      length,
      ratio,
      outlier,
    }
  })

  return {
    virtual,
    pointStates,
    boneStates,
    lowConfidence,
    missing,
    outlierBones: boneStates.reduce((items, state, index) => state.outlier ? [...items, index] : items, []),
  }
}

export function cameraPreset(name, profile) {
  const target = profile?.center || [0, 0, 0]
  const distance = profile?.distance || 2.4
  const [x, y, z] = target
  const presets = {
    front: [x, y, z + distance],
    left: [x + distance, y, z],
    right: [x - distance, y, z],
    back: [x, y, z - distance],
  }
  return presets[name] ? { position: presets[name], target: [...target] } : null
}

export function jointAngle(frame, index) {
  const triplet = ANGLE_TRIPLETS[index]
  if (!triplet) return null
  const [aIndex, vertexIndex, bIndex] = triplet
  const a = frame?.[aIndex], vertex = frame?.[vertexIndex], b = frame?.[bIndex]
  if ([a, vertex, b].some((point) => pointConfidence(point) < MIN_POINT_CONFIDENCE)) return null
  const va = [a[0] - vertex[0], a[1] - vertex[1], a[2] - vertex[2]]
  const vb = [b[0] - vertex[0], b[1] - vertex[1], b[2] - vertex[2]]
  const la = Math.hypot(...va), lb = Math.hypot(...vb)
  if (la < 1e-6 || lb < 1e-6) return null
  const cosine = Math.max(-1, Math.min(1, (va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2]) / (la * lb)))
  return Math.acos(cosine) * 180 / Math.PI
}
