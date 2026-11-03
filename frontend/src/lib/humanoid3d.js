import * as THREE from 'three'
import {
  MIN_POINT_CONFIDENCE,
  RELIABLE_POINT_CONFIDENCE,
  distance3d,
  pointConfidence,
  toScenePoint,
} from './skeleton3d.js'

export const HUMANOID_PART_NAMES = Object.freeze([
  'head', 'neck', 'chest', 'abdomen', 'pelvis',
  'leftShoulder', 'rightShoulder',
  'leftUpperArm', 'rightUpperArm', 'leftForearm', 'rightForearm',
  'leftHand', 'rightHand', 'leftThigh', 'rightThigh',
  'leftShin', 'rightShin', 'leftFoot', 'rightFoot',
])

const BODY_COLOR = 0x35e0c2
const LOW_COLOR = 0xffb45b
const OUTLIER_COLOR = 0xff5b7f
const Y_AXIS = new THREE.Vector3(0, 1, 0)

const CAPSULE_SPECS = [
  ['neck', 'neck', 'headBase', 0.10],
  ['leftUpperArm', 11, 13, 0.13], ['rightUpperArm', 12, 14, 0.13],
  ['leftForearm', 13, 15, 0.105], ['rightForearm', 14, 16, 0.105],
  ['leftHand', 15, 'leftHand', 0.095], ['rightHand', 16, 'rightHand', 0.095],
  ['leftThigh', 23, 25, 0.19], ['rightThigh', 24, 26, 0.19],
  ['leftShin', 25, 27, 0.145], ['rightShin', 26, 28, 0.145],
  ['leftFoot', 29, 31, 0.13], ['rightFoot', 30, 32, 0.13],
]

function bodyMaterial(opacity = 0.86) {
  return new THREE.MeshPhysicalMaterial({
    color: BODY_COLOR,
    emissive: 0x087f71,
    emissiveIntensity: 0.42,
    roughness: 0.28,
    metalness: 0.05,
    clearcoat: 0.5,
    clearcoatRoughness: 0.36,
    transparent: true,
    opacity,
    depthWrite: true,
  })
}

function createCapsule(name, cylinderGeometry, sphereGeometry) {
  const material = bodyMaterial(0.88)
  const group = new THREE.Group()
  group.name = name
  const cylinder = new THREE.Mesh(cylinderGeometry, material)
  const start = new THREE.Mesh(sphereGeometry, material)
  const end = new THREE.Mesh(sphereGeometry, material)
  group.add(cylinder, start, end)
  return { name, group, cylinder, start, end, material }
}

function createVolume(name, geometry, opacity = 0.82) {
  const material = bodyMaterial(opacity)
  const mesh = new THREE.Mesh(geometry, material)
  mesh.name = name
  return { name, mesh, material }
}

function average(points) {
  const valid = points.filter((point) => Array.isArray(point) && point.slice(0, 3).every(Number.isFinite))
  if (!valid.length) return null
  return [
    valid.reduce((sum, point) => sum + point[0], 0) / valid.length,
    valid.reduce((sum, point) => sum + point[1], 0) / valid.length,
    valid.reduce((sum, point) => sum + point[2], 0) / valid.length,
    Math.min(...valid.map(pointConfidence)),
  ]
}

function mix(a, b, ratio) {
  if (!a || !b) return null
  return [
    a[0] + (b[0] - a[0]) * ratio,
    a[1] + (b[1] - a[1]) * ratio,
    a[2] + (b[2] - a[2]) * ratio,
    Math.min(pointConfidence(a), pointConfidence(b)),
  ]
}

function derivedPoints(frame, virtual) {
  const head = average([frame[0], frame[7], frame[8]])
  return {
    neck: virtual.neck,
    pelvis: virtual.pelvis,
    waist: mix(virtual.pelvis, virtual.neck, 0.34),
    head,
    headBase: mix(virtual.neck, head, 0.38),
    leftHand: average([frame[17], frame[19], frame[21]]),
    rightHand: average([frame[18], frame[20], frame[22]]),
  }
}

function rawEndpoint(frame, derived, key) {
  return typeof key === 'number' ? frame[key] : derived[key]
}

function setVisualState(material, state, opacity = 0.86) {
  const color = state === 'outlier' ? OUTLIER_COLOR : state === 'low' ? LOW_COLOR : BODY_COLOR
  material.color.setHex(color)
  material.emissive.setHex(state === 'reliable' ? 0x087f71 : color)
  material.emissiveIntensity = state === 'reliable' ? 0.42 : 0.75
  material.opacity = state === 'reliable' ? opacity : Math.min(opacity, 0.62)
}

function combinedState(frame, indices, diagnostics) {
  const states = indices.map((index) => diagnostics.pointStates[index])
  if (states.includes('missing') || indices.some((index) => pointConfidence(frame[index]) < MIN_POINT_CONFIDENCE)) return 'missing'
  if (states.includes('outlier')) return 'outlier'
  if (states.includes('low') || indices.some((index) => pointConfidence(frame[index]) < RELIABLE_POINT_CONFIDENCE)) return 'low'
  return 'reliable'
}

function placeCapsule(part, a, b, radius) {
  const startArray = toScenePoint(a), endArray = toScenePoint(b)
  if (!startArray || !endArray || Math.min(pointConfidence(a), pointConfidence(b)) < MIN_POINT_CONFIDENCE) {
    part.group.visible = false
    return
  }
  const start = new THREE.Vector3(...startArray), end = new THREE.Vector3(...endArray)
  const direction = end.clone().sub(start)
  const length = direction.length()
  if (!Number.isFinite(length) || length < 1e-4) {
    part.group.visible = false
    return
  }
  part.group.visible = true
  part.cylinder.position.copy(start).add(end).multiplyScalar(0.5)
  part.cylinder.quaternion.setFromUnitVectors(Y_AXIS, direction.normalize())
  part.cylinder.scale.set(radius, Math.max(0.002, length - radius * 0.35), radius)
  part.start.position.copy(start); part.start.scale.setScalar(radius)
  part.end.position.copy(end); part.end.scale.setScalar(radius)
}

function sceneVector(point) {
  const converted = toScenePoint(point)
  return converted ? new THREE.Vector3(...converted) : null
}

function bodyQuaternion(left, right, bottom, top) {
  const leftPoint = sceneVector(left), rightPoint = sceneVector(right)
  const bottomPoint = sceneVector(bottom), topPoint = sceneVector(top)
  if (!leftPoint || !rightPoint || !bottomPoint || !topPoint) return new THREE.Quaternion()
  const xAxis = leftPoint.clone().sub(rightPoint).normalize()
  const yAxis = topPoint.clone().sub(bottomPoint).normalize()
  const zAxis = xAxis.clone().cross(yAxis).normalize()
  if (zAxis.lengthSq() < 1e-5) return new THREE.Quaternion()
  xAxis.copy(yAxis).cross(zAxis).normalize()
  const basis = new THREE.Matrix4().makeBasis(xAxis, yAxis, zAxis)
  return new THREE.Quaternion().setFromRotationMatrix(basis)
}

function placeVolume(part, center, quaternion, scale) {
  const point = sceneVector(center)
  if (!point) {
    part.mesh.visible = false
    return
  }
  part.mesh.visible = true
  part.mesh.position.copy(point)
  part.mesh.quaternion.copy(quaternion)
  part.mesh.scale.set(...scale)
}

export function createHumanoid() {
  const group = new THREE.Group()
  group.name = 'capsule-humanoid'
  const geometries = {
    cylinder: new THREE.CylinderGeometry(1, 1, 1, 12, 1, false),
    sphere: new THREE.SphereGeometry(1, 18, 14),
    chest: new THREE.CylinderGeometry(1, 0.66, 1, 12, 2, false),
    abdomen: new THREE.CylinderGeometry(0.72, 0.92, 1, 12, 2, false),
  }
  const capsules = Object.fromEntries(CAPSULE_SPECS.map(([name]) => {
    const part = createCapsule(name, geometries.cylinder, geometries.sphere)
    group.add(part.group)
    return [name, part]
  }))
  const parts = {
    head: createVolume('head', geometries.sphere, 0.86),
    chest: createVolume('chest', geometries.chest, 0.78),
    abdomen: createVolume('abdomen', geometries.abdomen, 0.78),
    pelvis: createVolume('pelvis', geometries.sphere, 0.82),
    leftShoulder: createVolume('leftShoulder', geometries.sphere, 0.88),
    rightShoulder: createVolume('rightShoulder', geometries.sphere, 0.88),
  }
  Object.values(parts).forEach((part) => group.add(part.mesh))
  return { group, capsules, parts, geometries }
}

export function updateHumanoid(humanoid, frame, diagnostics, profile) {
  if (!humanoid || !Array.isArray(frame)) return
  const derived = derivedPoints(frame, diagnostics.virtual)
  const bodyScale = Math.max(0.25, Math.min(0.55, profile?.bodyScale || distance3d(frame[11], frame[12]) || 0.34))

  CAPSULE_SPECS.forEach(([name, aKey, bKey, radiusRatio]) => {
    const part = humanoid.capsules[name]
    const a = rawEndpoint(frame, derived, aKey), b = rawEndpoint(frame, derived, bKey)
    placeCapsule(part, a, b, bodyScale * radiusRatio)
    const indices = name.includes('left')
      ? name.includes('Thigh') ? [23, 25] : name.includes('Shin') ? [25, 27] : name.includes('Foot') ? [27, 29, 31] : name.includes('Upper') ? [11, 13] : name.includes('Forearm') ? [13, 15] : [15, 17, 19, 21]
      : name.includes('right')
        ? name.includes('Thigh') ? [24, 26] : name.includes('Shin') ? [26, 28] : name.includes('Foot') ? [28, 30, 32] : name.includes('Upper') ? [12, 14] : name.includes('Forearm') ? [14, 16] : [16, 18, 20, 22]
        : [0, 11, 12]
    const state = combinedState(frame, indices, diagnostics)
    part.group.visible = part.group.visible && state !== 'missing'
    setVisualState(part.material, state)
  })

  const neck = derived.neck, pelvis = derived.pelvis, waist = derived.waist
  const torsoState = combinedState(frame, [11, 12, 23, 24], diagnostics)
  const torsoQuaternion = bodyQuaternion(frame[11], frame[12], pelvis, neck)
  const shoulderWidth = distance3d(frame[11], frame[12]) || bodyScale
  const hipWidth = distance3d(frame[23], frame[24]) || bodyScale * 0.7
  const chestLength = distance3d(waist, neck) || bodyScale * 1.1
  const abdomenLength = distance3d(pelvis, waist) || bodyScale * 0.55

  placeVolume(humanoid.parts.chest, mix(waist, neck, 0.5), torsoQuaternion, [shoulderWidth * 0.52, chestLength, shoulderWidth * 0.29])
  placeVolume(humanoid.parts.abdomen, mix(pelvis, waist, 0.5), torsoQuaternion, [hipWidth * 0.52, abdomenLength, shoulderWidth * 0.23])
  placeVolume(humanoid.parts.pelvis, pelvis, torsoQuaternion, [hipWidth * 0.63, bodyScale * 0.24, hipWidth * 0.46])
  ;['chest', 'abdomen', 'pelvis'].forEach((name) => setVisualState(humanoid.parts[name].material, torsoState, name === 'pelvis' ? 0.82 : 0.78))

  const headState = combinedState(frame, [0, 7, 8, 11, 12], diagnostics)
  const headWidth = Math.max(bodyScale * 0.38, Math.min(bodyScale * 0.58, (distance3d(frame[7], frame[8]) || bodyScale * 0.36) * 1.18))
  const headQuaternion = bodyQuaternion(frame[7], frame[8], neck, derived.head)
  placeVolume(humanoid.parts.head, derived.head, headQuaternion, [headWidth * 0.53, headWidth * 0.66, headWidth * 0.45])
  setVisualState(humanoid.parts.head.material, headState, 0.86)

  ;[[11, 'leftShoulder'], [12, 'rightShoulder']].forEach(([index, name]) => {
    const state = combinedState(frame, [index], diagnostics)
    placeVolume(humanoid.parts[name], frame[index], torsoQuaternion, [bodyScale * 0.16, bodyScale * 0.145, bodyScale * 0.15])
    humanoid.parts[name].mesh.visible = humanoid.parts[name].mesh.visible && state !== 'missing'
    setVisualState(humanoid.parts[name].material, state, 0.88)
  })
}

export function setHumanoidVisible(humanoid, visible) {
  if (humanoid?.group) humanoid.group.visible = visible
}

export function disposeHumanoid(humanoid) {
  if (!humanoid) return
  Object.values(humanoid.capsules).forEach((part) => part.material.dispose())
  Object.values(humanoid.parts).forEach((part) => part.material.dispose())
  Object.values(humanoid.geometries).forEach((geometry) => geometry.dispose())
}
