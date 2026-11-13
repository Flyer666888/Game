import bpy,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
f=next(o for o in bpy.context.scene.objects if o.name.startswith('Front face | exact dragon reference'))
report={'matrix':[[v for v in row] for row in f.matrix_world],'has_custom_normals':f.data.has_custom_normals,'attributes':[a.name for a in f.data.attributes],'modifiers':[m.type for m in f.modifiers],'smooth_polygons':sum(p.use_smooth for p in f.data.polygons),'polygons':len(f.data.polygons),'normals':[tuple(f.data.vertices[i].normal) for i in [0,100,1000,10000]],'positions':[tuple(f.data.vertices[i].co) for i in [0,100,1000,10000]],'methods':[n for n in dir(f.data) if 'normal' in n]}
(OUT/'ReliefInspection.json').write_text(json.dumps(report,indent=2));print('RELIEF_INSPECTION',report)
