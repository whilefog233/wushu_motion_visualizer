import fs from 'node:fs'
import * as THREE from 'three'
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'

globalThis.FileReader = class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(data => { this.result = data; this.onloadend?.() }) }
  readAsDataURL(blob) { blob.arrayBuffer().then(data => { this.result = `data:${blob.type};base64,${Buffer.from(data).toString('base64')}`; this.onloadend?.() }) }
}
const source = '../data/asset-audit/beta/Packages/jp.keijiro.beta'
const bytes = fs.readFileSync(`${source}/Runtime/Beta.fbx`)
const model = new FBXLoader().parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '')
model.updateMatrixWorld(true)
const audit = []
model.traverse(mesh => {
  if (!mesh.isSkinnedMesh) return
  mesh.material = new THREE.MeshStandardMaterial({color: 0x193948})
  const weights = mesh.geometry.attributes.skinWeight
  const indices = mesh.geometry.attributes.skinIndex
  if (!weights || !indices) throw new Error('Skin weights absent')
  let invalid = 0, blended = 0
  for (let i=0;i<weights.count;i++) {
    const w=[weights.getX(i),weights.getY(i),weights.getZ(i),weights.getW(i)]
    if (Math.abs(w.reduce((a,b)=>a+b,0)-1)>0.002 || w.some(x=>!Number.isFinite(x)||x<0)) invalid++
    if(w.filter(x=>x>0.001).length>1) blended++
  }
  if(invalid) throw new Error(`Invalid weights: ${invalid}`)
  audit.push({mesh:mesh.name,vertices:weights.count,blended,invalid,bones:mesh.skeleton.bones.map(b=>({name:b.name,parent:b.parent?.name,position:b.getWorldPosition(new THREE.Vector3()).toArray()}))})
})
if(!audit.length) throw new Error('No SkinnedMesh')
console.log(JSON.stringify(audit,null,2))
fs.mkdirSync('public/models/beta',{recursive:true})
const glb=await new GLTFExporter().parseAsync(model,{binary:true,onlyVisible:true,animations:[]})
fs.writeFileSync('public/models/beta/human.glb',Buffer.from(glb))
fs.copyFileSync(`${source}/LICENSE`,'public/models/beta/LICENSE.txt')
fs.writeFileSync('public/models/beta/audit.json',JSON.stringify(audit,null,2))
