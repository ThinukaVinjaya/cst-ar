#!/usr/bin/env python3
"""
Full Remake of Ghost Military Operator with:
1. Dynamic, highly visible HAND ANIMATIONS:
   - Hands raise from ready stance up into combat aiming (moving +24cm up, +22cm forward).
   - Hands lock together into two-handed shooting grip (proportional scale & translation).
   - Intense double-tap weapon recoil kicks on hands, wrists, and upper torso.
   - Tactical reload & re-grip actions.
2. Full Call of Duty 4 Military Perimeter Items:
   - M18A1 Claymore Mine ("FRONT TOWARD ENEMY").
   - 7.62mm NATO Ammo Crates & Cans.
   - CoD4 Intel Laptop with glowing green UAV radar screen.
   - Curved Sandbag Fortification Barricade.
   - C4 Demolition Charge with digital receiver & red LED.
   - Tactical Supply Drop Crate.
3. Enforces ~20cm tabletop clearance around (X=0, Z=0) for physical table centerpiece.
4. Generates both models/ghost_animated.glb (Android) and 64-byte aligned models/ghost_animated.usdz (iOS).
"""
import struct, json, os, zlib, math
from build_ghost_usdz import build_usdz

SOURCE_GLB = r'C:\Users\LOQ\.gemini\antigravity\brain\7e0c3c7e-be00-499e-b751-a6e0d806dd3c\.user_uploaded\media_1794564257560_64713d27.glb'
OUT_GLB = 'models/ghost_animated.glb'
OUT_USDZ = 'models/ghost_animated.usdz'

def euler_to_quat(rx, ry, rz):
    cx, sx = math.cos(rx/2), math.sin(rx/2)
    cy, sy = math.cos(ry/2), math.sin(ry/2)
    cz, sz = math.cos(rz/2), math.sin(rz/2)
    qx = sx*cy*cz - cx*sy*sz
    qy = cx*sy*cz + sx*cy*sz
    qz = cx*cy*sz - sx*sy*cz
    qw = cx*cy*cz + sx*sy*sz
    mag = math.hypot(qx, qy, qz, qw) or 1.0
    return [qx/mag, qy/mag, qz/mag, qw/mag]

def rot(x, z, angle):
    c, s = math.cos(angle), math.sin(angle)
    return x*c - z*s, x*s + z*c

def make_box(dx, dy, dz, cx=0, cy=0, cz=0, rot_y=0):
    hx, hy, hz = dx/2, dy/2, dz/2
    faces = [
        ((0,0,1),  [(-hx,-hy,hz), (hx,-hy,hz), (hx,hy,hz), (-hx,hy,hz)]),
        ((0,0,-1), [(hx,-hy,-hz), (-hx,-hy,-hz), (-hx,hy,-hz), (hx,hy,-hz)]),
        ((1,0,0),  [(hx,-hy,hz), (hx,-hy,-hz), (hx,hy,-hz), (hx,hy,hz)]),
        ((-1,0,0), [(-hx,-hy,-hz), (-hx,-hy,hz), (-hx,hy,hz), (-hx,-hy,-hz)]),
        ((0,1,0),  [(-hx,hy,hz), (hx,hy,hz), (hx,hy,-hz), (-hx,hy,-hz)]),
        ((0,-1,0), [(-hx,-hy,-hz), (hx,-hy,-hz), (hx,hy,hz), (-hx,-hy,hz)]),
    ]
    verts, norms, uvs, idxs = [], [], [], []
    for norm, corners in faces:
        base_idx = len(verts)
        rx_norm, rz_norm = rot(norm[0], norm[2], rot_y)
        r_norm = [rx_norm, norm[1], rz_norm]
        for i, (x, y, z) in enumerate(corners):
            rx, rz = rot(x, z, rot_y)
            verts.append([rx + cx, y + cy, rz + cz])
            norms.append(r_norm)
            u = 1.0 if i in [1, 2] else 0.0
            v = 1.0 if i in [2, 3] else 0.0
            uvs.append([u, v])
        idxs.extend([base_idx, base_idx+1, base_idx+2, base_idx, base_idx+2, base_idx+3])
    return verts, norms, uvs, idxs

def merge_mesh(parts):
    all_v, all_n, all_u, all_i = [], [], [], []
    for v, n, u, i in parts:
        base = len(all_v)
        all_v.extend(v)
        all_n.extend(n)
        all_u.extend(u)
        all_i.extend([idx + base for idx in i])
    return all_v, all_n, all_u, all_i

def create_png(width, height, get_pixel):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            r, g, b, a = get_pixel(x, y)
            raw.extend([r, g, b, a])
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(raw, 9)
    png = bytearray(b'\x89PNG\r\n\x1a\n')
    for tag, data in [(b'IHDR', ihdr), (b'IDAT', idat), (b'IEND', b'')]:
        crc = zlib.crc32(tag + data) & 0xffffffff
        png.extend(struct.pack('>I4s', len(data), tag) + data + struct.pack('>I', crc))
    return bytes(png)

def tex_claymore():
    def get_pixel(x, y):
        r, g, b = 60, 75, 45
        if 42 <= y <= 86 and 14 <= x <= 114:
            if (58 <= y <= 63) or (68 <= y <= 73 and (x % 14 < 7)):
                r, g, b = 215, 200, 65
            elif (46 <= y <= 50) and ((x // 18) % 2 == 0):
                r, g, b = 220, 205, 70
        if x < 4 or x > 123 or y < 4 or y > 123:
            r, g, b = 35, 42, 28
        return r, g, b, 255
    return create_png(128, 128, get_pixel)

def tex_ammo():
    def get_pixel(x, y):
        r, g, b = 50, 62, 38
        if (35 <= y <= 42 and 20 <= x <= 108) or (50 <= y <= 56 and 30 <= x <= 98) or (64 <= y <= 70 and 25 <= x <= 103):
            r, g, b = 205, 195, 160
        if x < 6 or x > 121 or y < 6 or y > 121:
            r, g, b = 32, 38, 25
        return r, g, b, 255
    return create_png(128, 128, get_pixel)

def tex_sandbag():
    def get_pixel(x, y):
        weave = ((x // 4 + y // 4) % 2) * 15
        r = 165 + weave
        g = 145 + weave
        b = 110 + weave
        if y < 8 or y > 120 or x < 6 or x > 122:
            r, g, b = int(r * 0.7), int(g * 0.7), int(b * 0.7)
        return r, g, b, 255
    return create_png(128, 128, get_pixel)

def tex_intel_screen():
    def get_pixel(x, y):
        dx, dy = x - 64, y - 64
        dist_sq = dx*dx + dy*dy
        r, g, b = 8, 28, 12
        if 850 <= dist_sq <= 950 or 2400 <= dist_sq <= 2600 or 4700 <= dist_sq <= 4950:
            r, g, b = 40, 240, 90
        elif abs(dx) <= 1 or abs(dy) <= 1:
            r, g, b = 30, 200, 70
        elif 0 <= dx and 0 <= dy and abs(dx - dy*1.5) < 2:
            r, g, b = 70, 255, 120
        elif ((dx-20)**2 + (dy+25)**2 < 12) or ((dx+32)**2 + (dy-18)**2 < 12):
            r, g, b = 255, 50, 30
        return r, g, b, 255
    return create_png(128, 128, get_pixel)

def tex_c4():
    def get_pixel(x, y):
        r, g, b = 115, 115, 110
        if 20 <= x <= 36 or 92 <= x <= 108:
            r, g, b = 20, 20, 22
        if 48 <= x <= 80 and 45 <= y <= 83:
            r, g, b = 30, 32, 34
            if 58 <= x <= 70 and 58 <= y <= 70:
                r, g, b = 255, 30, 20
        return r, g, b, 255
    return create_png(128, 128, get_pixel)

def remake():
    print(f"Reading original model: {SOURCE_GLB}")
    with open(SOURCE_GLB, 'rb') as f:
        magic, version, length = struct.unpack('<4sII', f.read(12))
        chunk0_len, _ = struct.unpack('<II', f.read(8))
        gltf = json.loads(f.read(chunk0_len).decode('utf-8'))
        chunk1_len, _ = struct.unpack('<II', f.read(8))
        bin_buf = bytearray(f.read(chunk1_len))

    old_accessors = gltf['accessors']
    old_bvs = gltf['bufferViews']

    def read_accessor_bytes(acc_idx):
        acc = old_accessors[acc_idx]
        bv = old_bvs[acc['bufferView']]
        offset = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
        count = acc['count']
        comp_type = acc['componentType']
        typ = acc['type']

        type_map = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
        num_comps = type_map[typ]
        format_map = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
        elem_fmt = format_map[comp_type]
        stride = bv.get('byteStride', struct.calcsize('<' + elem_fmt * num_comps))

        tight_fmt = '<' + elem_fmt * num_comps
        out_bytes = bytearray()
        for i in range(count):
            elem_offset = offset + i * stride
            out_bytes += bin_buf[elem_offset:elem_offset + struct.calcsize(tight_fmt)]
        return bytes(out_bytes), acc

    new_bin = bytearray()
    new_bvs = []
    new_accs = []

    def add_buffer_data(data_bytes, target=None):
        while len(new_bin) % 4 != 0: new_bin.append(0)
        offset = len(new_bin)
        new_bin.extend(data_bytes)
        bv = {'buffer': 0, 'byteOffset': offset, 'byteLength': len(data_bytes)}
        if target: bv['target'] = target
        new_bvs.append(bv)
        return len(new_bvs) - 1

    # 1. Repack character meshes (stripping redundant tangent & extra texcoord channels)
    for m in gltf['meshes']:
        for p in m['primitives']:
            idx_bytes, old_idx_acc = read_accessor_bytes(p['indices'])
            bv_idx = add_buffer_data(idx_bytes, target=34963)
            new_idx_acc = {
                'bufferView': bv_idx, 'componentType': old_idx_acc['componentType'],
                'count': old_idx_acc['count'], 'type': old_idx_acc['type']
            }
            if 'min' in old_idx_acc: new_idx_acc['min'] = old_idx_acc['min']
            if 'max' in old_idx_acc: new_idx_acc['max'] = old_idx_acc['max']
            new_accs.append(new_idx_acc)
            p['indices'] = len(new_accs) - 1

            new_attrs = {}
            for attr in ['POSITION', 'NORMAL', 'TEXCOORD_0']:
                if attr in p['attributes']:
                    old_acc_idx = p['attributes'][attr]
                    attr_bytes, old_acc = read_accessor_bytes(old_acc_idx)
                    bv_idx = add_buffer_data(attr_bytes, target=34962)
                    new_acc = {
                        'bufferView': bv_idx, 'componentType': old_acc['componentType'],
                        'count': old_acc['count'], 'type': old_acc['type']
                    }
                    if 'min' in old_acc: new_acc['min'] = old_acc['min']
                    if 'max' in old_acc: new_acc['max'] = old_acc['max']
                    new_accs.append(new_acc)
                    new_attrs[attr] = len(new_accs) - 1
            p['attributes'] = new_attrs

    # 2. Repack character images
    used_tex_indices = set()
    for m in gltf.get('materials', []):
        for k, v in m.items():
            if isinstance(v, dict) and 'index' in v: used_tex_indices.add(v['index'])
        if 'pbrMetallicRoughness' in m:
            for pk, pv in m['pbrMetallicRoughness'].items():
                if isinstance(pv, dict) and 'index' in pv: used_tex_indices.add(pv['index'])

    textures = gltf.get('textures', [])
    old_images = gltf.get('images', [])
    new_images = []
    old_img_to_new = {}

    for t_idx in sorted(list(used_tex_indices)):
        if t_idx < len(textures):
            old_img_idx = textures[t_idx].get('source')
            if old_img_idx is not None and old_img_idx not in old_img_to_new and old_img_idx < len(old_images):
                img = old_images[old_img_idx]
                bv = old_bvs[img['bufferView']]
                offset = bv.get('byteOffset', 0)
                length = bv['byteLength']
                img_data = bin_buf[offset:offset+length]

                new_bv_idx = add_buffer_data(img_data)
                new_img = {'bufferView': new_bv_idx, 'mimeType': img['mimeType']}
                if 'name' in img: new_img['name'] = img['name']
                new_images.append(new_img)
                old_img_to_new[old_img_idx] = len(new_images) - 1

    for t in textures:
        if 'source' in t and t['source'] in old_img_to_new:
            t['source'] = old_img_to_new[t['source']]
    gltf['images'] = new_images

    # 3. Build CoD4 Military Perimeter Props
    claymore_parts = [
        make_box(0.32, 0.20, 0.08, cx=0.75, cy=0.14, cz=1.75, rot_y=-0.45),
        make_box(0.02, 0.12, 0.16, cx=0.75, cy=0.06, cz=1.75, rot_y=-0.45),
        make_box(0.04, 0.04, 0.04, cx=0.70, cy=0.25, cz=1.73, rot_y=-0.45),
        make_box(0.04, 0.04, 0.04, cx=0.80, cy=0.25, cz=1.77, rot_y=-0.45),
    ]
    clay_v, clay_n, clay_u, clay_i = merge_mesh(claymore_parts)

    ammo_parts = [
        make_box(0.65, 0.38, 0.42, cx=1.55, cy=0.19, cz=0.55, rot_y=0.25),
        make_box(0.67, 0.06, 0.44, cx=1.55, cy=0.36, cz=0.55, rot_y=0.25),
        make_box(0.32, 0.22, 0.18, cx=1.45, cy=0.49, cz=0.55, rot_y=-0.15),
        make_box(0.32, 0.22, 0.18, cx=1.35, cy=0.11, cz=0.95, rot_y=0.55),
    ]
    ammo_v, ammo_n, ammo_u, ammo_i = merge_mesh(ammo_parts)

    intel_parts = [
        make_box(0.55, 0.35, 0.45, cx=-1.45, cy=0.175, cz=0.55, rot_y=-0.25),
        make_box(0.36, 0.03, 0.28, cx=-1.45, cy=0.365, cz=0.55, rot_y=-0.25),
        make_box(0.36, 0.26, 0.025, cx=-1.45, cy=0.49, cz=0.42, rot_y=-0.25),
    ]
    intel_v, intel_n, intel_u, intel_i = merge_mesh(intel_parts)
    screen_v, screen_n, screen_u, screen_i = make_box(0.30, 0.20, 0.005, cx=-1.45, cy=0.49, cz=0.435, rot_y=-0.25)

    sandbag_parts = [
        make_box(0.48, 0.14, 0.25, cx=1.25, cy=0.07, cz=1.30, rot_y=0.40),
        make_box(0.48, 0.14, 0.25, cx=1.48, cy=0.07, cz=0.90, rot_y=0.75),
        make_box(0.48, 0.14, 0.25, cx=1.65, cy=0.07, cz=0.45, rot_y=1.10),
        make_box(0.48, 0.14, 0.25, cx=1.68, cy=0.07, cz=-0.05, rot_y=1.45),
        make_box(0.48, 0.14, 0.25, cx=1.38, cy=0.20, cz=1.10, rot_y=0.55),
        make_box(0.48, 0.14, 0.25, cx=1.58, cy=0.20, cz=0.68, rot_y=0.90),
        make_box(0.48, 0.14, 0.25, cx=1.68, cy=0.20, cz=0.20, rot_y=1.30),
        make_box(0.48, 0.14, 0.25, cx=1.48, cy=0.33, cz=0.88, rot_y=0.75)
    ]
    sand_v, sand_n, sand_u, sand_i = merge_mesh(sandbag_parts)

    c4_parts = [
        make_box(0.24, 0.08, 0.14, cx=-0.75, cy=0.04, cz=1.70, rot_y=0.35),
        make_box(0.08, 0.04, 0.06, cx=-0.75, cy=0.10, cz=1.70, rot_y=0.35),
        make_box(0.01, 0.12, 0.01, cx=-0.72, cy=0.15, cz=1.71, rot_y=0.35),
    ]
    c4_v, c4_n, c4_u, c4_i = merge_mesh(c4_parts)

    crate_parts = [
        make_box(0.75, 0.45, 0.55, cx=-1.55, cy=0.225, cz=-0.05, rot_y=-0.10),
        make_box(0.78, 0.08, 0.58, cx=-1.55, cy=0.42, cz=-0.05, rot_y=-0.10),
    ]
    crate_v, crate_n, crate_u, crate_i = merge_mesh(crate_parts)

    prop_images = [
        ('tex_claymore.png', tex_claymore()),
        ('tex_ammo.png', tex_ammo()),
        ('tex_sandbag.png', tex_sandbag()),
        ('tex_intel.png', tex_intel_screen()),
        ('tex_c4.png', tex_c4()),
    ]
    new_tex_start = len(gltf['textures'])
    new_mat_start = len(gltf['materials'])

    for fname, img_bytes in prop_images:
        bv_idx = add_buffer_data(img_bytes)
        gltf['images'].append({'bufferView': bv_idx, 'mimeType': 'image/png', 'name': fname})
        gltf['textures'].append({'source': len(gltf['images']) - 1})

    gltf['materials'].extend([
        {'name': 'Mat_Claymore', 'pbrMetallicRoughness': {'baseColorTexture': {'index': new_tex_start + 0}, 'roughnessFactor': 0.6, 'metallicFactor': 0.15}},
        {'name': 'Mat_Ammo', 'pbrMetallicRoughness': {'baseColorTexture': {'index': new_tex_start + 1}, 'roughnessFactor': 0.4, 'metallicFactor': 0.75}},
        {'name': 'Mat_Sandbag', 'pbrMetallicRoughness': {'baseColorTexture': {'index': new_tex_start + 2}, 'roughnessFactor': 0.9, 'metallicFactor': 0.0}},
        {'name': 'Mat_Intel_Screen', 'pbrMetallicRoughness': {'baseColorTexture': {'index': new_tex_start + 3}, 'roughnessFactor': 0.2, 'metallicFactor': 0.0}, 'emissiveTexture': {'index': new_tex_start + 3}, 'emissiveFactor': [0.2, 0.9, 0.3]},
        {'name': 'Mat_C4', 'pbrMetallicRoughness': {'baseColorTexture': {'index': new_tex_start + 4}, 'roughnessFactor': 0.7, 'metallicFactor': 0.1}},
        {'name': 'Mat_Supply_Crate', 'pbrMetallicRoughness': {'baseColorTexture': {'index': new_tex_start + 1}, 'roughnessFactor': 0.5, 'metallicFactor': 0.6}},
    ])

    def add_primitive(verts, norms, uvs, idxs, mat_idx):
        idx_bytes = struct.pack(f'<{len(idxs)}H', *idxs)
        idx_bv = add_buffer_data(idx_bytes, target=34963)
        new_accs.append({'bufferView': idx_bv, 'componentType': 5123, 'count': len(idxs), 'type': 'SCALAR'})
        idx_acc = len(new_accs) - 1

        pos_flat = [c for pt in verts for c in pt]
        pos_bytes = struct.pack(f'<{len(pos_flat)}f', *pos_flat)
        pos_bv = add_buffer_data(pos_bytes, target=34962)
        mins = [min(pt[i] for pt in verts) for i in range(3)]
        maxs = [max(pt[i] for pt in verts) for i in range(3)]
        new_accs.append({'bufferView': pos_bv, 'componentType': 5126, 'count': len(verts), 'type': 'VEC3', 'min': mins, 'max': maxs})
        pos_acc = len(new_accs) - 1

        nrm_flat = [c for pt in norms for c in pt]
        nrm_bytes = struct.pack(f'<{len(nrm_flat)}f', *nrm_flat)
        nrm_bv = add_buffer_data(nrm_bytes, target=34962)
        new_accs.append({'bufferView': nrm_bv, 'componentType': 5126, 'count': len(norms), 'type': 'VEC3'})
        nrm_acc = len(new_accs) - 1

        uv_flat = [c for pt in uvs for c in pt]
        uv_bytes = struct.pack(f'<{len(uv_flat)}f', *uv_flat)
        uv_bv = add_buffer_data(uv_bytes, target=34962)
        new_accs.append({'bufferView': uv_bv, 'componentType': 5126, 'count': len(uvs), 'type': 'VEC2'})
        uv_acc = len(new_accs) - 1

        return {'attributes': {'POSITION': pos_acc, 'NORMAL': nrm_acc, 'TEXCOORD_0': uv_acc}, 'indices': idx_acc, 'material': mat_idx}

    prop_prims = [
        add_primitive(clay_v, clay_n, clay_u, clay_i, new_mat_start + 0),
        add_primitive(ammo_v, ammo_n, ammo_u, ammo_i, new_mat_start + 1),
        add_primitive(intel_v, intel_n, intel_u, intel_i, new_mat_start + 1),
        add_primitive(screen_v, screen_n, screen_u, screen_i, new_mat_start + 3),
        add_primitive(sand_v, sand_n, sand_u, sand_i, new_mat_start + 2),
        add_primitive(c4_v, c4_n, c4_u, c4_i, new_mat_start + 4),
        add_primitive(crate_v, crate_n, crate_u, crate_i, new_mat_start + 5),
    ]
    prop_mesh_idx = len(gltf['meshes'])
    gltf['meshes'].append({'name': 'CoD4_Military_Perimeter_Props', 'primitives': prop_prims})
    prop_node_idx = len(gltf['nodes'])
    gltf['nodes'].append({'name': 'CoD4_Military_Props', 'mesh': prop_mesh_idx, 'translation': [0.0, 0.0, 0.0]})
    if prop_node_idx not in gltf['scenes'][0]['nodes']:
        gltf['scenes'][0]['nodes'].append(prop_node_idx)

    # 4. Set Ghost Position on Perimeter (Z = +1.65m)
    # Keeping center (0, 0) completely clear for physical table decoration
    gltf['nodes'][24]['translation'] = [0.0, 0.0, 1.65]

    # 5. Build DYNAMIC COMBAT ANIMATION with FULL HAND MOVEMENTS
    def add_anim_accessor(times, values, typ):
        times_bytes = struct.pack(f'<{len(times)}f', *times)
        bv_time = add_buffer_data(times_bytes)
        acc_time = {'bufferView': bv_time, 'componentType': 5126, 'count': len(times), 'type': 'SCALAR', 'min': [min(times)], 'max': [max(times)]}
        new_accs.append(acc_time)
        acc_time_idx = len(new_accs) - 1

        val_flat = []
        for v in values:
            if isinstance(v, (list, tuple)): val_flat.extend(v)
            else: val_flat.append(v)

        val_bytes = struct.pack(f'<{len(val_flat)}f', *val_flat)
        bv_val = add_buffer_data(val_bytes)
        acc_val = {'bufferView': bv_val, 'componentType': 5126, 'count': len(values), 'type': typ}
        new_accs.append(acc_val)
        acc_val_idx = len(new_accs) - 1
        return acc_time_idx, acc_val_idx

    NODE_HAND = 8       # hand_000_r.model_7 (hands & gloves)
    NODE_UPPR = 22      # uppr_000_u.model_19 (torso)
    NODE_HEAD = 25      # HeadPivot
    NODE_SWAY = 24      # Sway
    NODE_ACCS = 5       # accs_000_u.model_5

    BASE_HAND_T = [0.0, 1.00445, 0.0]
    BASE_UPPR_T = [0.0, 1.00445, 0.0]
    BASE_HEAD_T = [0.0, 1.554, -0.02]
    BASE_ACCS_T = [0.0, 1.00445, 0.0]

    FPS = 30
    DUR = 9.0
    num_frames = int(DUR * FPS) + 1
    times = [i / FPS for i in range(num_frames)]

    hand_t_list, hand_r_list, hand_s_list = [], [], []
    uppr_t_list, uppr_r_list = [], []
    head_t_list, head_r_list = [], []
    accs_t_list, sway_r_list = [], []

    for t in times:
        # Breathing
        p_breath = 2 * math.pi * t / 2.0
        breath = 0.006 * math.sin(p_breath)
        sway = 0.003 * math.cos(p_breath)

        # Combat phases:
        # 0.0s - 2.0s: Ready stance & breathing
        # 2.0s - 3.8s: Hands raise up (+24cm Y, +22cm Z) into combat firing grip
        # 3.8s - 5.5s: 3-round burst fire with sharp hand recoil kicks (shots at 4.0s, 4.4s, 4.8s)
        # 5.5s - 7.2s: Tactical reload / re-grip action
        # 7.2s - 9.0s: Sector scan & smooth return to ready stance
        if t < 2.0:
            p = 2 * math.pi * t / 2.0
            h_y = BASE_HAND_T[1] + 0.08 + 0.012 * math.sin(p)
            h_z = 0.04 + 0.008 * math.sin(p)
            h_sx = 0.88
            h_pitch = 0.04 * math.sin(p)
            h_yaw = 0.0
            recoil = 0.0
            scan_yaw = 0.0
            aim_prog = 0.0
        elif t < 3.8:
            s = (t - 2.0) / 1.8
            prog = (1 - math.cos(s * math.pi)) / 2
            h_y = BASE_HAND_T[1] + 0.08 + 0.24 * prog
            h_z = 0.04 + 0.22 * prog
            h_sx = 0.88 - 0.16 * prog
            h_pitch = -0.22 * prog
            h_yaw = -0.04 * prog
            recoil = 0.0
            scan_yaw = 0.0
            aim_prog = prog
        elif t < 5.5:
            recoil = 0.0
            for shot in [4.0, 4.4, 4.8]:
                if shot <= t < shot + 0.18:
                    dt = t - shot
                    if dt < 0.04: recoil += math.sin(dt / 0.04 * math.pi / 2)
                    else: recoil += math.cos((dt - 0.04) / 0.14 * math.pi / 2)
            recoil = min(1.3, recoil)
            h_y = BASE_HAND_T[1] + 0.32 + 0.025 * recoil
            h_z = 0.26 - 0.065 * recoil  # Sharp recoil kickback
            h_sx = 0.72
            h_pitch = -0.22 + 0.18 * recoil  # Muzzle climb on hand
            h_yaw = -0.04
            scan_yaw = 0.0
            aim_prog = 1.0
        elif t < 7.2:
            s = (t - 5.5) / 1.7
            dip = math.sin(s * math.pi)
            bump = math.sin((s - 0.5) / 0.2 * math.pi) if 0.5 <= s <= 0.7 else 0.0
            h_y = BASE_HAND_T[1] + 0.32 - 0.16 * dip + 0.05 * bump
            h_z = 0.26 - 0.14 * dip
            h_sx = 0.72 + 0.12 * dip
            h_pitch = -0.22 + 0.32 * dip
            h_yaw = -0.04 - 0.08 * dip
            recoil = 0.0
            scan_yaw = 0.0
            aim_prog = max(0.0, 1.0 - dip)
        else:
            s = (t - 7.2) / 1.8
            ret = (1 + math.cos(s * math.pi)) / 2
            scan_s = math.sin(s * math.pi)
            scan_yaw = 0.45 * scan_s
            h_y = BASE_HAND_T[1] + 0.08 + 0.24 * ret
            h_z = 0.04 + 0.22 * ret
            h_sx = 0.88 - 0.16 * ret
            h_pitch = -0.22 * ret
            h_yaw = scan_yaw * 0.65
            recoil = 0.0
            aim_prog = ret

        # Hand transforms
        hand_t_list.append([0.0, h_y, h_z])
        hand_r_list.append(euler_to_quat(h_pitch, h_yaw, 0.015 * sway))
        hand_s_list.append([h_sx, 1.0, 1.0])

        # Upper Body (Torso)
        u_y = BASE_UPPR_T[1] + breath
        u_z = BASE_UPPR_T[2] + 0.022 * aim_prog - 0.015 * recoil
        uppr_t_list.append([0.0, u_y, u_z])
        uppr_r_list.append(euler_to_quat(0.08 * aim_prog - 0.05 * recoil + 0.012 * breath, scan_yaw * 0.40, 0.0))

        # Head (Cheek weld & scan)
        h_head_y = BASE_HEAD_T[1] - 0.016 * aim_prog + breath
        h_head_z = BASE_HEAD_T[2] + 0.014 * aim_prog - 0.010 * recoil
        head_t_list.append([0.012 * aim_prog, h_head_y, h_head_z])
        head_r_list.append(euler_to_quat(-0.10 * aim_prog + 0.04 * recoil, scan_yaw + 0.02 * math.sin(p_breath), 0.05 * aim_prog))

        # Accs & Stance
        accs_t_list.append([0.0, BASE_ACCS_T[1] + breath, BASE_ACCS_T[2] + 0.016 * aim_prog])
        sway_r_list.append(euler_to_quat(0.0, 0.0, 0.006 * sway))

    # Channels & Samplers
    channels, samplers = [], []
    def add_channel(node_id, prop, values, typ):
        t_acc, v_acc = add_anim_accessor(times, values, typ)
        s_idx = len(samplers)
        samplers.append({'input': t_acc, 'output': v_acc, 'interpolation': 'LINEAR'})
        channels.append({'sampler': s_idx, 'target': {'node': node_id, 'path': prop}})

    add_channel(NODE_HAND, 'translation', hand_t_list, 'VEC3')
    add_channel(NODE_HAND, 'rotation', hand_r_list, 'VEC4')
    add_channel(NODE_HAND, 'scale', hand_s_list, 'VEC3')

    add_channel(NODE_UPPR, 'translation', uppr_t_list, 'VEC3')
    add_channel(NODE_UPPR, 'rotation', uppr_r_list, 'VEC4')

    add_channel(NODE_HEAD, 'translation', head_t_list, 'VEC3')
    add_channel(NODE_HEAD, 'rotation', head_r_list, 'VEC4')

    add_channel(NODE_ACCS, 'translation', accs_t_list, 'VEC3')
    add_channel(NODE_SWAY, 'rotation', sway_r_list, 'VEC4')

    gltf['animations'] = [{'name': 'Action', 'channels': channels, 'samplers': samplers}]

    # Assemble GLB
    gltf['bufferViews'] = new_bvs
    gltf['accessors'] = new_accs
    gltf['buffers'] = [{'byteLength': len(new_bin)}]

    json_str = json.dumps(gltf, separators=(',', ':'))
    json_bytes = json_str.encode('utf-8')
    while len(json_bytes) % 4 != 0: json_bytes += b' '
    while len(new_bin) % 4 != 0: new_bin.append(0)

    total_len = 12 + 8 + len(json_bytes) + 8 + len(new_bin)
    out_glb = bytearray()
    out_glb.extend(struct.pack('<4sII', b'glTF', 2, total_len))
    out_glb.extend(struct.pack('<II', len(json_bytes), 0x4E4F534A))
    out_glb.extend(json_bytes)
    out_glb.extend(struct.pack('<II', len(new_bin), 0x004E4942))
    out_glb.extend(new_bin)

    with open(OUT_GLB, 'wb') as f:
        f.write(out_glb)

    out_size = os.path.getsize(OUT_GLB) / 1024 / 1024
    print(f"Successfully remade {OUT_GLB} ({out_size:.2f} MB)")
    print("Rebuilding 64-byte aligned USDZ for iOS...")
    build_usdz(OUT_GLB, OUT_USDZ, target_height=0.25)
    print("All models remade successfully!")

if __name__ == '__main__':
    remake()

