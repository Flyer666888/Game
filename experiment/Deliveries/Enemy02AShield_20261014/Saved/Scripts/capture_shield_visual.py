"""Preview held art without raising guard, changing collision or sending input."""
import json
import time
from pathlib import Path
import unreal

_shield_start = time.monotonic()
_shield_handle = None
_shield_stage = 0
_shield_guard = None
_shield_original_visual = None
_shield_docs = Path(unreal.Paths.project_dir()) / 'Docs/AI'


def _shield_restore_visual():
    if _shield_guard:
        _shield_guard.set_editor_property('guard_visual', _shield_original_visual)
        if _shield_original_visual:
            active = _shield_guard.is_guard_active()
            _shield_original_visual.set_visibility(active, True)
            _shield_original_visual.set_hidden_in_game(not active, True)
            collision = _shield_guard.get_editor_property('guard_collision')
            collision.set_visibility(False)
            collision.set_hidden_in_game(True)


def _shield_transform(value):
    return {'location_cm': [value.translation.x, value.translation.y, value.translation.z],
            'quaternion_xyzw': [value.rotation.x, value.rotation.y, value.rotation.z, value.rotation.w],
            'scale': [value.scale3d.x, value.scale3d.y, value.scale3d.z]}


def _shield_preview(delta):
    global _shield_stage, _shield_guard, _shield_original_visual
    elapsed = time.monotonic() - _shield_start
    if elapsed < 26.0:
        return
    world = unreal.find_object(None, '/Game/ReversedScale/Maps/L_CombatLabMixed.L_CombatLabMixed')
    if not world:
        return
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    if not player:
        return
    encounter = player.get_encounter_controller()
    if not encounter or encounter.get_state() != unreal.NLEncounterState.READY:
        _shield_restore_visual()
        unreal.unregister_slate_post_tick_callback(_shield_handle)
        return
    if _shield_stage == 0:
        # GuardVisual is presentation-only. Detach that pointer temporarily so
        # the normal guard tick keeps its collision/resources while the mesh
        # is visible for this asset screenshot. Never call SetGuardHeld.
        _shield_guard = player.get_editor_property('guard')
        _shield_original_visual = _shield_guard.get_editor_property('guard_visual')
        _shield_guard.set_editor_property('guard_visual', None)
        pivot = player.get_editor_property('mirror_pivot')
        pivot.set_visibility(True, True)
        pivot.set_hidden_in_game(False, True)
        collision = player.get_editor_property('guard_collision')
        collision.set_visibility(False)
        collision.set_hidden_in_game(True)
        _shield_stage = 1
        unreal.log('SHIELD_ART_VISIBLE_WITHOUT_GUARD_INPUT')
    elif _shield_stage == 1 and elapsed >= 30.0:
        source = player.get_editor_property('left_hand')
        record = {
            'date': '2026-10-14', 'mesh': player.get_editor_property('mirror_face').get_editor_property('static_mesh').get_path_name(),
            'shield_world_transform': _shield_transform(player.get_editor_property('mirror_face').get_world_transform()),
            'hand_relative_transform': _shield_transform(source.get_relative_transform()),
            'hand_bone_component_transform': _shield_transform(source.get_socket_transform('hand_r', unreal.RelativeTransformSpace.RTS_COMPONENT)),
            'ready': True, 'guard_active': player.get_editor_property('guard').is_guard_active(),
            'real_guard_collision': str(player.get_editor_property('guard_collision').get_collision_enabled()),
            'temporary_art_actor_count': 0,
            'presentation_binding_temporarily_detached': True,
            'screenshot': 'Docs/AI/DragonShieldFirstPerson.png',
            'scope': 'Held mesh presentation only. GuardVisual pointer is restored after capture; no guard raise, inputs, collision edits, attacks, AI starts, forced resource changes or gameplay tests. External user input may still change guard normally.',
        }
        (_shield_docs / 'DragonShieldVisual-2026-10-14.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="' + str(_shield_docs / 'DragonShieldFirstPerson.png') + '"')
        _shield_stage = 2
        unreal.log('SHIELD_VISUAL_ONLY_CAPTURE_REQUESTED')
    elif _shield_stage == 2 and elapsed >= 34.0:
        _shield_restore_visual()
        unreal.unregister_slate_post_tick_callback(_shield_handle)
        unreal.log('SHIELD_VISUAL_BINDING_RESTORED')


def _shield_safe_preview(delta):
    try:
        _shield_preview(delta)
    except Exception:
        import traceback
        _shield_restore_visual()
        unreal.unregister_slate_post_tick_callback(_shield_handle)
        unreal.log_error(traceback.format_exc())


_shield_handle = unreal.register_slate_post_tick_callback(_shield_safe_preview)
unreal.log('SHIELD_VISUAL_CAPTURE_REGISTERED')
