"""Import a local weight-only derivative onto the existing enemy skeleton."""
import hashlib,json,shutil,re
from pathlib import Path
import unreal

PROJECT=Path(unreal.Paths.project_dir()).resolve()
OUT=PROJECT/'Docs/Gameplay/RigPolish_v04'
ROOT='/Game/ReversedScale/Characters/WuxiaMale'
A=unreal.EditorAssetLibrary
spec_path=OUT/'HandsImportSpec.json'
spec=json.loads(spec_path.read_text(encoding='utf-8')) if spec_path.exists() else {}
source=Path(spec['source_fbx']) if spec.get('source_fbx') else PROJECT/'ArtSource/WuxiaMale/RigPolishV04/Hands/WuxiaMaleHands_v04.fbx'
assert source.resolve().is_relative_to(PROJECT/'ArtSource/WuxiaMale/RigPolishV04')
replacement=bool(spec.get('right_hand_replacement',False))
assert source.exists(),str(source)
old=A.load_asset(ROOT+'/SK_WuxiaMale_Shoulder_v02')
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
task.destination_name='SK_WuxiaMale_Hands_v04'
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
opts.set_editor_property('reset_to_fbx_on_material_conflict',True)
opts.skeletal_mesh_import_data.set_editor_property('import_morph_targets',True)
opts.skeletal_mesh_import_data.set_editor_property('vertex_color_import_option',unreal.VertexColorImportOption.REPLACE)
opts.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose',False)
opts.skeletal_mesh_import_data.set_editor_property('use_t0_as_ref_pose',False)
opts.skeletal_mesh_import_data.convert_scene=True
opts.skeletal_mesh_import_data.convert_scene_unit=True
opts.skeletal_mesh_import_data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
opts.anim_sequence_import_data.set_editor_property('add_curve_metadata_to_skeleton',False)
task.options=opts
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh=A.load_asset(ROOT+'/SK_WuxiaMale_Hands_v04')
assert isinstance(mesh,unreal.SkeletalMesh)
assert mesh.get_editor_property('skeleton')==skeleton
material_records=[]
if replacement:
    def normalized(name):return re.sub(r'\.\d+$','',str(name))
    body_materials={}
    for slot in old.get_editor_property('materials'):
        for field in ('material_slot_name','imported_material_slot_name'):
            body_materials[normalized(slot.get_editor_property(field))]=slot.get_editor_property('material_interface')
    hand_materials={name:A.load_asset('/Game/ReversedScale/Player/Materials/'+asset)
        for name,asset in (('M_Skin','M_PlayerSkin'),('M_Nails','M_PlayerNails'))}
    slots=list(mesh.get_editor_property('materials'))
    for slot in slots:
        name=normalized(slot.get_editor_property('imported_material_slot_name'))
        material=hand_materials.get(name) or body_materials.get(name)
        assert material,'Unmapped imported material '+name
        slot.set_editor_property('material_interface',material)
        material_records.append({'slot':name,'material':material.get_path_name()})
    mesh.set_editor_property('materials',slots)
else:
    mesh.set_editor_property('materials',old.get_editor_property('materials'))
mesh.set_editor_property('physics_asset',old.get_editor_property('physics_asset'))
old_morphs=sorted(str(m.get_name()) for m in old.get_editor_property('morph_targets'))
new_morphs=sorted(str(m.get_name()) for m in mesh.get_editor_property('morph_targets'))
if replacement:
    assert set(old_morphs)-{'EnemyGrip_R'}<=set(new_morphs)<=set(old_morphs),(old_morphs,new_morphs)
else:assert new_morphs==old_morphs,(old_morphs,new_morphs)
sub=unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
assert sub.get_lod_count(mesh)==sub.get_lod_count(old)
if replacement:
    assert 40000<=sub.get_num_verts(mesh,0)<=60000,'Unexpected topology beyond local hand replacement'
    assert sub.get_num_sections(mesh,0)<=sub.get_num_sections(old,0)+2,'Unexpected material section growth'
else:
    assert sub.get_num_verts(mesh,0)==sub.get_num_verts(old,0)
    assert sub.get_num_sections(mesh,0)==sub.get_num_sections(old,0)
def bounds(model):
    b=model.get_imported_bounds()
    return [b.origin.x,b.origin.y,b.origin.z,b.box_extent.x,b.box_extent.y,b.box_extent.z]
before_bounds=bounds(old);after_bounds=bounds(mesh)
assert max(abs(a-b) for a,b in zip(before_bounds,after_bounds))<(12 if replacement else .01)
assert A.save_loaded_asset(mesh,False)
for item in backups:
    item['after_sha256']=hashlib.sha256(Path(item['file']).read_bytes()).hexdigest()
    assert item['after_sha256']==item['sha256'],'Original mesh/skeleton changed'
report={'mesh':mesh.get_path_name(),'skeleton':skeleton.get_path_name(),'vertices_lod0':sub.get_num_verts(mesh,0),'sections_lod0':sub.get_num_sections(mesh,0),'morphs':new_morphs,'bounds_before':before_bounds,'bounds_after':after_bounds,'original_backups':backups,'state':'passed',
    'source_fbx':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'right_hand_replacement':replacement,'materials':material_records}
(OUT/'HandsImport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('HANDS_V04_IMPORTED '+mesh.get_path_name())

