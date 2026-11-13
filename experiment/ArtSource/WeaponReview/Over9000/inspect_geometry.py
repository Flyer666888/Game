import bpy, json, math, re, os
from pathlib import Path
from mathutils import Vector, Matrix
ROOT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
report=[]
for p in sorted(ROOT.glob('*.fbx')):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(p), use_custom_normals=True)
    objs=[o for o in bpy.data.objects if o not in before and o.type=='MESH']
    coords=[o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo=[min(v[i] for v in coords) for i in range(3)]; hi=[max(v[i] for v in coords) for i in range(3)]
    report.append(dict(name=p.stem,min=lo,max=hi,dimensions=[hi[i]-lo[i] for i in range(3)],objects=[o.name for o in objs]))
(ROOT/'BlenderGeometry.json').write_text(json.dumps(report,indent=2))
print('GEOMETRY_READY',report[:2])
