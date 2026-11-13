"""Read-only Blender inspection. Does not save or modify the supplied blend."""
import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector

out_dir = Path(__file__).resolve().parent
depsgraph = bpy.context.evaluated_depsgraph_get()
objects = []
visible_bounds = []
visible_triangles = 0
for obj in bpy.context.scene.objects:
    row = {
        'name': obj.name, 'type': obj.type, 'hide_render': obj.hide_render,
        'hide_viewport': obj.hide_viewport, 'hidden': obj.hide_get(),
        'parent': obj.parent.name if obj.parent else None,
        'location': list(obj.location), 'rotation_euler': list(obj.rotation_euler),
        'scale': list(obj.scale), 'dimensions': list(obj.dimensions),
        'modifiers': [{'name': m.name, 'type': m.type, 'show_render': m.show_render,
                       'show_viewport': m.show_viewport} for m in obj.modifiers],
    }
    if obj.type in ('MESH', 'CURVE', 'SURFACE', 'FONT'):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            world_points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
            lo = [min(p[a] for p in world_points) for a in range(3)] if world_points else []
            hi = [max(p[a] for p in world_points) for a in range(3)] if world_points else []
            row.update(evaluated_vertices=len(mesh.vertices), evaluated_triangles=len(mesh.loop_triangles),
                       bounds_min=lo, bounds_max=hi,
                       uv_layers=[uv.name for uv in mesh.uv_layers],
                       materials=[m.name if m else None for m in mesh.materials])
            if not obj.hide_render:
                visible_triangles += len(mesh.loop_triangles)
                visible_bounds.extend((Vector(lo), Vector(hi)))
        finally:
            evaluated.to_mesh_clear()
    objects.append(row)

material_rows = []
for mat in bpy.data.materials:
    row = {'name': mat.name, 'use_nodes': mat.use_nodes, 'diffuse_color': list(mat.diffuse_color),
           'nodes': [], 'links': []}
    if mat.node_tree:
        for node in mat.node_tree.nodes:
            node_row = {'name': node.name, 'type': node.type}
            if hasattr(node, 'image'):
                node_row['image'] = node.image.name if node.image else None
            if node.type == 'UVMAP':
                node_row['uv_map'] = node.uv_map
            if node.type == 'BSDF_PRINCIPLED':
                node_row['unlinked_inputs'] = {
                    s.name: (list(s.default_value) if hasattr(s.default_value, '__len__') else s.default_value)
                    for s in node.inputs if not s.is_linked and hasattr(s, 'default_value')
                    and s.name in ('Base Color', 'Metallic', 'Roughness', 'Alpha', 'Specular IOR Level')}
            if node.type == 'NORMAL_MAP':
                node_row['strength'] = node.inputs['Strength'].default_value
                node_row['space'] = node.space
            row['nodes'].append(node_row)
        row['links'] = [{'from': l.from_node.name, 'from_socket': l.from_socket.name,
                         'to': l.to_node.name, 'to_socket': l.to_socket.name} for l in mat.node_tree.links]
    material_rows.append(row)

report = {
    'blender_version': bpy.app.version_string, 'source': bpy.data.filepath,
    'unit_system': bpy.context.scene.unit_settings.system,
    'unit_scale': bpy.context.scene.unit_settings.scale_length,
    'all_object_count': len(objects),
    'visible_geometry_count': sum(o['type'] in ('MESH', 'CURVE', 'SURFACE', 'FONT') and not o['hide_render'] for o in objects),
    'visible_evaluated_triangles': visible_triangles,
    'visible_bounds_min': [min(p[a] for p in visible_bounds) for a in range(3)],
    'visible_bounds_max': [max(p[a] for p in visible_bounds) for a in range(3)],
    'objects': objects, 'materials': material_rows,
    'images': [{'name': i.name, 'filepath': i.filepath, 'absolute_path': bpy.path.abspath(i.filepath),
                'external_exists': Path(bpy.path.abspath(i.filepath)).is_file() if i.filepath else False,
                'packed': bool(i.packed_file), 'size': list(i.size), 'source': i.source,
                'colorspace': i.colorspace_settings.name} for i in bpy.data.images],
    'actions': [a.name for a in bpy.data.actions],
    'notes': ['All bounds are evaluated world bounds in Blender scene units.',
              'Render-visible filtering is essential: original approximate relief is hidden in refined source.'],
}
(out_dir / 'DragonShieldSourceInspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: report[k] for k in ('source', 'visible_geometry_count', 'visible_evaluated_triangles',
                                      'visible_bounds_min', 'visible_bounds_max', 'unit_system', 'unit_scale')}, ensure_ascii=False))
