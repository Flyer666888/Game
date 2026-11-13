"""Import only the enemy hilt variant with the existing Yueyao material contract."""
import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/HandGripPolish1104';A=unreal.EditorAssetLibrary
C=json.loads((O/'HiltImportConfig.json').read_text(encoding='utf-8-sig'))
baseline=json.loads((O/'SwordBaseline.json').read_text(encoding='utf-8-sig'))
DEST='/Game/ReversedScale/Weapons/Yueyao/EnemyGrip1104';NAME='SM_Yueyao_EnemyGrip'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
# A prior interrupted import may leave this task-owned package in memory.
assert DEST=='/Game/ReversedScale/Weapons/Yueyao/EnemyGrip1104'
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
task=unreal.AssetImportTask();task.filename=C['fbx'];task.destination_path=DEST;task.destination_name=NAME
task.automated=True;task.replace_existing=True;task.replace_existing_settings=True;task.save=False
opts=unreal.FbxImportUI();opts.automated_import_should_detect_type=False
opts.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH;opts.import_as_skeletal=False;opts.import_mesh=True
opts.import_animations=opts.import_materials=opts.import_textures=False
data=opts.static_mesh_import_data;data.combine_meshes=True;data.convert_scene=data.convert_scene_unit=True
data.auto_generate_collision=data.build_nanite=False;data.generate_lightmap_u_vs=True
data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
data.normal_generation_method=unreal.FBXNormalGenerationMethod.MIKK_T_SPACE
data.vertex_color_import_option=unreal.VertexColorImportOption.REPLACE
task.options=opts;unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh=A.load_asset(DEST+'/'+NAME);assert isinstance(mesh,unreal.StaticMesh),task.imported_object_paths
materials={}
for row in baseline['materials']:
    for key in [row['slot'],row['imported_slot']]:materials[key]=unreal.load_asset(row['material'])
assigned=[]
for i,slot in enumerate(mesh.static_materials):
    name=str(slot.get_editor_property('imported_material_slot_name'))
    if name not in materials:name=str(slot.material_slot_name)
    assert name in materials,(name,list(materials))
    mesh.set_material(i,materials[name]);assigned.append({'slot':name,'material':materials[name].get_path_name()})
assert len(assigned)==len(baseline['materials'])
b=mesh.get_bounds();before=baseline['bounds']
assert abs(b.origin.z-before['origin'][2])<.01 and abs(b.box_extent.z-before['extent'][2])<.01,(b,before)
assert mesh.get_num_triangles(0)==baseline['triangles']
# The FBX's authored UV0 is used by all sword materials. The shared UE asset
# also has an editor-generated lightmap channel, unused by this movable sword.
assert mesh.get_num_tex_coords(0)>=1
sub=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem);sub.remove_collisions(mesh)
settings=sub.get_lod_build_settings(mesh,0);settings.recompute_normals=False;settings.recompute_tangents=True
settings.use_mikk_t_space=True;settings.use_full_precision_u_vs=True;settings.use_high_precision_tangent_basis=True
settings.generate_lightmap_u_vs=True;settings.src_lightmap_index=0;settings.dst_lightmap_index=1
sub.set_lod_build_settings(mesh,0,settings);mesh.set_editor_property('bHasNavigationData',False)
assert A.save_loaded_asset(mesh,False)
assert hashlib.sha256((P/'Content/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player.uasset').read_bytes()).hexdigest()==baseline['sha256']
(O/'HiltImported.json').write_text(json.dumps({'state':'passed','asset':mesh.get_path_name(),'fbx':C['fbx'],
    'materials':assigned,'triangles':mesh.get_num_triangles(0),'uv_channels':mesh.get_num_tex_coords(0),
    'player_sword_unchanged':True,'blade_and_handle_extent_unchanged':True},indent=2),encoding='utf-8')
