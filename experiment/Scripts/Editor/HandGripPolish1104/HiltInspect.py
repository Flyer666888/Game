import bpy,json,math
from pathlib import Path
from mathutils import Matrix,Vector
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/HandGripPolish1104'
bpy.ops.wm.open_mainfile(filepath=str(P/'ArtSource/Weapons/Yueyao/SlenderBladeRevision/Yueyao_Hero_Weapon_SlenderBlade.blend'))
T=Matrix.Rotation(math.pi/2,4,'Y')@Matrix.Translation(Vector((-.09672,0,0)))
dep=bpy.context.evaluated_depsgraph_get();rows=[]
for ob in bpy.context.scene.objects:
 if ob.type not in ['MESH','CURVE'] or ob.hide_render:continue
 ev=ob.evaluated_get(dep);me=ev.to_mesh();vs=[T@ob.matrix_world@v.co for v in me.vertices]
 rows.append({'name':ob.name,'verts':len(vs),'bounds_cm':[[100*min(v[i] for v in vs),100*max(v[i] for v in vs)] for i in range(3)],
 'vertices':list(map(list,vs)),'faces':[list(p.vertices) for p in me.polygons]});ev.to_mesh_clear()
(O/'HiltComponents.json').write_text(json.dumps(rows),encoding='utf-8')
print(json.dumps([{k:v for k,v in row.items() if k not in ['vertices','faces']} for row in rows],indent=2))
