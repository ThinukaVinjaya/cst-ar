#!/usr/bin/env python3
"""
Optimizes models/ghost_animated.glb and generates the recommended tactical military action loop:
- Continuous, seamless 8.5-second cinematic military sequence:
  1. Tactical Combat Idle & breathing (0.0s - 2.0s)
  2. Weapon Raise & Target Lock (2.0s - 3.5s)
  3. 3-Round Burst Fire with weapon recoil kickback & muzzle climb (3.5s - 5.0s)
  4. Perimeter Sector Sweep checking for threats (5.0s - 7.0s)
  5. Tactical Recovery back to ready stance (7.0s - 8.5s)
Loops seamlessly without requiring manual button clicks!
"""
import struct, json, os, math

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

def optimize_and_animate(input_glb, output_glb):
    with open(input_glb, 'rb') as f:
        magic, version, length = struct.unpack('<4sII', f.read(12))
        chunk0_len, _ = struct.unpack('<II', f.read(8))
        gltf = json.loads(f.read(chunk0_len).decode('utf-8'))
        chunk1_len, _ = struct.unpack('<II', f.read(8))
        bin_buf = f.read(chunk1_len)

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
        while len(new_bin) % 4 != 0:
            new_bin.append(0)
        offset = len(new_bin)
        new_bin.extend(data_bytes)
        bv = {'buffer': 0, 'byteOffset': offset, 'byteLength': len(data_bytes)}
        if target:
            bv['target'] = target
        new_bvs.append(bv)
        return len(new_bvs) - 1

    # 1. Repack Primitives
    for m in gltf['meshes']:
        for p in m['primitives']:
            idx_bytes, old_idx_acc = read_accessor_bytes(p['indices'])
            bv_idx = add_buffer_data(idx_bytes, target=34963)
            new_idx_acc = {
                'bufferView': bv_idx,
                'componentType': old_idx_acc['componentType'],
                'count': old_idx_acc['count'],
                'type': old_idx_acc['type']
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
                        'bufferView': bv_idx,
                        'componentType': old_acc['componentType'],
                        'count': old_acc['count'],
                        'type': old_acc['type']
                    }
                    if 'min' in old_acc: new_acc['min'] = old_acc['min']
                    if 'max' in old_acc: new_acc['max'] = old_acc['max']
                    new_accs.append(new_acc)
                    new_attrs[attr] = len(new_accs) - 1
            p['attributes'] = new_attrs

    # 2. Repack Images
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

    # 3. Add Animation Accessor
    def add_anim_accessor(times, values, typ):
        times_bytes = struct.pack(f'<{len(times)}f', *times)
        bv_time = add_buffer_data(times_bytes)
        acc_time = {
            'bufferView': bv_time,
            'componentType': 5126,
            'count': len(times),
            'type': 'SCALAR',
            'min': [min(times)],
            'max': [max(times)]
        }
        new_accs.append(acc_time)
        acc_time_idx = len(new_accs) - 1

        val_flat = []
        for v in values:
            if isinstance(v, (list, tuple)): val_flat.extend(v)
            else: val_flat.append(v)

        val_bytes = struct.pack(f'<{len(val_flat)}f', *val_flat)
        bv_val = add_buffer_data(val_bytes)
        acc_val = {
            'bufferView': bv_val,
            'componentType': 5126,
            'count': len(values),
            'type': typ
        }
        new_accs.append(acc_val)
        acc_val_idx = len(new_accs) - 1
        return acc_time_idx, acc_val_idx

    NODE_HAND = 8       # hand_000_r.model_7
    NODE_UPPR = 22      # uppr_000_u.model_19
    NODE_HEAD = 25      # HeadPivot
    NODE_SWAY = 24      # Sway
    NODE_ACCS = 5       # accs_000_u.model_5

    BASE_HAND_T = [0.0, 1.00445, 0.0]
    BASE_UPPR_T = [0.0, 1.00445, 0.0]
    BASE_HEAD_T = [0.0, 1.554, -0.02]
    BASE_ACCS_T = [0.0, 1.00445, 0.0]

    FPS = 30

    def create_clip(name, duration, frame_gen_fn):
        num_frames = int(duration * FPS) + 1
        times = [i / FPS for i in range(num_frames)]
        node_tracks = {}

        for i, t in enumerate(times):
            data = frame_gen_fn(t, duration)
            for (node_id, prop), val in data.items():
                if (node_id, prop) not in node_tracks:
                    node_tracks[(node_id, prop)] = []
                node_tracks[(node_id, prop)].append(val)

        samplers = []
        channels = []

        for (node_id, prop), vals in node_tracks.items():
            typ = 'VEC4' if prop == 'rotation' else 'VEC3'
            t_acc, v_acc = add_anim_accessor(times, vals, typ)
            sampler_idx = len(samplers)
            samplers.append({'input': t_acc, 'output': v_acc, 'interpolation': 'LINEAR'})
            channels.append({
                'sampler': sampler_idx,
                'target': {'node': node_id, 'path': prop}
            })

        return {'name': name, 'samplers': samplers, 'channels': channels}

    # RECOMMENDED MASTER SEQUENCE: Tactical Action Loop (8.5 seconds)
    def gen_combat_sequence(t, dur):
        # Phase 1: 0.0s - 2.0s: Combat Idle breathing & surveillance
        # Phase 2: 2.0s - 3.5s: Raise weapon to aim down sights
        # Phase 3: 3.5s - 5.0s: 3-round burst fire with recoil
        # Phase 4: 5.0s - 7.0s: Tactical sector scan
        # Phase 5: 7.0s - 8.5s: Return to ready stance
        breath_p = 2 * math.pi * t / 2.0
        breath = 0.006 * math.sin(breath_p)
        sway = 0.003 * math.cos(breath_p)

        # Default ready pose values
        aim_prog = 0.0
        recoil = 0.0
        scan_yaw = 0.0

        if t < 2.0:
            pass # Idle
        elif t < 3.5:
            # Raise weapon
            s = (t - 2.0) / 1.5
            aim_prog = (1 - math.cos(s * math.pi)) / 2
        elif t < 5.0:
            # Holding aim & 3 burst shots at 3.7s, 4.1s, 4.5s
            aim_prog = 1.0
            for shot in [3.7, 4.1, 4.5]:
                if shot <= t < shot + 0.16:
                    dt = t - shot
                    if dt < 0.04: recoil += math.sin(dt / 0.04 * math.pi / 2)
                    else: recoil += math.cos((dt - 0.04) / 0.12 * math.pi / 2)
            recoil = min(1.2, recoil)
        elif t < 7.0:
            # Sector scan while in alert ready
            s = (t - 5.0) / 2.0
            aim_prog = max(0.0, 1.0 - s * 1.5)
            scan_yaw = 0.50 * math.sin(s * math.pi)
        else:
            # Return smoothly to idle
            s = (t - 7.0) / 1.5
            aim_prog = 0.0
            scan_yaw = 0.0

        tremor = 0.001 * math.sin(t * 15) * aim_prog

        # Hand / Weapon transform
        hand_x = BASE_HAND_T[0] + 0.015 * aim_prog + 0.035 * math.sin(scan_yaw * 0.7) + sway
        hand_y = BASE_HAND_T[1] + 0.050 * aim_prog + 0.010 * recoil + breath
        hand_z = BASE_HAND_T[2] + 0.035 * aim_prog - 0.040 * recoil + tremor

        hand_rx = -0.22 * aim_prog + 0.12 * recoil + 0.02 * breath
        hand_ry = -0.04 * aim_prog + scan_yaw * 0.70
        hand_rz = 0.015 * aim_prog + 0.01 * sway

        hand_t = [hand_x, hand_y, hand_z]
        hand_r = euler_to_quat(hand_rx, hand_ry, hand_rz)

        # Torso transform
        uppr_t = [BASE_UPPR_T[0], BASE_UPPR_T[1] + breath, BASE_UPPR_T[2] + 0.020 * aim_prog - 0.012 * recoil]
        uppr_r = euler_to_quat(0.08 * aim_prog - 0.04 * recoil + 0.012 * breath, scan_yaw * 0.40, 0.0)

        # Head transform
        head_t = [BASE_HEAD_T[0] + 0.012 * aim_prog, BASE_HEAD_T[1] - 0.015 * aim_prog + breath, BASE_HEAD_T[2] + 0.012 * aim_prog]
        head_r = euler_to_quat(-0.10 * aim_prog + 0.03 * recoil, scan_yaw + 0.02 * math.sin(breath_p), 0.05 * aim_prog)

        accs_t = [BASE_ACCS_T[0], BASE_ACCS_T[1] + breath, BASE_ACCS_T[2] + 0.016 * aim_prog]
        sway_r = euler_to_quat(0.0, 0.0, 0.006 * sway)

        return {
            (NODE_UPPR, 'translation'): uppr_t, (NODE_UPPR, 'rotation'): uppr_r,
            (NODE_HAND, 'translation'): hand_t, (NODE_HAND, 'rotation'): hand_r,
            (NODE_HEAD, 'translation'): head_t, (NODE_HEAD, 'rotation'): head_r,
            (NODE_ACCS, 'translation'): accs_t,
            (NODE_SWAY, 'rotation'): sway_r
        }

    clips = [
        create_clip('Action', 8.5, gen_combat_sequence)
    ]
    gltf['animations'] = clips

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

    with open(output_glb, 'wb') as f:
        f.write(out_glb)

    in_size = os.path.getsize(input_glb) / 1024 / 1024
    out_size = os.path.getsize(output_glb) / 1024 / 1024
    print(f"GLB optimized: {out_size:.2f} MB. Recommended animation 'Action' generated successfully!")

if __name__ == '__main__':
    optimize_and_animate('models/ghost_animated.glb', 'models/ghost_animated.glb')
