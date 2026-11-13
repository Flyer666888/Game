"""Inspect a standalone import of the provided FBX, before changing gameplay."""
import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve()
O=P/'Docs/Gameplay/SlashRevision1104'
A=unreal.EditorAssetLibrary
R='/Game/ReversedScale/Characters/WuxiaMale/ProvidedRigV07/SourceProbe'
source=P/'ArtSource/WuxiaMale/ProvidedRigV07/ProvidedWalk_Source.fbx'
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
task=unreal.AssetImportTask()
task.filename=str(source);task.destination_path=R;task.destination_name='SK_ProvidedSource'
task.automated=True;task.replace_existing=False;task.save=True
opts=unreal.FbxImportUI()
opts.automated_import_should_detect_type=False
opts.mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH
opts.import_as_skeletal=True;opts.import_mesh=True;opts.import_animations=True
opts.import_materials=False;opts.import_textures=False;opts.create_physics_asset=False
opts.skeletal_mesh_import_data.convert_scene=True
opts.skeletal_mesh_import_data.convert_scene_unit=True
opts.skeletal_mesh_import_data.set_editor_property('use_t0_as_ref_pose',False)
opts.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose',False)
opts.skeletal_mesh_import_data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
opts.anim_sequence_import_data.convert_scene=True
opts.anim_sequence_import_data.convert_scene_unit=True
task.options=opts
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
assets=[A.load_asset(p) for p in task.imported_object_paths]
mesh=next(a for a in assets if isinstance(a,unreal.SkeletalMesh))
old=A.load_asset('/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Shoulder_v02')
slots=list(mesh.get_editor_property('materials'))
for slot in slots:slot.set_editor_property('material_interface',old.get_editor_property('materials')[0].get_editor_property('material_interface'))
mesh.set_editor_property('materials',slots);A.save_loaded_asset(mesh,False)
skel=mesh.skeleton
b=mesh.get_imported_bounds()
report={'state':'passed','assets':[a.get_path_name() for a in assets],
 'bounds':{'origin':[b.origin.x,b.origin.y,b.origin.z],'extent':[b.box_extent.x,b.box_extent.y,b.box_extent.z]},
 'materials':[{'name':str(s.material_slot_name),'material':str(s.material_interface)} for s in slots],
 'skeleton_api':[x for x in dir(skel) if any(w in x for w in ('bone','socket','reference','mesh'))],
 'mesh_api':[x for x in dir(mesh) if any(w in x for w in ('bone','socket','reference'))],
 'subsystem_api':[x for x in dir(unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)) if any(w in x for w in ('bone','socket','reference'))],
 'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
(O/'SourceImport.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('PROVIDED_SOURCE_PROBE_IMPORTED')
