"""Save selected death refinement and update scene/prefab references, retaining old assets."""
import json
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir())
OUT = PROJECT / 'ArtSource/WuxiaMale/DeathSelection20261012'
ROOT = '/Game/ReversedScale/Characters/WuxiaMale'
DEST = ROOT + '/Animations/Wuxia_Death_Grounded'
OLD = ROOT + '/Animations/Wuxia_Death_Natural'
A = unreal.EditorAssetLibrary
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
data = json.loads((OUT / 'OptimizedDeathPoses.json').read_text(encoding='utf-8'))
clip = data['clips'][0]
mesh = A.load_asset(ROOT + '/SK_WuxiaMale_Combat')
skeleton = mesh.get_editor_property('skeleton')
if data.get('skeleton') and data['skeleton'] != skeleton.get_path_name():
    raise RuntimeError('Selected death must retain the existing enemy skeleton.')
if len(clip['samples']) != int(clip['frames']) + 1:
    raise RuntimeError('Authoring samples must include both clip boundaries.')
animation = A.load_asset(DEST) if A.does_asset_exist(DEST) else A.duplicate_asset(OLD, DEST)
animation.set_editor_property('enable_root_motion', False)
animation.set_editor_property('force_root_lock', False)
animation.set_editor_property('rate_scale', 1.0)
controller = animation.controller
morph_names = {str(target.get_name()) for target in mesh.get_editor_property('morph_targets')}
curve_rows = []
controller.open_bracket('Selected natural death with continuous contact and relaxed limbs', False)
try:
    controller.set_frame_rate(unreal.FrameRate(numerator=int(data['fps']), denominator=1), False)
    controller.set_number_of_frames(unreal.FrameNumber(value=int(clip['frames'])), False)
    controller.remove_all_curves_of_type(unreal.RawCurveTrackTypes.RCT_FLOAT, False)
    for bone in clip['samples'][0]['local']:
        keys = [sample['local'][bone] for sample in clip['samples']]
        if not controller.set_bone_track_keys(bone, [unreal.Vector(*key['p']) for key in keys],
                                             [unreal.Quat(*key['q']) for key in keys],
                                             [unreal.Vector(*key['s']) for key in keys], False):
            raise RuntimeError('Could not save selected death bone ' + bone)
    curves = dict(clip.get('morph_curves', {}))
    # Preserve the authored hand shape even for plain preview/unarmed actors.
    # Native sword disciples already apply the same component grip override.
    for name, weight in data.get('preview_morph_overrides', {}).items():
        if name not in curves:
            curves[name] = [{'time': sample['time'], 'value': float(weight)} for sample in clip['samples']]
    for name, samples in curves.items():
        if name not in morph_names:
            curve_rows.append({'name': name, 'skipped_empty_morph': True})
            continue
        identifier = unreal.AnimationCurveIdentifier()
        identifier.set_curve_identifier(name, unreal.RawCurveTrackTypes.RCT_FLOAT)
        if not controller.add_curve(identifier, 4, False):
            raise RuntimeError('Could not create cloth curve ' + name)
        keys = [unreal.RichCurveKey(time=float(key['time']), value=float(key['value']),
                                    interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR) for key in samples]
        if not controller.set_curve_keys(identifier, keys, False):
            raise RuntimeError('Could not save cloth curve ' + name)
        curve_rows.append({'name': name, 'keys': len(keys), 'interpolation': 'Linear'})
finally:
    controller.close_bracket(False)
for track in unreal.AnimationLibrary.get_animation_notify_track_names(animation):
    unreal.AnimationLibrary.remove_animation_notify_events_by_track(animation, track)
if not A.save_loaded_asset(animation, False):
    raise RuntimeError('Could not save selected death animation.')

classes = [unreal.load_class(None, '/Script/experiment.' + name)
           for name in ('NLEnemyCharacter', 'NLTrainingEnemy')]
maps = []
for suffix in ('SwordDuel', 'Reflection', 'Guard', 'Melee'):
    map_path = '/Game/ReversedScale/Maps/L_CombatLab' + suffix
    if not A.does_asset_exist(map_path):
        continue
    backup = map_path + '_BeforeDeathGrounded_20261012'
    if not A.does_asset_exist(backup) and not A.duplicate_asset(map_path, backup):
        raise RuntimeError('Could not preserve previous scene ' + map_path)
    if not LEVEL.load_level(map_path):
        raise RuntimeError('Could not load scene ' + map_path)
    actors = []
    for actor in ACTORS.get_all_level_actors():
        if actor.get_class() not in classes:
            continue
        actor.set_editor_property('death_animation', animation)
        actors.append({'name': actor.get_actor_label(), 'death_animation': animation.get_path_name(),
                       'mesh': actor.get_component_by_class(unreal.SkeletalMeshComponent).get_editor_property('skeletal_mesh_asset').get_path_name()})
    if not actors or not LEVEL.save_current_level():
        raise RuntimeError('Could not save death references in scene ' + map_path)
    maps.append({'map': map_path, 'backup': backup, 'actors': actors})

prefab_path = ROOT + '/BP_EnemySwordDisciple'
prefab_row = None
if A.does_asset_exist(prefab_path):
    backup = prefab_path + '_BeforeDeathGrounded_20261012'
    if not A.does_asset_exist(backup) and not A.duplicate_asset(prefab_path, backup):
        raise RuntimeError('Could not preserve previous enemy prefab.')
    prefab = A.load_asset(prefab_path)
    cdo = unreal.get_default_object(A.load_blueprint_class(prefab_path))
    cdo.set_editor_property('death_animation', animation)
    if not unreal.BlueprintEditorLibrary.compile_blueprint(prefab) or not A.save_loaded_asset(prefab, False):
        raise RuntimeError('Could not save enemy prefab death reference.')
    cdo = unreal.get_default_object(A.load_blueprint_class(prefab_path))
    prefab_row = {'asset': prefab.get_path_name(), 'backup': backup,
                  'death_animation': cdo.get_editor_property('death_animation').get_path_name()}

opts = unreal.AnimPoseEvaluationOptions()
opts.evaluation_type = unreal.AnimDataEvalType.COMPRESSED
opts.optional_skeletal_mesh = mesh
final_pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, animation.get_play_length(), opts)
final_bones = {}
for name in ('root', 'pelvis', 'head', 'hand_l', 'hand_r', 'foot_l', 'foot_r'):
    transform = unreal.AnimPoseExtensions.get_bone_pose(final_pose, name, unreal.AnimPoseSpaces.WORLD)
    final_bones[name] = [transform.translation.x, transform.translation.y, transform.translation.z]
report = {'date': '2026-10-12', 'asset': animation.get_path_name(), 'old_asset_preserved': OLD,
          'source_asset': clip.get('source_asset'), 'duration_seconds': animation.get_play_length(),
          'skeleton': skeleton.get_path_name(), 'mesh': mesh.get_path_name(),
          'force_root_lock': animation.get_editor_property('force_root_lock'),
          'enable_root_motion': animation.get_editor_property('enable_root_motion'),
          'morph_curves': curve_rows, 'maps': maps, 'prefab': prefab_row,
          'compressed_final_bones_cm': final_bones, 'authoring': clip.get('authoring', {}),
          'scope': 'Animation authoring and saved references; no gameplay input or automated tests.'}
(OUT / 'SelectedDeathImported.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(PROJECT / 'Docs/AI/SelectedDeathSaved-2026-10-12.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('SELECTED_GROUNDED_DEATH_SAVED ' + DEST)
