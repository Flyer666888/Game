"""Prepare a canonical static shield FBX without saving the source blend.

Run Blender background with --disable-autoexec and the supplied refined blend.
Only this directory receives outputs; source meshes, images and blend stay intact.
"""
import bpy
import hashlib
import json
import shutil
from pathlib import Path
from mathutils import Matrix, Vector

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = Path(bpy.data.filepath).resolve()
SOURCE_SHA = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
FACTOR = 100.0 * 46.0 / 82.0
CANONICAL = Matrix(((0.0, -FACTOR, 0.0, 0.0),
                    (FACTOR, 0.0, 0.0, 0.0),
                    (0.0, 0.0, FACTOR, 0.0),
                    (0.0, 0.0, 0.0, 1.0)))
scene = bpy.context.scene
sources = [o for o in scene.objects if o.type in ('MESH', 'CURVE') and not o.hide_render]
source_names = [o.name for o in sources]
source_materials = sorted([m for m in bpy.data.materials if m.use_nodes], key=lambda m: m.name)
if len(source_materials) != 8:
    raise RuntimeError('Expected the eight supplied shield materials.')

image_exports = {}
def export_image(image, file_name):
    if image.name in image_exports:
        return image_exports[image.name]
    target = OUT / file_name
    external = Path(bpy.path.abspath(image.filepath)) if image.filepath else None
    if external and external.is_file():
        # Import may hold a read handle on an unchanged local source texture.
        # Reuse identical content without opening its destination for writing.
        if not target.is_file() or hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(external.read_bytes()).digest():
            shutil.copy2(external, target)
    elif image.packed_file:
        # A copy avoids changing filepath or packing of the supplied image datablock.
        copy = image.copy()
        copy.filepath_raw = str(target)
        copy.file_format = 'PNG'
        copy.save()
        bpy.data.images.remove(copy)
    else:
        raise RuntimeError('Missing shield image: ' + image.name)
    image_exports[image.name] = str(target.resolve())
    return image_exports[image.name]

materials = []
for slot, material in enumerate(source_materials):
    original_name = material.name
    bsdf = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    base = bsdf.inputs['Base Color']
    color = list(base.default_value)
    color_ramp = None
    if base.is_linked:
        color_node = base.links[0].from_node
        if color_node.type == 'VALTORGB':
            color = list(color_node.color_ramp.evaluate(0.5))
            color_ramp = [{'position': e.position, 'color': list(e.color)}
                          for e in color_node.color_ramp.elements]
    face = original_name.startswith('Reference fidelity')
    row = {'slot': slot, 'ue_name': 'M_DragonShield_%02d' % slot,
           'name': original_name, 'color': color,
           'metallic': float(bsdf.inputs['Metallic'].default_value),
           'roughness': float(bsdf.inputs['Roughness'].default_value),
           'base_color_texture': None, 'normal_texture': None,
           'normal_uv_index': 1 if face else 0,
           'normal_strength': 0.18 if face else 0.0,
           'source_color_ramp': color_ramp,
           'procedural_shader_approximated': not face,
           'approximation': None if face else 'Noise color reduced to ColorRamp midpoint; procedural bump omitted.'}
    if face:
        if not base.is_linked or base.links[0].from_node.type != 'TEX_IMAGE':
            raise RuntimeError('Unexpected face base color graph.')
        row['base_color_texture'] = export_image(base.links[0].from_node.image, 'T_DragonShield_Reference.jpg')
        normal_map = next(n for n in material.node_tree.nodes if n.type == 'NORMAL_MAP')
        normal_texture_node = normal_map.inputs['Color'].links[0].from_node
        row['normal_texture'] = export_image(normal_texture_node.image, 'T_DragonShield_ReferenceNormal.png')
        row['source_normal_strength'] = float(normal_map.inputs['Strength'].default_value)
        row['base_color_uv_index'] = 0
    materials.append(row)

# Evaluate visible source pieces into fresh meshes, retaining both face UVs.
# Hidden approximate dragon relief remains in the editable source and is excluded.
collection = bpy.data.collections.new('UE shield export only')
scene.collection.children.link(collection)
depsgraph = bpy.context.evaluated_depsgraph_get()
export_objects = []
uv_sources = []
untextured_uv_faces_repaired = 0
untextured_uv_loops_repaired = 0
face_uv_degenerate_polygons_preserved = 0
for index, source in enumerate(sources):
    evaluated = source.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
    source_slots = list(mesh.materials)
    slot_indices = [source_materials.index(m) if m in source_materials else 0 for m in source_slots]
    polygon_slots = [slot_indices[p.material_index] if p.material_index < len(slot_indices) else 0
                     for p in mesh.polygons]
    mesh.materials.clear()
    for material in source_materials:
        mesh.materials.append(material)
    for polygon, slot_index in zip(mesh.polygons, polygon_slots):
        polygon.material_index = slot_index
    mesh.transform(CANONICAL @ source.matrix_world)
    mesh.update()

    old_layers = [layer.name for layer in mesh.uv_layers]
    face = source.name.startswith('Front face | exact dragon reference')
    if face and old_layers[:2] != ['ReferenceCropUV', 'ReferenceNormalUV']:
        raise RuntimeError('Shield face UV channels differ from supplied source.')
    if not mesh.uv_layers:
        mesh.uv_layers.new(name='UV0')
        for polygon in mesh.polygons:
            dominant = max(range(3), key=lambda a: abs(polygon.normal[a]))
            plane = [a for a in range(3) if a != dominant]
            for loop_index in polygon.loop_indices:
                point = mesh.vertices[mesh.loops[loop_index].vertex_index].co
                mesh.uv_layers[0].data[loop_index].uv = (point[plane[0]] / 46.0 + 0.5,
                                                       point[plane[1]] / 46.0 + 0.5)
    if len(mesh.uv_layers) < 2:
        second = mesh.uv_layers.new(name='UV1')
        for dst, src in zip(second.data, mesh.uv_layers[0].data):
            dst.uv = src.uv
    # Converted ornaments can carry collapsed UVs despite having named layers.
    # Give only untextured polygons a usable tangent basis, and preserve both
    # original image UV channels of the dragon face exactly.
    repaired_here = 0
    for polygon in mesh.polygons:
        loop_indices = list(polygon.loop_indices)
        collapsed = False
        for layer in list(mesh.uv_layers)[:2]:
            points = [layer.data[i].uv for i in loop_indices]
            area_twice = abs(sum(points[i].x * points[(i + 1) % len(points)].y
                                 - points[(i + 1) % len(points)].x * points[i].y
                                 for i in range(len(points))))
            if area_twice <= 1.0e-10:
                collapsed = True
                break
        if not collapsed:
            continue
        if face:
            face_uv_degenerate_polygons_preserved += 1
            continue
        dominant = max(range(3), key=lambda a: abs(polygon.normal[a]))
        plane = [a for a in range(3) if a != dominant]
        for layer in list(mesh.uv_layers)[:2]:
            for loop_index in loop_indices:
                point = mesh.vertices[mesh.loops[loop_index].vertex_index].co
                layer.data[loop_index].uv = (point[plane[0]] * 0.1, point[plane[1]] * 0.1)
        repaired_here += 1
        untextured_uv_loops_repaired += len(loop_indices)
    untextured_uv_faces_repaired += repaired_here
    # Distinct temporary names avoid Blender auto-suffix collisions on renaming.
    for i, layer in enumerate(mesh.uv_layers):
        layer.name = 'ExportTempUV%d' % i
    for layer in list(mesh.uv_layers)[2:]:
        mesh.uv_layers.remove(layer)
    mesh.uv_layers[0].name = 'UV0'
    mesh.uv_layers[1].name = 'UV1'
    mesh.uv_layers.active_index = 0
    mesh.uv_layers[0].active_render = True
    uv_sources.append({'object': source.name, 'source_uv_layers': old_layers,
                       'export_uv_layers': ['UV0', 'UV1'], 'face_uvs_preserved': face,
                       'untextured_degenerate_uv_faces_repaired': repaired_here})
    obj = bpy.data.objects.new('ShieldExportPart%03d' % index, mesh)
    collection.objects.link(obj)
    obj.matrix_world = Matrix.Identity(4)
    export_objects.append(obj)

bpy.ops.object.select_all(action='DESELECT')
for obj in export_objects:
    obj.select_set(True)
bpy.context.view_layer.objects.active = export_objects[0]
bpy.ops.object.join()
shield = bpy.context.object
shield.name = 'SM_DragonShield_Player'
shield.data.name = 'SM_DragonShield_Player_Geometry'
for material, row in zip(source_materials, materials):
    # This changes only the in-memory scene. No .blend save is performed.
    material.name = row['ue_name']
shield.data.calc_loop_triangles()
grip = CANONICAL @ Vector((0.0, 0.092, -0.01))
report = {
    'source': str(SOURCE), 'source_sha256': SOURCE_SHA,
    'source_parts': len(sources), 'source_object_names': source_names,
    'excluded_hidden_geometry': sum(o.type in ('MESH', 'CURVE') and o.hide_render for o in scene.objects),
    'triangles': len(shield.data.loop_triangles), 'vertices': len(shield.data.vertices),
    'bounds_cm': [[min(v.co[a] for v in shield.data.vertices), max(v.co[a] for v in shield.data.vertices)]
                  for a in range(3)],
    'grip_center_cm': list(grip), 'pivot_cm': [0.0, 0.0, 0.0],
    'direction': {'front': '+X', 'up': '+Z', 'horizontal': '+Y'},
    'source_front': '-Y', 'scale_cm_per_source_unit': FACTOR,
    'nominal_diameter_cm': 46.0, 'materials': materials,
    'images': image_exports, 'export_uv_channels': ['UV0', 'UV1'],
    'source_uv_channels': uv_sources,
    'untextured_degenerate_uv_faces_repaired': untextured_uv_faces_repaired,
    'untextured_uv_loops_repaired_per_channel': untextured_uv_loops_repaired,
    'face_degenerate_uv_polygons_preserved': face_uv_degenerate_polygons_preserved,
    'limitations': ['Procedural material noise/bump is approximated; face color and normal images are retained.',
                   'No triangle reduction applied; runtime LOD authoring may be performed during UE import.',
                   'Front dragon relief uses reference texture and subtle normal map rather than detailed sculpted geometry.'],
}
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.01
bpy.ops.export_scene.fbx(filepath=str(OUT / 'DragonShieldPrepared.fbx'), use_selection=True,
                         object_types={'MESH'}, apply_unit_scale=True,
                         apply_scale_options='FBX_SCALE_NONE', axis_forward='-Y', axis_up='Z',
                         mesh_smooth_type='FACE', bake_anim=False, path_mode='STRIP')
report['fbx'] = str((OUT / 'DragonShieldPrepared.fbx').resolve())
report['fbx_path'] = report['fbx']
report['source_unchanged'] = hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA
(OUT / 'DragonShieldPrepared.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('DRAGON_SHIELD_PREPARED', report['triangles'], 'triangles', len(shield.data.materials), 'material slots',
      'bounds_cm=', report['bounds_cm'], 'source_unchanged=', report['source_unchanged'])
