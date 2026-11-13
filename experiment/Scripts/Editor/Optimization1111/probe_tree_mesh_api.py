"""Inspect reflected read-only static-mesh triangle return shapes."""
import json
from pathlib import Path
import unreal

out = Path(unreal.Paths.project_dir()).resolve() / 'Docs/Gameplay/Optimization1111/TreeClearance/TriangleAPI.json'
mesh = unreal.load_asset('/Game/AsianTemple/Environment/Mesh/SM_Tree_Big_01a')
description = mesh.get_static_mesh_description(0)
rows = []
for index in range(6):
    triangle = unreal.TriangleID(id_value=index)
    if description.is_triangle_valid(triangle):
        result = description.get_triangle_vertices(triangle)
        rows.append({'index': index, 'type': type(result).__name__, 'repr': repr(result),
                     'length': len(result), 'items': [{'type': type(x).__name__, 'repr': repr(x)} for x in result]})
out.write_text(json.dumps({'vertex_count': description.get_vertex_count(), 'triangle_count': description.get_triangle_count(),
    'doc': description.get_triangle_vertices.__doc__, 'rows': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('OPT1111_TRIANGLE_API_READ')
