#!/usr/bin/env python3
"""
Builds models/ghost_salute_ar.usdz as an official Apple ARKit binary (.usdc) USDZ package
with Pixar OpenUSD UsdSkel animation from models/ghost_salute.glb:
- 46 pure skinned joints (unused leaf end-effectors pruned)
- bindTransforms aligned 1:1 with world(restTransforms) and raw mesh grounded at y=0..0.25m
- Single merged skinned Mesh with validated GeomSubset material partitions (1 draw call)
- SkelAnimation nested inside SkelRoot and bound on SkelRoot, Skeleton, and Mesh
"""
import json
import math
import os
import shutil
import struct
import tempfile
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, UsdUtils, Vt

GLB_PATH = os.path.abspath('models/ghost_salute.glb')
OUT_USDZ = os.path.abspath('models/ghost_salute_ar.usdz')


def sanitize_tok(name):
    return ''.join(c if c.isalnum() or c == '_' else '_' for c in name)


def build_salute_usdz():
    with open(GLB_PATH, 'rb') as f:
        f.read(12)
        c0, _ = struct.unpack('<II', f.read(8))
        g = json.loads(f.read(c0).decode('utf-8'))
        c1, _ = struct.unpack('<II', f.read(8))
        buf = f.read(c1)

    accs = g['accessors']
    bvs = g['bufferViews']
    nodes = g['nodes']

    def read_acc(idx):
        a = accs[idx]
        bv = bvs[a['bufferView']]
        off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        ncomp = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
        fc = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}[a['componentType']]
        sz = struct.calcsize('<' + fc * ncomp)
        stride = bv.get('byteStride', sz)
        out = []
        for i in range(a['count']):
            vals = struct.unpack_from('<' + fc * ncomp, buf, off + i * stride)
            out.append(vals[0] if ncomp == 1 else list(vals))
        return out

    # Collect all joints actually used by any skin (plus all their ancestors back to Hips)
    joint_ibm = {}
    for sk in g['skins']:
        ibms = read_acc(sk['inverseBindMatrices'])
        for ji_local, jn in enumerate(sk['joints']):
            if jn not in joint_ibm:
                joint_ibm[jn] = ibms[ji_local]

    parent_of = {}
    for pi, n in enumerate(nodes):
        for ci in n.get('children', []):
            parent_of[ci] = pi

    hips_idx = next(i for i, n in enumerate(nodes) if n.get('name') == 'mixamorig:Hips')
    keep_nodes = set(joint_ibm.keys())
    for jn in list(keep_nodes):
        cur = jn
        while cur in parent_of and cur != hips_idx:
            cur = parent_of[cur]
            keep_nodes.add(cur)
    keep_nodes.add(hips_idx)

    # 1. Topological skeleton containing ONLY the 46 skinned joints (no unused leaf end-bones)
    joint_nodes = []
    joint_paths = []
    joint_parent = []
    node_to_joint = {}

    def dfs(ni, prefix, parent_ji):
        if ni not in keep_nodes:
            return
        tok = sanitize_tok(nodes[ni].get('name', f'J_{ni}'))
        path = tok if not prefix else f'{prefix}/{tok}'
        ji = len(joint_nodes)
        joint_nodes.append(ni)
        joint_paths.append(path)
        joint_parent.append(parent_ji)
        node_to_joint[ni] = ji
        for ci in nodes[ni].get('children', []):
            dfs(ci, path, ji)

    dfs(hips_idx, '', -1)
    nj = len(joint_nodes)

    # Compute restTransforms and raw bindTransforms
    rest_mats = []
    world_rest_mats = []
    raw_bind_mats = []
    for ji, jn in enumerate(joint_nodes):
        n = nodes[jn]
        t = n.get('translation', [0.0, 0.0, 0.0])
        q = n.get('rotation', [0.0, 0.0, 0.0, 1.0])
        s = n.get('scale', [1.0, 1.0, 1.0])
        ql = math.hypot(q[0], q[1], q[2], q[3]) or 1.0
        rm = UsdSkel.MakeTransform(
            Gf.Vec3f(float(t[0]), float(t[1]), float(t[2])),
            Gf.Quatf(float(q[3] / ql), Gf.Vec3f(float(q[0] / ql), float(q[1] / ql), float(q[2] / ql))),
            Gf.Vec3h(float(s[0]), float(s[1]), float(s[2])),
        )
        rest_mats.append(rm)
        pji = joint_parent[ji]
        world_rest_mats.append(rm * world_rest_mats[pji] if pji >= 0 else rm)
        if jn in joint_ibm:
            raw_bind_mats.append(Gf.Matrix4d(*joint_ibm[jn]).GetInverse())
        else:
            raw_bind_mats.append(world_rest_mats[-1])

    # Align bind pose with rest pose so bindTransforms == world(restTransforms) and mesh stands on y=0!
    # Shifting BOTH points and bindTransforms by the exact same translation preserves skinning identically.
    align_delta = world_rest_mats[0].ExtractTranslation() - raw_bind_mats[0].ExtractTranslation()
    shift_mat = Gf.Matrix4d(1.0)
    shift_mat.SetTranslate(align_delta)
    bind_mats = [bm * shift_mat for bm in raw_bind_mats]

    max_bind_rest_diff = max(
        (bind_mats[i].ExtractTranslation() - world_rest_mats[i].ExtractTranslation()).GetLength()
        for i in range(nj)
    )
    print(f'Skeleton: {nj} pure skinned joints, bind/rest alignment delta={align_delta}, max residual={max_bind_rest_diff:.6f}m')

    # 2. Extract Salute animation frames (normalized, hemisphere-continuous quaternions)
    anim = g['animations'][0]
    anim_t = {}
    anim_r = {}
    num_frames = 0
    for ch in anim['channels']:
        ni = ch['target']['node']
        path = ch['target']['path']
        vals = read_acc(anim['samplers'][ch['sampler']]['output'])
        num_frames = max(num_frames, len(vals))
        if path == 'translation':
            anim_t[ni] = vals
        elif path == 'rotation':
            clean = []
            prev = None
            for q in vals:
                ql = math.hypot(q[0], q[1], q[2], q[3]) or 1.0
                q = [q[0] / ql, q[1] / ql, q[2] / ql, q[3] / ql]
                if prev is not None and (prev[0]*q[0] + prev[1]*q[1] + prev[2]*q[2] + prev[3]*q[3]) < 0:
                    q = [-q[0], -q[1], -q[2], -q[3]]
                clean.append(q)
                prev = q
            anim_r[ni] = clean

    # 3. Build binary .usdc stage + textures inside temp dir, then package with official Pixar ARKit packager
    tmpdir = tempfile.mkdtemp(prefix='ghost_usdz_')
    old_cwd = os.getcwd()
    try:
        tex_dir = os.path.join(tmpdir, 'tex')
        os.makedirs(tex_dir, exist_ok=True)
        tex_rel = {}
        for i, img in enumerate(g.get('images', [])):
            bv = bvs[img['bufferView']]
            off = bv.get('byteOffset', 0)
            ext = 'png' if 'png' in img.get('mimeType', '') else 'jpg'
            fname = f't{i}.{ext}'
            with open(os.path.join(tex_dir, fname), 'wb') as tf:
                tf.write(buf[off:off + bv['byteLength']])
            tex_rel[i] = f'tex/{fname}'

        usda_path = os.path.join(tmpdir, 'ghost_salute_ar.usda')
        st = Usd.Stage.CreateNew(usda_path)
        UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(st, 1.0)
        st.SetTimeCodesPerSecond(24.0)
        st.SetFramesPerSecond(24.0)
        st.SetStartTimeCode(0)
        st.SetEndTimeCode(num_frames - 1)
        st.GetRootLayer().customLayerData = {'autoPlay': True, 'playbackMode': 'loop'}

        world = UsdGeom.Xform.Define(st, '/World')
        st.SetDefaultPrim(world.GetPrim())
        world.GetPrim().SetMetadata('apiSchemas', Sdf.TokenListOp.CreateExplicit(['Preliminary_AnchoringAPI']))
        world.GetPrim().CreateAttribute('preliminary:anchoring:type', Sdf.ValueTypeNames.Token, custom=False).Set('plane')
        world.GetPrim().CreateAttribute('preliminary:planeAnchoring:alignment', Sdf.ValueTypeNames.Token, custom=False).Set('horizontal')

        # Materials under /World/Looks
        textures = g.get('textures', [])
        mats = []
        for k, mat in enumerate(g['materials']):
            pbr = mat.get('pbrMetallicRoughness', {})
            bc = pbr.get('baseColorFactor', [1.0, 1.0, 1.0, 1.0])
            rough = float(pbr.get('roughnessFactor', 0.8))
            metal = float(pbr.get('metallicFactor', 0.05))
            mp = f'/World/Looks/M{k}'
            umat = UsdShade.Material.Define(st, mp)
            sh = UsdShade.Shader.Define(st, mp + '/Surf')
            sh.CreateIdAttr('UsdPreviewSurface')
            sh.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(rough)
            sh.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(metal)
            if 'baseColorTexture' in pbr:
                ti = pbr['baseColorTexture']['index']
                ii = textures[ti]['source']
                rd = UsdShade.Shader.Define(st, mp + '/St')
                rd.CreateIdAttr('UsdPrimvarReader_float2')
                rd.CreateInput('varname', Sdf.ValueTypeNames.Token).Set('st')
                rd.CreateOutput('result', Sdf.ValueTypeNames.Float2)

                tx = UsdShade.Shader.Define(st, mp + '/Tex')
                tx.CreateIdAttr('UsdUVTexture')
                tx.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(tex_rel[ii])
                tx.CreateInput('st', Sdf.ValueTypeNames.Float2).ConnectToSource(rd.ConnectableAPI(), 'result')
                tx.CreateInput('sourceColorSpace', Sdf.ValueTypeNames.Token).Set('sRGB')
                tx.CreateOutput('rgb', Sdf.ValueTypeNames.Float3)

                sh.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).ConnectToSource(tx.ConnectableAPI(), 'rgb')
            else:
                sh.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(float(bc[0]), float(bc[1]), float(bc[2])))
            umat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), 'surface')
            mats.append(umat)

        joints_vt = Vt.TokenArray(joint_paths)
        bind_vt = Vt.Matrix4dArray(bind_mats)
        rest_vt = Vt.Matrix4dArray(rest_mats)

        # Clean flat SkelRoot at /World/Rig with Skeleton, SkelAnimation, and 1 merged skinned Mesh
        root = UsdSkel.Root.Define(st, '/World/Rig')
        sk = UsdSkel.Skeleton.Define(st, '/World/Rig/Skel')
        sk.CreateJointsAttr(joints_vt)
        sk.CreateBindTransformsAttr(bind_vt)
        sk.CreateRestTransformsAttr(rest_vt)

        anim_prim = UsdSkel.Animation.Define(st, '/World/Rig/Skel/Anim')
        anim_prim.CreateJointsAttr(joints_vt)
        ta = anim_prim.CreateTranslationsAttr()
        ra = anim_prim.CreateRotationsAttr()
        sa = anim_prim.CreateScalesAttr()
        ones_vt = Vt.Vec3hArray([Gf.Vec3h(1, 1, 1) for _ in range(nj)])

        for f_idx in range(num_frames):
            tc = Usd.TimeCode(f_idx)
            ts = []
            rs = []
            for jn in joint_nodes:
                v = anim_t[jn][f_idx] if jn in anim_t else nodes[jn].get('translation', [0.0, 0.0, 0.0])
                ts.append(Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])))
                q = anim_r[jn][f_idx] if jn in anim_r else nodes[jn].get('rotation', [0.0, 0.0, 0.0, 1.0])
                ql = math.hypot(q[0], q[1], q[2], q[3]) or 1.0
                rs.append(Gf.Quatf(float(q[3] / ql), Gf.Vec3f(float(q[0] / ql), float(q[1] / ql), float(q[2] / ql))))
            ta.Set(Vt.Vec3fArray(ts), tc)
            ra.Set(Vt.QuatfArray(rs), tc)
            sa.Set(ones_vt, tc)

        # Bind skeleton & animationSource consistently on SkelRoot and Skeleton
        root_b = UsdSkel.BindingAPI.Apply(root.GetPrim())
        root_b.CreateSkeletonRel().SetTargets([sk.GetPath()])
        root_b.CreateAnimationSourceRel().SetTargets([anim_prim.GetPath()])

        sk_b = UsdSkel.BindingAPI.Apply(sk.GetPrim())
        sk_b.CreateAnimationSourceRel().SetTargets([anim_prim.GetPath()])

        # Merge all 12 visible meshes into ONE single skinned Mesh with 12 GeomSubset material partitions
        all_pts = []
        all_nrms = []
        all_uvs = []
        all_ji = []
        all_jw = []
        all_idxs = []
        subsets = []

        mesh_nodes = [n for n in nodes if n.get('mesh') is not None]
        v_offset = 0
        f_offset = 0
        dx, dy, dz = float(align_delta[0]), float(align_delta[1]), float(align_delta[2])

        for k, mn in enumerate(mesh_nodes):
            mi = mn['mesh']
            si = mn['skin']
            sk_g = g['skins'][si]
            prim = g['meshes'][mi]['primitives'][0]
            mat_idx = prim.get('material', 0)

            pbr_m = g['materials'][mat_idx].get('pbrMetallicRoughness', {})
            bc_m = pbr_m.get('baseColorFactor', [1, 1, 1, 1])
            if len(bc_m) > 3 and bc_m[3] == 0:
                continue

            pts = read_acc(prim['attributes']['POSITION'])
            nrms = read_acc(prim['attributes']['NORMAL'])
            uvs = read_acc(prim['attributes']['TEXCOORD_0'])
            jidxs = read_acc(prim['attributes']['JOINTS_0'])
            wgts = read_acc(prim['attributes']['WEIGHTS_0'])
            idxs = read_acc(prim['indices'])

            remap = [node_to_joint[jn] for jn in sk_g['joints']]
            for p in pts:
                all_pts.append(Gf.Vec3f(float(p[0]) + dx, float(p[1]) + dy, float(p[2]) + dz))
            for n in nrms:
                all_nrms.append(Gf.Vec3f(float(n[0]), float(n[1]), float(n[2])))
            for u in uvs:
                all_uvs.append(Gf.Vec2f(float(u[0]), float(1.0 - u[1])))

            for j4, w4 in zip(jidxs, wgts):
                s_w = sum(w4) or 1.0
                for c in range(4):
                    w_norm = float(w4[c] / s_w)
                    # Pad zero-weight slots with joint 0 (clean RealityKit convention)
                    j_mapped = int(remap[int(j4[c])]) if w_norm > 0.0 else 0
                    all_ji.append(j_mapped)
                    all_jw.append(w_norm)

            n_faces = len(idxs) // 3
            for i_val in idxs:
                all_idxs.append(int(i_val) + v_offset)

            subsets.append((k, mat_idx, list(range(f_offset, f_offset + n_faces))))
            v_offset += len(pts)
            f_offset += n_faces

        me = UsdGeom.Mesh.Define(st, '/World/Rig/Ghost')
        me.CreatePointsAttr(Vt.Vec3fArray(all_pts))
        me.CreateFaceVertexCountsAttr(Vt.IntArray([3] * f_offset))
        me.CreateFaceVertexIndicesAttr(Vt.IntArray(all_idxs))
        me.CreateNormalsAttr(Vt.Vec3fArray(all_nrms))
        me.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
        me.CreateSubdivisionSchemeAttr('none')

        pv = UsdGeom.PrimvarsAPI(me).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
        pv.Set(Vt.Vec2fArray(all_uvs))

        mb = UsdSkel.BindingAPI.Apply(me.GetPrim())
        mb.CreateSkeletonRel().SetTargets([sk.GetPath()])
        mb.CreateAnimationSourceRel().SetTargets([anim_prim.GetPath()])
        mb.CreateJointIndicesPrimvar(False, 4).Set(Vt.IntArray(all_ji))
        mb.CreateJointWeightsPrimvar(False, 4).Set(Vt.FloatArray(all_jw))
        mb.CreateGeomBindTransformAttr(Gf.Matrix4d(1))

        UsdGeom.Subset.SetFamilyType(me, UsdShade.Tokens.materialBind, UsdGeom.Tokens.partition)
        for k, mat_idx, face_ids in subsets:
            sub = UsdGeom.Subset.CreateGeomSubset(
                me, f'Sub{k}', UsdGeom.Tokens.face, Vt.IntArray(face_ids),
                UsdShade.Tokens.materialBind, UsdGeom.Tokens.partition
            )
            UsdShade.MaterialBindingAPI.Apply(sub.GetPrim()).Bind(mats[mat_idx])

        ok_fam, reason = UsdGeom.Subset.ValidateFamily(me, UsdGeom.Tokens.face, UsdShade.Tokens.materialBind)
        assert ok_fam, f'GeomSubset validation failed: {reason}'

        st.GetRootLayer().Save()
        del st

        os.chdir(tmpdir)
        ok = UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath('ghost_salute_ar.usda'), OUT_USDZ)
        os.chdir(old_cwd)
        assert ok and os.path.exists(OUT_USDZ), 'UsdUtils.CreateNewARKitUsdzPackage failed!'
        print(f'Built official Pixar ARKit binary USDZ: {OUT_USDZ} ({os.path.getsize(OUT_USDZ)/1048576:.2f} MB, 1 merged mesh / {len(subsets)} subsets, {v_offset} verts, {f_offset} tris, {nj} joints, {num_frames} frames)')
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    build_salute_usdz()
