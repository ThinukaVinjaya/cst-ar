// node build_squad.js  ->  ../models/squad.glb   (npm i @gltf-transform/core @gltf-transform/functions)
const {NodeIO}=require('@gltf-transform/core'); const {getBounds,prune}=require('@gltf-transform/functions');
const RING_RADIUS=0.20, HEIGHT=0.15, COUNT=6, PATROL_SECONDS_PER_LAP=24;   // metres / count
(async()=>{
const io=new NodeIO(); const doc=await io.read('Soldier.glb'); const root=doc.getRoot(); const scene=root.listScenes()[0];
const src=scene.listChildren()[0]; const b=getBounds(scene); const S=HEIGHT/(b.max[1]-b.min[1]);
const srcAnims={}; root.listAnimations().forEach(a=>srcAnims[a.getName()]=a);
// collect subtree
const sub=[]; (function walk(n){sub.push(n); n.listChildren().forEach(walk);})(src);
const ring=doc.createNode('ring'); scene.addChild(ring);
const copies=[];
for(let i=0;i<COUNT;i++){
  const a=2*Math.PI*i/COUNT, wrap=doc.createNode('s'+i);
  wrap.setTranslation([RING_RADIUS*Math.sin(a),0,RING_RADIUS*Math.cos(a)]).setScale([S*src.getScale()[0],S*src.getScale()[0],S*src.getScale()[0]]); ring.addChild(wrap);
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
src.dispose(); await doc.transform(prune());
await io.write('../models/squad.glb',doc); console.log('ok, scale',S.toFixed(4));
})();
