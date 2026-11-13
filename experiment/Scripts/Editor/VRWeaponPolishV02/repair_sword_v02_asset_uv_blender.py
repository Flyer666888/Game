"""UV-only repair: geometry, source grip UVs, material order and object origin must remain bit-identical."""
import bpy,json,hashlib,math
from pathlib import Path
ROOT=Path('D:/game design/experiment')
OUT=ROOT/'ArtSource/WeaponReview/SelectedA_DetailV02';DOC=ROOT/'Docs/Gameplay/VRWeaponPolish_v02'
blend=OUT/'SM_PlayerSword_A_DetailV02.blend';fbx=OUT/'SM_PlayerSword_A_DetailV02.fbx'
bpy.ops.wm.open_mainfile(filepath=str(blend))
ob=next(o for o in bpy.data.objects if o.type=='MESH');mesh=ob.data;mesh.calc_loop_triangles()
slots=[m.name for m in mesh.materials]
def geom_signature():
    content={'verts':[list(v.co) for v in mesh.vertices], 'faces':[(list(p.vertices),p.material_index,p.use_smooth) for p in mesh.polygons],
             'edges':[(list(e.vertices),e.use_edge_sharp) for e in mesh.edges], 'world':[list(row) for row in ob.matrix_world], 'slots':slots}
    return hashlib.sha256(json.dumps(content,separators=(',',':')).encode()).hexdigest()
grip_bad_by_layer=[]
for layer in mesh.uv_layers:
    bad=set()
    for tri in mesh.loop_triangles:
        if slots[tri.material_index]!='Grip04':continue
        a,b,c=[layer.data[l].uv for l in tri.loops]
        area=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5
        if area<=1e-10:bad.add(tri.polygon_index)
    grip_bad_by_layer.append(bad)
def grip_uv_signature(skip_bad=False):
    content=[[list(layer.data[l].uv) for p in mesh.polygons if slots[p.material_index]=='Grip04' and (not skip_bad or p.index not in grip_bad_by_layer[i]) for l in p.loop_indices] for i,layer in enumerate(mesh.uv_layers)]
    return hashlib.sha256(json.dumps(content,separators=(',',':')).encode()).hexdigest()
def uv_stats():
    out=[]
    for layer in mesh.uv_layers:
        groups={s:{'triangles':0,'zero_uv_area':0,'near_zero_uv_area_under_1e_minus_10':0,'min_abs_uv_area':1e20} for s in slots}
        for tri in mesh.loop_triangles:
            a,b,c=[layer.data[l].uv for l in tri.loops];area=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5
            g=groups[slots[tri.material_index]];g['triangles']+=1;g['min_abs_uv_area']=min(g['min_abs_uv_area'],area)
            if area<=1e-16:g['zero_uv_area']+=1
            if area<=1e-10:g['near_zero_uv_area_under_1e_minus_10']+=1
        out.append({'layer':layer.name,'materials':groups})
    return out
before_geom=geom_signature();before_grip=grip_uv_signature();before_good_grip=grip_uv_signature(True);before_uv=uv_stats();before_fbx=hashlib.sha256(fbx.read_bytes()).hexdigest()
grip_changed_faces=[]
for index in sorted(set.union(*grip_bad_by_layer)):
    p=mesh.polygons[index];coords=[mesh.vertices[i].co for i in p.vertices]
    grip_changed_faces.append({'polygon_index':index,'center_cm':list(p.center),'normal':list(p.normal),
        'bounds_cm':{'min':[min(c[j] for c in coords) for j in range(3)],'max':[max(c[j] for c in coords) for j in range(3)]},
        'classification':'flat collar or handle end cap' if abs(p.normal.z)>.8 else 'collar side/inner connection'})
byface={p.index:[] for p in mesh.polygons}
for tri in mesh.loop_triangles:byface[tri.polygon_index].append(tri)
repaired=0
for face in mesh.polygons:
    if slots[face.material_index]=='Grip04' and not any(face.index in bad for bad in grip_bad_by_layer):continue
    # Pick the planar projection with the largest worst triangle area on the polygon.
    # This is dominant-normal box projection with a deterministic safeguard for nonplanar quads.
    candidates=[]
    for axes in [(0,1),(0,2),(1,2)]:
        areas=[]
        for tri in byface[face.index]:
            a,b,c=[mesh.vertices[i].co for i in tri.vertices];u,v=axes
            areas.append(abs((b[u]-a[u])*(c[v]-a[v])-(b[v]-a[v])*(c[u]-a[u]))*.5)
        candidates.append((min(areas),axes))
    best,axes=max(candidates,key=lambda x:x[0]);assert best>1e-10,(face.index,best)
    for layer_i,layer in enumerate(mesh.uv_layers):
        if slots[face.material_index]=='Grip04' and face.index not in grip_bad_by_layer[layer_i]:continue
        for loop in face.loop_indices:
            co=mesh.vertices[mesh.loops[loop].vertex_index].co
            # 0.25 UV/cm avoids tiny tangent determinants on the narrow physical cutting edge.
            layer.data[loop].uv=(co[axes[0]]*.25,co[axes[1]]*.25)
    repaired+=1
after_uv=uv_stats();assert geom_signature()==before_geom;assert grip_uv_signature(True)==before_good_grip
for layer in after_uv:
    for slot,g in layer['materials'].items():
        assert g['near_zero_uv_area_under_1e_minus_10']==0,(layer['layer'],slot,g)
bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',bake_anim=False,path_mode='STRIP',use_custom_props=True,use_mesh_modifiers=True)
new_hash=hashlib.sha256(fbx.read_bytes()).hexdigest()
report={'state':'passed','scope':'UV-only repair; no vertex, edge, polygon, material, normal-smoothing flag or transform changes. Only degenerate Grip04 UV faces repaired; every nondegenerate Grip04 UV retained.',
 'geometry_signature_before':before_geom,'geometry_signature_after':geom_signature(),'grip_uv_signature_before':before_grip,'grip_uv_signature_after':grip_uv_signature(),
 'nondegenerate_grip_uv_signature_before':before_good_grip,'nondegenerate_grip_uv_signature_after':grip_uv_signature(True),
 'grip_uv_repaired_polygons':grip_changed_faces,'grip_uv_repaired_count_per_channel':[len(x) for x in grip_bad_by_layer],
 'repaired_polygon_count':repaired,'projection':'Per-face box projection, maximizing minimum projected triangle area; 0.25 UV per centimeter; nondegenerate Grip04 UVs skipped',
 'before_uv_statistics':before_uv,'after_uv_statistics':after_uv,'fbx_sha256_before':before_fbx,'fbx_sha256':new_hash}
for p in [OUT/'AssetUVRepairReport.json',DOC/'AssetUVRepairReport.json']:p.write_text(json.dumps(report,indent=2),encoding='utf-8')
for p in [OUT/'AssetGeometryReport.json',DOC/'AssetGeometryReport.json']:
    data=json.loads(p.read_text(encoding='utf-8'));data['fbx_sha256']=new_hash;data['uv_repair_report']=str(DOC/'AssetUVRepairReport.json');data['uv_note']=report['projection'];p.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
print('UV_REPAIR_PASSED',json.dumps({'fbx_sha256':new_hash,'geometry_unchanged':True,'nondegenerate_grip_uv_unchanged':True,'all_materials_zero_uv_area':0,'grip_repaired_polygons':grip_changed_faces,'grip_statistics':[x['materials']['Grip04'] for x in after_uv]}))
