"""Read the initial mixed scene and screenshot; never start or retry an encounter."""
import json
import time
from pathlib import Path
import unreal

_mixed_dir = Path(unreal.Paths.project_dir()) / 'Docs/AI'
_mixed_start = time.monotonic()
_mixed_handle = None
_mixed_map = '/Game/ReversedScale/Maps/L_CombatLabMixed'


def _mixed_capture(delta):
    if time.monotonic() - _mixed_start < 20.0:
        return
    world = unreal.find_object(None, _mixed_map + '.L_CombatLabMixed')
    if not world:
        return
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    if not player:
        return
    controller = player.get_encounter_controller()
    if not controller:
        return
    unreal.unregister_slate_post_tick_callback(_mixed_handle)
    camera = player.get_editor_property('player_camera')
    instance = unreal.GameplayStatics.get_game_instance(world)
    # This engine build does not export SubsystemBlueprintLibrary to Python.
    # Inspect only existing subsystem objects owned by this game instance.
    service = next((obj for obj in unreal.ObjectIterator(unreal.NLCheckpointService)
                    if obj.get_outer() == instance), None)
    run = next((obj for obj in unreal.ObjectIterator(unreal.NLRunStateSubsystem)
                if obj.get_outer() == instance), None)
    enemies = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NLEnemyCharacter))
    waves = controller.get_editor_property('waves')
    report = {
        'date': '2026-10-14', 'task': 'ENEMY02A', 'map': _mixed_map,
        'controller_state': str(controller.get_state()),
        'checkpoint_enabled': controller.get_editor_property('bEnableCheckpoints'),
        'entry_wave_index': controller.get_entry_wave_index(),
        'wave_index': controller.get_wave_index(), 'wave_count': controller.get_wave_count(),
        'planned_count': controller.get_planned_count(), 'spawned_count': controller.get_spawned_count(),
        'defeated_count': controller.get_defeated_count(), 'alive_count': controller.get_alive_count(),
        'initial_seed': controller.get_initial_seed(),
        'random_state': controller.get_wave_entry_random_state(),
        'level_id': str(controller.get_editor_property('level_id')),
        'encounter_id': str(controller.get_editor_property('encounter_id')),
        'content_revision': str(controller.get_editor_property('content_revision')),
        'authored_wave_counts': [sum(entry.get_editor_property('count')
                                    for entry in wave.get_editor_property('spawn_entries')) for wave in waves],
        'authored_entries': [[{'entry_id': str(entry.get_editor_property('entry_id')),
                              'enemy_class': entry.get_editor_property('enemy_class').get_path_name(),
                              'count': entry.get_editor_property('count')}
                             for entry in wave.get_editor_property('spawn_entries')] for wave in waves],
        'initial_runtime_enemy_count': len(enemies),
        'initial_enemy_roles': [str(enemy.get_enemy_brain().get_editor_property('role')) for enemy in enemies],
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
        'shield_mesh': player.get_editor_property('mirror_face').get_editor_property('static_mesh').get_path_name(),
        'left_hand_mesh': player.get_editor_property('left_hand').get_editor_property('skeletal_mesh_asset').get_path_name(),
        'screenshot': str(_mixed_dir / 'MixedLabFirstPerson.png'),
        'scope': 'Only reads the initial running presentation and requests a screenshot. No Start, R/retry, pause, movement, attack, damage, disk Save, seed replay, enemy spawn or automated gameplay test. Normal startup may read a scoped checkpoint.',
    }
    (_mixed_dir / 'MixedLabRuntimeScene-2026-10-14.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.SystemLibrary.execute_console_command(world,
        'HighResShot 1600x900 filename="' + str(_mixed_dir / 'MixedLabFirstPerson.png') + '"')
    unreal.log('MIXED_LAB_INITIAL_SCENE_CAPTURED')


_mixed_handle = unreal.register_slate_post_tick_callback(_mixed_capture)
unreal.log('MIXED_LAB_CAPTURE_REGISTERED')

# The second script temporarily displays held art for a grip screenshot.
# It never raises the real guard or starts combat.
import runpy
runpy.run_path(str(Path(unreal.Paths.project_dir()) / 'Saved/Scripts/capture_shield_visual.py'))
