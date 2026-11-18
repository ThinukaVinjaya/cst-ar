#!/usr/bin/env python3
"""
Builds models/ghost_salute_v6.usdz from simplified models/ghost_salute_lite.glb (~42K tris)
mirroring Apple's official 2025 AR Quick Look animated skeletal USDZ (robot.usdz):
- 42,357 tris / 41,848 verts (matching Apple robot.usdz 42K tris, well under 100K mobile limit)
- defaultPrim is `def SkelRoot "GhostSalute" (kind = "component")` with animated `extent.timeSamples`
- metersPerUnit = 0.01 (centimeters, 25 cm height = 0..25.0), 30 fps
- Static identity `root` joint at index 0 (`root/mixamorig_Hips/...`), bindTransforms == world(restTransforms)
- Per-mesh elementSize <= len(skel:joints) with ZERO duplicate joint indices on every vertex
- Constant `half3[] scales` on SkelAnimation and `GeomSubset` materialBind partitions
"""
import json
import math
import os
import shutil
import struct
import tempfile
from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, UsdUtils, Vt

GLB_PATH = os.path.abspath('models/ghost_salute_lite.glb')
OUT_USDZ = os.path.abspath('models/ghost_salute_v6.usdz')
CM = 100.0


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

    norm_div = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}

    def read_acc(idx):
        a = accs[idx]
        bv = bvs[a['bufferView']]
        off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        ncomp = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
        ct = a['componentType']
        fc = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}[ct]
        sz = struct.calcsize('<' + fc * ncomp)
        stride = bv.get('byteStride', sz)
        is_norm = a.get('normalized', False) and ct in norm_div
        div = norm_div.get(ct, 1.0)
        signed = ct in (5120, 5122)
        out = []
        for i in range(a['count']):
            vals = struct.unpack_from('<' + fc * ncomp, buf, off + i * stride)
            if is_norm:
                vals = tuple(max(v / div, -1.0) if signed else (v / div) for v in vals)
            out.append(vals[0] if ncomp == 1 else list(vals))
        return out

    # Collect all joints used by any skin (+ ancestors back to Hips)
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

    # 1. Build topological skeleton with synthetic identity `root` at index 0
    joint_nodes = [None]
    joint_paths = ['root']
    joint_parent = [-1]
    node_to_joint = {}

    def dfs(ni, prefix, parent_ji):
        if ni not in keep_nodes:
            return
        tok = sanitize_tok(nodes[ni].get('name', f'J_{ni}'))
        path = f'{prefix}/{tok}'
        ji = len(joint_nodes)
        joint_nodes.append(ni)
        joint_paths.append(path)
        joint_parent.append(parent_ji)
        node_to_joint[ni] = ji
        for ci in nodes[ni].get('children', []):
            dfs(ci, path, ji)

    dfs(hips_idx, 'root', 0)
    nj = len(joint_nodes)

    rest_mats = [Gf.Matrix4d(1.0)]
    world_rest_mats = [Gf.Matrix4d(1.0)]
    raw_bind_mats = [Gf.Matrix4d(1.0)]

    for ji in range(1, nj):
        jn = joint_nodes[ji]
        n = nodes[jn]
        t = n.get('translation', [0.0, 0.0, 0.0])
        q = n.get('rotation', [0.0, 0.0, 0.0, 1.0])
        s = n.get('scale', [1.0, 1.0, 1.0])
        ql = math.hypot(q[0], q[1], q[2], q[3]) or 1.0
        rm = UsdSkel.MakeTransform(
            Gf.Vec3f(float(t[0]) * CM, float(t[1]) * CM, float(t[2]) * CM),
            Gf.Quatf(float(q[3] / ql), Gf.Vec3f(float(q[0] / ql), float(q[1] / ql), float(q[2] / ql))),
            Gf.Vec3h(float(s[0]), float(s[1]), float(s[2])),
        )
        rest_mats.append(rm)
        pji = joint_parent[ji]
        world_rest_mats.append(rm * world_rest_mats[pji])
        if jn in joint_ibm:
            bm_m = Gf.Matrix4d(*joint_ibm[jn]).GetInverse()
            bm_cm = Gf.Matrix4d(bm_m)
            tr = bm_m.ExtractTranslation()
            bm_cm.SetTranslateOnly(Gf.Vec3d(tr[0] * CM, tr[1] * CM, tr[2] * CM))
            raw_bind_mats.append(bm_cm)
        else:
            raw_bind_mats.append(world_rest_mats[-1])

    align_delta = world_rest_mats[1].ExtractTranslation() - raw_bind_mats[1].ExtractTranslation()
    shift_mat = Gf.Matrix4d(1.0)
    shift_mat.SetTranslate(align_delta)
    bind_mats = [Gf.Matrix4d(1.0)] + [bm * shift_mat for bm in raw_bind_mats[1:]]

    # 2. Extract Salute animation frames & compute exact FPS from input times
    anim = g['animations'][0]
    anim_t = {}
    anim_r = {}
    num_frames = 0
    max_time = 2.833333
    for ch in anim['channels']:
        ni = ch['target']['node']
        path = ch['target']['path']
        samp = anim['samplers'][ch['sampler']]
        in_acc = accs[samp['input']]
        if 'max' in in_acc and in_acc['max']:
            max_time = max(max_time, float(in_acc['max'][0]))
        vals = read_acc(samp['output'])
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

    fps = round((num_frames - 1) / max_time) if max_time > 0 else 30
    print(f'Animation: {num_frames} frames over {max_time:.3f}s -> {fps} fps, {nj} joints')

    # 3. Build stage mirroring Apple robot.usdz (Geo -> Rig -> Looks) & compile binary ARKit USDZ
    tmpdir = tempfile.mkdtemp(prefix='ghost_v6_')
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

        usda_path = os.path.join(tmpdir, 'ghost_salute_v6.usda')
        st = Usd.Stage.CreateNew(usda_path)
        UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(st, 0.01)
        st.SetTimeCodesPerSecond(float(fps))
        st.SetFramesPerSecond(float(fps))
        st.SetStartTimeCode(0)
        st.SetEndTimeCode(num_frames - 1)
        st.GetRootLayer().customLayerData = {'autoPlay': True, 'playbackMode': 'loop'}

        root_skel = UsdSkel.Root.Define(st, '/GhostSalute')
        st.SetDefaultPrim(root_skel.GetPrim())
        Usd.ModelAPI(root_skel.GetPrim()).SetKind(Kind.Tokens.component)

        # Materials under /GhostSalute/Looks
        UsdGeom.Scope.Define(st, '/GhostSalute/Looks')
        textures = g.get('textures', [])
        mats = []
        for k, mat in enumerate(g['materials']):
            pbr = mat.get('pbrMetallicRoughness', {})
            bc = pbr.get('baseColorFactor', [1.0, 1.0, 1.0, 1.0])
            rough = float(pbr.get('roughnessFactor', 0.8))
            metal = float(pbr.get('metallicFactor', 0.05))
            mp = f'/GhostSalute/Looks/M{k}'
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

        # Define Skeleton path early (will live at /GhostSalute/Rig/root)
        UsdGeom.Xform.Define(st, '/GhostSalute/Geo')
        UsdGeom.Xform.Define(st, '/GhostSalute/Rig')
        sk = UsdSkel.Skeleton.Define(st, '/GhostSalute/Rig/root')
        joints_vt = Vt.TokenArray(joint_paths)
        sk.CreateJointsAttr(joints_vt)
        sk.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_mats))
        sk.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_mats))

        anim_prim = UsdSkel.Animation.Define(st, '/GhostSalute/Rig/root/Animation')
        anim_prim.CreateJointsAttr(joints_vt)
        ta = anim_prim.CreateTranslationsAttr()
        ra = anim_prim.CreateRotationsAttr()
        anim_prim.CreateScalesAttr().Set(Vt.Vec3hArray([Gf.Vec3h(1, 1, 1) for _ in range(nj)]))

        for f_idx in range(num_frames):
            tc = Usd.TimeCode(f_idx)
            ts = [Gf.Vec3f(0.0, 0.0, 0.0)]
            rs = [Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0))]
            for ji in range(1, nj):
                jn = joint_nodes[ji]
                if jn in anim_t and f_idx < len(anim_t[jn]):
                    v = anim_t[jn][f_idx]
                else:
                    v = nodes[jn].get('translation', [0.0, 0.0, 0.0])
                ts.append(Gf.Vec3f(float(v[0]) * CM, float(v[1]) * CM, float(v[2]) * CM))
                if jn in anim_r and f_idx < len(anim_r[jn]):
                    q = anim_r[jn][f_idx]
                else:
                    q = nodes[jn].get('rotation', [0.0, 0.0, 0.0, 1.0])
                ql = math.hypot(q[0], q[1], q[2], q[3]) or 1.0
                rs.append(Gf.Quatf(float(q[3] / ql), Gf.Vec3f(float(q[0] / ql), float(q[1] / ql), float(q[2] / ql))))
            ta.Set(Vt.Vec3fArray(ts), tc)
            ra.Set(Vt.QuatfArray(rs), tc)

        UsdSkel.BindingAPI.Apply(sk.GetPrim()).CreateAnimationSourceRel().SetTargets([anim_prim.GetPath()])

        # Build 12 lightweight skinned meshes with strict elementSize <= len(skel:joints) and ZERO duplicate joint indices!
        dx, dy, dz = float(align_delta[0]), float(align_delta[1]), float(align_delta[2])
        mesh_nodes = [n for n in nodes if n.get('mesh') is not None]
        built = 0
        tot_v = 0
        tot_t = 0

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

            mesh_joint_tokens = [joint_paths[node_to_joint[jn]] for jn in sk_g['joints']]
            n_mj = len(mesh_joint_tokens)

            # Deduplicate, sort descending, normalize, and compute exact elementSize <= n_mj
            vert_pairs = []
            max_nz = 1
            for j4, w4 in zip(jidxs, wgts):
                merged = {}
                for c in range(4):
                    w = float(w4[c])
                    if w > 1e-5:
                        ji_loc = int(j4[c])
                        merged[ji_loc] = merged.get(ji_loc, 0.0) + w
                if not merged:
                    merged[int(j4[0])] = 1.0
                pairs = sorted(merged.items(), key=lambda x: -x[1])[:4]
                sw = sum(w for _, w in pairs) or 1.0
                pairs = [(j, w / sw) for j, w in pairs]
                max_nz = max(max_nz, len(pairs))
                vert_pairs.append(pairs)

            es = min(max_nz, n_mj)
            flat_ji = []
            flat_jw = []
            for pairs in vert_pairs:
                used_set = {j for j, _ in pairs}
                padded = list(pairs[:es])
                # Pad remaining slots with DISTINCT unused joint indices (0.0 weight) -> dups == 0!
                cand = 0
                while len(padded) < es:
                    while cand in used_set and cand < n_mj:
                        cand += 1
                    padded.append((cand % n_mj, 0.0))
                    used_set.add(cand % n_mj)
                    cand += 1
                for j, w in padded:
                    flat_ji.append(int(j))
                    flat_jw.append(float(w))

            n_faces = len(idxs) // 3
            me = UsdGeom.Mesh.Define(st, f'/GhostSalute/Geo/Mesh{k}')
            pts_vt = Vt.Vec3fArray([Gf.Vec3f(float(p[0])*CM + dx, float(p[1])*CM + dy, float(p[2])*CM + dz) for p in pts])
            me.CreatePointsAttr(pts_vt)
            me.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(pts_vt))
            me.CreateFaceVertexCountsAttr(Vt.IntArray([3] * n_faces))
            me.CreateFaceVertexIndicesAttr(Vt.IntArray([int(i) for i in idxs]))
            me.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(float(n[0]), float(n[1]), float(n[2])) for n in nrms]))
            me.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
            me.CreateSubdivisionSchemeAttr('none')

            pv = UsdGeom.PrimvarsAPI(me).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
            pv.Set(Vt.Vec2fArray([Gf.Vec2f(float(u[0]), float(1.0 - u[1])) for u in uvs]))

            b = UsdSkel.BindingAPI.Apply(me.GetPrim())
            b.CreateSkeletonRel().SetTargets([sk.GetPath()])
            b.CreateJointsAttr(Vt.TokenArray(mesh_joint_tokens))
            b.CreateJointIndicesPrimvar(False, es).Set(Vt.IntArray(flat_ji))
            b.CreateJointWeightsPrimvar(False, es).Set(Vt.FloatArray(flat_jw))
            b.CreateGeomBindTransformAttr(Gf.Matrix4d(1))

            UsdShade.MaterialBindingAPI.Apply(me.GetPrim())
            UsdGeom.Subset.SetFamilyType(me, UsdShade.Tokens.materialBind, UsdGeom.Tokens.partition)
            sub = UsdGeom.Subset.CreateGeomSubset(
                me, f'Mat{mat_idx}', UsdGeom.Tokens.face, Vt.IntArray(list(range(n_faces))),
                UsdShade.Tokens.materialBind, UsdGeom.Tokens.partition
            )
            UsdShade.MaterialBindingAPI.Apply(sub.GetPrim()).Bind(mats[mat_idx])
            built += 1
            tot_v += len(pts)
            tot_t += n_faces

        # Compute exact animated extent.timeSamples on SkelRoot (matching Apple robot.usdz!)
        cache = UsdSkel.Cache()
        cache.Populate(root_skel, Usd.TraverseInstanceProxies())
        bindings = cache.ComputeSkelBindings(root_skel, Usd.TraverseInstanceProxies())
        sq = cache.GetSkelQuery(bindings[0].GetSkeleton())
        skin_targets = bindings[0].GetSkinningTargets()
        ext_attr = root_skel.CreateExtentAttr()
        for f_idx in range(num_frames):
            xforms = sq.ComputeSkinningTransforms(f_idx)
            mn_v = Gf.Vec3f(1e9, 1e9, 1e9)
            mx_v = Gf.Vec3f(-1e9, -1e9, -1e9)
            for stg in skin_targets:
                m_pts = Vt.Vec3fArray(UsdGeom.Mesh(stg.GetPrim()).GetPointsAttr().Get())
                stg.ComputeSkinnedPoints(xforms, m_pts)
                e = UsdGeom.PointBased.ComputeExtent(m_pts)
                mn_v = Gf.Vec3f(min(mn_v[0], e[0][0]), min(mn_v[1], e[0][1]), min(mn_v[2], e[0][2]))
                mx_v = Gf.Vec3f(max(mx_v[0], e[1][0]), max(mx_v[1], e[1][1]), max(mx_v[2], e[1][2]))
            ext_attr.Set(Vt.Vec3fArray([mn_v, mx_v]), Usd.TimeCode(f_idx))

        st.GetRootLayer().Save()
        del st

        os.chdir(tmpdir)
        ok = UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath('ghost_salute_v6.usda'), OUT_USDZ)
        os.chdir(old_cwd)
        assert ok and os.path.exists(OUT_USDZ), 'UsdUtils.CreateNewARKitUsdzPackage failed!'
        print(f'Built lightweight Apple-canonical USDZ: {OUT_USDZ} ({os.path.getsize(OUT_USDZ)/1048576:.2f} MB, {built} meshes, {tot_v} verts, {tot_t} tris, {nj} joints, {num_frames} frames @ {fps}fps)')
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    build_salute_usdz()
