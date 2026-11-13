"""Read and photograph the initial Ready scene; never send gameplay input."""
import json
import time
from pathlib import Path
import unreal

_wave_dir = Path(unreal.Paths.project_dir()) / 'Docs/AI'
_wave_start = time.monotonic()
_wave_handle = None
_wave_map = '/Game/ReversedScale/Maps/L_CombatLabWaves'


def _wave_v(value):
    return [value.x, value.y, value.z]


def _wave_path(value):
    return value.get_path_name() if value else None


def _wave_capture(delta):
    if time.monotonic() - _wave_start < 20.0:
        return
    world = unreal.find_object(None, _wave_map + '.L_CombatLabWaves')
    if not world:
        return
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    if not pawn:
        return
    # Unregister before metadata reads so an error cannot repeat every frame.
    unreal.unregister_slate_post_tick_callback(_wave_handle)
    controller_class = unreal.load_class(None, '/Script/experiment.NLEncounterController')
    enemy_class = unreal.load_class(None, '/Script/experiment.NLEnemyCharacter')
    controllers = unreal.GameplayStatics.get_all_actors_of_class(world, controller_class)
    controller_rows = []
    for controller in controllers:
        controller_rows.append({
            'actor': _wave_path(controller), 'class': _wave_path(controller.get_class()),
            'state': str(controller.get_state()), 'running': controller.is_running(),
            'paused': controller.is_encounter_paused(),
            'configured_seed': controller.get_editor_property('seed'),
            'initial_seed': controller.get_initial_seed(),
            'current_random_seed': controller.get_current_random_seed(),
            'wave_index': controller.get_wave_index(), 'wave_count': controller.get_wave_count(),
            'completed_wave_count': controller.get_completed_wave_count(),
            'planned_count': controller.get_planned_count(), 'spawned_count': controller.get_spawned_count(),
            'defeated_count': controller.get_defeated_count(), 'alive_count': controller.get_alive_count(),
            'failed_spawn_count': controller.get_failed_spawn_count(),
            'current_wave_planned_count': controller.get_current_wave_planned_count(),
            'current_wave_spawned_count': controller.get_current_wave_spawned_count(),
            'intermission_remaining_seconds': controller.get_intermission_remaining(),
            'failure_reason': str(controller.get_failure_reason()),
            'corpse_hold_seconds': controller.get_editor_property('corpse_hold_seconds'),
            'max_spawns_per_tick': controller.get_editor_property('max_spawns_per_tick'),
            'wave_assets': [_wave_path(wave) for wave in controller.get_editor_property('waves')],
        })
    camera = pawn.get_editor_property('player_camera')
    report = {
        'date': '2026-10-12', 'slice': 'WAVE-01', 'scene_loaded': True,
        'map': _wave_map, 'world': _wave_path(world), 'controller_count': len(controllers),
        'controllers': controller_rows,
        'world_enemy_count': len(unreal.GameplayStatics.get_all_actors_of_class(world, enemy_class)),
        'health': pawn.get_editor_property('vitals').get_health(),
        'guard': pawn.get_editor_property('guard').get_guard(),
        'camera_cm': _wave_v(camera.get_world_location()),
        'player': {'actor': _wave_path(pawn), 'class': _wave_path(pawn.get_class()),
                   'capsule_origin_cm': _wave_v(pawn.get_actor_location()),
                   'health': pawn.get_editor_property('vitals').get_health(),
                   'guard': pawn.get_editor_property('guard').get_guard(),
                   'standing_eye_height_cm': pawn.get_editor_property('standing_eye_height'),
                   'camera_cm': _wave_v(camera.get_world_location()),
                   'camera_field_of_view': camera.get_editor_property('field_of_view'),
                   'melee_damage': pawn.get_editor_property('blade').get_editor_property('attack_definition').get_editor_property('damage'),
                   'held_weapon': _wave_path(pawn.get_editor_property('held_weapon').get_editor_property('static_mesh'))},
        'screenshot': str(_wave_dir / 'WaveLabFirstPerson.png'),
        'scope': 'Read-only initial scene presentation after a 20-second Slate wait. No G input, enemy spawn, navigation or movement query, seed replay, pause/retry action or WAVE gameplay acceptance was performed.',
    }
    (_wave_dir / 'WaveLabRuntimeScene-2026-10-12.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.SystemLibrary.execute_console_command(
        world, 'HighResShot 1600x900 filename="' + str(_wave_dir / 'WaveLabFirstPerson.png') + '"')
    unreal.log('WAVE_LAB_INITIAL_SCENE_CAPTURED')


_wave_handle = unreal.register_slate_post_tick_callback(_wave_capture)
unreal.log('WAVE_LAB_CAPTURE_REGISTERED')
