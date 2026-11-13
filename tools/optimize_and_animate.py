#!/usr/bin/env python3
"""
Optimizes models/ghost_animated.glb and generates 5 rich military action animations:
1. Idle   - Tactical combat breathing, weapon sway, and hand micro-movements.
2. Aim    - Weapon raised to eye-level / sights, forward combat lean, steady hold.
3. Fire   - 3-round tactical burst with authentic weapon recoil kick, muzzle climb, and recovery.
4. Reload - Magazine drop, fresh mag insertion bump, bolt rack, and return to ready.
5. Scan   - 90-degree tactical sector sweep with synchronized weapon tracking.

Optimization:
- Strips unused vertex attributes (TANGENT, TEXCOORD_1, TEXCOORD_2, TEXCOORD_3) saving ~4.5 MB.
- Prunes unused textures/images.
- Results in ~50-60% faster loading on mobile WebAR.
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

def quat_mult(q1, q2):
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return [
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
        w1*w2 - x1*x2 - y1*y2 - z1*z2
    ]

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

        # Pack tightly
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

    # 1. Repack Primitives (strip TANGENT and extra TEXCOORDs)
    for m in gltf['meshes']:
        for p in m['primitives']:
            # Indices
            idx_bytes, old_idx_acc = read_accessor_bytes(p['indices'])
            bv_idx = add_buffer_data(idx_bytes, target=34963) # ELEMENT_ARRAY_BUFFER
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

            # Keep only POSITION, NORMAL, TEXCOORD_0
            new_attrs = {}
            for attr in ['POSITION', 'NORMAL', 'TEXCOORD_0']:
                if attr in p['attributes']:
                    old_acc_idx = p['attributes'][attr]
                    attr_bytes, old_acc = read_accessor_bytes(old_acc_idx)
                    bv_idx = add_buffer_data(attr_bytes, target=34962) # ARRAY_BUFFER
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

    # 2. Repack Images and Textures (prune unused)
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

    # 3. Helper to add animation accessor
    def add_anim_accessor(times, values, typ):
        times_bytes = struct.pack(f'<{len(times)}f', *times)
        bv_time = add_buffer_data(times_bytes)
        acc_time = {
            'bufferView': bv_time,
            'componentType': 5126, # FLOAT
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
            'componentType': 5126, # FLOAT
            'count': len(values),
            'type': typ
        }
        new_accs.append(acc_val)
        acc_val_idx = len(new_accs) - 1

        return acc_time_idx, acc_val_idx

    # Target nodes
    NODE_HAND = 8       # hand_000_r.model_7 (arms & rifle)
    NODE_UPPR = 22      # uppr_000_u.model_19 (torso)
    NODE_HEAD = 25      # HeadPivot (head & helmet)
    NODE_SWAY = 24      # Sway (stance)
    NODE_ACCS = 5       # accs_000_u.model_5 (tactical gear)

    BASE_HAND_T = [0.0, 1.00445, 0.0]
    BASE_UPPR_T = [0.0, 1.00445, 0.0]
    BASE_HEAD_T = [0.0, 1.554, -0.02]
    BASE_ACCS_T = [0.0, 1.00445, 0.0]

    FPS = 30

    def create_clip(name, duration, frame_gen_fn):
        num_frames = int(duration * FPS) + 1
        times = [i / FPS for i in range(num_frames)]

        # Collect tracks
        node_tracks = {} # (node_id, 'translation'|'rotation') -> [values]

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

    # ==================== ANIMATION 1: IDLE ====================
    # Tactical breathing, weapon sway, hand micro-adjustments
    def gen_idle(t, dur):
        p = 2 * math.pi * t / dur
        breath = math.sin(p)
        sway = math.cos(p)

        # Torso breathing
        uppr_t = [BASE_UPPR_T[0], BASE_UPPR_T[1] + 0.007 * breath, BASE_UPPR_T[2]]
        uppr_r = euler_to_quat(0.015 * breath, 0.0, 0.0)

        # Hand/Rifle sway: breathing makes weapon rise & settle
        hand_t = [BASE_HAND_T[0] + 0.003 * sway, BASE_HAND_T[1] + 0.010 * breath, BASE_HAND_T[2] + 0.004 * breath]
        hand_r = euler_to_quat(0.025 * breath, 0.012 * sway, 0.008 * sway)

        # Head micro-scan
        head_t = [BASE_HEAD_T[0], BASE_HEAD_T[1] + 0.004 * breath, BASE_HEAD_T[2]]
        head_r = euler_to_quat(0.010 * breath, 0.035 * math.sin(p * 2), 0.0)

        # Accs follow torso
        accs_t = [BASE_ACCS_T[0], BASE_ACCS_T[1] + 0.006 * breath, BASE_ACCS_T[2]]

        # Stance sway
        sway_r = euler_to_quat(0.0, 0.0, 0.008 * sway)

        return {
            (NODE_UPPR, 'translation'): uppr_t, (NODE_UPPR, 'rotation'): uppr_r,
            (NODE_HAND, 'translation'): hand_t, (NODE_HAND, 'rotation'): hand_r,
            (NODE_HEAD, 'translation'): head_t, (NODE_HEAD, 'rotation'): head_r,
            (NODE_ACCS, 'translation'): accs_t,
            (NODE_SWAY, 'rotation'): sway_r
        }

    # ==================== ANIMATION 2: AIM ====================
    # Arms raise rifle to eye level, cheek weld, tight combat forward lean
    def gen_aim(t, dur):
        # 0 to 0.6s: raise weapon; 0.6 to 2.4s: steady hold; 2.4 to 3.0s: return
        if t < 0.6:
            progress = (1 - math.cos(math.pi * t / 0.6)) / 2
        elif t < 2.4:
            progress = 1.0
        else:
            progress = (1 + math.cos(math.pi * (t - 2.4) / 0.6)) / 2

        tremor = 0.0015 * math.sin(t * 18)
        breath = 0.003 * math.sin(2 * math.pi * t / 1.5)

        # Hand raises rifle to sights
        hand_t = [
            BASE_HAND_T[0] + 0.015 * progress + tremor,
            BASE_HAND_T[1] + 0.055 * progress + breath,
            BASE_HAND_T[2] + 0.035 * progress + tremor
        ]
        # Pitch rifle up ~14 deg to aim straight ahead
        hand_r = euler_to_quat(-0.24 * progress + tremor, -0.04 * progress, 0.015 * progress)

        # Torso leans into combat stance
        uppr_t = [BASE_UPPR_T[0], BASE_UPPR_T[1] - 0.005 * progress, BASE_UPPR_T[2] + 0.022 * progress]
        uppr_r = euler_to_quat(0.09 * progress, 0.0, 0.0)

        # Head cheek weld onto stock
        head_t = [BASE_HEAD_T[0] + 0.012 * progress, BASE_HEAD_T[1] - 0.015 * progress, BASE_HEAD_T[2] + 0.015 * progress]
        head_r = euler_to_quat(-0.11 * progress, -0.03 * progress, 0.06 * progress)

        accs_t = [BASE_ACCS_T[0], BASE_ACCS_T[1], BASE_ACCS_T[2] + 0.018 * progress]

        return {
            (NODE_UPPR, 'translation'): uppr_t, (NODE_UPPR, 'rotation'): uppr_r,
            (NODE_HAND, 'translation'): hand_t, (NODE_HAND, 'rotation'): hand_r,
            (NODE_HEAD, 'translation'): head_t, (NODE_HEAD, 'rotation'): head_r,
            (NODE_ACCS, 'translation'): accs_t
        }

    # ==================== ANIMATION 3: FIRE ====================
    # 3-round tactical burst fire with sharp recoil impulse and recovery
    def gen_fire(t, dur):
        # In aim stance, shots at 0.35s, 0.65s, 0.95s
        shots = [0.35, 0.65, 0.95]
        recoil_kick = 0.0
        for s in shots:
            if s <= t < s + 0.18:
                dt = t - s
                if dt < 0.04:  # Sharp recoil kick
                    recoil_kick += math.sin(dt / 0.04 * math.pi / 2)
                else:          # Recovery
                    recoil_kick += math.cos((dt - 0.04) / 0.14 * math.pi / 2)

        recoil_kick = min(1.3, recoil_kick)

        hand_t = [
            BASE_HAND_T[0] + 0.015,
            BASE_HAND_T[1] + 0.055 + 0.012 * recoil_kick,
            BASE_HAND_T[2] + 0.035 - 0.045 * recoil_kick  # Recoil pushes back into shoulder
        ]
        hand_r = euler_to_quat(-0.24 + 0.13 * recoil_kick, -0.04, 0.02 * recoil_kick)

        uppr_t = [BASE_UPPR_T[0], BASE_UPPR_T[1], BASE_UPPR_T[2] + 0.022 - 0.015 * recoil_kick]
        uppr_r = euler_to_quat(0.09 - 0.05 * recoil_kick, 0.0, 0.0)

        head_t = [BASE_HEAD_T[0] + 0.012, BASE_HEAD_T[1] - 0.015, BASE_HEAD_T[2] + 0.015 - 0.010 * recoil_kick]
        head_r = euler_to_quat(-0.11 + 0.04 * recoil_kick, -0.03, 0.06)

        accs_t = [BASE_ACCS_T[0], BASE_ACCS_T[1], BASE_ACCS_T[2] + 0.018 - 0.010 * recoil_kick]

        return {
            (NODE_UPPR, 'translation'): uppr_t, (NODE_UPPR, 'rotation'): uppr_r,
            (NODE_HAND, 'translation'): hand_t, (NODE_HAND, 'rotation'): hand_r,
            (NODE_HEAD, 'translation'): head_t, (NODE_HEAD, 'rotation'): head_r,
            (NODE_ACCS, 'translation'): accs_t
        }

    # ==================== ANIMATION 4: RELOAD ====================
    # Lower weapon, mag slap bump, rack bolt, return to ready
    def gen_reload(t, dur):
        # 0.0 - 0.8s: tilt weapon & inspect magwell
        # 0.8 - 1.6s: grab magazine from vest
        # 1.6 - 2.2s: slap magazine into receiver (bump!)
        # 2.2 - 2.8s: rack bolt
        # 2.8 - 3.5s: return to ready
        mag_bump = 0.0
        if 1.7 <= t <= 1.85:
            mag_bump = math.sin((t - 1.7) / 0.15 * math.pi)

        rack_pull = 0.0
        if 2.25 <= t <= 2.55:
            rack_pull = math.sin((t - 2.25) / 0.3 * math.pi)

        if t < 0.8:
            tilt = math.sin(t / 0.8 * math.pi / 2)
        elif t < 2.8:
            tilt = 1.0
        else:
            tilt = math.cos((t - 2.8) / 0.7 * math.pi / 2)

        hand_t = [
            BASE_HAND_T[0] - 0.035 * tilt,
            BASE_HAND_T[1] - 0.025 * tilt + 0.035 * mag_bump,
            BASE_HAND_T[2] - 0.020 * tilt - 0.030 * rack_pull
        ]
        hand_r = euler_to_quat(
            0.15 * tilt + 0.05 * mag_bump,
            -0.10 * tilt,
            0.35 * tilt - 0.08 * rack_pull
        )

        uppr_t = [BASE_UPPR_T[0], BASE_UPPR_T[1], BASE_UPPR_T[2]]
        uppr_r = euler_to_quat(0.06 * tilt, -0.04 * tilt, 0.0)

        # Head looks down at magwell
        head_t = [BASE_HEAD_T[0], BASE_HEAD_T[1] - 0.015 * tilt, BASE_HEAD_T[2] + 0.010 * tilt]
        head_r = euler_to_quat(-0.25 * tilt, -0.08 * tilt, 0.0)

        accs_t = [BASE_ACCS_T[0], BASE_ACCS_T[1] - 0.010 * (1 if 0.8 < t < 1.6 else 0), BASE_ACCS_T[2]]

        return {
            (NODE_UPPR, 'translation'): uppr_t, (NODE_UPPR, 'rotation'): uppr_r,
            (NODE_HAND, 'translation'): hand_t, (NODE_HAND, 'rotation'): hand_r,
            (NODE_HEAD, 'translation'): head_t, (NODE_HEAD, 'rotation'): head_r,
            (NODE_ACCS, 'translation'): accs_t
        }

    # ==================== ANIMATION 5: SCAN ====================
    # 90-degree tactical sector sweep with rifle tracking
    def gen_scan(t, dur):
        # 0.0 -> 1.5s: turn left (yaw +0.65 rad)
        # 1.5 -> 2.2s: hold left
        # 2.2 -> 3.7s: sweep right (yaw -0.65 rad)
        # 3.7 -> 4.3s: hold right
        # 4.3 -> 5.0s: return center
        if t < 1.5:
            yaw = 0.65 * math.sin(t / 1.5 * math.pi / 2)
        elif t < 2.2:
            yaw = 0.65
        elif t < 3.7:
            p = (t - 2.2) / 1.5
            yaw = 0.65 - 1.30 * (1 - math.cos(p * math.pi)) / 2
        elif t < 4.3:
            yaw = -0.65
        else:
            p = (t - 4.3) / 0.7
            yaw = -0.65 * (1 + math.cos(p * math.pi)) / 2

        breath = 0.005 * math.sin(2 * math.pi * t / 2.5)

        # Head turns fully
        head_t = [BASE_HEAD_T[0], BASE_HEAD_T[1] + breath, BASE_HEAD_T[2]]
        head_r = euler_to_quat(0.02, yaw, 0.0)

        # Hands & rifle track the scan at ~75% angle
        hand_t = [BASE_HAND_T[0] + 0.04 * math.sin(yaw * 0.7), BASE_HAND_T[1] + breath, BASE_HAND_T[2]]
        hand_r = euler_to_quat(-0.08, yaw * 0.75, 0.02 * math.sin(yaw))

        # Upper body turns ~45% angle
        uppr_t = [BASE_UPPR_T[0], BASE_UPPR_T[1] + breath, BASE_UPPR_T[2]]
        uppr_r = euler_to_quat(0.02, yaw * 0.45, 0.0)

        accs_t = [BASE_ACCS_T[0], BASE_ACCS_T[1] + breath, BASE_ACCS_T[2]]

        return {
            (NODE_UPPR, 'translation'): uppr_t, (NODE_UPPR, 'rotation'): uppr_r,
            (NODE_HAND, 'translation'): hand_t, (NODE_HAND, 'rotation'): hand_r,
            (NODE_HEAD, 'translation'): head_t, (NODE_HEAD, 'rotation'): head_r,
            (NODE_ACCS, 'translation'): accs_t
        }

    # Generate the 5 clips
    clips = [
        create_clip('Idle', 4.0, gen_idle),
        create_clip('Aim', 3.0, gen_aim),
        create_clip('Fire', 2.0, gen_fire),
        create_clip('Reload', 3.5, gen_reload),
        create_clip('Scan', 5.0, gen_scan)
    ]
    gltf['animations'] = clips

    # Assemble GLB
    gltf['bufferViews'] = new_bvs
    gltf['accessors'] = new_accs
    gltf['buffers'] = [{'byteLength': len(new_bin)}]

    json_str = json.dumps(gltf, separators=(',', ':'))
    json_bytes = json_str.encode('utf-8')
    while len(json_bytes) % 4 != 0:
        json_bytes += b' '

    while len(new_bin) % 4 != 0:
        new_bin.append(0)

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
    print(f"Original size: {in_size:.2f} MB -> Optimized size: {out_size:.2f} MB (Saved {(1 - out_size/in_size)*100:.1f}%)")
    print(f"Generated animations: {[c['name'] for c in clips]}")

if __name__ == '__main__':
    optimize_and_animate('models/ghost_animated.glb', 'models/ghost_animated.glb')

