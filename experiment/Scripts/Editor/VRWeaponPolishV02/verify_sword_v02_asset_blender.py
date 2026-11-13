"""Independent fresh FBX readback; does not trust the build scene."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path('D:/game design/experiment')
OUT=ROOT/'ArtSource/WeaponReview/SelectedA_DetailV02'
source=ROOT/'ArtSource/WeaponReview/Over9000/SelectedA/SM_PlayerSword_A.blend'
fbx=OUT/'SM_PlayerSword_A_DetailV02.fbx'
bpy.ops.wm.open_mainfile(filepath=str(source))
ob=next(o for o in bpy.data.objects if o.type=='MESH')
grip_ids={i for p in ob.data.polygons if ob.data.materials[p.material_index].name=='Grip04' for i in p.vertices}
original_grip=[tuple(ob.data.vertices[i].co) for i in sorted(grip_ids)]
orig_uv=[]
orig_grip_uv_channels=[]
source_bad_grip_face_keys=[]
def face_key(coords):return tuple(sorted(tuple(round(float(x),4) for x in co) for co in coords))
ob.data.calc_loop_triangles()
for layer in ob.data.uv_layers:
    bad=set()
    for tri in ob.data.loop_triangles:
        if ob.data.materials[tri.material_index].name!='Grip04':continue
        a,b,c=[layer.data[l].uv for l in tri.loops]
        area=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5
        if area<=1e-10:bad.add(tri.polygon_index)
    source_bad_grip_face_keys.append({face_key([ob.data.vertices[i].co for i in ob.data.polygons[p].vertices]) for p in bad})
    orig_grip_uv_channels.append(sorted(tuple(layer.data[i].uv) for p in ob.data.polygons if ob.data.materials[p.material_index].name=='Grip04' and p.index not in bad for i in p.loop_indices))
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
triangles=len(mesh.loop_triangles);assert 5000<triangles<18000,triangles
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
uv_statistics=[];grip_uv_delta=[]
for layer_i,layer in enumerate(mesh.uv_layers):
    by_slot={s:{'zero_uv_area':0,'near_zero_uv_area_under_1e_minus_10':0,'min_abs_uv_area':1e20} for s in slots}
    for tri in mesh.loop_triangles:
        a,b,c=[layer.data[l].uv for l in tri.loops]
        area=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5
        group=by_slot[slots[tri.material_index]];group['min_abs_uv_area']=min(group['min_abs_uv_area'],area)
        if area<=1e-16:group['zero_uv_area']+=1
        if area<=1e-10:group['near_zero_uv_area_under_1e_minus_10']+=1
    for name,group in by_slot.items():
        assert group['near_zero_uv_area_under_1e_minus_10']==0,(name,group)
    uv_statistics.append({'layer':layer.name,'materials':by_slot})
    current=sorted(tuple(layer.data[l].uv) for p in mesh.polygons if slots[p.material_index]=='Grip04' and face_key([points[i] for i in p.vertices]) not in source_bad_grip_face_keys[layer_i] for l in p.loop_indices)
    original=orig_grip_uv_channels[layer_i];assert len(current)==len(original)
    delta=max(abs(a[i]-b[i]) for a,b in zip(current,original) for i in [0,1]);assert delta<1e-6,delta
    grip_uv_delta.append(delta)
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
 'uv_statistics':uv_statistics,'nondegenerate_original_grip_uv_max_delta_per_channel':grip_uv_delta,
 'source_grip_repaired_uv_polygon_count_per_channel':[len(x) for x in source_bad_grip_face_keys],
 'uv_note':'All triangles in both UV channels have nonzero area. Only 16 originally-degenerate grip collar/inner connection faces were repaired; every other original Grip04 UV value is unchanged.',
 'scope':'Static geometry and FBX roundtrip only. Root integration owns UE import, in-engine normals, performance and VR fit.'}
(OUT/'AssetReadbackReport.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(ROOT/'Docs/Gameplay/VRWeaponPolish_v02/AssetReadbackReport.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ASSET_READBACK_PASSED',json.dumps(report))

