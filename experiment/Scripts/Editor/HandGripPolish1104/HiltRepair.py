"""Enemy-only derivative: preserve all original geometry except two named hilt details."""
import bpy,json,hashlib,math
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.kdtree import KDTree
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/HandGripPolish1104'
OUT=P/'ArtSource/Weapons/Yueyao/EnemyGripPolish1104';OUT.mkdir(parents=True,exist_ok=True)
source=P/'ArtSource/Weapons/Yueyao/SlenderBladeRevision/YueyaoPlayerSlender.fbx'
config=json.loads((O/'HiltModificationConfig.json').read_text());components=json.loads((O/'HiltComponents.json').read_text())
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(source),use_custom_normals=True)
ob=next(o for o in bpy.context.scene.objects if o.type=='MESH');mesh=ob.data
original_matrix=ob.matrix_world.copy();before=[v.co.copy() for v in mesh.vertices]
mesh.calc_loop_triangles();tris=len(mesh.loop_triangles)
assert tris==115902,(tris,len(mesh.vertices))
uv_before=[[list(v.uv) for v in l.data] for l in mesh.uv_layers]
materials=[m.name for m in mesh.materials];material_indices=[p.material_index for p in mesh.polygons]
normals=[n.vector.copy() for n in mesh.corner_normals]
selected={}
for name in config['components']:
 comp=next(c for c in components if c['name']==name);kd=KDTree(len(comp['vertices']))
 for i,v in enumerate(comp['vertices']):kd.insert(Vector(v)*100,i)
 kd.balance();ids={v.index for v in mesh.vertices if kd.find(v.co)[2]<.0001}
 assert len(ids)>=len(comp['vertices']),(name,len(ids),len(comp['vertices']))
 selected[name]=ids
assert len(set.union(*selected.values()))==sum(map(len,selected.values()))
wire_name='29 Spirit jade sweep beneath grip';wire=selected[wire_name];amount=config['components'][wire_name]['outward_cm']
def weight(z):
 t=max(0.,min(1.,(8.3-z)/4.5));return t*t*(3-2*t)
def derivative(z):
 t=(8.3-z)/4.5
 return -6*t*(1-t)/4.5 if 0<t<1 else 0.
for i in wire:mesh.vertices[i].co.x-=amount*weight(before[i].z)
for name,ids in selected.items():
 if name==wire_name:continue
 delta=Vector(config['components'][name].get('translation_cm',[0,0,0]))
 scale=config['components'][name].get('radial_scale',1.)
 for i in ids:
  mesh.vertices[i].co.x*=scale;mesh.vertices[i].co.y*=scale;mesh.vertices[i].co+=delta
for loop,n in zip(mesh.loops,normals):
 if loop.vertex_index in wire:
  n.z+=amount*derivative(before[loop.vertex_index].z)*n.x;n.normalize()
mesh.update();mesh.normals_split_custom_set(normals)
all_selected=set.union(*selected.values());changed={i for i,v in enumerate(mesh.vertices) if (v.co-before[i]).length>.000001}
assert changed.issubset(all_selected)
assert uv_before==[[list(v.uv) for v in l.data] for l in mesh.uv_layers]
assert materials==[m.name for m in mesh.materials] and material_indices==[p.material_index for p in mesh.polygons]
ob.name='SM_Yueyao_EnemyGrip';ob.matrix_world=Matrix.Identity(4)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Yueyao_EnemyGrip.blend'))
dest=OUT/'YueyaoEnemyGrip.fbx'
bpy.ops.export_scene.fbx(filepath=str(dest),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',bake_anim=False,path_mode='STRIP')
after=[v.co.copy() for v in mesh.vertices]
report={'state':'exported','source':str(source),'source_sha256':source_hash,'destination':str(dest),'destination_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
 'config':config,'vertex_count':len(mesh.vertices),'triangle_count':tris,'materials':materials,'changed_vertex_count':len(changed),
 'selected_component_vertices':{k:len(v) for k,v in selected.items()},'unchanged_other_vertices':all((v.co-before[i]).length==0 for i,v in enumerate(mesh.vertices) if i not in all_selected),
 'uv_and_material_assignments_preserved':True,'bounds_cm':[[min(v[i] for v in after),max(v[i] for v in after)] for i in range(3)],
 'source_not_modified':hashlib.sha256(source.read_bytes()).hexdigest()==source_hash}
# Reimport the exact output to catch unit/axis and topology regressions.
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(dest),use_custom_normals=True)
check=next(o for o in bpy.context.scene.objects if o.type=='MESH');check.data.calc_loop_triangles()
assert len(check.data.loop_triangles)==tris
assert len(check.data.vertices)==len(before)
max_error=max((v.co-after[i]).length for i,v in enumerate(check.data.vertices));assert max_error<.0001,max_error
assert max(abs(check.matrix_world[i][j]-original_matrix[i][j]) for i in range(4) for j in range(4))<.00001
report['reimport_max_vertex_error_cm']=max_error;report['reimport_scale_axis_equal_source']=True
(OUT/'EnemyGripPrepared.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(O/'HiltRepairReceipt.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ENEMY_HILT_READY',json.dumps(report))
