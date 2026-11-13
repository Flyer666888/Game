"""Import a local weight-only derivative onto the existing enemy skeleton."""
import hashlib,json,shutil
from pathlib import Path
import unreal

PROJECT=Path(unreal.Paths.project_dir())
OUT=PROJECT/'Docs/Gameplay/RigPolish_v02'
ROOT='/Game/ReversedScale/Characters/WuxiaMale'
A=unreal.EditorAssetLibrary
source=PROJECT/'ArtSource/WuxiaMale/RigPolishV02/Shoulder/WuxiaMaleShoulder_v02.fbx'
assert source.exists(),str(source)
old=A.load_asset(ROOT+'/SK_WuxiaMale_Combat')
skeleton=old.get_editor_property('skeleton')
def backup(asset):
    path=asset.get_path_name().split('.')[0]
    original=PROJECT/'Content'/(path.removeprefix('/Game/')+'.uasset')
    target=OUT/'Backups/Assets'/(path.removeprefix('/Game/')+'.uasset')
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():shutil.copy2(original,target)
    return {'file':str(original),'backup':str(target),'sha256':hashlib.sha256(original.read_bytes()).hexdigest()}
backups=[backup(old),backup(skeleton)]
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
task=unreal.AssetImportTask()
task.filename=str(source)
task.destination_path=ROOT
task.destination_name='SK_WuxiaMale_Shoulder_v02'
task.automated=True
task.replace_existing=True
task.save=True
opts=unreal.FbxImportUI()
opts.automated_import_should_detect_type=False
opts.mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH
opts.import_as_skeletal=True
opts.import_mesh=True
opts.import_animations=False
opts.import_materials=False
opts.import_textures=False
opts.create_physics_asset=False
opts.skeleton=skeleton
opts.skeletal_mesh_import_data.set_editor_property('import_morph_targets',True)
opts.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose',False)
opts.skeletal_mesh_import_data.set_editor_property('use_t0_as_ref_pose',False)
opts.skeletal_mesh_import_data.convert_scene=True
opts.skeletal_mesh_import_data.convert_scene_unit=True
opts.skeletal_mesh_import_data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
opts.anim_sequence_import_data.set_editor_property('add_curve_metadata_to_skeleton',False)
task.options=opts
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh=A.load_asset(ROOT+'/SK_WuxiaMale_Shoulder_v02')
assert isinstance(mesh,unreal.SkeletalMesh)
assert mesh.get_editor_property('skeleton')==skeleton
mesh.set_editor_property('materials',old.get_editor_property('materials'))
mesh.set_editor_property('physics_asset',old.get_editor_property('physics_asset'))
old_morphs=sorted(str(m.get_name()) for m in old.get_editor_property('morph_targets'))
new_morphs=sorted(str(m.get_name()) for m in mesh.get_editor_property('morph_targets'))
assert new_morphs==old_morphs,(old_morphs,new_morphs)
sub=unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
assert sub.get_lod_count(mesh)==sub.get_lod_count(old)
assert sub.get_num_verts(mesh,0)==sub.get_num_verts(old,0)
assert sub.get_num_sections(mesh,0)==sub.get_num_sections(old,0)
def bounds(model):
    b=model.get_imported_bounds()
    return [b.origin.x,b.origin.y,b.origin.z,b.box_extent.x,b.box_extent.y,b.box_extent.z]
before_bounds=bounds(old);after_bounds=bounds(mesh)
assert max(abs(a-b) for a,b in zip(before_bounds,after_bounds))<.01
assert A.save_loaded_asset(mesh,False)
for item in backups:
    item['after_sha256']=hashlib.sha256(Path(item['file']).read_bytes()).hexdigest()
    assert item['after_sha256']==item['sha256'],'Original mesh/skeleton changed'
report={'mesh':mesh.get_path_name(),'skeleton':skeleton.get_path_name(),'vertices_lod0':sub.get_num_verts(mesh,0),'sections_lod0':sub.get_num_sections(mesh,0),'morphs':new_morphs,'bounds_before':before_bounds,'bounds_after':after_bounds,'original_backups':backups,'state':'passed'}
(OUT/'ShoulderImport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('SHOULDER_V02_IMPORTED '+mesh.get_path_name())
