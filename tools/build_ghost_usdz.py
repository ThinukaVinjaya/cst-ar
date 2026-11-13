#!/usr/bin/env python3
"""
Converts the optimized models/ghost_animated.glb to models/ghost_animated.usdz for iOS Apple AR Quick Look.
Includes:
- Tabletop auto-scaling (height ~0.25m)
- Preliminary horizontal plane anchoring (auto-places on table without tapping)
- Full materials and diffuse textures
- Dynamic military character animation with weapon sway, arm movements, and breathing
"""
import struct, json, os, zipfile, math

def build_usdz(glb_path, out_usdz_path, target_height=0.25, anim_name='Idle'):
    with open(glb_path, 'rb') as f:
        magic, version, length = struct.unpack('<4sII', f.read(12))
        chunk0_len, _ = struct.unpack('<II', f.read(8))
        gltf = json.loads(f.read(chunk0_len).decode('utf-8'))
        chunk1_len, _ = struct.unpack('<II', f.read(8))
        bin_buf = f.read(chunk1_len)

    accessors = gltf['accessors']
    bufferViews = gltf['bufferViews']

    def read_accessor(idx):
        acc = accessors[idx]
        bv = bufferViews[acc['bufferView']]
        offset = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
        count = acc['count']
        comp_type = acc['componentType']
        typ = acc['type']

        type_map = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
        num_comps = type_map[typ]

        format_map = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
        elem_fmt = format_map[comp_type]
        stride = bv.get('byteStride', struct.calcsize('<' + elem_fmt * num_comps))

        out = []
        for i in range(count):
            elem_offset = offset + i * stride
            vals = struct.unpack_from('<' + elem_fmt * num_comps, bin_buf, elem_offset)
            out.append(vals[0] if num_comps == 1 else list(vals))
        return out

    # Compute bounding box and scale
    all_mins = [float('inf')]*3
    all_maxs = [float('-inf')]*3
    for m in gltf['meshes']:
        p = m['primitives'][0]
        pos_acc = accessors[p['attributes']['POSITION']]
        for i in range(3):
            all_mins[i] = min(all_mins[i], pos_acc['min'][i])
            all_maxs[i] = max(all_maxs[i], pos_acc['max'][i])

    raw_height = all_maxs[1] - all_mins[1]
    scale_factor = (target_height / raw_height) if target_height else 1.0
    print(f"Model raw height: {raw_height:.3f}m, Target scale factor: {scale_factor:.4f}")

    # Extract textures
    textures_dir = 'scratch/ghost_usdz_build/textures'
    os.makedirs(textures_dir, exist_ok=True)
    images = gltf.get('images', [])
    tex_files = {}
    for i, img in enumerate(images):
        bv_idx = img.get('bufferView')
        if bv_idx is not None:
            bv = bufferViews[bv_idx]
            offset = bv.get('byteOffset', 0)
            length = bv['byteLength']
            img_bytes = bin_buf[offset:offset+length]
            mime = img.get('mimeType', 'image/jpeg')
            ext = 'png' if 'png' in mime else 'jpg'
            fname = f'tex_{i}.{ext}'
            with open(os.path.join(textures_dir, fname), 'wb') as out_f:
                out_f.write(img_bytes)
            tex_files[i] = fname

    # Select animation
    selected_anim = next((a for a in gltf['animations'] if a['name'] == anim_name), gltf['animations'][0])
    anim_data = {}
    max_frame = 0

    for ch in selected_anim['channels']:
        target = ch['target']
        node_idx = target['node']
        prop = target['path']
        sampler = selected_anim['samplers'][ch['sampler']]
        times = read_accessor(sampler['input'])
        values = read_accessor(sampler['output'])

        if node_idx not in anim_data:
            anim_data[node_idx] = {}

        samples = []
        for t, v in zip(times, values):
            frame = round(t * 30)
            max_frame = max(max_frame, frame)
            if prop == 'rotation':
                # glTF (x, y, z, w) -> USD quatf (w, x, y, z)
                samples.append((frame, (v[3], v[0], v[1], v[2])))
            elif prop == 'translation':
                samples.append((frame, (v[0], v[1], v[2])))
        anim_data[node_idx][prop] = samples

    # Build USDA
    usda_lines = []
    usda_lines.append('#usda 1.0')
    usda_lines.append('(')
    usda_lines.append('    defaultPrim = "World"')
    usda_lines.append('    metersPerUnit = 1.0')
    usda_lines.append('    upAxis = "Y"')
    usda_lines.append('    startTimeCode = 0')
    usda_lines.append(f'    endTimeCode = {max_frame}')
    usda_lines.append('    timeCodesPerSecond = 30')
    usda_lines.append('    customLayerData = {')
    usda_lines.append('        bool autoPlay = 1')
    usda_lines.append('        string playbackMode = "loop"')
    usda_lines.append('    }')
    usda_lines.append(')')
    usda_lines.append('')
    usda_lines.append('def Xform "World" (')
    usda_lines.append('    apiSchemas = ["Preliminary_AnchoringAPI"]')
    usda_lines.append(')')
    usda_lines.append('{')
    usda_lines.append('    token preliminary:anchoring:type = "plane"')
    usda_lines.append('    token preliminary:planeAnchoring:alignment = "horizontal"')
    usda_lines.append('')
    usda_lines.append('    def Scope "Materials"')
    usda_lines.append('    {')

    materials = gltf.get('materials', [])
    textures = gltf.get('textures', [])

    for mat_idx, mat in enumerate(materials):
        pbr = mat.get('pbrMetallicRoughness', {})
        base_color = pbr.get('baseColorFactor', [1.0, 1.0, 1.0, 1.0])
        roughness = pbr.get('roughnessFactor', 0.5)
        metallic = pbr.get('metallicFactor', 0.0)

        tex_fname = None
        if 'baseColorTexture' in pbr:
            tex_idx = pbr['baseColorTexture']['index']
            if tex_idx < len(textures):
                img_idx = textures[tex_idx].get('source')
                if img_idx in tex_files:
                    tex_fname = tex_files[img_idx]

        m_name = f'Material_{mat_idx}'
        usda_lines.append(f'        def Material "{m_name}"')
        usda_lines.append('        {')
        usda_lines.append(f'            token outputs:surface.connect = </World/Materials/{m_name}/Surf.outputs:surface>')
        usda_lines.append('            def Shader "Surf"')
        usda_lines.append('            {')
        usda_lines.append('                uniform token info:id = "UsdPreviewSurface"')
        if tex_fname:
            usda_lines.append(f'                color3f inputs:diffuseColor.connect = </World/Materials/{m_name}/DiffuseTex.outputs:rgb>')
        else:
            usda_lines.append(f'                color3f inputs:diffuseColor = ({base_color[0]:.3f}, {base_color[1]:.3f}, {base_color[2]:.3f})')
        usda_lines.append(f'                float inputs:roughness = {roughness:.3f}')
        usda_lines.append(f'                float inputs:metallic = {metallic:.3f}')
        usda_lines.append('                token outputs:surface')
        usda_lines.append('            }')
        if tex_fname:
            usda_lines.append('            def Shader "DiffuseTex"')
            usda_lines.append('            {')
            usda_lines.append('                uniform token info:id = "UsdUVTexture"')
            usda_lines.append(f'                asset inputs:file = @textures/{tex_fname}@')
            usda_lines.append(f'                float2 inputs:st.connect = </World/Materials/{m_name}/PrimvarReader.outputs:result>')
            usda_lines.append('                token inputs:sourceColorSpace = "sRGB"')
            usda_lines.append('                float3 outputs:rgb')
            usda_lines.append('            }')
            usda_lines.append('            def Shader "PrimvarReader"')
            usda_lines.append('            {')
            usda_lines.append('                uniform token info:id = "UsdPrimvarReader_float2"')
            usda_lines.append('                token inputs:varname = "st"')
            usda_lines.append('                float2 outputs:result')
            usda_lines.append('            }')
        usda_lines.append('        }')

    usda_lines.append('    }')
    usda_lines.append('')

    # Root Model Xform
    usda_lines.append('    def Xform "Ghost"')
    usda_lines.append('    {')
    usda_lines.append(f'        custom double3 xformOp:scale = ({scale_factor:.6f}, {scale_factor:.6f}, {scale_factor:.6f})')
    usda_lines.append('        uniform token[] xformOpOrder = ["xformOp:scale"]')
    usda_lines.append('')

    nodes = gltf['nodes']
    scene_root_nodes = gltf['scenes'][0]['nodes']

    def sanitize(name):
        return "".join(c if c.isalnum() or c == '_' else '_' for c in name)

    def write_node(n_idx, indent_level):
        ind = '    ' * indent_level
        n = nodes[n_idx]
        raw_name = n.get('name') or f'Node_{n_idx}'
        safe_name = sanitize(raw_name)

        usda_lines.append(f'{ind}def Xform "{safe_name}"')
        usda_lines.append(f'{ind}{{')

        xform_ops = []
        t = n.get('translation')
        r = n.get('rotation')

        n_anim = anim_data.get(n_idx, {})

        if 'translation' in n_anim:
            xform_ops.append('"xformOp:translate"')
            usda_lines.append(f'{ind}    custom double3 xformOp:translate.timeSamples = {{')
            for f, val in n_anim['translation']:
                usda_lines.append(f'{ind}        {f}: ({val[0]:.4f}, {val[1]:.4f}, {val[2]:.4f}),')
            usda_lines.append(f'{ind}    }}')
        elif t:
            xform_ops.append('"xformOp:translate"')
            usda_lines.append(f'{ind}    custom double3 xformOp:translate = ({t[0]:.4f}, {t[1]:.4f}, {t[2]:.4f})')

        if 'rotation' in n_anim:
            xform_ops.append('"xformOp:orient"')
            usda_lines.append(f'{ind}    custom quatf xformOp:orient.timeSamples = {{')
            for f, val in n_anim['rotation']:
                usda_lines.append(f'{ind}        {f}: ({val[0]:.4f}, {val[1]:.4f}, {val[2]:.4f}, {val[3]:.4f}),')
            usda_lines.append(f'{ind}    }}')
        elif r:
            xform_ops.append('"xformOp:orient"')
            usda_lines.append(f'{ind}    custom quatf xformOp:orient = ({r[3]:.4f}, {r[0]:.4f}, {r[1]:.4f}, {r[2]:.4f})')

        if xform_ops:
            usda_lines.append(f'{ind}    uniform token[] xformOpOrder = [{", ".join(xform_ops)}]')

        mesh_idx = n.get('mesh')
        if mesh_idx is not None:
            mesh = gltf['meshes'][mesh_idx]
            prim = mesh['primitives'][0]
            pos_list = read_accessor(prim['attributes']['POSITION'])
            nrm_list = read_accessor(prim['attributes']['NORMAL'])
            idx_list = read_accessor(prim['indices'])
            uv_list = read_accessor(prim['attributes']['TEXCOORD_0']) if 'TEXCOORD_0' in prim['attributes'] else []
            mat_idx = prim.get('material', 0)

            m_name = f'Mesh_{mesh_idx}'
            usda_lines.append(f'{ind}    def Mesh "{m_name}"')
            usda_lines.append(f'{ind}    {{')
            usda_lines.append(f'{ind}        rel material:binding = </World/Materials/Material_{mat_idx}>')
            usda_lines.append(f'{ind}        uniform token subdivisionScheme = "none"')

            pts_str = ", ".join(f"({p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f})" for p in pos_list)
            usda_lines.append(f'{ind}        point3f[] points = [{pts_str}]')

            num_faces = len(idx_list) // 3
            usda_lines.append(f'{ind}        int[] faceVertexCounts = [{", ".join(["3"]*num_faces)}]')

            idx_str = ", ".join(str(i) for i in idx_list)
            usda_lines.append(f'{ind}        int[] faceVertexIndices = [{idx_str}]')

            if nrm_list:
                nrm_str = ", ".join(f"({n[0]:.4f}, {n[1]:.4f}, {n[2]:.4f})" for n in nrm_list)
                usda_lines.append(f'{ind}        normal3f[] normals = [{nrm_str}] (')
                usda_lines.append(f'{ind}            interpolation = "vertex"')
                usda_lines.append(f'{ind}        )')

            if uv_list:
                uv_str = ", ".join(f"({u[0]:.4f}, {1.0 - u[1]:.4f})" for u in uv_list)
                usda_lines.append(f'{ind}        texCoord2f[] primvars:st = [{uv_str}] (')
                usda_lines.append(f'{ind}            interpolation = "vertex"')
                usda_lines.append(f'{ind}        )')

            usda_lines.append(f'{ind}    }}')

        for child_idx in n.get('children', []):
            write_node(child_idx, indent_level + 1)

        usda_lines.append(f'{ind}}}')

    for r_idx in scene_root_nodes:
        write_node(r_idx, 2)

    usda_lines.append('    }')
    usda_lines.append('}')

    usda_file = 'scratch/ghost_usdz_build/ghost.usda'
    with open(usda_file, 'w', encoding='utf-8') as out_f:
        out_f.write("\n".join(usda_lines))

    with zipfile.ZipFile(out_usdz_path, 'w', compression=zipfile.ZIP_STORED) as zf:
        zf.write(usda_file, 'ghost.usda')
        for fname in os.listdir(textures_dir):
            zf.write(os.path.join(textures_dir, fname), f'textures/{fname}')

    print(f"Successfully generated USDZ: {out_usdz_path} ({os.path.getsize(out_usdz_path)/1024/1024:.2f} MB)")

if __name__ == '__main__':
    build_usdz('models/ghost_animated.glb', 'models/ghost_animated.usdz', target_height=0.25, anim_name='Idle')
