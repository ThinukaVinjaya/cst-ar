import fs from 'fs';
import {NodeIO} from '@gltf-transform/core';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
const io=new NodeIO(); const doc=await io.read('/home/claude/cst-ar/models/squad.glb'); const R=doc.getRoot();
fs.mkdirSync('/tmp/usd/tex',{recursive:true});
// textures per material
const info={meshes:[]};
const nodes=R.listNodes().filter(n=>n.getMesh()&&n.getName().endsWith('_0'));
const skin0=nodes[0].getSkin(); const joints=skin0.listJoints(); const ibm=Array.from(skin0.getInverseBindMatrices().getArray());
info.joints=joints.map((j,i)=>({name:j.getName(),parent:joints.indexOf(j.getParentNode()),T:j.getTranslation(),Q:j.getRotation(),S:j.getScale(),ibm:ibm.slice(i*16,i*16+16)}));
nodes.forEach((n,k)=>{const p=n.getMesh().listPrimitives()[0]; const mat=p.getMaterial(); const tex=mat&&mat.getBaseColorTexture(); let file=null;
  if(tex){const ext=tex.getMimeType()==='image/png'?'png':'jpg'; file='tex'+k+'.'+ext; fs.writeFileSync('/tmp/usd/tex/'+file,tex.getImage());}
  const get=(nm)=>{const a=p.getAttribute(nm);return a?Array.from(a.getArray()):null};
  const bc=mat?mat.getBaseColorFactor():[1,1,1,1];
  info.meshes.push({name:n.getName(),pos:get('POSITION'),nrm:get('NORMAL'),uv:get('TEXCOORD_0'),jidx:get('JOINTS_0'),w:get('WEIGHTS_0'),idx:Array.from(p.getIndices().getArray()),tex:file,color:bc,alpha:mat?mat.getAlphaMode():'OPAQUE'});});
// sample Patrol with three (textures stripped)
R.listTextures().forEach(t=>t.dispose()); R.listMaterials().forEach(m=>{m.setBaseColorTexture(null);m.setNormalTexture(null);m.setMetallicRoughnessTexture(null);m.setEmissiveTexture(null);m.setOcclusionTexture(null)});
const glb=await io.writeBinary(doc);
const gltf=await new Promise((res,rej)=>new GLTFLoader().parse(glb.buffer.slice(glb.byteOffset,glb.byteOffset+glb.byteLength),'',res,rej));
const root=gltf.scene, clip=gltf.animations.find(a=>a.name==='Patrol'); const mixer=new THREE.AnimationMixer(root); mixer.clipAction(clip).play();
const san=n=>THREE.PropertyBinding.sanitizeNodeName(n); const objs=info.joints.map(j=>root.getObjectByName(san(j.name)));
const FPS=30; const walkD=clip.tracks.find(t=>t.name.includes('Hips_0')&&t.name.endsWith('quaternion')).times; // find single-cycle length
// find walk cycle length: first time where Hips quaternion returns to start
const hq=clip.tracks.find(t=>/Hips_0\.quaternion/.test(t.name)); const d=hq.times[hq.times.length-1]; 
info.walkD=null; // determine below
mixer.update(0); const frames=[]; const N=Math.round(clip.duration*FPS);
info.fps=FPS; info.N=N; info.dur=clip.duration;
for(let f=0;f<N;f++){ mixer.setTime(f/FPS); root.updateMatrixWorld(true);
  frames.push(objs.map(o=>[o.position.x,o.position.y,o.position.z,o.quaternion.w,o.quaternion.x,o.quaternion.y,o.quaternion.z,o.scale.x,o.scale.y,o.scale.z].map(v=>+v.toFixed(6)))); }
info.frames=frames;
const ring=root.getObjectByName('ring'); info.ringY=[];
for(let f=0;f<N;f++){mixer.setTime(f/FPS); info.ringY.push(+ring.rotation.y.toFixed(5));}
fs.writeFileSync('/tmp/usd/dump.json',JSON.stringify(info));
console.log('joints',joints.length,'meshes',info.meshes.map(m=>m.name+' v'+m.pos.length/3+' t'+m.idx.length/3+' '+m.tex),'frames',N,'dur',clip.duration.toFixed(2));
