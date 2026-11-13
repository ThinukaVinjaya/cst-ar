// node build_squad.js  ->  ../models/squad.glb   (npm i @gltf-transform/core @gltf-transform/functions)
const {NodeIO}=require('@gltf-transform/core'); const {getBounds,prune}=require('@gltf-transform/functions');
const RING_RADIUS=0.20, HEIGHT=0.15, COUNT=6, PATROL_SECONDS_PER_LAP=24;   // metres / count
(async()=>{
const io=new NodeIO(); const doc=await io.read('Soldier.glb'); const root=doc.getRoot(); const scene=root.listScenes()[0];
const src=scene.listChildren()[0]; const b=getBounds(scene); const S=HEIGHT/(b.max[1]-b.min[1]);

// ---- bake real-world size into the data (AR viewers read size/ground contact from mesh data, not node scale) ----
const K=S*src.getScale()[0];                       // cm -> metres at final tabletop size
const done=new Set(); const scaleAcc=(a,stride,offs)=>{ if(done.has(a))return; done.add(a); const arr=a.getArray().slice(); for(let i=0;i<arr.length;i+=stride) offs.forEach(o=>arr[i+o]*=K); a.setArray(arr); };
(function walk(n){ if(n!==src && !n.getMesh()) n.setTranslation(n.getTranslation().map(v=>v*K)); n.listChildren().forEach(walk); })(src);
root.listMeshes().forEach(m=>m.listPrimitives().forEach(p=>scaleAcc(p.getAttribute('POSITION'),3,[0,1,2])));
root.listSkins().forEach(sk=>scaleAcc(sk.getInverseBindMatrices(),16,[12,13,14]));
root.listAnimations().forEach(an=>an.listChannels().forEach(ch=>{ if(ch.getTargetPath()==='translation') scaleAcc(ch.getSampler().getOutput(),3,[0,1,2]); }));
src.setScale([1,1,1]);

// ---- bake Character's own rotation (Mixamo is Z-up) into the data so the model is upright with feet on y=0 ----
const Q=src.getRotation(); console.log('Character rotation',Q.map(v=>+v.toFixed(3)));
const qmul=(a,b)=>[a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1], a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0], a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3], a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]];
const rot=(q,v)=>{const p=qmul(qmul(q,[v[0],v[1],v[2],0]),[-q[0],-q[1],-q[2],q[3]]);return [p[0],p[1],p[2]];};
const mat=(q)=>{const [x,y,z,w]=q; return [1-2*(y*y+z*z),2*(x*y+z*w),2*(x*z-y*w),0, 2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w),0, 2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y),0, 0,0,0,1];};
const mm=(A,B)=>{const C=new Array(16).fill(0);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)C[c*4+r]+=A[k*4+r]*B[c*4+k];return C;};
if(Math.abs(Q[3])<0.9999){
  const Rinv=mat([-Q[0],-Q[1],-Q[2],Q[3]]); const seen=new Set();
  root.listMeshes().forEach(m=>m.listPrimitives().forEach(p=>['POSITION','NORMAL'].forEach(nm=>{const a=p.getAttribute(nm); if(!a||seen.has(a))return; seen.add(a); const r=a.getArray().slice(); for(let i=0;i<r.length;i+=3){const v=rot(Q,[r[i],r[i+1],r[i+2]]); r[i]=v[0];r[i+1]=v[1];r[i+2]=v[2];} a.setArray(r);})));
  const sk=new Set(); root.listSkins().forEach(k=>{const a=k.getInverseBindMatrices(); if(sk.has(a))return; sk.add(a); const r=a.getArray().slice(); for(let i=0;i<r.length;i+=16){const n=mm(Array.from(r.slice(i,i+16)),Rinv); for(let j=0;j<16;j++)r[i+j]=n[j];} a.setArray(r);});
  const hips=src.listChildren().filter(n=>!n.getMesh());
  hips.forEach(h=>{h.setTranslation(rot(Q,h.getTranslation())); h.setRotation(qmul(Q,h.getRotation()));});
  root.listAnimations().forEach(an=>an.listChannels().forEach(ch=>{ if(!hips.includes(ch.getTargetNode()))return; const o=ch.getSampler().getOutput(); if(seen.has(o))return; seen.add(o); const r=o.getArray().slice();
    if(ch.getTargetPath()==='translation') for(let i=0;i<r.length;i+=3){const v=rot(Q,[r[i],r[i+1],r[i+2]]); r[i]=v[0];r[i+1]=v[1];r[i+2]=v[2];}
    else if(ch.getTargetPath()==='rotation') for(let i=0;i<r.length;i+=4){const v=qmul(Q,[r[i],r[i+1],r[i+2],r[i+3]]); r[i]=v[0];r[i+1]=v[1];r[i+2]=v[2];r[i+3]=v[3];}
    o.setArray(r);}));
  src.setRotation([0,0,0,1]);
}
const srcAnims={}; root.listAnimations().forEach(a=>srcAnims[a.getName()]=a);
// collect subtree
const sub=[]; (function walk(n){sub.push(n); n.listChildren().forEach(walk);})(src);
const ring=doc.createNode('ring'); scene.addChild(ring);
const copies=[];
for(let i=0;i<COUNT;i++){
  const a=2*Math.PI*i/COUNT, wrap=doc.createNode('s'+i);
  wrap.setTranslation([RING_RADIUS*Math.sin(a),0,RING_RADIUS*Math.cos(a)]).setScale([1,1,1]); ring.addChild(wrap);
  const map=new Map();
  sub.filter(n=>n!==src).forEach(n=>{const c=doc.createNode(n.getName()+'_'+i).setTranslation(n.getTranslation()).setRotation(n.getRotation()).setScale(n.getScale()); if(n.getMesh())c.setMesh(n.getMesh()); map.set(n,c);});
  sub.filter(n=>n!==src).forEach(n=>{const c=map.get(n); if(n.getMesh()) scene.addChild(c); else if(n.getParentNode()===src) wrap.addChild(c); else map.get(n.getParentNode()).addChild(c);
    const sk=n.getSkin(); if(sk){const ns=doc.createSkin(sk.getName()+'_'+i).setInverseBindMatrices(sk.getInverseBindMatrices()); if(sk.getSkeleton())ns.setSkeleton(map.get(sk.getSkeleton())); sk.listJoints().forEach(j=>ns.addJoint(map.get(j))); c.setSkin(ns);}});
  copies.push({a,wrap,map});
}
const q=(ang)=>[0,Math.sin(ang/2),0,Math.cos(ang/2)];
const acc=(arr,type)=>doc.createAccessor().setArray(new Float32Array(arr.flat())).setType(type).setBuffer(root.listBuffers()[0]);
const chan=(anim,node,path,times,vals,type)=>{const s=doc.createAnimationSampler().setInput(acc(times,'SCALAR')).setOutput(acc(vals,type)).setInterpolation('LINEAR');
  anim.addSampler(s); anim.addChannel(doc.createAnimationChannel().setTargetNode(node).setTargetPath(path).setSampler(s));};
function build(name,srcName,cycles,patrol){
  const an=srcAnims[srcName], anim=doc.createAnimation(name); let D=0;
  const chs=an.listChannels();
  chs.forEach(ch=>{const t=ch.getSampler().getInput().getArray(); D=Math.max(D,t[t.length-1]);});
  const T=D*cycles;
  const shared=new Map();   // one tiled sampler per source channel, reused by all soldiers
  chs.forEach(ch=>{const s=ch.getSampler(), t=Array.from(s.getInput().getArray()), o=s.getOutput(), w=o.getElementSize(), v=Array.from(o.getArray());
    const times=[],vals=[]; for(let k=0;k<cycles;k++)t.forEach((x,j)=>{if(k>0&&j===0)return; times.push(x+k*D); vals.push(v.slice(j*w,j*w+w));});
    const ns=doc.createAnimationSampler().setInput(acc(times,'SCALAR')).setOutput(acc(vals,o.getType())).setInterpolation('LINEAR');
    anim.addSampler(ns); shared.set(ch,ns);});
  copies.forEach(({a,wrap,map})=>{
    chs.forEach(ch=>anim.addChannel(doc.createAnimationChannel().setTargetNode(map.get(ch.getTargetNode())).setTargetPath(ch.getTargetPath()).setSampler(shared.get(ch))));
    const face=patrol?a-Math.PI/2:a; chan(anim,wrap,'rotation',[0,T],[q(face),q(face)],'VEC4');
  });
  const laps=4, times=[], vals=[]; for(let k=0;k<=laps;k++){times.push(T*k/laps); vals.push(q(patrol?-2*Math.PI*k/laps:0));}
  chan(anim,ring,'rotation',times,vals,'VEC4'); return anim;
}
const walkD=srcAnims.Walk.listChannels()[0].getSampler().getInput().getArray().slice(-1)[0];
build('Patrol','Walk',Math.round(PATROL_SECONDS_PER_LAP/walkD),true);
build('Guard','Idle',4,false);
root.listAnimations().forEach(a=>{if(!['Patrol','Guard'].includes(a.getName()))a.dispose();});
// drop the original un-posed character

const nq=(r,i)=>{const l=Math.hypot(r[i],r[i+1],r[i+2],r[i+3]); for(let j=0;j<4;j++) r[i+j]=Math.max(-1,Math.min(1,r[i+j]/l));};
root.listNodes().forEach(n=>{const r=[...n.getRotation()]; nq(r,0); n.setRotation(r);});
const nd=new Set(); root.listAnimations().forEach(an=>an.listChannels().forEach(ch=>{ if(ch.getTargetPath()!=='rotation')return; const o=ch.getSampler().getOutput(); if(nd.has(o))return; nd.add(o); const r=o.getArray().slice(); for(let i=0;i<r.length;i+=4)nq(r,i); o.setArray(r);}));
src.dispose(); await doc.transform(prune());
await io.write('../models/squad.glb',doc); const fb=getBounds(scene); console.log('final bounds min',fb.min.map(v=>+v.toFixed(3)),'max',fb.max.map(v=>+v.toFixed(3))); console.log('ok, scale',S.toFixed(4));
})();
