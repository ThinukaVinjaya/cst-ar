#!/usr/bin/env python3
"""
Converts models/ghost_salute_lite.glb -> models/ghost_salute_blender.usdz
using official Blender (bpy) native USDZ skeletal animation exporter for Apple AR Quick Look.
"""
import os
import bpy

GLB_PATH = os.path.abspath('models/ghost_salute_lite.glb')
OUT_USDZ = os.path.abspath('models/ghost_salute_blender.usdz')


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Import our pre-oriented, 25cm tabletop, 42K-tri animated GLB
    bpy.ops.import_scene.gltf(filepath=GLB_PATH)

    scene = bpy.context.scene
    scene.render.fps = 24

    # Ensure frame range matches the imported Salute action exactly
    f_start, f_end = 0, 68
    if bpy.data.actions:
        act = bpy.data.actions[0]
        f_start = int(round(act.frame_range[0]))
        f_end = int(round(act.frame_range[1]))
        print(f'Loaded action: {act.name}, range: {f_start}..{f_end}')
    scene.frame_start = f_start
    scene.frame_end = f_end
    scene.frame_set(f_start)

    # Remove unused glTF bone display Icosphere and invisible alpha=0 helper mesh (Object_19 / Mat 10)
    for obj in list(bpy.data.objects):
        if obj.name == 'Icosphere' or obj.name == 'Object_19':
            print('Removing helper object:', obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)

    print('Objects in scene:', [(o.name, o.type) for o in bpy.data.objects])

    # Build kwargs dynamically from Blender's usd_export operator RNA so it works across Blender 4.x / 5.x
    rna_props = {p.identifier for p in bpy.ops.wm.usd_export.get_rna_type().properties}
    desired = {
        'filepath': OUT_USDZ,
        'selected_objects_only': False,
        'visible_objects_only': True,
        'export_animation': True,
        'export_armatures': True,
        'export_shapekeys': True,
        'export_materials': True,
        'generate_preview_surface': True,
        'export_textures': True,
        'export_textures_mode': 'NEW',
        'export_uvmaps': True,
        'export_normals': True,
        'export_mesh_colors': False,
        'use_instancing': False,
        'evaluation_mode': 'RENDER',
        'root_prim_path': '/GhostSalute',
        'convert_orientation': True,
        'export_global_forward_selection': 'NEGATIVE_Z',
        'export_global_up_selection': 'Y',
        'convert_scene_units': 'CENTIMETERS',
        'usdz_downscale_size': 'KEEP',
    }
    kwargs = {k: v for k, v in desired.items() if k in rna_props}
    print('Calling bpy.ops.wm.usd_export with:', kwargs)
    bpy.ops.wm.usd_export(**kwargs)
    print(f'Exported Blender USDZ: {OUT_USDZ} ({os.path.getsize(OUT_USDZ)/1048576:.2f} MB)')


if __name__ == '__main__':
    main()
