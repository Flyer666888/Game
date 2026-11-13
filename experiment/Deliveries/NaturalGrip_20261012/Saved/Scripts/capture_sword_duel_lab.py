"""Capture only the initial idle scene; send no game inputs or combat requests."""
import json
import time
from pathlib import Path
import unreal

_duel_dir = Path(unreal.Paths.project_dir()) / 'Docs/AI'
_duel_start = time.monotonic()
_duel_handle = None
_duel_near_handle = None
_duel_near_start = None
_duel_near_camera = None
_duel_near_stage = 0
_duel_original_camera_transform = None
_duel_original_fov = None
_duel_original_control_rotation = None
_duel_hidden_components = []


def _duel_near_capture(delta):
    global _duel_near_camera, _duel_near_stage, _duel_original_camera_transform, _duel_original_fov, _duel_original_control_rotation
    elapsed = time.monotonic() - _duel_near_start
    if elapsed < 2:
        return
    world = unreal.find_object(None, '/Game/ReversedScale/Maps/L_CombatLabSwordDuel.L_CombatLabSwordDuel')
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    if _duel_near_stage == 0:
        enemy = sorted(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.load_class(None, '/Script/experiment.NLEnemyCharacter')),
                       key=lambda a: a.get_name())[0]
        target = enemy.get_component_by_class(unreal.SkeletalMeshComponent).get_socket_location('hand_r')
        position = target + enemy.get_actor_forward_vector() * 100 + enemy.get_actor_right_vector() * 25 + unreal.Vector(0, 0, 12)
        transform = unreal.Transform(location=position, rotation=unreal.MathLibrary.find_look_at_rotation(position, target))
        _duel_near_camera = pawn.get_editor_property('player_camera')
        _duel_original_camera_transform = _duel_near_camera.get_world_transform()
        _duel_original_fov = _duel_near_camera.get_editor_property('field_of_view')
        _duel_original_control_rotation = pc.get_control_rotation()
        # Temporarily stop the player's eye-height camera update for this idle portrait.
        pawn.set_actor_tick_enabled(False)
        pc.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(position, target))
        _duel_near_camera.set_world_transform(transform, False, True)
        _duel_near_camera.set_editor_property('field_of_view', 38.0)
        for component in pawn.get_components_by_class(unreal.PrimitiveComponent):
            if component.get_name() in ('RightHand', 'HeldWeapon', 'RightSleeve'):
                _duel_hidden_components.append((component, component.get_editor_property('hidden_in_game')))
                component.set_hidden_in_game(True)
        _duel_near_stage = 1
    elif _duel_near_stage == 1 and elapsed > 5:
        unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="' + str(_duel_dir / 'EnemyGripRuntime.png') + '"')
        _duel_near_stage = 2
    elif _duel_near_stage == 2 and elapsed > 7:
        _duel_near_camera.set_world_transform(_duel_original_camera_transform, False, True)
        _duel_near_camera.set_editor_property('field_of_view', _duel_original_fov)
        pc.set_control_rotation(_duel_original_control_rotation)
        for component, hidden in _duel_hidden_components:
            component.set_hidden_in_game(hidden)
        pawn.set_actor_tick_enabled(True)
        unreal.unregister_slate_post_tick_callback(_duel_near_handle)
        unreal.log('ENEMY_GRIP_IDLE_PORTRAIT_CAPTURED')


def _duel_v(vector):
    return [vector.x, vector.y, vector.z]


def _duel_path(obj):
    return obj.get_path_name() if obj else None


def _duel_capture(delta):
    global _duel_near_handle, _duel_near_start
    if time.monotonic() - _duel_start < 20:
        return
    world = unreal.find_object(None, '/Game/ReversedScale/Maps/L_CombatLabSwordDuel.L_CombatLabSwordDuel')
    if not world:
        return
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    if not pawn:
        return
    # A metadata error must not repeat on every frame.
    unreal.unregister_slate_post_tick_callback(_duel_handle)
    enemies = []
    enemy_class = unreal.load_class(None, '/Script/experiment.NLEnemyCharacter')
    for enemy in unreal.GameplayStatics.get_all_actors_of_class(world, enemy_class):
        mesh = enemy.get_component_by_class(unreal.SkeletalMeshComponent)
        sword = enemy.get_editor_property('sword')
        brain = enemy.get_enemy_brain()
        definition = enemy.get_editor_property('blade').get_editor_property('attack_definition')
        enemies.append({'name': enemy.get_name(), 'capsule_origin_cm': _duel_v(enemy.get_actor_location()),
                        'mesh': _duel_path(mesh.get_editor_property('skeletal_mesh_asset')),
                        'grip_morph_name': str(enemy.get_editor_property('grip_morph_name')),
                        'grip_morph_weight': mesh.get_morph_target(enemy.get_editor_property('grip_morph_name')),
                        'grip_relative_location_cm': _duel_v(sword.get_editor_property('relative_location')),
                        'mesh_floor_origin_cm': _duel_v(mesh.get_world_location()),
                        'head_cm': _duel_v(mesh.get_socket_location('head')),
                        'hand_r_cm': _duel_v(mesh.get_socket_location('hand_r')),
                        'foot_l_cm': _duel_v(mesh.get_socket_location('foot_l')),
                        'foot_r_cm': _duel_v(mesh.get_socket_location('foot_r')),
                        'sword_origin_cm': _duel_v(sword.get_world_location()),
                        'sword_axis_cm': _duel_v(sword.get_up_vector()),
                        'health': enemy.get_editor_property('vitals').get_health(),
                        'combat_enabled': enemy.is_combat_enabled(), 'brain_state': str(brain.get_state()),
                        'damage': definition.get_editor_property('damage') if definition else None,
                        'telegraph_seconds': brain.get_editor_property('telegraph_seconds'),
                        'active_seconds': brain.get_editor_property('attack_seconds'),
                        'recover_seconds': brain.get_editor_property('recover_seconds'),
                        'animations': {key: _duel_path(enemy.get_editor_property(key)) for key in (
                            'idle_animation', 'walk_animation', 'attack_animation', 'hit_reaction_animation', 'death_animation')}})
    emitters = []
    emitter_class = unreal.load_class(None, '/Script/experiment.NLTrainingProjectileEmitter')
    for emitter in unreal.GameplayStatics.get_all_actors_of_class(world, emitter_class):
        emitters.append({'position_cm': _duel_v(emitter.get_actor_location()), 'enabled': emitter.is_firing_enabled()})
    nav_data = [{'name': nav.get_name(), 'runtime_generation_configured': 'Dynamic (DefaultEngine.ini)',
                 'agent_radius': nav.get_editor_property('AgentRadius'),
                 'agent_height': nav.get_editor_property('AgentHeight')}
                for nav in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.RecastNavMesh)]
    report = {'date': '2026-10-12', 'scene_loaded': True, 'map': '/Game/ReversedScale/Maps/L_CombatLabSwordDuel',
              'health': pawn.get_editor_property('vitals').get_health(),
              'guard': pawn.get_editor_property('guard').get_guard(),
              'camera_cm': _duel_v(pawn.get_editor_property('player_camera').get_world_location()),
              'melee_damage': pawn.get_editor_property('blade').get_editor_property('attack_definition').get_editor_property('damage'),
              'enemies': enemies, 'emitters': emitters, 'navigation_data': nav_data,
              'scope': 'Read-only initial scene capture. No gameplay input, movement/path query or combat tests were run.'}
    (_duel_dir / 'SwordDuelRuntimeScene-2026-10-12.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="' + str(_duel_dir / 'SwordDuelFirstPerson.png') + '"')
    unreal.log('SWORD_DUEL_INITIAL_SCENE_CAPTURED')
    _duel_near_start = time.monotonic()
    _duel_near_handle = unreal.register_slate_post_tick_callback(_duel_near_capture)


_duel_handle = unreal.register_slate_post_tick_callback(_duel_capture)
unreal.log('SWORD_DUEL_CAPTURE_REGISTERED')
