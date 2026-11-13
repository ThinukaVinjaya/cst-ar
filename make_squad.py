"""
Builds models/squad.glb : animated soldiers in a ring around an EMPTY centre (your physical loot box).
Two animation clips inside the file:  "Patrol" (walking around the box)  and  "Guard" (standing, breathing).
Usage:  python3 make_squad.py
Tune the 4 settings below. (Custom character models: animate them in Blender and replace models/squad.glb.)
"""
import numpy as np, trimesh, math
from trimesh.visual import ColorVisuals
from pygltflib import GLTF2, Animation, AnimationSampler, AnimationChannel, AnimationChannelTarget, Accessor, BufferView

RING_RADIUS_M, SOLDIER_HEIGHT_M, COUNT = 0.20, 0.14, 6
S = SOLDIER_HEIGHT_M / 1.95            # model is built ~1.95 units tall
LOOKS = [((70,85,55),(60,70,45),(40,50,35),(214,170,140)),
         ((35,35,38),(28,28,30),(20,20,22),(30,30,30)),
         ((105,95,70),(90,82,60),(60,55,40),(200,160,130))]

def paint(m, rgb):
    m.visual = ColorVisuals(mesh=m, face_colors=np.tile(list(rgb)+[255], (len(m.faces),1))); return m
def box(sz, c, rgb):
    m = trimesh.creation.box(sz); m.apply_translation(c); return paint(m, rgb)
def ball(r, c, rgb, sy=1):
    m = trimesh.creation.uv_sphere(radius=r); m.apply_scale([1,sy,1]); m.apply_translation(c); return paint(m, rgb)

sc = trimesh.Scene()
sc.graph.update(frame_to='ring', frame_from='world')
meta = {}   # node name -> (translation, scale)
def add(name, geom, parent, t=(0,0,0), s=1.0):
    sc.add_geometry(geom, node_name=name, geom_name=name+'_g', parent_node_name=parent,
                    transform=trimesh.transformations.translation_matrix(t))
    meta[name] = (t, s)
def empty(name, parent, t=(0,0,0), s=1.0):
    sc.graph.update(frame_to=name, frame_from=parent, matrix=trimesh.transformations.translation_matrix(t))
    meta[name] = (t, s)

for i in range(COUNT):
    a = 2*math.pi*i/COUNT
    cloth, vest, dark, skin = LOOKS[i % 3][0], LOOKS[i % 3][1], LOOKS[i % 3][2], LOOKS[i % 3][3]
    empty(f's{i}', 'ring', (RING_RADIUS_M*math.sin(a), 0, RING_RADIUS_M*math.cos(a)), S)
    empty(f'body{i}', f's{i}')
    for side, x in (('L',-.14),('R',.14)):
        add(f'leg{side}{i}', box([.22,.85,.26],(0,-.425,0),cloth), f'body{i}', (x,.85,0))
    for side, x in (('L',-.36),('R',.36)):
        add(f'arm{side}{i}', box([.17,.6,.2],(0,-.3,0),cloth), f'body{i}', (x,1.55,.05))
    torso = trimesh.util.concatenate([box([.5,.2,.3],(0,.95,0),dark), box([.52,.6,.32],(0,1.28,0),vest),
        ball(.19,(0,1.72,0),skin), ball(.22,(0,1.78,0),dark,.75), box([.07,.07,.8],(.12,1.18,.42),(25,25,25))])
    add(f'torso{i}', torso, f'body{i}')

sc.export('models/squad.glb')
g = GLTF2().load('models/squad.glb')
idx = {n.name: k for k, n in enumerate(g.nodes) if n.name}
for name, (t, s) in meta.items():            # force plain TRS on every node so rotation can be animated
    n = g.nodes[idx[name]]; n.matrix = None
    n.translation = [float(v) for v in t]; n.rotation = [0,0,0,1]; n.scale = [s,s,s] if s != 1.0 else None
g.nodes[idx['ring']].matrix = None; g.nodes[idx['ring']].rotation = [0,0,0,1]

blob = bytearray(g.binary_blob() or b'')
def accessor(arr, typ, ctype):
    global blob
    while len(blob) % 4: blob += b'\0'
    arr = np.asarray(arr, dtype=np.float32); off = len(blob); blob += arr.tobytes()
    g.bufferViews.append(BufferView(buffer=0, byteOffset=off, byteLength=arr.nbytes))
    g.accessors.append(Accessor(bufferView=len(g.bufferViews)-1, componentType=5126, count=len(arr),
        type=typ, min=[float(arr.min())] if typ=='SCALAR' else None, max=[float(arr.max())] if typ=='SCALAR' else None))
    return len(g.accessors)-1
def quat_y(a): return [0, math.sin(a/2), 0, math.cos(a/2)]
def quat_x(a): return [math.sin(a/2), 0, 0, math.cos(a/2)]

def clip(name, T, fn):
    anim = Animation(name=name, samplers=[], channels=[])
    def chan(node, path, times, vals, typ):
        anim.samplers.append(AnimationSampler(input=accessor(times,'SCALAR',5126), output=accessor(vals,typ,5126), interpolation='LINEAR'))
        anim.channels.append(AnimationChannel(sampler=len(anim.samplers)-1, target=AnimationChannelTarget(node=idx[node], path=path)))
    fn(chan, T); g.animations.append(anim)

def patrol(chan, T):
    times = np.arange(0, T+1e-6, 0.5)
    chan('ring','rotation',[0,5,10,15,20],[quat_y(-k*math.pi/2) for k in range(5)],'VEC4')
    for i in range(COUNT):
        a = 2*math.pi*i/COUNT
        chan(f's{i}','rotation',[0,T],[quat_y(a-math.pi/2)]*2,'VEC4')
        ph = np.sin(times*2*math.pi/1.0)               # 1 step cycle per second
        for side, sgn in (('L',1),('R',-1)):
            chan(f'leg{side}{i}','rotation',times,[quat_x(sgn*.55*p) for p in ph],'VEC4')
            chan(f'arm{side}{i}','rotation',times,[quat_x(-sgn*.4*p) for p in ph],'VEC4')
        chan(f'body{i}','translation',times,[[0,.05*abs(p),0] for p in ph],'VEC3')
def guard(chan, T):
    for i in range(COUNT):
        a = 2*math.pi*i/COUNT
        chan('ring','rotation',[0,T],[quat_y(0)]*2,'VEC4') if i==0 else None
        chan(f's{i}','rotation',[0,T],[quat_y(a)]*2,'VEC4')
        chan(f'body{i}','translation',[0,T/2,T],[[0,0,0],[0,.035,0],[0,0,0]],'VEC3')
        for side in 'LR':
            chan(f'leg{side}{i}','rotation',[0,T],[quat_x(0)]*2,'VEC4')
            chan(f'arm{side}{i}','rotation',[0,T/2,T],[quat_x(0),quat_x(.08),quat_x(0)],'VEC4')
clip('Patrol', 20.0, patrol)
clip('Guard', 4.0, guard)
g.buffers[0].byteLength = len(blob); g.set_binary_blob(bytes(blob)); g.save('models/squad.glb')
print('saved models/squad.glb  animations:', [a.name for a in g.animations])
