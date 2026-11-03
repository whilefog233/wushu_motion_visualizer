import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { pointConfidence, toScenePoint } from './skeleton3d.js'

export const LIMB_MAP = [
  ['LeftArm','LeftForeArm',11,13], ['LeftForeArm','LeftHand',13,15],
  ['RightArm','RightForeArm',12,14], ['RightForeArm','RightHand',14,16],
  ['LeftUpLeg','LeftLeg',23,25], ['LeftLeg','LeftFoot',25,27],
  ['RightUpLeg','RightLeg',24,26], ['RightLeg','RightFoot',26,28],
  ['LeftFoot','LeftToeBase',29,31], ['RightFoot','RightToeBase',30,32],
]
const v = p => p && pointConfidence(p)>=0.15 ? new THREE.Vector3(...toScenePoint(p)) : null
const midpoint = (a,b) => a && b ? a.clone().add(b).multiplyScalar(.5) : null
function basis(left,right,bottom,top) {
  if(!left||!right||!bottom||!top) return null
  const y=top.clone().sub(bottom).normalize(), x=left.clone().sub(right).normalize()
  const z=x.clone().cross(y).normalize()
  if(z.lengthSq()<.1) return null
  x.copy(y).cross(z).normalize()
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x,y,z))
}

export function validateRig(root) {
  const meshes=[], bones={}
  root.traverse(o=>{
    if(o.isBone) bones[o.name.replace(/^mixamorig:?/,'')]=o
    if(o.isSkinnedMesh) {
      const w=o.geometry.attributes.skinWeight, ix=o.geometry.attributes.skinIndex
      if(!w||!ix||!o.skeleton?.bones.length) throw new Error('模型缺少有效蒙皮')
      for(let i=0;i<w.count;i++) {
        let sum=0
        for(let j=0;j<4;j++) {
          const weight=w.array[i*4+j], index=ix.array[i*4+j]
          if(!Number.isFinite(weight)||weight<0||index>=o.skeleton.bones.length) throw new Error('非法蒙皮权重/骨骼索引')
          sum+=weight
        }
        if(Math.abs(sum-1)>.002) throw new Error('蒙皮权重未归一化')
      }
      meshes.push(o)
    }
  })
  for(const name of ['Hips','Spine','Spine1','Spine2','Neck','Head',...LIMB_MAP.flatMap(m=>m.slice(0,2))])
    if(!bones[name]) throw new Error(`模型缺少骨骼 ${name}`)
  if(!meshes.length) throw new Error('模型不是 SkinnedMesh')
  return {meshes,bones}
}

function setWorldQuaternion(bone,q) {
  const parent=bone.parent.getWorldQuaternion(new THREE.Quaternion())
  bone.quaternion.copy(parent.invert().multiply(q))
  bone.updateWorldMatrix(false,true)
}

// Rotation-only retargeting: rest offsets and vertex positions remain immutable.
// Only the hip root translates. Uniform subject scale is fixed for the sequence.
export function solvePose(rig,frame) {
  const points=frame.map(v), p=midpoint(points[23],points[24]), s=midpoint(points[11],points[12])
  for(const [name,b] of Object.entries(rig.bones)) {
    b.quaternion.copy(rig.rest[name].q)
    b.position.copy(rig.rest[name].p)
  }
  rig.group.updateMatrixWorld(true)
  if(!p||!s) return null
  const hipQ=basis(points[23],points[24],p,s), chestQ=basis(points[11],points[12],p,s)
  if(!hipQ||!chestQ) return null
  const hip=rig.bones.Hips
  hip.position.copy(hip.parent.worldToLocal(p.clone()))
  setWorldQuaternion(hip,hipQ.clone().multiply(rig.rest.Hips.worldQ))
  for(const [name,t] of [['Spine',.33],['Spine1',.67],['Spine2',1]]) {
    setWorldQuaternion(rig.bones[name],hipQ.clone().slerp(chestQ,t).multiply(rig.rest[name].worldQ))
  }
  for(const [name,child,a,b] of LIMB_MAP) {
    if(!points[a]||!points[b]) continue
    const bone=rig.bones[name], tip=rig.bones[child]
    const current=tip.getWorldPosition(new THREE.Vector3()).sub(bone.getWorldPosition(new THREE.Vector3())).normalize()
    const target=points[b].clone().sub(points[a]).normalize()
    if(target.lengthSq()<.5) continue
    const q=new THREE.Quaternion().setFromUnitVectors(current,target).multiply(bone.getWorldQuaternion(new THREE.Quaternion()))
    setWorldQuaternion(bone,q)
  }
  // Head orientation from ears and neck direction; fingers remain in bind pose.
  const head=midpoint(points[7],points[8]), headQ=basis(points[7],points[8],s,head)
  if(headQ) setWorldQuaternion(rig.bones.Head,headQ.multiply(rig.rest.Head.worldQ))
  return {root:hip.position.clone(),quaternions:Object.fromEntries(Object.entries(rig.bones).map(([n,b])=>[n,b.quaternion.clone()]))}
}

export function prepareSequence(rig,frames) {
  const raw=frames.map(f=>solvePose(rig,f))
  // Symmetric local quaternion smoothing: independent of playback/seek history,
  // no time shift, no blending across missing frames, positions never smoothed.
  return raw.map((pose,i)=>{
    if(!pose) return null
    const quaternions={}
    for(const [name,q] of Object.entries(pose.quaternions)) {
      const neighbor=raw[i-1]?.quaternions[name] && raw[i+1]?.quaternions[name]
        ? raw[i-1].quaternions[name].clone().slerp(raw[i+1].quaternions[name],.5) : q
      quaternions[name]=q.clone().slerp(neighbor,.12)
    }
    return {...pose,quaternions}
  })
}

export function createHumanoid(frames,profile) {
  const group=new THREE.Group(); group.name='rigged-human'
  const rig={group,disposed:false,sequence:[],mode:'wire'}
  rig.ready=new GLTFLoader().loadAsync('/models/beta/human.glb').then(({scene})=>{
    if(rig.disposed) { scene.traverse(o=>{o.geometry?.dispose();if(o.material) o.material.dispose()}); return }
    const {meshes,bones}=validateRig(scene)
    group.add(scene); group.updateMatrixWorld(true)
    rig.bones=bones; rig.meshes=meshes; rig.wires=[]; rig.rest={}
    for(const [name,b] of Object.entries(bones)) rig.rest[name]={q:b.quaternion.clone(),p:b.position.clone(),worldQ:b.getWorldQuaternion(new THREE.Quaternion())}
    // Fixed global scale, never separately scaling limbs.
    group.scale.setScalar(Math.max(.8,Math.min(1.3,(profile.bodyScale||.38)/.388)))
    for(const mesh of meshes) {
      mesh.material.dispose()
      mesh.material=new THREE.MeshPhysicalMaterial({color:0x102637,roughness:.5,metalness:.15,transparent:true,opacity:.64,depthWrite:true,side:THREE.DoubleSide})
      mesh.frustumCulled=false
      const wire=new THREE.SkinnedMesh(mesh.geometry,new THREE.MeshBasicMaterial({color:0x4debdc,wireframe:true,transparent:true,opacity:.3,depthWrite:false}))
      wire.name='skin-wire-overlay'; wire.position.copy(mesh.position);wire.quaternion.copy(mesh.quaternion);wire.scale.copy(mesh.scale)
      wire.bindMode=mesh.bindMode; wire.bind(mesh.skeleton,mesh.bindMatrix); wire.frustumCulled=false
      mesh.parent.add(wire); rig.wires.push(wire)
    }
    rig.sequence=prepareSequence(rig,frames)
    return rig
  })
  return rig
}

export function updateHumanoid(rig,frame,diagnostics,profile,index=0,calibration='motion') {
  if(!rig.bones) return
  const pose=rig.sequence[index]
  if(calibration!=='motion') {
    for(const [n,b] of Object.entries(rig.bones)) {b.position.copy(rig.rest[n].p);b.quaternion.copy(rig.rest[n].q)}
    rig.bones.Hips.position.set(0,0,0)
    if(calibration==='bend') {rig.bones.LeftForeArm.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),-Math.PI/2));rig.bones.LeftLeg.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),Math.PI/3))}
  } else if(pose) {
    for(const [name,b] of Object.entries(rig.bones)) b.quaternion.copy(pose.quaternions[name])
    rig.bones.Hips.position.copy(pose.root)
  }
  rig.group.visible=calibration!=='motion'||Boolean(pose)
  rig.group.updateMatrixWorld(true)
  for(const mesh of rig.meshes) mesh.skeleton.update()
}
export function setHumanoidMode(rig,mode) {
  rig.mode=mode
  rig.meshes?.forEach(m=>{m.material.opacity=mode==='solid'?.98:.48})
  rig.wires?.forEach(m=>{m.visible=mode!=='solid'})
}
export function disposeHumanoid(rig) {
  rig.disposed=true
  const geometries=new Set(), materials=new Set(),skeletons=new Set()
  rig.group.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)materials.add(o.material);if(o.skeleton)skeletons.add(o.skeleton)})
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());skeletons.forEach(s=>s.dispose())
}
