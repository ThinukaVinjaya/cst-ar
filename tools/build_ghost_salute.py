#!/usr/bin/env python3
"""
Builds models/ghost_salute.glb from models/ghost_salute_raw.glb (converted from Gost Salute.fbx):
1. Bakes exact tabletop real-world scale (25 cm height, boots flush on y = 0) into mesh vertices,
   node translations, skin inverseBindMatrices, and animation translation tracks.
2. Attaches all 13 original PBR materials + compact baseColor textures from the original Ghost model.
3. Renames the Mixamo skeletal clip to "Salute".
"""
import struct, json, os

RAW_GLB = 'models/ghost_salute_raw.glb'
ORIG_TEX_GLB = r'C:\Users\LOQ\.gemini\antigravity\brain\7e0c3c7e-be00-499e-b751-a6e0d806dd3c\.user_uploaded\media_1794564257560_64713d27.glb'
OUT_GLB = 'models/ghost_salute.glb'
TARGET_HEIGHT_M = 0.25  # 25 cm tabletop height

def load_glb(path):
    with open(path, 'rb') as f:
        magic, ver, length = struct.unpack('<4sII', f.read(12))
        c0_len, _ = struct.unpack('<II', f.read(8))
        gltf = json.loads(f.read(c0_len).decode('utf-8'))
        c1_len, _ = struct.unpack('<II', f.read(8))
        buf = bytearray(f.read(c1_len))
    return gltf, buf

def save_glb(path, gltf, buf):
    while len(buf) % 4 != 0:
        buf.append(0)
    gltf['buffers'][0]['byteLength'] = len(buf)
    jbytes = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
    while len(jbytes) % 4 != 0:
        jbytes += b' '
    total = 12 + 8 + len(jbytes) + 8 + len(buf)
    out = bytearray()
    out.extend(struct.pack('<4sII', b'glTF', 2, total))
    out.extend(struct.pack('<II', len(jbytes), 0x4E4F534A))
    out.extend(jbytes)
    out.extend(struct.pack('<II', len(buf), 0x004E4942))
    out.extend(buf)
    with open(path, 'wb') as f:
        f.write(out)

def main():
    g, buf = load_glb(RAW_GLB)
    orig_g, orig_buf = load_glb(ORIG_TEX_GLB)

    # 1. Compute scale factor K to reach TARGET_HEIGHT_M (0.25m)
    accs = g['accessors']
    bvs = g['bufferViews']
    min_y, max_y = 1e9, -1e9
    for m in g['meshes']:
        for p in m['primitives']:
            a = accs[p['attributes']['POSITION']]
            if 'min' in a and 'max' in a:
                min_y = min(min_y, a['min'][1])
                max_y = max(max_y, a['max'][1])
    raw_h = max_y - min_y
    K = TARGET_HEIGHT_M / raw_h
    print(f'Raw height: {raw_h:.5f}m -> baking scale K={K:.4f} for {TARGET_HEIGHT_M}m tabletop height')

    scaled_accs = set()
    def scale_vec3_accessor(acc_idx):
        if acc_idx in scaled_accs:
            return
        scaled_accs.add(acc_idx)
        acc = accs[acc_idx]
        bv = bvs[acc['bufferView']]
        off = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
        stride = bv.get('byteStride', 12)
        mins = [1e9, 1e9, 1e9]
        maxs = [-1e9, -1e9, -1e9]
        for i in range(acc['count']):
            pos = off + i * stride
            x, y, z = struct.unpack_from('<3f', buf, pos)
            x *= K; y *= K; z *= K
            struct.pack_into('<3f', buf, pos, x, y, z)
            if x < mins[0]: mins[0] = x
            if y < mins[1]: mins[1] = y
            if z < mins[2]: mins[2] = z
            if x > maxs[0]: maxs[0] = x
            if y > maxs[1]: maxs[1] = y
            if z > maxs[2]: maxs[2] = z
        if 'min' in acc: acc['min'] = mins
        if 'max' in acc: acc['max'] = maxs

    def scale_ibm_accessor(acc_idx):
        if acc_idx in scaled_accs:
            return
        scaled_accs.add(acc_idx)
        acc = accs[acc_idx]
        bv = bvs[acc['bufferView']]
        off = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
        stride = bv.get('byteStride', 64)
        for i in range(acc['count']):
            pos = off + i * stride
            mat = list(struct.unpack_from('<16f', buf, pos))
            mat[12] *= K
            mat[13] *= K
            mat[14] *= K
            struct.pack_into('<16f', buf, pos, *mat)

    # Scale all mesh POSITIONs
    for m in g['meshes']:
        for p in m['primitives']:
            scale_vec3_accessor(p['attributes']['POSITION'])

    # Scale all node translations
    for n in g['nodes']:
        if 'translation' in n:
            n['translation'] = [v * K for v in n['translation']]

    # Zero all non-bone mesh ancestor nodes (0..23) so Three.js SkinnedMesh bindMatrix is pure Identity (fixes 90-deg face-down bug!)
    for i in range(24):
        n = g['nodes'][i]
        n['translation'] = [0.0, 0.0, 0.0]
        n['rotation'] = [0.0, 0.0, 0.0, 1.0]
        n['scale'] = [1.0, 1.0, 1.0]
    for sk in g.get('skins', []):
        sk['skeleton'] = 24

    # Fix Hips rest translation from Z-up (0,0,0.0099*K) to Y-up (0,0.00987*K,0) so static pose is upright
    for n in g['nodes']:
        if n.get('name') == 'mixamorig:Hips':
            n['translation'] = [0.0, 0.00987 * K, 0.0]

    # Scale all skin inverseBindMatrices
    for sk in g.get('skins', []):
        if 'inverseBindMatrices' in sk:
            scale_ibm_accessor(sk['inverseBindMatrices'])

    # Scale all animation translation channels & rename clip to "Salute"
    for anim in g.get('animations', []):
        anim['name'] = 'Salute'
        for ch in anim['channels']:
            if ch['target'].get('path') == 'translation':
                s = anim['samplers'][ch['sampler']]
                scale_vec3_accessor(s['output'])

    # 2. Attach original 13 materials + compact baseColor textures from ORIG_TEX_GLB
    orig_bvs = orig_g['bufferViews']
    orig_imgs = orig_g['images']
    orig_texs = orig_g['textures']
    orig_mats_by_name = {m.get('name'): m for m in orig_g['materials']}

    g['images'] = []
    g['textures'] = []
    g['samplers'] = [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}]
    copied_imgs = {}  # orig_img_idx -> new_tex_idx

    def add_orig_texture(orig_tex_idx):
        orig_img_idx = orig_texs[orig_tex_idx]['source']
        if orig_img_idx in copied_imgs:
            return copied_imgs[orig_img_idx]
        img = orig_imgs[orig_img_idx]
        bv = orig_bvs[img['bufferView']]
        off = bv.get('byteOffset', 0)
        img_bytes = orig_buf[off:off + bv['byteLength']]

        while len(buf) % 4 != 0:
            buf.append(0)
        new_off = len(buf)
        buf.extend(img_bytes)
        bvs.append({'buffer': 0, 'byteOffset': new_off, 'byteLength': len(img_bytes)})
        g['images'].append({'bufferView': len(bvs) - 1, 'mimeType': img['mimeType']})
        g['textures'].append({'sampler': 0, 'source': len(g['images']) - 1})
        tex_idx = len(g['textures']) - 1
        copied_imgs[orig_img_idx] = tex_idx
        return tex_idx

    new_mats = []
    for m in g['materials']:
        name = m.get('name', '')
        om = orig_mats_by_name.get(name)
        if om:
            opbr = om.get('pbrMetallicRoughness', {})
            pbr = {
                'roughnessFactor': opbr.get('roughnessFactor', 0.8),
                'metallicFactor': opbr.get('metallicFactor', 0.05)
            }
            if 'baseColorFactor' in opbr:
                pbr['baseColorFactor'] = opbr['baseColorFactor']
            if 'baseColorTexture' in opbr:
                t_idx = add_orig_texture(opbr['baseColorTexture']['index'])
                pbr['baseColorTexture'] = {'index': t_idx}
            nm = {'name': name, 'pbrMetallicRoughness': pbr}
            if 'alphaMode' in om:
                nm['alphaMode'] = om['alphaMode']
            if 'alphaCutoff' in om:
                nm['alphaCutoff'] = om['alphaCutoff']
            if 'doubleSided' in om:
                nm['doubleSided'] = om['doubleSided']
            new_mats.append(nm)
        else:
            new_mats.append(m)
    g['materials'] = new_mats

    save_glb(OUT_GLB, g, buf)
    sz = os.path.getsize(OUT_GLB) / 1048576
    print(f'Built {OUT_GLB}: {sz:.2f} MB ({len(g["images"])} embedded textures, animation: {[a["name"] for a in g["animations"]]})')

if __name__ == '__main__':
    main()
