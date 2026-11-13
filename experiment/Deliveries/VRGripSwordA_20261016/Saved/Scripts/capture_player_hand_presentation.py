"""Initial Ready presentation only; no player inputs or combat are initiated."""
import hashlib
import json
import time
import traceback
from pathlib import Path
import unreal

_hand_capture_begin = time.monotonic()
_hand_capture_stage = 0
_hand_capture_player = None
_hand_capture_guard = None
_hand_capture_visual = None
_hand_capture_face = None
_hand_capture_handle = None
_hand_capture_docs = Path(unreal.Paths.project_dir()) / 'Docs/AI'
_hand_capture_report = {'date': '2026-10-15', 'views': [], 'no_agent_gameplay_inputs': True,
                        'tests_added_or_run': False,
                        'scope': 'Initial desktop Ready art presentation of the actual equipped hands. No controller simulation, enemy start or gameplay acceptance.'}

def _hand_component_record(component):
    return {'mesh': component.get_editor_property('skeletal_mesh_asset').get_path_name(),
            'materials': [component.get_material(i).get_path_name() for i in range(component.get_num_materials())],
            'relative_transform': str(component.get_relative_transform()),
            'animation': str(component.get_animation_mode())}

def _hand_capture_restore():
    if _hand_capture_face:
        _hand_capture_face.set_visibility(True)
        _hand_capture_face.set_hidden_in_game(False)
    if _hand_capture_guard:
        _hand_capture_guard.set_editor_property('guard_visual', _hand_capture_visual)
        if _hand_capture_visual:
            active = _hand_capture_guard.is_guard_active()
            _hand_capture_visual.set_visibility(active, True)
            _hand_capture_visual.set_hidden_in_game(not active, True)
    if _hand_capture_player:
        collision = _hand_capture_player.get_editor_property('guard_collision')
        collision.set_visibility(False)
        collision.set_hidden_in_game(True)

def _hand_capture_tick(delta):
    global _hand_capture_stage, _hand_capture_player, _hand_capture_guard, _hand_capture_visual, _hand_capture_face
    elapsed = time.monotonic() - _hand_capture_begin
    if elapsed < 18.0:
        return
    world = unreal.find_object(None, '/Game/ReversedScale/Maps/L_CombatLabMixed.L_CombatLabMixed')
    if not world:
        return
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    if not player:
        return
    encounter = player.get_encounter_controller()
    if not encounter or encounter.get_state() != unreal.NLEncounterState.READY:
        _hand_capture_restore()
        unreal.unregister_slate_post_tick_callback(_hand_capture_handle)
        return
    if _hand_capture_stage == 0:
        _hand_capture_player = player
        _hand_capture_report['hand_mesh_uasset_sha256'] = hashlib.sha256((Path(unreal.Paths.project_dir()) / 'Content/ReversedScale/Player/Hands/SK_PlayerHand_Realistic_R.uasset').read_bytes()).hexdigest()
        _hand_capture_report['right_hand'] = _hand_component_record(player.get_editor_property('right_hand'))
        _hand_capture_report['left_hand'] = _hand_component_record(player.get_editor_property('left_hand'))
        _hand_capture_report['health'] = player.get_editor_property('vitals').get_health()
        _hand_capture_report['guard'] = player.get_editor_property('guard').get_guard()
        _hand_capture_report['encounter_state'] = str(encounter.get_state())
        _hand_capture_report['alive_enemies'] = encounter.get_alive_count()
        _hand_capture_report['melee_damage'] = player.get_editor_property('blade').get_editor_property('attack_definition').get_editor_property('damage')
        filename = _hand_capture_docs / 'PlayerHands_Equipped.png'
        unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1800x1100 filename="' + str(filename) + '"')
        _hand_capture_report['views'].append(str(filename))
        _hand_capture_stage = 1
    elif _hand_capture_stage == 1 and elapsed >= 22.0:
        _hand_capture_guard = player.get_editor_property('guard')
        _hand_capture_visual = _hand_capture_guard.get_editor_property('guard_visual')
        _hand_capture_guard.set_editor_property('guard_visual', None)
        _hand_capture_visual.set_visibility(True, True)
        _hand_capture_visual.set_hidden_in_game(False, True)
        _hand_capture_face = player.get_editor_property('mirror_face')
        _hand_capture_face.set_visibility(False)
        _hand_capture_face.set_hidden_in_game(True)
        collision = player.get_editor_property('guard_collision')
        collision.set_visibility(False)
        collision.set_hidden_in_game(True)
        _hand_capture_stage = 2
    elif _hand_capture_stage == 2 and elapsed >= 25.0:
        filename = _hand_capture_docs / 'PlayerHands_BothGrip.png'
        unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1800x1100 filename="' + str(filename) + '"')
        _hand_capture_report['views'].append(str(filename))
        _hand_capture_report['guard_active_at_art_capture'] = _hand_capture_guard.is_guard_active()
        _hand_capture_report['guard_collision_at_art_capture'] = str(player.get_editor_property('guard_collision').get_collision_enabled())
        _hand_capture_stage = 3
    elif _hand_capture_stage == 3 and elapsed >= 29.0:
        _hand_capture_restore()
        _hand_capture_report['visual_binding_restored'] = True
        (_hand_capture_docs / 'PlayerHandsInitialPresentation-2026-10-15.json').write_text(json.dumps(_hand_capture_report, indent=2), encoding='utf-8')
        unreal.unregister_slate_post_tick_callback(_hand_capture_handle)
        unreal.SystemLibrary.execute_console_command(world, 'quit')

def _hand_capture_safe(delta):
    try:
        _hand_capture_tick(delta)
    except Exception:
        _hand_capture_restore()
        _hand_capture_report['error'] = traceback.format_exc()
        (_hand_capture_docs / 'PlayerHandsInitialPresentation-2026-10-15.json').write_text(json.dumps(_hand_capture_report, indent=2), encoding='utf-8')
        unreal.unregister_slate_post_tick_callback(_hand_capture_handle)
        unreal.log_error(_hand_capture_report['error'])

_hand_capture_handle = unreal.register_slate_post_tick_callback(_hand_capture_safe)
