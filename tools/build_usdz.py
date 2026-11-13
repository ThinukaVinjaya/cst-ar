"""Builds models/squad.usdz (animated skeleton, for iPhone AR Quick Look) from /tmp/usd/dump.json (see README)."""
import json, math, shutil, os, sys
from pxr import Usd, UsdGeom, UsdSkel, UsdShade, Sdf, Gf, Vt, UsdUtils
D=json.load(open('/tmp/usd/dump.json')); N=D['N']; FPS=D['fps']
RING_RADIUS, COUNT = 0.20, 6
out='/tmp/usd/squad.usda'
st=Usd.Stage.CreateNew(out); UsdGeom.SetStageUpAxis(st,UsdGeom.Tokens.y); UsdGeom.SetStageMetersPerUnit(st,1.0)
st.SetTimeCodesPerSecond(FPS); st.SetStartTimeCode(0); st.SetEndTimeCode(N-1)
st.GetRootLayer().customLayerData={'autoPlay':True,'playbackMode':'loop'}   # Quick Look reads these
world=UsdGeom.Xform.Define(st,'/World'); st.SetDefaultPrim(world.GetPrim())
# Apple 'preliminary anchoring': Quick Look places the scene on the first horizontal surface by itself (no tap to place)
from pxr import Sdf as _S
world.GetPrim().SetMetadata('apiSchemas',_S.TokenListOp.CreateExplicit(['Preliminary_AnchoringAPI']))
world.GetPrim().CreateAttribute('preliminary:anchoring:type',_S.ValueTypeNames.Token,custom=False).Set('plane')
world.GetPrim().CreateAttribute('preliminary:planeAnchoring:alignment',_S.ValueTypeNames.Token,custom=False).Set('horizontal')
ring=UsdGeom.Xform.Define(st,'/World/Ring'); rop=ring.AddRotateYOp()
for f in range(N): rop.Set(-360.0*f/N, Usd.TimeCode(f))        # one full lap over the loop

J=D['joints']; nj=len(J); names=[j['name'].replace(':','_') for j in J]
paths=[None]*nj
def jp(i):
    if paths[i] is None: paths[i]=names[i] if J[i]['parent']<0 else jp(J[i]['parent'])+'/'+names[i]
    return paths[i]
joints=Vt.TokenArray([jp(i) for i in range(nj)])
bind=Vt.Matrix4dArray([Gf.Matrix4d(*j['ibm']).GetInverse() for j in J])
def mk(t,q,s): return UsdSkel.MakeTransform(Gf.Vec3f(*t),Gf.Quatf(q[0],Gf.Vec3f(*q[1:])),Gf.Vec3h(*s))
rest=Vt.Matrix4dArray([mk(j['T'],[j['Q'][3],j['Q'][0],j['Q'][1],j['Q'][2]],j['S']) for j in J])

# shared animation
anim=UsdSkel.Animation.Define(st,'/World/Anim'); anim.CreateJointsAttr(joints)
ta,ra,sa=anim.CreateTranslationsAttr(),anim.CreateRotationsAttr(),anim.CreateScalesAttr()
for f,fr in enumerate(D['frames']):
    tc=Usd.TimeCode(f)
    ta.Set(Vt.Vec3fArray([Gf.Vec3f(*v[0:3]) for v in fr]),tc)
    ra.Set(Vt.QuatfArray([Gf.Quatf(v[3],Gf.Vec3f(v[4],v[5],v[6])) for v in fr]),tc)
    sa.Set(Vt.Vec3hArray([Gf.Vec3h(*v[7:10]) for v in fr]),tc)

# materials
mats=[]
for k,m in enumerate(D['meshes']):
    mp=f'/World/Looks/M{k}'; mat=UsdShade.Material.Define(st,mp); sh=UsdShade.Shader.Define(st,mp+'/Surf'); sh.CreateIdAttr('UsdPreviewSurface')
    sh.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(0.8); sh.CreateInput('metallic',Sdf.ValueTypeNames.Float).Set(0.0)
    if m['tex']:
        rd=UsdShade.Shader.Define(st,mp+'/St'); rd.CreateIdAttr('UsdPrimvarReader_float2'); rd.CreateInput('varname',Sdf.ValueTypeNames.Token).Set('st'); rd.CreateOutput('result',Sdf.ValueTypeNames.Float2)
        tx=UsdShade.Shader.Define(st,mp+'/Tex'); tx.CreateIdAttr('UsdUVTexture'); tx.CreateInput('file',Sdf.ValueTypeNames.Asset).Set('tex/'+m['tex'])
        tx.CreateInput('st',Sdf.ValueTypeNames.Float2).ConnectToSource(rd.ConnectableAPI(),'result'); tx.CreateInput('sourceColorSpace',Sdf.ValueTypeNames.Token).Set('sRGB'); tx.CreateOutput('rgb',Sdf.ValueTypeNames.Float3)
        sh.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).ConnectToSource(tx.ConnectableAPI(),'rgb')
    else: sh.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*m['color'][:3]))
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(),'surface'); mats.append(mat)

for i in range(COUNT):
    a=2*math.pi*i/COUNT; sp=f'/World/Ring/S{i}'
    x=UsdGeom.Xform.Define(st,sp); x.AddTranslateOp().Set(Gf.Vec3d(RING_RADIUS*math.sin(a),0,RING_RADIUS*math.cos(a))); x.AddRotateYOp().Set(math.degrees(a-math.pi/2))
    root=UsdSkel.Root.Define(st,sp+'/Rig'); sk=UsdSkel.Skeleton.Define(st,sp+'/Rig/Skel')
    sk.CreateJointsAttr(joints); sk.CreateBindTransformsAttr(bind); sk.CreateRestTransformsAttr(rest)
    UsdSkel.BindingAPI.Apply(sk.GetPrim()).CreateAnimationSourceRel().SetTargets([Sdf.Path('/World/Anim')])
    UsdSkel.BindingAPI.Apply(root.GetPrim()).CreateSkeletonRel().SetTargets([sk.GetPath()])
    for k,m in enumerate(D['meshes']):
        me=UsdGeom.Mesh.Define(st,f'{sp}/Rig/Mesh{k}')
        pts=m['pos']; n=len(pts)//3
        me.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*pts[j*3:j*3+3]) for j in range(n)]))
        me.CreateFaceVertexCountsAttr(Vt.IntArray([3]*(len(m['idx'])//3))); me.CreateFaceVertexIndicesAttr(Vt.IntArray(m['idx']))
        me.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(*m['nrm'][j*3:j*3+3]) for j in range(n)])); me.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
        me.CreateSubdivisionSchemeAttr('none')
        if m['uv']:
            pv=UsdGeom.PrimvarsAPI(me).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,UsdGeom.Tokens.vertex)
            pv.Set(Vt.Vec2fArray([Gf.Vec2f(m['uv'][j*2],1-m['uv'][j*2+1]) for j in range(n)]))
        b=UsdSkel.BindingAPI.Apply(me.GetPrim()); b.CreateSkeletonRel().SetTargets([sk.GetPath()])
        b.CreateJointIndicesPrimvar(False,4).Set(Vt.IntArray([int(v) for v in m['jidx']]))
        w=m['w']; ws=[]
        for j in range(n):
            q=w[j*4:j*4+4]; s=sum(q) or 1.0; ws+= [v/s for v in q]
        b.CreateJointWeightsPrimvar(False,4).Set(Vt.FloatArray(ws))
        b.CreateGeomBindTransformAttr(Gf.Matrix4d(1))
        UsdShade.MaterialBindingAPI.Apply(me.GetPrim()).Bind(mats[k])
st.GetRootLayer().Save()
os.chdir('/tmp/usd')
dst='/home/claude/cst-ar/models/squad.usdz'
ok=UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath(out),dst)
print('ARKit package ok:',ok, os.path.getsize(dst) if os.path.exists(dst) else None)
