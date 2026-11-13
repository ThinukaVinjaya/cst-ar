#!/usr/bin/env python3
"""
Adds Call of Duty 4 inspired military perimeter items around the physical table centerpiece:
1. M18A1 Claymore Mine with scissor wire legs & "FRONT TOWARD ENEMY" stenciling.
2. Military 7.62mm NATO Metal Ammo Crates & Cans.
3. CoD4 Tactical Intel Laptop (open Toughbook on supply crate with glowing green UAV radar display).
4. Curved Sandbag Fortification Barricade protecting the flank.
5. C4 Remote Demolition Charge with digital receiver & LED.
6. Tactical Care Package / Heavy Equipment Drop Crate.

Positions Ghost and all props in a defensive perimeter around (X=0, Z=0),
leaving an open clearance radius (~20 cm on the real table) for the user's physical table decoration.
"""
import struct, json, os, zlib, math
from build_ghost_usdz import build_usdz

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

def make_cylinder(r, h, cx=0, cy=0, cz=0, segs=8, rot_y=0):
    verts, norms, uvs, idxs = [], [], [], []
    half_h = h / 2
    # Bottom circle & top circle
    for i in range(segs):
        theta1 = 2 * math.pi * i / segs
        theta2 = 2 * math.pi * (i + 1) / segs
        x1, z1 = r * math.cos(theta1), r * math.sin(theta1)
        x2, z2 = r * math.cos(theta2), r * math.sin(theta2)

        # Side quad
        b = len(verts)
        n1 = [x1 / r, 0, z1 / r]
        n2 = [x2 / r, 0, z2 / r]
        rx1, rz1 = rot(x1, z1, rot_y)
        rx2, rz2 = rot(x2, z2, rot_y)
        rn1x, rn1z = rot(n1[0], n1[2], rot_y)
        rn2x, rn2z = rot(n2[0], n2[2], rot_y)

        verts.extend([
            [rx1 + cx, -half_h + cy, rz1 + cz],
            [rx2 + cx, -half_h + cy, rz2 + cz],
            [rx2 + cx,  half_h + cy, rz2 + cz],
            [rx1 + cx,  half_h + cy, rz1 + cz],
        ])
        norms.extend([[rn1x, 0, rn1z], [rn2x, 0, rn2z], [rn2x, 0, rn2z], [rn1x, 0, rn1z]])
        uvs.extend([[i/segs, 0], [(i+1)/segs, 0], [(i+1)/segs, 1], [i/segs, 1]])
        idxs.extend([b, b+1, b+2, b, b+2, b+3])

    return verts, norms, uvs, idxs

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

# Textures
def tex_claymore():
    def get_pixel(x, y):
        # Olive green background
        r, g, b = 60, 75, 45
        # "FRONT TOWARD ENEMY" yellow stenciling & chevrons
        if 42 <= y <= 86 and 14 <= x <= 114:
            if (58 <= y <= 63) or (68 <= y <= 73 and (x % 14 < 7)):
                r, g, b = 215, 200, 65 # yellow text
            elif (46 <= y <= 50) and ((x // 18) % 2 == 0):
                r, g, b = 220, 205, 70 # chevrons
        if x < 4 or x > 123 or y < 4 or y > 123:
            r, g, b = 35, 42, 28 # dark border
        return r, g, b, 255
    return create_png(128, 128, get_pixel)

def tex_ammo():
    def get_pixel(x, y):
        r, g, b = 50, 62, 38
        # Stenciled markings
        if (35 <= y <= 42 and 20 <= x <= 108) or (50 <= y <= 56 and 30 <= x <= 98) or (64 <= y <= 70 and 25 <= x <= 103):
            r, g, b = 205, 195, 160 # off-white military stencil
        if x < 6 or x > 121 or y < 6 or y > 121:
            r, g, b = 32, 38, 25
        return r, g, b, 255
    return create_png(128, 128, get_pixel)

def tex_sandbag():
    def get_pixel(x, y):
        # Canvas burlap weave
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
        # Glowing green UAV radar screen
        dx, dy = x - 64, y - 64
        dist_sq = dx*dx + dy*dy
        r, g, b = 8, 28, 12
        # Concentric radar rings
        if 850 <= dist_sq <= 950 or 2400 <= dist_sq <= 2600 or 4700 <= dist_sq <= 4950:
            r, g, b = 40, 240, 90
        # Radar crosshairs
        elif abs(dx) <= 1 or abs(dy) <= 1:
            r, g, b = 30, 200, 70
        # Sweep line (diagonal)
        elif 0 <= dx and 0 <= dy and abs(dx - dy*1.5) < 2:
            r, g, b = 70, 255, 120
        # Threat blips (red/yellow enemy dots)
        elif ((dx-20)**2 + (dy+25)**2 < 12) or ((dx+32)**2 + (dy-18)**2 < 12):
            r, g, b = 255, 50, 30
        return r, g, b, 255
    return create_png(128, 128, get_pixel)

def tex_c4():
    def get_pixel(x, y):
        r, g, b = 115, 115, 110 # C4 explosive putty
        # Black electrical tape bands
        if 20 <= x <= 36 or 92 <= x <= 108:
            r, g, b = 20, 20, 22
        # Digital receiver box
        if 48 <= x <= 80 and 45 <= y <= 83:
            r, g, b = 30, 32, 34
            if 58 <= x <= 70 and 58 <= y <= 70:
                r, g, b = 255, 30, 20 # Red active LED
        return r, g, b, 255
    return create_png(128, 128, get_pixel)

def merge_mesh(parts):
    # parts: list of (verts, norms, uvs, idxs)
    all_v, all_n, all_u, all_i = [], [], [], []
    for v, n, u, i in parts:
        base = len(all_v)
        all_v.extend(v)
        all_n.extend(n)
        all_u.extend(u)
        all_i.extend([idx + base for idx in i])
    return all_v, all_n, all_u, all_i

def build_scene_with_props(input_glb, output_glb):
    with open(input_glb, 'rb') as f:
        magic, version, length = struct.unpack('<4sII', f.read(12))
        chunk0_len, _ = struct.unpack('<II', f.read(8))
        gltf = json.loads(f.read(chunk0_len).decode('utf-8'))
        chunk1_len, _ = struct.unpack('<II', f.read(8))
        bin_buf = bytearray(f.read(chunk1_len))

    # 1. Reposition Ghost to perimeter: Z = +1.65m (so center X=0, Z=0 is clear for table item)
    # Node 24 is Sway
    gltf['nodes'][24]['translation'] = [0.0, 0.0, 1.65]

    # 2. Build 3D Military Props
    # PROP A: M18A1 Claymore Mine (at X=+0.75, Z=+1.75, angle -25 deg)
    claymore_parts = [
        # Curved body
        make_box(0.32, 0.20, 0.08, cx=0.75, cy=0.14, cz=1.75, rot_y=-0.45),
        # Scissor wire tripod legs
        make_box(0.02, 0.12, 0.16, cx=0.75, cy=0.06, cz=1.75, rot_y=-0.45),
        # Dual top fuse wells
        make_box(0.04, 0.04, 0.04, cx=0.70, cy=0.25, cz=1.73, rot_y=-0.45),
        make_box(0.04, 0.04, 0.04, cx=0.80, cy=0.25, cz=1.77, rot_y=-0.45),
    ]
    clay_v, clay_n, clay_u, clay_i = merge_mesh(claymore_parts)

    # PROP B: 7.62mm Ammo Crates & Cans (at X=+1.55, Z=+0.55)
    ammo_parts = [
        # Main heavy metal crate
        make_box(0.65, 0.38, 0.42, cx=1.55, cy=0.19, cz=0.55, rot_y=0.25),
        # Corner metal braces
        make_box(0.67, 0.06, 0.44, cx=1.55, cy=0.36, cz=0.55, rot_y=0.25),
        # Stacked .50 cal / 5.56mm ammo can
        make_box(0.32, 0.22, 0.18, cx=1.45, cy=0.49, cz=0.55, rot_y=-0.15),
        # Second ammo can beside on ground
        make_box(0.32, 0.22, 0.18, cx=1.35, cy=0.11, cz=0.95, rot_y=0.55),
    ]
    ammo_v, ammo_n, ammo_u, ammo_i = merge_mesh(ammo_parts)

    # PROP C: CoD4 Intel Laptop on Supply Case (at X=-1.45, Z=+0.55)
    intel_parts = [
        # Rugged field equipment case (table/stand for laptop)
        make_box(0.55, 0.35, 0.45, cx=-1.45, cy=0.175, cz=0.55, rot_y=-0.25),
        # Laptop base chassis
        make_box(0.36, 0.03, 0.28, cx=-1.45, cy=0.365, cz=0.55, rot_y=-0.25),
        # Open tilted display lid (angled at ~75 deg)
        make_box(0.36, 0.26, 0.025, cx=-1.45, cy=0.49, cz=0.42, rot_y=-0.25),
    ]
    intel_v, intel_n, intel_u, intel_i = merge_mesh(intel_parts)

    # Laptop screen face (separate primitive with glowing radar material)
    screen_parts = [
        make_box(0.30, 0.20, 0.005, cx=-1.45, cy=0.49, cz=0.435, rot_y=-0.25),
    ]
    screen_v, screen_n, screen_u, screen_i = merge_mesh(screen_parts)

    # PROP D: Sandbag Defensive Barricade (curved arc on right flank)
    sandbag_parts = []
    # Tier 1 (base layer on floor)
    sandbag_parts.append(make_box(0.48, 0.14, 0.25, cx=1.25, cy=0.07, cz=1.30, rot_y=0.40))
    sandbag_parts.append(make_box(0.48, 0.14, 0.25, cx=1.48, cy=0.07, cz=0.90, rot_y=0.75))
    sandbag_parts.append(make_box(0.48, 0.14, 0.25, cx=1.65, cy=0.07, cz=0.45, rot_y=1.10))
    sandbag_parts.append(make_box(0.48, 0.14, 0.25, cx=1.68, cy=0.07, cz=-0.05, rot_y=1.45))
    # Tier 2 (stacked overlapping)
    sandbag_parts.append(make_box(0.48, 0.14, 0.25, cx=1.38, cy=0.20, cz=1.10, rot_y=0.55))
    sandbag_parts.append(make_box(0.48, 0.14, 0.25, cx=1.58, cy=0.20, cz=0.68, rot_y=0.90))
    sandbag_parts.append(make_box(0.48, 0.14, 0.25, cx=1.68, cy=0.20, cz=0.20, rot_y=1.30))
    # Tier 3 (crest)
    sandbag_parts.append(make_box(0.48, 0.14, 0.25, cx=1.48, cy=0.33, cz=0.88, rot_y=0.75))
    sand_v, sand_n, sand_u, sand_i = merge_mesh(sandbag_parts)

    # PROP E: C4 Remote Explosive Charge (at X=-0.75, Z=+1.70)
    c4_parts = [
        # Explosive brick
        make_box(0.24, 0.08, 0.14, cx=-0.75, cy=0.04, cz=1.70, rot_y=0.35),
        # RF receiver module
        make_box(0.08, 0.04, 0.06, cx=-0.75, cy=0.10, cz=1.70, rot_y=0.35),
        # Antenna wire
        make_box(0.01, 0.12, 0.01, cx=-0.72, cy=0.15, cz=1.71, rot_y=0.35),
    ]
    c4_v, c4_n, c4_u, c4_i = merge_mesh(c4_parts)

    # PROP F: Tactical Supply / Weapons Drop Crate (at X=-1.55, Z=-0.05)
    crate_parts = [
        # Main drop crate body
        make_box(0.75, 0.45, 0.55, cx=-1.55, cy=0.225, cz=-0.05, rot_y=-0.10),
        # Top reinforced rim
        make_box(0.78, 0.08, 0.58, cx=-1.55, cy=0.42, cz=-0.05, rot_y=-0.10),
    ]
    crate_v, crate_n, crate_u, crate_i = merge_mesh(crate_parts)

    # Generate Prop Images
    images_data = [
        ('tex_claymore.png', tex_claymore()),
        ('tex_ammo.png', tex_ammo()),
        ('tex_sandbag.png', tex_sandbag()),
        ('tex_intel.png', tex_intel_screen()),
        ('tex_c4.png', tex_c4()),
    ]

    new_img_start_idx = len(gltf.get('images', []))
    new_tex_start_idx = len(gltf.get('textures', []))
    new_mat_start_idx = len(gltf.get('materials', []))

    def add_buffer_data(data_bytes, target=None):
        while len(bin_buf) % 4 != 0: bin_buf.append(0)
        offset = len(bin_buf)
        bin_buf.extend(data_bytes)
        bv = {'buffer': 0, 'byteOffset': offset, 'byteLength': len(data_bytes)}
        if target: bv['target'] = target
        gltf['bufferViews'].append(bv)
        return len(gltf['bufferViews']) - 1

    # Add images
    for fname, img_bytes in images_data:
        bv_idx = add_buffer_data(img_bytes)
        gltf['images'].append({'bufferView': bv_idx, 'mimeType': 'image/png', 'name': fname})
        gltf['textures'].append({'source': len(gltf['images']) - 1})

    # Add Materials
    # Mat 0: Claymore
    gltf['materials'].append({
        'name': 'Mat_Claymore',
        'pbrMetallicRoughness': {
            'baseColorTexture': {'index': new_tex_start_idx + 0},
            'roughnessFactor': 0.6,
            'metallicFactor': 0.15
        }
    })
    # Mat 1: Ammo Crate
    gltf['materials'].append({
        'name': 'Mat_Ammo',
        'pbrMetallicRoughness': {
            'baseColorTexture': {'index': new_tex_start_idx + 1},
            'roughnessFactor': 0.4,
            'metallicFactor': 0.75
        }
    })
    # Mat 2: Sandbags
    gltf['materials'].append({
        'name': 'Mat_Sandbag',
        'pbrMetallicRoughness': {
            'baseColorTexture': {'index': new_tex_start_idx + 2},
            'roughnessFactor': 0.9,
            'metallicFactor': 0.0
        }
    })
    # Mat 3: Intel Laptop Screen (Glowing Green)
    gltf['materials'].append({
        'name': 'Mat_Intel_Screen',
        'pbrMetallicRoughness': {
            'baseColorTexture': {'index': new_tex_start_idx + 3},
            'roughnessFactor': 0.2,
            'metallicFactor': 0.0
        },
        'emissiveTexture': {'index': new_tex_start_idx + 3},
        'emissiveFactor': [0.2, 0.9, 0.3]
    })
    # Mat 4: C4 Demolition Charge
    gltf['materials'].append({
        'name': 'Mat_C4',
        'pbrMetallicRoughness': {
            'baseColorTexture': {'index': new_tex_start_idx + 4},
            'roughnessFactor': 0.7,
            'metallicFactor': 0.1
        }
    })
    # Mat 5: Tactical Supply Crate
    gltf['materials'].append({
        'name': 'Mat_Supply_Crate',
        'pbrMetallicRoughness': {
            'baseColorTexture': {'index': new_tex_start_idx + 1},
            'roughnessFactor': 0.5,
            'metallicFactor': 0.6
        }
    })

    # Helper to add primitive
    def add_primitive(verts, norms, uvs, idxs, mat_idx):
        # Pack indices
        idx_bytes = struct.pack(f'<{len(idxs)}H', *idxs)
        idx_bv = add_buffer_data(idx_bytes, target=34963)
        gltf['accessors'].append({
            'bufferView': idx_bv, 'componentType': 5123, 'count': len(idxs), 'type': 'SCALAR'
        })
        idx_acc = len(gltf['accessors']) - 1

        # Pack positions
        pos_flat = [coord for pt in verts for coord in pt]
        pos_bytes = struct.pack(f'<{len(pos_flat)}f', *pos_flat)
        pos_bv = add_buffer_data(pos_bytes, target=34962)
        mins = [min(pt[i] for pt in verts) for i in range(3)]
        maxs = [max(pt[i] for pt in verts) for i in range(3)]
        gltf['accessors'].append({
            'bufferView': pos_bv, 'componentType': 5126, 'count': len(verts), 'type': 'VEC3',
            'min': mins, 'max': maxs
        })
        pos_acc = len(gltf['accessors']) - 1

        # Pack normals
        nrm_flat = [coord for pt in norms for coord in pt]
        nrm_bytes = struct.pack(f'<{len(nrm_flat)}f', *nrm_flat)
        nrm_bv = add_buffer_data(nrm_bytes, target=34962)
        gltf['accessors'].append({
            'bufferView': nrm_bv, 'componentType': 5126, 'count': len(norms), 'type': 'VEC3'
        })
        nrm_acc = len(gltf['accessors']) - 1

        # Pack UVs
        uv_flat = [coord for pt in uvs for coord in pt]
        uv_bytes = struct.pack(f'<{len(uv_flat)}f', *uv_flat)
        uv_bv = add_buffer_data(uv_bytes, target=34962)
        gltf['accessors'].append({
            'bufferView': uv_bv, 'componentType': 5126, 'count': len(uvs), 'type': 'VEC2'
        })
        uv_acc = len(gltf['accessors']) - 1

        return {
            'attributes': {'POSITION': pos_acc, 'NORMAL': nrm_acc, 'TEXCOORD_0': uv_acc},
            'indices': idx_acc,
            'material': mat_idx
        }

    # Build meshes
    prims = [
        add_primitive(clay_v, clay_n, clay_u, clay_i, new_mat_start_idx + 0),       # Claymore
        add_primitive(ammo_v, ammo_n, ammo_u, ammo_i, new_mat_start_idx + 1),       # Ammo Crates
        add_primitive(intel_v, intel_n, intel_u, intel_i, new_mat_start_idx + 1),   # Intel Laptop Body
        add_primitive(screen_v, screen_n, screen_u, screen_i, new_mat_start_idx + 3),# Intel Radar Screen
        add_primitive(sand_v, sand_n, sand_u, sand_i, new_mat_start_idx + 2),       # Sandbags
        add_primitive(c4_v, c4_n, c4_u, c4_i, new_mat_start_idx + 4),              # C4 Charge
        add_primitive(crate_v, crate_n, crate_u, crate_i, new_mat_start_idx + 5),   # Supply Crate
    ]

    prop_mesh_idx = len(gltf['meshes'])
    gltf['meshes'].append({'name': 'CoD4_Military_Perimeter_Props', 'primitives': prims})

    # Add Node for Props
    prop_node_idx = len(gltf['nodes'])
    gltf['nodes'].append({
        'name': 'CoD4_Military_Props',
        'mesh': prop_mesh_idx,
        'translation': [0.0, 0.0, 0.0]
    })

    # Add to scene root nodes
    if prop_node_idx not in gltf['scenes'][0]['nodes']:
        gltf['scenes'][0]['nodes'].append(prop_node_idx)

    # Assemble GLB
    gltf['buffers'][0]['byteLength'] = len(bin_buf)
    json_str = json.dumps(gltf, separators=(',', ':'))
    json_bytes = json_str.encode('utf-8')
    while len(json_bytes) % 4 != 0: json_bytes += b' '
    while len(bin_buf) % 4 != 0: bin_buf.append(0)

    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_buf)
    out_glb = bytearray()
    out_glb.extend(struct.pack('<4sII', b'glTF', 2, total_len))
    out_glb.extend(struct.pack('<II', len(json_bytes), 0x4E4F534A))
    out_glb.extend(json_bytes)
    out_glb.extend(struct.pack('<II', len(bin_buf), 0x004E4942))
    out_glb.extend(bin_buf)

    with open(output_glb, 'wb') as f:
        f.write(out_glb)

    out_size = os.path.getsize(output_glb) / 1024 / 1024
    print(f"Generated complete CoD4 military perimeter scene: {out_size:.2f} MB")
    print(f"Clearance center radius preserved for physical table centerpiece!")

if __name__ == '__main__':
    build_scene_with_props('models/ghost_animated.glb', 'models/ghost_animated.glb')
    print("Rebuilding iOS USDZ package...")
    build_usdz('models/ghost_animated.glb', 'models/ghost_animated.usdz', target_height=0.25)
    print("All models successfully built for Android & iOS!")

