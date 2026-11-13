"""Independent fresh FBX readback; does not trust the build scene."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path('D:/game design/experiment')
OUT=ROOT/'ArtSource/WeaponReview/SelectedA_DetailV01'
source=ROOT/'ArtSource/WeaponReview/Over9000/SelectedA/SM_PlayerSword_A.blend'
fbx=OUT/'SM_PlayerSword_A_DetailV01.fbx'
bpy.ops.wm.open_mainfile(filepath=str(source))
ob=next(o for o in bpy.data.objects if o.type=='MESH')
grip_ids={i for p in ob.data.polygons if ob.data.materials[p.material_index].name=='Grip04' for i in p.vertices}
original_grip=[tuple(ob.data.vertices[i].co) for i in sorted(grip_ids)]
orig_uv=[]
for p in ob.data.polygons:
    if ob.data.materials[p.material_index].name=='Grip04':
        orig_uv.extend([list(ob.data.uv_layers[0].data[i].uv) for i in p.loop_indices])
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.scale_length=1.0
bpy.ops.import_scene.fbx(filepath=str(fbx),use_custom_normals=True)
objects=[o for o in bpy.data.objects if o.type=='MESH'];assert len(objects)==1
o=objects[0];mesh=o.data;mesh.calc_loop_triangles()
points=[(o.matrix_world@v.co)*100 for v in mesh.vertices]
slots=[m.name.split('.')[0] for m in mesh.materials]
expected=['BladeSteel','BladeEdge','BladeFuller','Guard03','Grip04','Pommel03','GoldDetail']
assert slots==expected,slots
bounds=[[min(v[i] for v in points) for i in range(3)],[max(v[i] for v in points) for i in range(3)]]
triangles=len(mesh.loop_triangles);assert 5000<triangles<15000,triangles
assert abs(bounds[1][2]-64.9390869)<.001,bounds
assert abs(bounds[0][2]+13.3752184)<.001,bounds
assert all(math.isfinite(v) for p in points for v in p)
assert len(mesh.uv_layers)==2
small=[];zero=[]
for i,t in enumerate(mesh.loop_triangles):
    a,b,c=[points[j] for j in t.vertices];area=(b-a).cross(c-a).length*.5
    if area<1e-10:zero.append(i)
    if area<1e-6:small.append(i)
if zero:
    print('ZERO_TRIANGLES_BY_SLOT', {s:sum(1 for i in zero if slots[mesh.loop_triangles[i].material_index]==s) for s in slots})
    print('ZERO_EXAMPLES',[(slots[mesh.loop_triangles[i].material_index],[list(points[j]) for j in mesh.loop_triangles[i].vertices]) for i in zero[:5]])
assert not zero,len(zero)
grip={i for p in mesh.polygons if slots[p.material_index]=='Grip04' for i in p.vertices}
current_grip=[points[i] for i in grip]
max_grip_distance=max(min((p-Vector(v)).length for p in current_grip) for v in original_grip)
assert max_grip_distance<.0001,max_grip_distance
uv_finite=all(math.isfinite(x) for l in mesh.uv_layers for d in l.data for x in d.uv);assert uv_finite
bm=bmesh.new();bm.from_mesh(mesh)
bladefaces=[f for f in bm.faces if slots[f.material_index] in ['BladeSteel','BladeEdge','BladeFuller']]
bladeedges={e for f in bladefaces for e in f.edges}
badblade=[e for e in bladeedges if len([f for f in e.link_faces if f in bladefaces])!=2]
assert not badblade,len(badblade)
counts={s:sum(1 for t in mesh.loop_triangles if slots[t.material_index]==s) for s in slots}
report={'state':'passed','verification':'Independent new Blender FBX import','fbx':str(fbx),'fbx_sha256':hashlib.sha256(fbx.read_bytes()).hexdigest(),
 'triangles':triangles,'triangles_by_material':counts,'slots':slots,'uv_channels':len(mesh.uv_layers),'bounds_cm':{'min':bounds[0],'max':bounds[1]},
 'zero_area_triangles':len(zero),'very_small_triangle_count_area_under_1e_minus_6_cm2':len(small),'blade_nonmanifold_edges':len(badblade),
 'unchanged_grip_max_vertex_delta_cm':max_grip_distance,'finite_coordinates_and_uvs':True,'source_blend_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'scope':'Static geometry and FBX roundtrip only. Root integration owns UE import, in-engine normals, performance and VR fit.'}
(OUT/'AssetReadbackReport.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(ROOT/'Docs/Gameplay/VRWeaponPolish_v01/AssetReadbackReport.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ASSET_READBACK_PASSED',json.dumps(report))
