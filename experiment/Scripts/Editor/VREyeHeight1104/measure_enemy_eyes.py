"""Read-only standing eye measurements from the current enemy assets."""
import json
from pathlib import Path
import unreal

out = Path(r'D:\game design\experiment\Docs\Gameplay\VREyeHeight1104')
player = unreal.get_default_object(unreal.NLVRPlayerCharacter)
eye_offset = player.get_editor_property('enemy_eye_offset')
records = []
for key in ('sword', 'talisman', 'GM01', 'boss'):
    path = '/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_' + key
    default = unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class(path))
    mesh = default.get_editor_property('enemy_skeletal_mesh')
    component = default.get_component_by_class(unreal.SkeletalMeshComponent)
    clip = default.get_editor_property('idle_animation')
    options = unreal.AnimPoseEvaluationOptions()
    options.evaluation_type = unreal.AnimDataEvalType.COMPRESSED
    options.optional_skeletal_mesh = mesh
    relative = component.get_relative_transform()
    actor_scale = default.get_actor_scale3d()
    samples = []
    for fraction in (0, .125, .25, .375, .5, .625, .75, .875, 1):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, fraction * clip.get_play_length(), options)
        assert unreal.AnimPoseExtensions.is_valid(pose)
        head = unreal.AnimPoseExtensions.get_bone_pose(pose, 'head', unreal.AnimPoseSpaces.WORLD)
        eye = unreal.MathLibrary.transform_location(head, eye_offset)
        eye = unreal.MathLibrary.transform_location(relative, eye)
        samples.append((eye.z - relative.translation.z) * actor_scale.z)
    records.append(dict(enemy=key, blueprint=path, mesh=mesh.get_path_name(), idle=clip.get_path_name(),
                        actor_scale=[actor_scale.x, actor_scale.y, actor_scale.z],
                        eye_heights_cm=samples, mean_cm=sum(samples)/len(samples)))
out.mkdir(parents=True, exist_ok=True)
(out / 'EnemyEyeMeasurements.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
unreal.log('VR_EYE_HEIGHT_MEASUREMENTS ' + json.dumps(records))
