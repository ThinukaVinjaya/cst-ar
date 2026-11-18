#!/usr/bin/env python3
"""
Builds models/ghost_salute.usdz (native UsdSkel animated skeleton + 64-byte ARKit alignment)
directly from models/ghost_salute.glb for iPhone Safari Apple AR Quick Look.
"""
import struct, json, os, zlib, math

GLB_PATH = 'models/ghost_salute.glb'
OUT_USDZ = 'models/ghost_salute.usdz'

class ArkitUsdzWriter:
    def __init__(self, filename):
        self.f = open(filename, 'wb')
        self.entries = []

    def add_file(self, arcname, data):
        cur_offset = self.f.tell()
        arcname_bytes = arcname.encode('utf-8')
        name_len = len(arcname_bytes)
        base_len = cur_offset + 30 + name_len
        pad_needed = (64 - (base_len % 64)) % 64
        if pad_needed < 4:
            pad_needed += 64
        extra = struct.pack('<HH', 0x1986, pad_needed - 4) + b'\x00' * (pad_needed - 4)
        extra_len = len(extra)
        data_offset = cur_offset + 30 + name_len + extra_len
        assert data_offset % 64 == 0, f'Offset {data_offset} not 64-byte aligned!'
        crc = zlib.crc32(data) & 0xffffffff
        size = len(data)
        self.f.write(struct.pack('<4s5H3I2H', b'PK\x03\x04', 20, 0, 0, 0, 0, crc, size, size, name_len, extra_len))
        self.f.write(arcname_bytes)
        self.f.write(extra)
        self.f.write(data)
        self.entries.append({'name': arcname_bytes, 'crc': crc, 'size': size, 'offset': cur_offset, 'extra': extra})

    def close(self):
        cd_start = self.f.tell()
        for e in self.entries:
            self.f.write(struct.pack('<4s6H3I5H2I', b'PK\x01\x02', 20, 20, 0, 0, 0, 0,
                                     e['crc'], e['size'], e['size'], len(e['name']), len(e['extra']), 0, 0, 0, 0, e['offset']))
            self.f.write(e['name'])
            self.f.write(e['extra'])
        cd_len = self.f.tell() - cd_start
        self.f.write(struct.pack('<4s4H2IH', b'PK\x05\x06', 0, 0, len(self.entries), len(self.entries), cd_len, cd_start, 0))
        self.f.close()

def mat4_from_tr(t, q):
    x, y, z, w = q
    return [
        1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w), 0.0,
        2*(x*y-z*w), 1-2*(x*x+z*z), 2*(y*z+x*w), 0.0,
        2*(x*z+y*w), 2*(y*z-x*w), 1-2*(x*x+y*y), 0.0,
        float(t[0]), float(t[1]), float(t[2]), 1.0
    ]

def mm_col(A, B):
    return [sum(A[k*4+r]*B[c*4+k] for k in range(4)) for c in range(4) for r in range(4)]

def inv_mat4_col(M):
    A = [[M[c*4+r] for c in range(4)] + [1.0 if r==c else 0.0 for c in range(4)] for r in range(4)]
    for i in range(4):
        piv = max(range(i, 4), key=lambda r: abs(A[r][i]))
        A[i], A[piv] = A[piv], A[i]
        div = A[i][i]
        if abs(div) < 1e-12:
            return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
        A[i] = [v / div for v in A[i]]
        for r in range(4):
            if r != i:
                f = A[r][i]
                A[r] = [A[r][c] - f * A[i][c] for c in range(8)]
    return [A[r][4+c] for c in range(4) for r in range(4)]

def fmt_mat4_usd(m):
    return '( ' + ', '.join(
        '(' + ', '.join(f'{m[r*4+c]:.6f}' for c in range(4)) + ')'
        for r in range(4)
    ) + ' )'

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

    # 1. Unified skeleton in topological parent-before-child order starting at mixamorig:Hips
    hips_idx = next(i for i, n in enumerate(nodes) if n.get('name') == 'mixamorig:Hips')
    joint_nodes = []
    joint_paths = []
    joint_parent_local = []
    node_to_joint = {}

    def dfs(ni, prefix, parent_ji):
        tok = sanitize_tok(nodes[ni].get('name', f'J_{ni}'))
        path = tok if not prefix else f'{prefix}/{tok}'
        ji = len(joint_nodes)
        joint_nodes.append(ni)
        joint_paths.append(path)
        joint_parent_local.append(parent_ji)
        node_to_joint[ni] = ji
        for ci in nodes[ni].get('children', []):
            dfs(ci, path, ji)

    dfs(hips_idx, '', -1)
    nj = len(joint_nodes)

    joint_ibm = {}
    for sk in g['skins']:
        ibms = read_acc(sk['inverseBindMatrices'])
        for ji_local, jn in enumerate(sk['joints']):
            if jn not in joint_ibm:
                joint_ibm[jn] = ibms[ji_local]

    rest_mats = []
    bind_mats = []
    for ji, jn in enumerate(joint_nodes):
        n = nodes[jn]
        rm = mat4_from_tr(n.get('translation', [0, 0, 0]), n.get('rotation', [0, 0, 0, 1]))
        rest_mats.append(rm)
        if jn in joint_ibm:
            bind_mats.append(inv_mat4_col(joint_ibm[jn]))
        else:
            pji = joint_parent_local[ji]
            bind_mats.append(mm_col(bind_mats[pji], rm) if pji >= 0 else rm)

    # 2. Extract Salute animation frames
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
            anim_r[ni] = vals

    # 3. Extract textures
    tex_files = {}
    for i, img in enumerate(g.get('images', [])):
        bv = bvs[img['bufferView']]
        off = bv.get('byteOffset', 0)
        ext = 'png' if 'png' in img.get('mimeType', '') else 'jpg'
        fname = f'textures/t{i}.{ext}'
        tex_files[i] = (fname, buf[off:off + bv['byteLength']])

    # 4. Build Apple RealityKit-compliant UsdSkel USDA
    L = []
    L.append('#usda 1.0')
    L.append('(')
    L.append('    defaultPrim = "World"')
    L.append('    metersPerUnit = 1')
    L.append('    upAxis = "Y"')
    L.append('    startTimeCode = 0')
    L.append(f'    endTimeCode = {num_frames - 1}')
    L.append('    framesPerSecond = 24')
    L.append('    timeCodesPerSecond = 24')
    L.append('    customLayerData = {')
    L.append('        bool autoPlay = 1')
    L.append('        string playbackMode = "loop"')
    L.append('    }')
    L.append(')')
    L.append('')
    L.append('def Xform "World" (')
    L.append('    apiSchemas = ["Preliminary_AnchoringAPI"]')
    L.append(')')
    L.append('{')
    L.append('    token preliminary:anchoring:type = "plane"')
    L.append('    token preliminary:planeAnchoring:alignment = "horizontal"')
    L.append('')

    # Materials
    L.append('    def Scope "Looks"')
    L.append('    {')
    textures = g.get('textures', [])
    for k, mat in enumerate(g['materials']):
        pbr = mat.get('pbrMetallicRoughness', {})
        bc = pbr.get('baseColorFactor', [1.0, 1.0, 1.0, 1.0])
        rough = pbr.get('roughnessFactor', 0.8)
        metal = pbr.get('metallicFactor', 0.05)
        tf = None
        if 'baseColorTexture' in pbr:
            ti = pbr['baseColorTexture']['index']
            ii = textures[ti]['source']
            tf = tex_files[ii][0]

        L.append(f'        def Material "M{k}"')
        L.append('        {')
        L.append(f'            token outputs:surface.connect = </World/Looks/M{k}/Surf.outputs:surface>')
        L.append('            def Shader "Surf"')
        L.append('            {')
        L.append('                uniform token info:id = "UsdPreviewSurface"')
        if tf:
            L.append(f'                color3f inputs:diffuseColor.connect = </World/Looks/M{k}/Tex.outputs:rgb>')
        else:
            L.append(f'                color3f inputs:diffuseColor = ({bc[0]:.3f}, {bc[1]:.3f}, {bc[2]:.3f})')
        L.append(f'                float inputs:roughness = {rough:.3f}')
        L.append(f'                float inputs:metallic = {metal:.3f}')
        L.append('                token outputs:surface')
        L.append('            }')
        if tf:
            L.append('            def Shader "Tex"')
            L.append('            {')
            L.append('                uniform token info:id = "UsdUVTexture"')
            L.append(f'                asset inputs:file = @{tf}@')
            L.append(f'                float2 inputs:st.connect = </World/Looks/M{k}/St.outputs:result>')
            L.append('                token inputs:sourceColorSpace = "sRGB"')
            L.append('                float3 outputs:rgb')
            L.append('            }')
            L.append('            def Shader "St"')
            L.append('            {')
            L.append('                uniform token info:id = "UsdPrimvarReader_float2"')
            L.append('                token inputs:varname = "st"')
            L.append('                float2 outputs:result')
            L.append('            }')
        L.append('        }')
    L.append('    }')
    L.append('')

    joints_tok_str = ', '.join(f'"{p}"' for p in joint_paths)
    ones = ', '.join('(1, 1, 1)' for _ in range(nj))

    # SkelRoot containing Skeleton + nested SkelAnimation + 12 Skinned Meshes
    L.append('    def SkelRoot "Rig" (')
    L.append('        prepend apiSchemas = ["SkelBindingAPI"]')
    L.append('    )')
    L.append('    {')
    L.append('        rel skel:skeleton = </World/Rig/Skel>')
    L.append('        rel skel:animationSource = </World/Rig/Skel/Anim>')
    L.append('')
    L.append('        def Skeleton "Skel" (')
    L.append('            prepend apiSchemas = ["SkelBindingAPI"]')
    L.append('        )')
    L.append('        {')
    L.append(f'            uniform token[] joints = [{joints_tok_str}]')
    L.append('            uniform matrix4d[] bindTransforms = [' + ', '.join(fmt_mat4_usd(m) for m in bind_mats) + ']')
    L.append('            uniform matrix4d[] restTransforms = [' + ', '.join(fmt_mat4_usd(m) for m in rest_mats) + ']')
    L.append('            rel skel:animationSource = </World/Rig/Skel/Anim>')
    L.append('')
    L.append('            def SkelAnimation "Anim"')
    L.append('            {')
    L.append(f'                uniform token[] joints = [{joints_tok_str}]')
    L.append('                float3[] translations.timeSamples = {')
    for f_idx in range(num_frames):
        ts = []
        for jn in joint_nodes:
            v = anim_t[jn][f_idx] if jn in anim_t else nodes[jn].get('translation', [0, 0, 0])
            ts.append(f'({v[0]:.5f}, {v[1]:.5f}, {v[2]:.5f})')
        L.append(f'                    {f_idx}: [{", ".join(ts)}],')
    L.append('                }')
    L.append('                quatf[] rotations.timeSamples = {')
    for f_idx in range(num_frames):
        rs = []
        for jn in joint_nodes:
            q = anim_r[jn][f_idx] if jn in anim_r else nodes[jn].get('rotation', [0, 0, 0, 1])
            rs.append(f'({q[3]:.5f}, {q[0]:.5f}, {q[1]:.5f}, {q[2]:.5f})')
        L.append(f'                    {f_idx}: [{", ".join(rs)}],')
    L.append('                }')
    L.append('                half3[] scales.timeSamples = {')
    for f_idx in range(num_frames):
        L.append(f'                    {f_idx}: [{ones}],')
    L.append('                }')
    L.append('            }')
    L.append('        }')

    mesh_nodes = [n for n in nodes if n.get('mesh') is not None]
    for k, mn in enumerate(mesh_nodes):
        mi = mn['mesh']
        si = mn['skin']
        sk = g['skins'][si]
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

        remap = [node_to_joint[jn] for jn in sk['joints']]
        flat_ji = []
        flat_jw = []
        for j4, w4 in zip(jidxs, wgts):
            s = sum(w4) or 1.0
            for c in range(4):
                flat_ji.append(str(remap[int(j4[c])]))
                flat_jw.append(f'{w4[c]/s:.3f}')

        n_faces = len(idxs) // 3
        L.append(f'        def Mesh "Mesh{k}" (')
        L.append('            prepend apiSchemas = ["MaterialBindingAPI", "SkelBindingAPI"]')
        L.append('        )')
        L.append('        {')
        L.append(f'            rel material:binding = </World/Looks/M{mat_idx}>')
        L.append('            rel skel:skeleton = </World/Rig/Skel>')
        L.append('            uniform token subdivisionScheme = "none"')
        L.append('            matrix4d primvars:skel:geomBindTransform = ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) )')
        L.append('            point3f[] points = [' + ', '.join(f'({p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f})' for p in pts) + ']')
        L.append('            int[] faceVertexCounts = [' + ', '.join(['3'] * n_faces) + ']')
        L.append('            int[] faceVertexIndices = [' + ', '.join(str(i) for i in idxs) + ']')
        L.append('            normal3f[] normals = [' + ', '.join(f'({n[0]:.3f}, {n[1]:.3f}, {n[2]:.3f})' for n in nrms) + '] (')
        L.append('                interpolation = "vertex"')
        L.append('            )')
        L.append('            texCoord2f[] primvars:st = [' + ', '.join(f'({u[0]:.3f}, {1.0 - u[1]:.3f})' for u in uvs) + '] (')
        L.append('                interpolation = "vertex"')
        L.append('            )')
        L.append('            int[] primvars:skel:jointIndices = [' + ', '.join(flat_ji) + '] (')
        L.append('                elementSize = 4')
        L.append('                interpolation = "vertex"')
        L.append('            )')
        L.append('            float[] primvars:skel:jointWeights = [' + ', '.join(flat_jw) + '] (')
        L.append('                elementSize = 4')
        L.append('                interpolation = "vertex"')
        L.append('            )')
        L.append('        }')

    L.append('    }')
    L.append('}')

    usda_bytes = '\n'.join(L).encode('utf-8')
    print(f'Generated UsdSkel USDA: {len(usda_bytes)/1048576:.2f} MB ({nj} joints, {num_frames} frames)')

    w = ArkitUsdzWriter(OUT_USDZ)
    w.add_file('ghost_salute.usda', usda_bytes)
    for _, (fname, img_bytes) in tex_files.items():
        w.add_file(fname, img_bytes)
    w.close()
    print(f'Built 64-byte aligned animated USDZ: {OUT_USDZ} ({os.path.getsize(OUT_USDZ)/1048576:.2f} MB)')

if __name__ == '__main__':
    build_salute_usdz()
