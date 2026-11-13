"""Read-only initial presentation. Never starts a wave, writes a save or invokes retry."""
import json
import time
from pathlib import Path
import unreal

_checkpoint_dir = Path(unreal.Paths.project_dir()) / 'Docs/AI'
_checkpoint_start = time.monotonic()
_checkpoint_handle = None
_checkpoint_map = '/Game/ReversedScale/Maps/L_CombatLabCheckpoint'


def _checkpoint_capture(delta):
    if time.monotonic() - _checkpoint_start < 20.0:
        return
    world = unreal.find_object(None, _checkpoint_map + '.L_CombatLabCheckpoint')
    if not world:
        return
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    if not player:
        return
    unreal.unregister_slate_post_tick_callback(_checkpoint_handle)
    controller = player.get_encounter_controller()
    camera = player.get_editor_property('player_camera')
    instance = unreal.GameplayStatics.get_game_instance(world)
    # SubsystemBlueprintLibrary is not exported by this build's Python wrapper.
    # Read only the already-existing subsystem objects owned by this game instance.
    service = next((obj for obj in unreal.ObjectIterator(unreal.NLCheckpointService)
                    if obj.get_outer() == instance), None)
    run = next((obj for obj in unreal.ObjectIterator(unreal.NLRunStateSubsystem)
                if obj.get_outer() == instance), None)
    report = {
        'date': '2026-10-13', 'task': 'SAVE-01', 'map': _checkpoint_map,
        'controller_state': str(controller.get_state()),
        'checkpoint_enabled': controller.get_editor_property('bEnableCheckpoints'),
        'entry_wave_index': controller.get_entry_wave_index(),
        'wave_index': controller.get_wave_index(), 'wave_count': controller.get_wave_count(),
        'planned_count': controller.get_planned_count(), 'spawned_count': controller.get_spawned_count(),
        'defeated_count': controller.get_defeated_count(), 'alive_count': controller.get_alive_count(),
        'initial_seed': controller.get_initial_seed(), 'random_state': controller.get_wave_entry_random_state(),
        'level_id': str(controller.get_editor_property('level_id')),
        'encounter_id': str(controller.get_editor_property('encounter_id')),
        'content_revision': str(controller.get_editor_property('content_revision')),
        'has_memory_checkpoint': service.has_checkpoint() if service else None,
        'persistence_status': str(service.get_last_persistence_status()) if service else None,
        'persistence_failure': str(service.get_last_failure_reason()) if service else None,
        'run_id': str(run.get_run_id()) if run else None,
        'defeat_event_ledger_count': run.get_defeat_event_count() if run else None,
        'health': player.get_editor_property('vitals').get_health(),
        'guard': player.get_editor_property('guard').get_guard(),
        'player_origin_cm': [player.get_actor_location().x, player.get_actor_location().y, player.get_actor_location().z],
        'camera_cm': [camera.get_world_location().x, camera.get_world_location().y, camera.get_world_location().z],
        'melee_damage': player.get_editor_property('blade').get_editor_property('attack_definition').get_editor_property('damage'),
        'screenshot': str(_checkpoint_dir / 'CheckpointLabFirstPerson.png'),
        'scope': 'Only read current initial scene and take a screenshot. No agent gameplay input, checkpoint disk-write, retry, enemy spawn, damage, seed replay or automated test. Existing disk checkpoints may be read by normal game startup.',
    }
    (_checkpoint_dir / 'CheckpointLabRuntimeScene-2026-10-13.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.SystemLibrary.execute_console_command(world,
        'HighResShot 1600x900 filename="' + str(_checkpoint_dir / 'CheckpointLabFirstPerson.png') + '"')
    unreal.log('CHECKPOINT_LAB_INITIAL_SCENE_CAPTURED')


_checkpoint_handle = unreal.register_slate_post_tick_callback(_checkpoint_capture)
unreal.log('CHECKPOINT_LAB_CAPTURE_REGISTERED')
