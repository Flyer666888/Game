"""Save a dedicated VR entrance and real Enhanced Input assets, without gameplay."""
import json
import runpy
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir())
runpy.run_path(str(root / 'Saved/Scripts/author_vr_input_assets.py'))
assets = unreal.EditorAssetLibrary
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
source = '/Game/ReversedScale/Maps/L_CombatLabMixed'
destination = '/Game/ReversedScale/Maps/L_CombatLabVR'
mode = unreal.load_class(None, '/Script/experiment.NLVRGameMode')
pawn = unreal.load_class(None, '/Script/experiment.NLVRPlayerCharacter')
if not mode or not pawn:
    raise RuntimeError('Compile the VR native module before authoring this map.')
if not (level.load_level(destination) if assets.does_asset_exist(destination)
        else level.new_level_from_template(destination, source)):
    raise RuntimeError('Could not create the independent VR map.')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
world.get_world_settings().set_editor_property('default_game_mode', mode)
controllers = [actor for actor in actors.get_all_level_actors() if isinstance(actor, unreal.NLEncounterController)]
if len(controllers) != 1:
    raise RuntimeError('The VR lab must retain the mixed encounter controller.')
controller = controllers[0]
for key, value in {'level_id': unreal.Name('Level.CombatLab.VR'),
                   'encounter_id': unreal.Name('Encounter.VRMixedDisciples'),
                   'content_revision': unreal.Name('VRMixed.VRINPUT01.1'),
                   'bEnableCheckpoints': True}.items():
    controller.set_editor_property(key, value)
controller.set_actor_label('Encounter_VR_MixedDisciples')
if not level.save_current_level():
    raise RuntimeError('Could not save the VR lab map.')
cdo = unreal.get_default_object(pawn)
report = {'date': '2026-10-15', 'map': destination, 'source_map_preserved': source,
          'game_mode': mode.get_path_name(), 'pawn': pawn.get_path_name(),
          'move_speed_cm_s': cdo.get_editor_property('vr_walk_speed'),
          'snap_turn_degrees': cdo.get_editor_property('snap_turn_degrees'),
          'tracking_sources': ['Left', 'Right'], 'floor_origin': True,
          'wave_count': len(controller.get_editor_property('waves')),
          'checkpoint_ids': [str(controller.get_editor_property(key)) for key in ('level_id','encounter_id','content_revision')],
          'melee_damage': unreal.load_asset('/Game/ReversedScale/Combat/DA_YueyaoMelee').get_editor_property('damage'),
          'scope': 'Native VR map and input assets saved only. No inputs, enemy start, damage or automated tests.'}
(root / 'Docs/AI/VRLabSaved-2026-10-15.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('VR_LAB_ASSETS_SAVED')
