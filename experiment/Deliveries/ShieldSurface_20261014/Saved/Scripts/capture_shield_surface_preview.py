"""Temporary front/back material views in Ready. No input or combat actions."""
import json
import time
import traceback
from pathlib import Path
import unreal

_surface_begin = time.monotonic()
_surface_handle = None
_surface_stage = 0
_surface_guard = None
_surface_visual = None
_surface_face = None
_surface_original_transform = None
_surface_player = None
_surface_hud_toggled = False
_surface_docs = Path(unreal.Paths.project_dir()) / 'Docs/AI'
_surface_records = {'date': '2026-10-14', 'views': [], 'no_agent_gameplay_inputs': True,
                    'tests_added_or_run': False,
                    'scope': 'Art appearance only. Visual pointer and mesh transform are restored. No guard activation or collision/combat edits.'}


def _surface_tr(t):
    return {'location': [t.translation.x, t.translation.y, t.translation.z],
            'quaternion_xyzw': [t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w],
            'scale': [t.scale3d.x, t.scale3d.y, t.scale3d.z]}


def _surface_restore(world):
    global _surface_hud_toggled
    if _surface_face and _surface_original_transform:
        _surface_face.set_relative_transform(_surface_original_transform, False, True)
    if _surface_guard:
        _surface_guard.set_editor_property('guard_visual', _surface_visual)
        if _surface_visual:
            active = _surface_guard.is_guard_active()
            _surface_visual.set_visibility(active, True)
            _surface_visual.set_hidden_in_game(not active, True)
    if _surface_player:
        for name in ('right_hand', 'right_sleeve', 'held_weapon'):
            c = _surface_player.get_editor_property(name)
            c.set_visibility(True)
            c.set_hidden_in_game(False)
        c = _surface_player.get_editor_property('guard_collision')
        c.set_visibility(False)
        c.set_hidden_in_game(True)
    if _surface_hud_toggled:
        unreal.SystemLibrary.execute_console_command(world, 'showhud')
        _surface_hud_toggled = False


def _surface_snapshot(world, player, name):
    filename = _surface_docs / name
    _surface_records['views'].append({
        'file': str(filename), 'guard_active': player.get_editor_property('guard').is_guard_active(),
        'collision': str(player.get_editor_property('guard_collision').get_collision_enabled()),
        'health': player.get_editor_property('vitals').get_health(),
        'guard': player.get_editor_property('guard').get_guard(),
        'mirror_transform': _surface_tr(_surface_face.get_relative_transform()),
        'camera_transform': _surface_tr(player.get_editor_property('player_camera').get_world_transform()),
    })
    unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="' + str(filename) + '"')


def _surface_tick(delta):
    global _surface_stage, _surface_guard, _surface_visual, _surface_face
    global _surface_original_transform, _surface_player, _surface_hud_toggled
    elapsed = time.monotonic() - _surface_begin
    if elapsed < 22.0:
        return
    world = unreal.find_object(None, '/Game/ReversedScale/Maps/L_CombatLabMixed.L_CombatLabMixed')
    if not world:
        return
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    if not player:
        return
    encounter = player.get_encounter_controller()
    if not encounter or encounter.get_state() != unreal.NLEncounterState.READY:
        _surface_restore(world)
        unreal.unregister_slate_post_tick_callback(_surface_handle)
        return
    if _surface_stage == 0:
        _surface_player = player
        _surface_guard = player.get_editor_property('guard')
        _surface_visual = _surface_guard.get_editor_property('guard_visual')
        _surface_face = player.get_editor_property('mirror_face')
        _surface_original_transform = _surface_face.get_relative_transform()
        _surface_guard.set_editor_property('guard_visual', None)
        _surface_visual.set_visibility(True, True)
        _surface_visual.set_hidden_in_game(False, True)
        for name in ('right_hand', 'right_sleeve', 'held_weapon'):
            c = player.get_editor_property(name)
            c.set_visibility(False)
            c.set_hidden_in_game(True)
        c = player.get_editor_property('guard_collision')
        c.set_visibility(False)
        c.set_hidden_in_game(True)
        unreal.SystemLibrary.execute_console_command(world, 'showhud')
        _surface_hud_toggled = True
        _surface_stage = 1
    elif _surface_stage == 1 and elapsed >= 26.0:
        _surface_snapshot(world, player, 'DragonShieldRealistic_Back.png')
        _surface_stage = 2
    elif _surface_stage == 2 and elapsed >= 30.0:
        front = unreal.Transform(location=_surface_original_transform.translation + unreal.Vector(28.0, 0.0, 16.0),
                                 rotation=unreal.Rotator(yaw=180.0), scale=_surface_original_transform.scale3d)
        _surface_face.set_relative_transform(front, False, True)
        for name in ('left_hand', 'left_sleeve'):
            c = player.get_editor_property(name)
            c.set_visibility(False)
            c.set_hidden_in_game(True)
        _surface_stage = 3
    elif _surface_stage == 3 and elapsed >= 34.0:
        _surface_snapshot(world, player, 'DragonShieldRealistic_Front.png')
        _surface_stage = 4
    elif _surface_stage == 4 and elapsed >= 38.0:
        _surface_restore(world)
        _surface_records['visual_and_hud_restored'] = True
        _surface_records['original_mirror_transform'] = _surface_tr(_surface_original_transform)
        (_surface_docs / 'ShieldSurfacePresentation-2026-10-14.json').write_text(json.dumps(_surface_records, indent=2), encoding='utf-8')
        unreal.unregister_slate_post_tick_callback(_surface_handle)
        unreal.log('SHIELD_SURFACE_FRONT_BACK_CAPTURED_AND_RESTORED')


def _surface_safe_tick(delta):
    try:
        _surface_tick(delta)
    except Exception:
        world = unreal.find_object(None, '/Game/ReversedScale/Maps/L_CombatLabMixed.L_CombatLabMixed')
        _surface_restore(world)
        unreal.unregister_slate_post_tick_callback(_surface_handle)
        unreal.log_error(traceback.format_exc())


_surface_handle = unreal.register_slate_post_tick_callback(_surface_safe_tick)
unreal.log('SHIELD_SURFACE_ART_PREVIEW_REGISTERED')
