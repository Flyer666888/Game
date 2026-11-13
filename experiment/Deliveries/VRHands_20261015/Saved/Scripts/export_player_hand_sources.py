"""Export only source meshes and poses for the requested human hand authoring."""
import json
from pathlib import Path
import unreal

out = Path(unreal.Paths.project_dir()) / 'ArtSource/PlayerHands/Source'
out.mkdir(parents=True, exist_ok=True)
exports = []
for name in ('SKM_MannyXR_right', 'SKM_MannyXR_left', 'SKM_QuinnXR_right', 'SKM_QuinnXR_left'):
    mesh = unreal.load_asset('/Game/XRMannequins/Meshes/' + name)
    task = unreal.AssetExportTask()
    task.object = mesh
    task.filename = str(out / (name + '.fbx'))
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    task.exporter = unreal.SkeletalMeshExporterFBX()
    options = unreal.FbxExportOption()
    options.set_editor_property('ascii', False)
    options.set_editor_property('level_of_detail', False)
    options.set_editor_property('export_morph_targets', False)
    options.set_editor_property('bake_material_inputs', unreal.FbxMaterialBakeMode.DISABLED)
    task.options = options
    if not unreal.Exporter.run_asset_export_task(task):
        raise RuntimeError('Could not export hand source: ' + name)
    exports.append({'asset': mesh.get_path_name(), 'file': task.filename})
data = {'exports': exports, 'poses': {}}
mesh = unreal.load_asset('/Game/XRMannequins/Meshes/SKM_MannyXR_right')
options = unreal.AnimPoseEvaluationOptions()
options.optional_skeletal_mesh = mesh
for label, path in {
    'Grip': '/Game/ReversedScale/Player/Animations/A_Yueyao_Grip_Right',
    'Idle': '/Game/XRMannequins/Animations/A_MannequinsXR_Idle_Right',
    'Grasp': '/Game/XRMannequins/Animations/A_MannequinsXR_Grasp_Right',
}.items():
    anim = unreal.load_asset(path)
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(anim, 0.0, options)
    record = {}
    for bone in unreal.AnimPoseExtensions.get_bone_names(pose):
        transforms = {}
        for key, space in (('local', unreal.AnimPoseSpaces.LOCAL), ('world', unreal.AnimPoseSpaces.WORLD)):
            t = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, space)
            transforms[key] = {'p': [t.translation.x,t.translation.y,t.translation.z],
                               'q': [t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w],
                               's': [t.scale3d.x,t.scale3d.y,t.scale3d.z]}
        record[str(bone)] = transforms
    data['poses'][label] = record
(out / 'PlayerHandSourceExport.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
unreal.log('PLAYER_HAND_SOURCE_EXPORT_SAVED')
