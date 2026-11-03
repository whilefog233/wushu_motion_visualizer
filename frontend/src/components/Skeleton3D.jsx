import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { JOINT_NAMES } from '../lib/poseSpec'
import { createHumanoid, disposeHumanoid, setHumanoidMode, updateHumanoid } from '../lib/riggedHuman'
import {
  MIN_POINT_CONFIDENCE,
  RELIABLE_POINT_CONFIDENCE,
  SKELETON_BONES,
  analyzeWorldFrame,
  buildDatasetProfile,
  cameraPreset,
  endpoint,
  jointAngle,
  pointConfidence,
  toScenePoint,
} from '../lib/skeleton3d'

const MAJOR_JOINTS = new Set([0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28])
const FACE_JOINTS = new Set([1, 2, 3, 4, 5, 6, 9, 10])
const FOOT_AND_HAND_JOINTS = new Set([17, 18, 19, 20, 21, 22, 29, 30, 31, 32])
const VIEW_LABELS = { front: '正面', left: '左侧', right: '右侧', back: '背面', free: '自由' }

const COLORS = {
  joint: 0x52f2d0,
  bone: 0x28d8bf,
  selected: 0xffffff,
  low: 0xffb45b,
  outlier: 0xff5b7f,
}

const Y_AXIS = new THREE.Vector3(0, 1, 0)

function setMaterialState(material, state, selected = false) {
  const color = selected
    ? COLORS.selected
    : state === 'outlier' ? COLORS.outlier : state === 'low' ? COLORS.low : COLORS.joint
  material.color.setHex(color)
  material.emissive?.setHex(color)
  material.emissiveIntensity = selected ? 1.25 : state === 'reliable' ? 0.72 : 0.95
  material.opacity = state === 'reliable' || selected ? 0.96 : 0.72
}

function placeBone(mesh, a, b, radius) {
  const aPoint = toScenePoint(a), bPoint = toScenePoint(b)
  if (!aPoint || !bPoint) {
    mesh.visible = false
    return
  }
  const start = new THREE.Vector3(...aPoint)
  const end = new THREE.Vector3(...bPoint)
  const direction = end.clone().sub(start)
  const length = direction.length()
  if (!Number.isFinite(length) || length < 1e-5) {
    mesh.visible = false
    return
  }
  mesh.visible = true
  mesh.position.copy(start).add(end).multiplyScalar(0.5)
  mesh.quaternion.setFromUnitVectors(Y_AXIS, direction.normalize())
  mesh.scale.set(radius, length, radius)
}

export default function Skeleton3D({ worldFrames, frameIndex = 0, visible = true }) {
  const mountRef = useRef(null)
  const stateRef = useRef(null)
  const [view, setView] = useState('front')
  const [mode, setMode] = useState('wire')
  const [assetStatus, setAssetStatus] = useState('loading')
  const [calibration, setCalibration] = useState('motion')
  const [selected, setSelected] = useState(null)
  const [quality, setQuality] = useState({ low: 0, missing: 0, outliers: 0 })
  const profile = useMemo(() => buildDatasetProfile(worldFrames), [worldFrames])
  const safeFrameIndex = Math.max(0, Math.min((worldFrames?.length || 1) - 1, frameIndex))

  useEffect(() => {
    if (!mountRef.current) return undefined
    const mount = mountRef.current
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x07051a)
    scene.fog = new THREE.FogExp2(0x07051a, 0.11)

    const camera = new THREE.PerspectiveCamera(38, Math.max(1, mount.clientWidth) / Math.max(1, mount.clientHeight), 0.01, 50)
    const initial = cameraPreset('front', profile)
    camera.position.set(...initial.position)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setSize(Math.max(1, mount.clientWidth), Math.max(1, mount.clientHeight))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    renderer.domElement.setAttribute('aria-label', 'MediaPipe 三维人体模型')
    mount.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.075
    controls.minDistance = Math.max(0.8, profile.height * 0.55)
    controls.maxDistance = Math.max(6, profile.height * 4)
    controls.target.set(...initial.target)
    controls.update()

    scene.add(new THREE.HemisphereLight(0xc8fff5, 0x120b36, 1.35))
    const keyLight = new THREE.DirectionalLight(0xbfffee, 1.2)
    keyLight.position.set(1.8, 2.8, 2.4)
    scene.add(keyLight)
    const rimLight = new THREE.PointLight(0x6d5dfc, 6, 5)
    rimLight.position.set(-1.8, 0.4, -1.6)
    scene.add(rimLight)

    const gridSize = Math.max(3, profile.height * 2.1)
    const grid = new THREE.GridHelper(gridSize, 18, 0x35d5bc, 0x2e2953)
    grid.position.set(profile.center[0], profile.groundY, profile.center[2])
    const gridMaterials = Array.isArray(grid.material) ? grid.material : [grid.material]
    gridMaterials.forEach((material) => {
      material.transparent = true
      material.opacity = 0.34
      material.depthWrite = false
    })
    scene.add(grid)

    const axes = new THREE.AxesHelper(Math.max(0.28, profile.height * 0.22))
    axes.position.set(profile.center[0] - gridSize * 0.38, profile.groundY + 0.004, profile.center[2] + gridSize * 0.32)
    scene.add(axes)

    const skeletonGroup = new THREE.Group()
    skeletonGroup.name = 'diagnostic-skeleton'
    skeletonGroup.visible = false
    scene.add(skeletonGroup)

    const jointGeometry = new THREE.SphereGeometry(1, 14, 12)
    const joints = JOINT_NAMES.map((_, index) => {
      const material = new THREE.MeshStandardMaterial({
        color: COLORS.joint,
        emissive: COLORS.joint,
        emissiveIntensity: 0.72,
        roughness: 0.32,
        metalness: 0.12,
        transparent: true,
      })
      const joint = new THREE.Mesh(jointGeometry, material)
      const radius = FACE_JOINTS.has(index) ? 0.008 : FOOT_AND_HAND_JOINTS.has(index) ? 0.011 : MAJOR_JOINTS.has(index) ? 0.021 : 0.014
      joint.scale.setScalar(radius)
      joint.userData.landmarkIndex = index
      skeletonGroup.add(joint)
      return joint
    })

    const boneGeometry = new THREE.CylinderGeometry(1, 1, 1, 10, 1, false)
    const bones = SKELETON_BONES.map((bone) => {
      const material = new THREE.MeshStandardMaterial({
        color: COLORS.bone,
        emissive: COLORS.bone,
        emissiveIntensity: 0.68,
        roughness: 0.36,
        metalness: 0.08,
        transparent: true,
        opacity: 0.9,
      })
      const mesh = new THREE.Mesh(boneGeometry, material)
      mesh.userData.bone = bone
      skeletonGroup.add(mesh)
      return mesh
    })

    const humanoid = createHumanoid(worldFrames, profile)
    scene.add(humanoid.group)
    let cancelled = false
    setAssetStatus('loading')
    humanoid.ready.then(() => { if(!cancelled) setAssetStatus('ready') }).catch(error => {
      if(!cancelled) setAssetStatus(`模型加载失败：${error.message}`)
    })

    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    const onPointerUp = (event) => {
      const rect = renderer.domElement.getBoundingClientRect()
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
      raycaster.setFromCamera(pointer, camera)
      if (stateRef.current?.mode !== 'combined') return
      const hit = raycaster.intersectObjects(joints.filter((joint) => joint.visible), false)[0]
      setSelected(hit ? hit.object.userData.landmarkIndex : null)
    }
    const onControlStart = () => {
      if (stateRef.current) stateRef.current.transition = null
      setView('free')
    }
    renderer.domElement.addEventListener('pointerup', onPointerUp)
    controls.addEventListener('start', onControlStart)

    const resizeObserver = new ResizeObserver(() => {
      const width = Math.max(1, mount.clientWidth), height = Math.max(1, mount.clientHeight)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    })
    resizeObserver.observe(mount)

    stateRef.current = {
      scene, camera, renderer, controls, joints, bones, skeletonGroup, humanoid, grid, axes,
      mode: 'wire',
      transition: null,
    }

    let animationFrame
    const render = (now) => {
      animationFrame = requestAnimationFrame(render)
      const state = stateRef.current
      if (!state) return
      if (state.transition) {
        const elapsed = Math.min(1, (now - state.transition.startedAt) / 320)
        const eased = 1 - Math.pow(1 - elapsed, 3)
        camera.position.lerpVectors(state.transition.fromPosition, state.transition.toPosition, eased)
        controls.target.lerpVectors(state.transition.fromTarget, state.transition.toTarget, eased)
        if (elapsed >= 1) state.transition = null
      }
      controls.update()
      renderer.render(scene, camera)
    }
    animationFrame = requestAnimationFrame(render)

    return () => {
      cancelled = true
      cancelAnimationFrame(animationFrame)
      resizeObserver.disconnect()
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      controls.removeEventListener('start', onControlStart)
      controls.dispose()
      joints.forEach((joint) => joint.material.dispose())
      bones.forEach((bone) => bone.material.dispose())
      disposeHumanoid(humanoid)
      jointGeometry.dispose()
      boneGeometry.dispose()
      grid.geometry.dispose()
      gridMaterials.forEach((material) => material.dispose())
      axes.geometry.dispose()
      ;(Array.isArray(axes.material) ? axes.material : [axes.material]).forEach(m=>m.dispose())
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
      stateRef.current = null
    }
  }, [profile, worldFrames])

  useEffect(() => {
    if (!visible || !stateRef.current) return
    const frame = worldFrames?.[safeFrameIndex]
    if (!Array.isArray(frame)) return
    const diagnostics = analyzeWorldFrame(frame, profile)
    setQuality({
      low: diagnostics.lowConfidence.length,
      missing: diagnostics.missing.length,
      outliers: diagnostics.outlierBones.length,
    })

    stateRef.current.joints.forEach((joint, index) => {
      const point = frame[index]
      const confidence = pointConfidence(point)
      const scenePoint = toScenePoint(point)
      joint.visible = Boolean(scenePoint && confidence >= MIN_POINT_CONFIDENCE)
      if (!joint.visible) return
      joint.position.set(...scenePoint)
      setMaterialState(joint.material, diagnostics.pointStates[index], selected === index)
    })

    stateRef.current.bones.forEach((mesh, index) => {
      const bone = SKELETON_BONES[index]
      const state = diagnostics.boneStates[index]
      const a = endpoint(frame, diagnostics.virtual, bone.a)
      const b = endpoint(frame, diagnostics.virtual, bone.b)
      if (!state.visible) {
        mesh.visible = false
        return
      }
      placeBone(mesh, a, b, bone.major ? 0.0105 : 0.0065)
      const visualState = state.outlier ? 'outlier' : state.confidence < RELIABLE_POINT_CONFIDENCE ? 'low' : 'reliable'
      setMaterialState(mesh.material, visualState)
      mesh.material.opacity = visualState === 'reliable' ? 0.88 : 0.48
    })
    updateHumanoid(stateRef.current.humanoid, frame, diagnostics, profile, safeFrameIndex, calibration)
  }, [profile, safeFrameIndex, selected, visible, worldFrames, assetStatus, calibration])

  useEffect(() => {
    const state = stateRef.current
    if (!state) return
    state.mode = mode
    state.skeletonGroup.visible = mode === 'combined' && calibration === 'motion'
    setHumanoidMode(state.humanoid, mode)
    if (mode !== 'combined') setSelected(null)
  }, [mode, assetStatus, calibration])

  const gotoView = useCallback((name) => {
    const state = stateRef.current
    if (!state) return
    setView(name)
    if (name === 'free') {
      state.transition = null
      return
    }
    const preset = cameraPreset(name, profile)
    state.transition = {
      startedAt: performance.now(),
      fromPosition: state.camera.position.clone(),
      toPosition: new THREE.Vector3(...preset.position),
      fromTarget: state.controls.target.clone(),
      toTarget: new THREE.Vector3(...preset.target),
    }
  }, [profile])

  const currentFrame = worldFrames?.[safeFrameIndex]
  const angle = selected != null ? jointAngle(currentFrame, selected) : null
  const warningCount = quality.low + quality.missing + quality.outliers

  return (
    <div className="skeleton3d-wrap" style={{display:visible ? undefined : 'none'}} data-asset-status={assetStatus}>
      <div className="skeleton3d-toolbar">
        <div className="s3d-heading">
          <span className="s3d-title">WORLD 3D</span>
          <div className="s3d-mode" aria-label="三维模型模式">
            {Object.entries({solid:'人体实体',wire:'科技线框',combined:'人体+骨架'}).map(([key,label])=><button key={key} type="button" className={mode===key?'on':''} aria-pressed={mode===key} onClick={()=>setMode(key)}>{label}</button>)}
          </div>
          <span className={`s3d-quality ${warningCount ? 'warn' : ''}`}>
            {warningCount ? `${warningCount} 项需关注` : '数据稳定'}
          </span>
        </div>
        <div className="s3d-views" aria-label="三维观察视角">
          {Object.keys(VIEW_LABELS).map((name) => (
            <button
              key={name}
              type="button"
              className={view === name ? 'on' : ''}
              aria-pressed={view === name}
              onClick={() => gotoView(name)}
            >
              {VIEW_LABELS[name]}
            </button>
          ))}
          <button type="button" className="s3d-reset" onClick={() => gotoView('front')}>重置</button>
        </div>
      </div>
      <div className="skeleton3d-canvas" ref={mountRef}>
        <div className="s3d-frame">帧 #{safeFrameIndex} · {calibration==='motion'?'蒙皮人体 · 动作重定向':'模型校验 · 非视频姿态'}</div>
        {assetStatus!=='ready' && <div className="skeleton3d-notice" role="status">{assetStatus==='loading'?'正在加载绑定人体…':assetStatus}</div>}
        <div className="s3d-axis-key" aria-label="坐标方向">
          <span className="axis-x">X 左右</span>
          <span className="axis-y">Y 上下</span>
          <span className="axis-z">Z 前后</span>
        </div>
      </div>
      <div className="skeleton3d-info">
        {mode === 'combined' && selected != null ? (
          <span>
            <b>{JOINT_NAMES[selected]}</b>
            {angle == null ? ' · 无标准关节角' : ` · ${angle.toFixed(1)}°`}
          </span>
        ) : (
          <span>通用体型 · 手指中性姿态 · {mode==='combined'?'叠加原始关键点':'拖动旋转 / 滚轮缩放'}</span>
        )}
        {(quality.low > 0 || quality.missing > 0) && (
          <span className="s3d-confidence-note">橙色：低置信度 · 隐藏：无效点</span>
        )}
      </div>
      <div className="s3d-calibration"><label>模型校验 <select aria-label="模型校验" value={calibration} onChange={e=>setCalibration(e.target.value)}><option value="motion">真实视频动作</option><option value="rest">静态 T-Pose</option><option value="bend">弯曲测试（合成）</option></select></label><span>固定坐标视角 · +Z 朝原相机</span></div>
    </div>
  )
}
