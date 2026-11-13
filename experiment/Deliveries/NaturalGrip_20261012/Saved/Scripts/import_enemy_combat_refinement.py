"""Save derivative grip/robe mesh and full natural death; preserve original assets."""
import json
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir())
ROOT = '/Game/ReversedScale/Characters/WuxiaMale'
A = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
old_mesh = A.load_asset(ROOT + '/SK_WuxiaMale_Feet')
skeleton = old_mesh.get_editor_property('skeleton')
grip_dir = PROJECT / 'ArtSource/WuxiaMale/GripRefinement'
natural_dir = PROJECT / 'ArtSource/WuxiaMale/NaturalDeath'
grip = json.loads((grip_dir / 'GripAuthoringSummary.json').read_text(encoding='utf-8'))
data = json.loads((natural_dir / 'NaturalDeathAuthoredPoses.json').read_text(encoding='utf-8'))
clip = data['clips'][0]
unreal.SystemLibrary.execute_console_command(None, 'Interchange.FeatureFlags.Import.FBX 0')
task = unreal.AssetImportTask()
task.filename = str(grip_dir / 'WuxiaMaleCombat.fbx')
task.destination_path = ROOT
task.destination_name = 'SK_WuxiaMale_Combat'
task.automated = True
task.replace_existing = True
task.save = True
opts = unreal.FbxImportUI()
opts.automated_import_should_detect_type = False
opts.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
opts.import_as_skeletal = True
opts.import_mesh = True
opts.import_animations = False
opts.import_materials = False
opts.import_textures = False
opts.create_physics_asset = False
opts.skeleton = skeleton
opts.skeletal_mesh_import_data.set_editor_property('import_morph_targets', True)
opts.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose', False)
opts.skeletal_mesh_import_data.set_editor_property('use_t0_as_ref_pose', False)
opts.skeletal_mesh_import_data.convert_scene = True
opts.skeletal_mesh_import_data.convert_scene_unit = True
opts.skeletal_mesh_import_data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
opts.anim_sequence_import_data.set_editor_property('add_curve_metadata_to_skeleton', False)
task.options = opts
TOOLS.import_asset_tasks([task])
mesh = A.load_asset(ROOT + '/SK_WuxiaMale_Combat')
if not isinstance(mesh, unreal.SkeletalMesh) or mesh.get_editor_property('skeleton') != skeleton:
    raise RuntimeError('Derivative mesh must import onto the unchanged enemy skeleton.')
mesh.set_editor_property('materials', old_mesh.get_editor_property('materials'))
materials = list(mesh.get_editor_property('materials'))
for slot in materials:
    original = slot.get_editor_property('material_interface')
    if not original:
        continue
    material_path = original.get_path_name().split('.')[0] + '_Combat'
    material = A.load_asset(material_path) if A.does_asset_exist(material_path) else A.duplicate_asset(original.get_path_name().split('.')[0], material_path)
    if isinstance(material, unreal.Material):
        unreal.MaterialEditingLibrary.set_base_material_usage(material, unreal.MaterialUsage.MATUSAGE_MORPH_TARGETS, True)
        unreal.MaterialEditingLibrary.recompile_material(material)
    elif isinstance(material, unreal.MaterialInstanceConstant):
        unreal.MaterialEditingLibrary.set_material_usage_override(material, unreal.MaterialUsage.MATUSAGE_MORPH_TARGETS, True, True)
    else:
        raise RuntimeError('Unsupported derivative material type ' + str(material.get_class()))
    A.save_loaded_asset(material, False)
    slot.set_editor_property('material_interface', material)
mesh.set_editor_property('materials', materials)
morph_names = [str(m.get_name()) for m in mesh.get_editor_property('morph_targets')]
unreal.log('COMBAT_MORPH_NAMES ' + json.dumps(morph_names))
def imported_name(name):
    return next((n for n in morph_names if n == name or n.endswith('_' + name)), None)
grip_name = imported_name('EnemyGrip_R')
if not grip_name:
    raise RuntimeError('The right-hand grip morph was not imported.')
if not A.save_loaded_asset(mesh, False):
    raise RuntimeError('Could not save the derivative mesh.')

dest = ROOT + '/Animations/Wuxia_Death_Natural'
animation = A.load_asset(dest) if A.does_asset_exist(dest) else A.duplicate_asset(ROOT + '/Animations/Wuxia_Death_Settle', dest)
animation.set_editor_property('enable_root_motion', False)
animation.set_editor_property('rate_scale', 1.0)
controller = animation.controller
curve_rows = []
controller.open_bracket('Full natural death with garment-only floor corrections', False)
try:
    controller.set_frame_rate(unreal.FrameRate(numerator=int(data['fps']), denominator=1), False)
    controller.set_number_of_frames(unreal.FrameNumber(value=int(clip['frames'])), False)
    for bone in clip['samples'][0]['local']:
        keys = [sample['local'][bone] for sample in clip['samples']]
        if not controller.set_bone_track_keys(bone, [unreal.Vector(*k['p']) for k in keys],
                                             [unreal.Quat(*k['q']) for k in keys],
                                             [unreal.Vector(*k['s']) for k in keys], False):
            raise RuntimeError('Could not save natural death bone ' + bone)
    for name, samples in clip['morph_curves'].items():
        actual = imported_name(name)
        if not actual:
            curve_rows.append({'requested': name, 'skipped_empty_morph': True})
            continue
        identifier = unreal.AnimationCurveIdentifier()
        identifier.set_curve_identifier(actual, unreal.RawCurveTrackTypes.RCT_FLOAT)
        controller.add_curve(identifier, 4, False)
        keys = [unreal.RichCurveKey(time=float(k['time']), value=float(k['value']),
                                    interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR) for k in samples]
        if not controller.set_curve_keys(identifier, keys, False):
            raise RuntimeError('Could not save garment morph curve ' + actual)
        curve_rows.append({'name': actual, 'keys': len(keys), 'interpolation': 'Linear'})
finally:
    controller.close_bracket(False)
for track in unreal.AnimationLibrary.get_animation_notify_track_names(animation):
    unreal.AnimationLibrary.remove_animation_notify_events_by_track(animation, track)
if not A.save_loaded_asset(animation, False):
    raise RuntimeError('Could not save natural death animation.')

native = unreal.load_class(None, '/Script/experiment.NLEnemyCharacter')
training = unreal.load_class(None, '/Script/experiment.NLTrainingEnemy')
transform = unreal.Transform(location=unreal.Vector(*grip['sword_relative_location_cm']),
                             rotation=unreal.Quat(*grip['sword_relative_quaternion_xyzw']).rotator(),
                             scale=unreal.Vector(1, 1, 1))
maps = []
for suffix in ('SwordDuel', 'Reflection', 'Guard', 'Melee'):
    map_path = '/Game/ReversedScale/Maps/L_CombatLab' + suffix
    if not A.does_asset_exist(map_path):
        continue
    backup = map_path + '_BeforeNaturalGrip_20261012'
    if not A.does_asset_exist(backup) and not A.duplicate_asset(map_path, backup):
        raise RuntimeError('Could not preserve previous map ' + map_path)
    if not LEVEL.load_level(map_path):
        raise RuntimeError('Could not load ' + map_path)
    rows = []
    for actor in ACTORS.get_all_level_actors():
        if actor.get_class() not in (native, training):
            continue
        actor.set_editor_property('death_animation', animation)
        component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
        component.set_skeletal_mesh_asset(mesh)
        if actor.get_class() == native:
            actor.set_editor_property('enemy_skeletal_mesh', mesh)
            actor.set_editor_property('sword_grip_transform', transform)
            actor.set_editor_property('grip_morph_name', grip_name)
            actor.set_editor_property('grip_morph_weight', 1.0)
            component.set_morph_target(grip_name, 1.0)
            actor.get_editor_property('sword').set_relative_transform(transform, False, True)
        rows.append({'name': actor.get_actor_label(), 'mesh': mesh.get_path_name(),
                     'death_animation': animation.get_path_name(), 'native_grip': actor.get_class() == native})
    if not rows or not LEVEL.save_current_level():
        raise RuntimeError('Could not save enemy presentation in ' + map_path)
    maps.append({'map': map_path, 'backup': backup, 'actors': rows})
report = {'date': '2026-10-12', 'mesh': mesh.get_path_name(), 'skeleton': skeleton.get_path_name(),
          'death_asset': animation.get_path_name(), 'duration_seconds': animation.get_play_length(),
          'final_hold_seconds': 0.6, 'morph_names': morph_names, 'morph_curves': curve_rows,
          'grip_morph_name': grip_name, 'grip_weight': 1.0,
          'grip_location_cm': grip['sword_relative_location_cm'],
          'grip_quaternion_xyzw': grip['sword_relative_quaternion_xyzw'], 'maps': maps,
          'scope': 'Asset authoring and saved references. Actual combat acceptance awaits user play.'}
(PROJECT / 'Docs/AI/NaturalGripSaved-2026-10-12.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('NATURAL_GRIP_REFINEMENT_SAVED ' + dest)
