"""
Builds models/squad.glb : soldiers standing in a ring around an EMPTY centre
(the centre is where your physical loot box sits).

Usage:
  python3 make_squad.py                      # uses generic placeholder soldiers
  python3 make_squad.py price.glb ghost.glb  # uses YOUR character models, repeated around the ring
Options (edit below): RING_RADIUS_M, SOLDIER_HEIGHT_M, COUNT, FACE_OUTWARD
"""
import sys, numpy as np, trimesh
from trimesh.visual import ColorVisuals

RING_RADIUS_M    = 0.20   # distance from loot-box centre to each soldier (metres). Box half-width + ~5 cm
SOLDIER_HEIGHT_M = 0.14   # tabletop figure size (14 cm)
COUNT            = 6      # soldiers around the box
FACE_OUTWARD     = True   # True = guarding the box, False = looking at it

def paint(m, rgb):
    m.visual = ColorVisuals(mesh=m, face_colors=np.tile(list(rgb)+[255], (len(m.faces),1))); return m
def box(sz, pos, rgb):
    m = trimesh.creation.box(sz); m.apply_translation(pos); return paint(m, rgb)
def ball(r, pos, rgb, sy=1):
    m = trimesh.creation.uv_sphere(radius=r); m.apply_scale([1,sy,1]); m.apply_translation(pos); return paint(m, rgb)

def placeholder(uniform, skin_mask):
    """Generic low-poly soldier, ~1.8 units tall, facing +Z."""
    cloth, vest, dark = uniform
    p = [
      box([.22,.85,.26],[-.14,.43,0],cloth), box([.22,.85,.26],[.14,.43,0],cloth),          # legs
      box([.50,.20,.30],[0,.95,0],dark),                                                    # belt
      box([.52,.60,.32],[0,1.28,0],vest),                                                   # torso
      box([.17,.60,.20],[-.36,1.25,.05],cloth), box([.17,.60,.20],[.36,1.25,.05],cloth),    # arms
      ball(.19,[0,1.72,0],skin_mask), ball(.22,[0,1.78,0],dark,.75),                        # head + helmet
      box([.07,.07,.80],[.12,1.18,.42],(25,25,25)),                                         # rifle
    ]
    return trimesh.util.concatenate(p)

def load_normalised(path):
    sc = trimesh.load(path, force='scene')
    m = sc.to_geometry() if hasattr(sc,'to_geometry') else sc.dump(concatenate=True)
    return m

def normalise(mesh):
    b = mesh.bounds
    mesh = mesh.copy()
    mesh.apply_translation([-(b[0][0]+b[1][0])/2, -b[0][1], -(b[0][2]+b[1][2])/2])  # feet on y=0, centred
    mesh.apply_scale(SOLDIER_HEIGHT_M / (b[1][1]-b[0][1]))
    return mesh

sources = []
if len(sys.argv) > 1:
    sources = [normalise(load_normalised(p)) for p in sys.argv[1:]]
else:
    looks = [((70,85,55),(60,70,45),(40,50,35),(214,170,140)),
             ((35,35,38),(28,28,30),(20,20,22),(30,30,30)),
             ((105,95,70),(90,82,60),(60,55,40),(200,160,130))]
    sources = [normalise(placeholder(l[:3], l[3])) for l in looks]

parts = []
for i in range(COUNT):
    ang = 2*np.pi*i/COUNT
    m = sources[i % len(sources)].copy()
    face = ang if FACE_OUTWARD else ang+np.pi          # model faces +Z by default
    m.apply_transform(trimesh.transformations.rotation_matrix(face, [0,1,0]))
    m.apply_translation([RING_RADIUS_M*np.sin(ang), 0, RING_RADIUS_M*np.cos(ang)])
    parts.append(m)
trimesh.util.concatenate(parts).export('models/squad.glb')
print('saved models/squad.glb with', COUNT, 'soldiers')
