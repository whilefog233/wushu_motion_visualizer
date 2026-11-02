import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { frameAt } from '../src/lib/frameData.js'
import { JOINT_NAMES } from '../src/lib/poseSpec.js'
import {
  SKELETON_BONES,
  analyzeWorldFrame,
  buildDatasetProfile,
  cameraPreset,
  toScenePoint,
} from '../src/lib/skeleton3d.js'
import { HUMANOID_PART_NAMES } from '../src/lib/humanoid3d.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const realPosePath = path.resolve(here, '../../data/analyses/20261009_182949_b583b9ef/pose.json')

function knownPose() {
  const frame = Array.from({ length: 33 }, () => [0, 0, 0, 0])
  const set = (index, x, y, z = 0, confidence = 1) => { frame[index] = [x, y, z, confidence] }
  set(0, 0, -0.78, -0.05)
  set(7, 0.08, -0.73, 0); set(8, -0.08, -0.73, 0)
  set(11, 0.23, -0.52, 0); set(12, -0.23, -0.52, 0)
  set(13, 0.56, -0.52, 0); set(14, -0.56, -0.52, 0)
  set(15, 0.88, -0.52, 0); set(16, -0.88, -0.52, 0)
  set(17, 0.93, -0.52, 0); set(18, -0.93, -0.52, 0)
  set(19, 0.94, -0.50, 0); set(20, -0.94, -0.50, 0)
  set(21, 0.91, -0.54, 0); set(22, -0.91, -0.54, 0)
  set(23, 0.14, 0, 0); set(24, -0.14, 0, 0)
  set(25, 0.14, 0.48, 0); set(26, -0.14, 0.48, 0)
  set(27, 0.14, 0.92, 0); set(28, -0.14, 0.92, 0)
  set(29, 0.14, 0.96, 0.06); set(30, -0.14, 0.96, 0.06)
  set(31, 0.14, 0.96, -0.18); set(32, -0.14, 0.96, -0.18)
  return frame
}

function compactWorldFrame(rawFrame) {
  return JOINT_NAMES.map((name) => {
    const point = rawFrame.world_landmarks?.[name]
    const confidence = point?.visibility ?? rawFrame.visibility?.[name] ?? rawFrame.landmarks?.[name]?.visibility ?? 0
    return point ? [point.x, point.y, point.z, confidence] : [0, 0, 0, 0]
  })
}

test('known pose keeps MediaPipe axes and body proportions', () => {
  const frame = knownPose()
  assert.deepEqual(toScenePoint([0.2, -0.5, -0.3, 1]), [0.2, 0.5, 0.3])
  assert(toScenePoint(frame[0])[1] > toScenePoint(frame[23])[1], 'head must render above pelvis')
  assert(toScenePoint(frame[27])[1] < toScenePoint(frame[23])[1], 'ankle must render below pelvis')
  assert(frame[11][0] > frame[12][0], 'subject left is +x in MediaPipe camera coordinates')
})

test('topology never crosses left and right limbs', () => {
  const leftArm = SKELETON_BONES.filter((bone) => bone.region === 'left-arm').map((bone) => [bone.a, bone.b])
  const rightArm = SKELETON_BONES.filter((bone) => bone.region === 'right-arm').map((bone) => [bone.a, bone.b])
  const leftLeg = SKELETON_BONES.filter((bone) => bone.region === 'left-leg').map((bone) => [bone.a, bone.b])
  const rightLeg = SKELETON_BONES.filter((bone) => bone.region === 'right-leg').map((bone) => [bone.a, bone.b])
  assert.deepEqual(leftArm, [[11, 13], [13, 15]])
  assert.deepEqual(rightArm, [[12, 14], [14, 16]])
  assert.deepEqual(leftLeg, [[23, 25], [25, 27]])
  assert.deepEqual(rightLeg, [[24, 26], [26, 28]])
})

test('capsule humanoid exposes every required anatomical volume', () => {
  for (const part of [
    'head', 'chest', 'abdomen', 'pelvis',
    'leftUpperArm', 'rightUpperArm', 'leftForearm', 'rightForearm',
    'leftThigh', 'rightThigh', 'leftShin', 'rightShin', 'leftFoot', 'rightFoot',
  ]) assert(HUMANOID_PART_NAMES.includes(part), `missing humanoid part: ${part}`)
})

test('all camera views share one target and use opposite positions', () => {
  const profile = buildDatasetProfile([knownPose()])
  const front = cameraPreset('front', profile), back = cameraPreset('back', profile)
  const left = cameraPreset('left', profile), right = cameraPreset('right', profile)
  assert.deepEqual(front.target, back.target)
  assert.deepEqual(front.target, left.target)
  assert.equal(front.position[2] - front.target[2], -(back.position[2] - back.target[2]))
  assert.equal(left.position[0] - left.target[0], -(right.position[0] - right.target[0]))
})

test('low-confidence points are marked without replacing their coordinates', () => {
  const frame = knownPose()
  frame[15][3] = 0.25
  const profile = buildDatasetProfile([knownPose()])
  const diagnostics = analyzeWorldFrame(frame, profile)
  assert(diagnostics.lowConfidence.includes(15))
  assert.equal(diagnostics.pointStates[15], 'low')
  assert.deepEqual(frame[15].slice(0, 3), [0.88, -0.52, 0])
})

test('shared frame mapping is exact at frame 355', () => {
  assert.equal(frameAt(355 / 30, 30, 713), 355)
  assert.equal(frameAt((355.999 / 30), 30, 713), 355)
  assert.equal(frameAt(713 / 30, 30, 713), 712)
})

test('real frames 0, 355 and 712 contain valid 33-point world data', { skip: !fs.existsSync(realPosePath) }, () => {
  const pose = JSON.parse(fs.readFileSync(realPosePath, 'utf8'))
  assert.equal(pose.fps, 30)
  assert.equal(pose.frame_count, 713)
  const frames = [0, 355, 712].map((index) => compactWorldFrame(pose.frames[index]))
  frames.forEach((frame) => {
    assert.equal(frame.length, 33)
    assert(frame.every((point) => point.slice(0, 3).every(Number.isFinite)))
    assert(frame.filter((point) => point[3] >= 0.15).length >= 29)
  })
  assert(Math.abs(frames[1][0][0] - 0.00882028) < 1e-4)
  assert(frames[1][23][0] > frames[1][24][0], 'frame 355 left/right hips must not be swapped')
  const profile = buildDatasetProfile(frames)
  frames.forEach((frame) => assert.equal(analyzeWorldFrame(frame, profile).missing.length, 0))
})
