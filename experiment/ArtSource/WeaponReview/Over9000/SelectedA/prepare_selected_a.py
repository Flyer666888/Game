import bpy, json, math, hashlib, struct
from pathlib import Path
from mathutils import Matrix, Vector
OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0
inventory=json.loads((ROOT/'Inventory.json').read_text(encoding='utf-8-sig'))['meshes']
parts=[('sword_blade_03','Blade03'),('sword_crossguard_03','Guard03'),('sword_hilt_04','Grip04'),('Sword_pommel_03','Pommel03')]
# Imported FBX coordinates are meters. Bake the requested centimeter-space transform.
requested_cm=Matrix.Translation((0,0,1.7053818)) @ Matrix.Rotation(math.radians(90),4,'Z') @ Matrix.Scale(.64,4)
from_import_meters=requested_cm @ Matrix.Scale(100.0,4)
records=[];meshes=[];source_points={}

def bounds(points):
    return {'min':[min(p[i] for p in points) for i in range(3)],'max':[max(p[i] for p in points) for i in range(3)]}
def midpoint(b):return [(b['min'][i]+b['max'][i])*.5 for i in range(3)]
def matrix_rows(m):return [[float(m[i][j]) for j in range(4)] for i in range(4)]
def uv_by_faces(mesh):
    result={}
    for layer in mesh.uv_layers:
        face_values=[]
        for face in mesh.polygons:
            uvs=[tuple(round(float(v),7) for v in layer.data[i].uv) for i in face.loop_indices]
            face_values.append(tuple(uvs))
        result[layer.name]=hashlib.sha256(repr(sorted(face_values)).encode()).hexdigest()
    return result

for source_name,slot_name in parts:
    before=set(bpy.data.objects);bpy.ops.import_scene.fbx(filepath=str(ROOT/(source_name+'.fbx')),use_custom_normals=True)
    added=[o for o in bpy.data.objects if o not in before]
    active=[o for o in added if o.type=='MESH' and not o.name.upper().startswith(('UCX_','UBX_','USP_','UCP_'))]
    for o in added:
        if o not in active:bpy.data.objects.remove(o,do_unlink=True)
    entry=next(x for x in inventory if x['name']==source_name)
    for o in active:
        source_world=o.matrix_world.copy();coords=[source_world @ v.co for v in o.data.vertices]
        source_points[slot_name]=[p*100.0 for p in coords]
        original_slots=[m.name if m else None for m in o.data.materials]
        uv_original=uv_by_faces(o.data)
        # Common UV layer names preserve each existing channel's values during mesh joining.
        original_uv_names=[uv.name for uv in o.data.uv_layers]
        for idx,layer in enumerate(o.data.uv_layers):layer.name=f'UVChannel_{idx}'
        mat=bpy.data.materials.new(slot_name);mat.diffuse_color=(.31,.34,.38,1);mat.use_nodes=True
        p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.31,.34,.38,1);p.inputs['Metallic'].default_value=.75;p.inputs['Roughness'].default_value=.32
        o.data.materials.clear();o.data.materials.append(mat)
        for face in o.data.polygons:face.material_index=0
        o.parent=None;o.data.transform(from_import_meters @ source_world);o.matrix_world=Matrix.Identity(4)
        final_coords=[v.co.copy() for v in o.data.vertices]
        records.append({'source_name':source_name,'material_slot':slot_name,'source_ue_asset':entry['asset'],'source_ue_materials':[m['material'] for m in entry['materials']],'source_fbx_material_names':original_slots,'source_import_matrix_world':matrix_rows(source_world),'source_mesh_bounds_cm':bounds(source_points[slot_name]),'source_ue_inventory_origin_cm':entry['origin'],'source_ue_inventory_extent_cm':entry['extent'],'transformed_bounds_cm':bounds(final_coords),'source_uv_names':original_uv_names,'uv_layer_count':len(o.data.uv_layers),'source_uv_face_hashes':uv_original,'vertex_count':len(o.data.vertices),'polygon_count':len(o.data.polygons),'local_to_final_matrix':matrix_rows(from_import_meters@source_world)})
        meshes.append(o)
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=meshes[0]
bpy.ops.object.join()
result=bpy.context.object;result.name='SM_PlayerSword_A';result.data.name='SM_PlayerSword_A_Mesh'
result.matrix_world=Matrix.Identity(4);result.data.calc_loop_triangles()
final_bounds=bounds([v.co.copy() for v in result.data.vertices])
source_grip=midpoint(bounds(source_points['Grip04']))
source_blade_bounds=bounds(source_points['Blade03'])
blade_x=(source_blade_bounds['min'][0]+source_blade_bounds['max'][0])*.5;blade_y=(source_blade_bounds['min'][1]+source_blade_bounds['max'][1])*.5
base_source=Vector((blade_x,blade_y,source_blade_bounds['min'][2]));tip_source=Vector((blade_x,blade_y,source_blade_bounds['max'][2]))
report={'asset_name':'SM_PlayerSword_A','candidate':'A','units':'centimeters: Blender unit scale 0.01','operations':'Keep all four original component coordinate origins; no per-component recentering; uniform 0.64 then +90 degrees around Z then +1.7053818 cm Z; exclude UCX; join static meshes only','requested_source_cm_to_output_cm':matrix_rows(requested_cm),'source_import_m_to_output_cm':matrix_rows(from_import_meters),'uniform_scale':.64,'rotation_z_degrees':90.0,'translation_cm':[0,0,1.7053818],'parts':records,'bounds_cm':final_bounds,'dimensions_cm':[final_bounds['max'][i]-final_bounds['min'][i] for i in range(3)],'vertex_count':len(result.data.vertices),'triangles':len(result.data.loop_triangles),'material_slots':[m.name for m in result.data.materials],'joined_uv_layers':[l.name for l in result.data.uv_layers],'grip_center_source_cm':source_grip,'grip_center_transformed_cm':list(requested_cm@Vector(source_grip)),'blade_base_source_cm':list(base_source),'blade_tip_source_cm':list(tip_source),'blade_base_transformed_cm':list(requested_cm@base_source),'blade_tip_transformed_cm':list(requested_cm@tip_source),'blade_point_definition':'Base and tip at center X/Y of blade mesh bounds, minimum/maximum Z; root can use as blade sweep samples','fbx_export':{'axis_forward':'-Y','axis_up':'Z','apply_unit_scale':True,'apply_scale_options':'FBX_SCALE_NONE','mesh_smooth_type':'FACE','bake_anim':False,'use_space_transform':True},'coordinate_note':'Uses same centimeter scene unit and -Y/Z FBX settings as existing project Yueyao static mesh export. UE import must confirm expected bounds and +Z blade direction.'}
# Store all original material mappings on the editable object too.
result['source_material_mapping']=json.dumps({r['material_slot']:r['source_ue_materials'] for r in records})
result['candidate']='A';result['grip_pivot_cm']=report['grip_center_transformed_cm']
scene.unit_settings.scale_length=.01
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SM_PlayerSword_A.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_PlayerSword_A.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',bake_anim=False,path_mode='STRIP',use_custom_props=True)
report['fbx_sha256']=hashlib.sha256((OUT/'SM_PlayerSword_A.fbx').read_bytes()).hexdigest()
(OUT/'SelectedA.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print('SELECTED_A_EXPORTED',json.dumps({'dimensions_cm':report['dimensions_cm'],'grip_center_cm':report['grip_center_transformed_cm'],'blade_base_cm':report['blade_base_transformed_cm'],'blade_tip_cm':report['blade_tip_transformed_cm'],'triangles':report['triangles'],'slots':report['material_slots']}),flush=True)

