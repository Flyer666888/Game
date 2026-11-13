"""Import normalized supplied skin into a new skeleton; no gameplay assignment yet."""
import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/SlashRevision1104'
A=unreal.EditorAssetLibrary
R='/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07'
source=P/'ArtSource/WuxiaMale/NativeRigV07/NativeMesh.fbx'
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
task=unreal.AssetImportTask()
task.filename=str(source);task.destination_path=R;task.destination_name='SK_WuxiaMale_Native_v07'
task.automated=True;task.replace_existing=True;task.save=True
opts=unreal.FbxImportUI();opts.automated_import_should_detect_type=False
opts.mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH
opts.import_as_skeletal=True;opts.import_mesh=True;opts.import_animations=False
opts.import_materials=False;opts.import_textures=False;opts.create_physics_asset=False
opts.skeletal_mesh_import_data.convert_scene=True
opts.skeletal_mesh_import_data.convert_scene_unit=True
opts.skeletal_mesh_import_data.set_editor_property('use_t0_as_ref_pose',False)
opts.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose',False)
opts.skeletal_mesh_import_data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
task.options=opts
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh=A.load_asset(R+'/SK_WuxiaMale_Native_v07');assert mesh
slots=list(mesh.get_editor_property('materials'))
assert len(slots)==1,'Original provided FBX has one textured material'
slots[0].set_editor_property('material_interface',A.load_asset('/Game/ReversedScale/Characters/WuxiaMale/M_WuxiaMale_Combat'))
mesh.set_editor_property('materials',slots)
assert A.save_loaded_asset(mesh,False)
assert A.save_loaded_asset(mesh.skeleton,False)
b=mesh.get_imported_bounds()
assert 170<b.box_extent.z*2<190,('Unexpected height',str(b))
probe=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(0,0,0))
component=probe.skeletal_mesh_component;component.set_skeletal_mesh_asset(mesh)
bones=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
rest={name:list((lambda v:(v.x,v.y,v.z))(component.get_socket_location(name))) for name in bones}
unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(probe)
assert 'RightHand' in bones
report={'state':'passed','mesh':mesh.get_path_name(),'skeleton':mesh.skeleton.get_path_name(),
 'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'height_cm':b.box_extent.z*2,'bounds':str(b),'bones':bones,'rest_world':rest,
 'vertices_lod0':unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem).get_num_verts(mesh,0),
 'materials':[str(s.material_interface) for s in slots]}
(O/'NativeMeshImport.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('NATIVE_MESH_V07_IMPORTED')
