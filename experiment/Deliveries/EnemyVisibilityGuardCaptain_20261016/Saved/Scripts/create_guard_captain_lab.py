"""Author ENEMY-02B's independent desktop lab. Does not start gameplay."""
import json
import math
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir())
A = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LIB = unreal.MaterialEditingLibrary
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SOURCE_MAP = '/Game/ReversedScale/Maps/L_CombatLabMixed'
MAP = '/Game/ReversedScale/Maps/L_CombatLabGuardCaptain'
CHARACTERS = '/Game/ReversedScale/Characters/WuxiaMale'
COMBAT = '/Game/ReversedScale/Combat'
ENCOUNTERS = '/Game/ReversedScale/Encounters'
PREFAB = CHARACTERS + '/BP_EnemyGuardCaptain'
SWORD_PREFAB = CHARACTERS + '/BP_EnemySwordDisciple'
CASTER_PREFAB = CHARACTERS + '/BP_EnemyTalismanDisciple'
MARKER_TAG = 'NL_GuardCaptainLabMarker'
PLAYER_POSITION = (30.0, -170.0, 90.4)
CAPTAIN_POINTS = (('CaptainFront', (430.0, -170.0, 90.4)),)
CASTER_POINTS = (('CaptainSupport', (900.0, 180.0, 90.4)),)
POINTS = CAPTAIN_POINTS + CASTER_POINTS


def path(value):
    return value.get_path_name() if value else None


def vector(value):
    return [value.x, value.y, value.z]


def asset(destination):
    value = A.load_asset(destination)
    if not value:
        raise RuntimeError('Required asset missing: ' + destination)
    return value


def snapshot_enemy(cdo):
    component = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
    transform = cdo.get_editor_property('sword_grip_transform')
    return {
        'class': path(cdo.get_class()),
        'refs': {key: path(cdo.get_editor_property(key)) for key in (
            'enemy_skeletal_mesh', 'idle_animation', 'walk_animation', 'attack_animation',
            'hit_reaction_animation', 'death_animation', 'enemy_attack_definition')},
        'mesh': path(component.get_editor_property('skeletal_mesh_asset')),
        'materials': [path(component.get_material(index)) for index in range(component.get_num_materials())],
        'grip_location': vector(transform.translation),
        'grip_quaternion': [transform.rotation.x, transform.rotation.y, transform.rotation.z, transform.rotation.w],
        'grip_morph': str(cdo.get_editor_property('grip_morph_name')),
        'grip_weight': cdo.get_editor_property('grip_morph_weight'),
    }


def make_data_asset(name, folder, cls):
    destination = folder + '/' + name
    value = A.load_asset(destination) if A.does_asset_exist(destination) else None
    if not value:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property('data_asset_class', cls)
        value = TOOLS.create_asset(name, folder, cls, factory)
    if not value or value.get_class() != cls:
        raise RuntimeError('Unexpected data asset class at ' + destination)
    return value


native = unreal.load_class(None, '/Script/experiment.NLGuardCaptainCharacter')
wave_class = unreal.load_class(None, '/Script/experiment.NLWaveDefinition')
attack_class = unreal.load_class(None, '/Script/experiment.NLAttackDefinition')
controller_class = unreal.load_class(None, '/Script/experiment.NLEncounterController')
sword_class = A.load_blueprint_class(SWORD_PREFAB)
caster_class = A.load_blueprint_class(CASTER_PREFAB)
if not all((native, wave_class, attack_class, controller_class, sword_class, caster_class)):
    raise RuntimeError('Compile ENEMY-02B and preserve the existing sword/caster prefabs first.')
if not A.does_asset_exist(SOURCE_MAP):
    raise RuntimeError('The preserved mixed desktop scene is required.')
if not hasattr(unreal.get_default_object(controller_class), 'get_ready_preview_count'):
    raise RuntimeError('Compile the Ready preview presentation before authoring this lab.')
sword_cdo = unreal.get_default_object(sword_class)
caster_cdo = unreal.get_default_object(caster_class)
preserved_sword, preserved_caster = snapshot_enemy(sword_cdo), snapshot_enemy(caster_cdo)
if preserved_sword['refs']['death_animation'] != CHARACTERS + '/Animations/Wuxia_Death_Grounded.Wuxia_Death_Grounded':
    raise RuntimeError('The current Grounded death must remain assigned.')
melee = asset(COMBAT + '/DA_YueyaoMelee')
if abs(melee.get_editor_property('damage') - 10.0) > .001:
    raise RuntimeError('Player melee damage must already be 10; this script does not alter it.')

# Only the new ward material is authored; all body/face/weapon materials are inherited.
material_path = COMBAT + '/Materials/M_GuardCaptainWard'
ward_material = A.load_asset(material_path) if A.does_asset_exist(material_path) else None
if not ward_material:
    ward_material = TOOLS.create_asset('M_GuardCaptainWard', COMBAT + '/Materials',
                                      unreal.Material, unreal.MaterialFactoryNew())
if not ward_material or ward_material.get_class() != unreal.Material.static_class():
    raise RuntimeError('Could not create the dedicated captain ward material.')
LIB.delete_all_material_expressions(ward_material)
ward_material.set_editor_property('two_sided', True)
ward_material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
color = LIB.create_material_expression(ward_material, unreal.MaterialExpressionVectorParameter)
color.set_editor_property('parameter_name', 'Color')
color.set_editor_property('default_value', unreal.LinearColor(.10, .46, .62, 1.0))
strength = LIB.create_material_expression(ward_material, unreal.MaterialExpressionScalarParameter)
strength.set_editor_property('parameter_name', 'GlowStrength')
strength.set_editor_property('default_value', .7)
glow = LIB.create_material_expression(ward_material, unreal.MaterialExpressionMultiply)
LIB.connect_material_expressions(color, '', glow, 'A')
LIB.connect_material_expressions(strength, '', glow, 'B')
LIB.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
LIB.connect_material_property(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
opacity = LIB.create_material_expression(ward_material, unreal.MaterialExpressionConstant)
opacity.set_editor_property('r', .36)
LIB.connect_material_property(opacity, '', unreal.MaterialProperty.MP_OPACITY)
roughness = LIB.create_material_expression(ward_material, unreal.MaterialExpressionConstant)
roughness.set_editor_property('r', .6)
LIB.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
LIB.recompile_material(ward_material)
if not A.save_loaded_asset(ward_material, False):
    raise RuntimeError('Could not save the captain ward material.')

sword_brain = sword_cdo.get_enemy_brain()
timings = {key: float(sword_brain.get_editor_property(key)) * 1.5
           for key in ('telegraph_seconds', 'attack_seconds', 'recover_seconds')}
definition = make_data_asset('DA_EnemyGuardCaptainHeavy', COMBAT, attack_class)
attack_values = {
    'stable_id': unreal.Name('Attack.Enemy.GuardCaptain.Heavy'), 'damage': 20.0,
    'telegraph_seconds': timings['telegraph_seconds'],
    'active_window_seconds': timings['attack_seconds'],
    'cooldown_seconds': timings['recover_seconds'],
    'can_be_blocked': True, 'can_be_parried': False, 'can_be_reflected': False,
    'can_be_interrupted': True, 'hit_feedback_tag': unreal.Name('Combat.Hit.GuardCaptainHeavy'),
}
for key, value in attack_values.items():
    definition.set_editor_property(key, value)
if not A.save_loaded_asset(definition, False):
    raise RuntimeError('Could not save the captain heavy attack definition.')

bp = A.load_asset(PREFAB) if A.does_asset_exist(PREFAB) else None
if not bp:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', native)
    bp = TOOLS.create_asset('BP_EnemyGuardCaptain', CHARACTERS, unreal.Blueprint, factory)
if not bp or unreal.BlueprintEditorLibrary.get_blueprint_parent_class(bp) != native:
    raise RuntimeError('The captain Blueprint must directly inherit NLGuardCaptainCharacter.')
if not unreal.BlueprintEditorLibrary.compile_blueprint(bp):
    raise RuntimeError('Could not compile the captain Blueprint.')
captain_class = A.load_blueprint_class(PREFAB)
if not captain_class:
    raise RuntimeError('The captain Blueprint must expose a generated class.')
cdo = unreal.get_default_object(captain_class)
for key in ('enemy_skeletal_mesh', 'idle_animation', 'walk_animation', 'attack_animation',
            'hit_reaction_animation', 'death_animation', 'sword_grip_transform',
            'grip_morph_name', 'grip_morph_weight'):
    cdo.set_editor_property(key, sword_cdo.get_editor_property(key))
cdo.set_editor_property('bShowSword', True)
cdo.set_editor_property('enemy_attack_definition', definition)
cdo.set_editor_property('guard_field_material', ward_material)
cdo.set_editor_property('guard_break_exposure_seconds', 1.2)
mesh = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
source_mesh = sword_cdo.get_component_by_class(unreal.SkeletalMeshComponent)
mesh.set_skeletal_mesh_asset(source_mesh.get_editor_property('skeletal_mesh_asset'))
mesh.set_relative_transform(source_mesh.get_relative_transform(), False, True)
for index in range(source_mesh.get_num_materials()):
    mesh.set_material(index, source_mesh.get_material(index))
cdo.get_editor_property('blade').set_editor_property('attack_definition', definition)
brain = cdo.get_enemy_brain()
for key in ('attack_range', 'spawn_grace_seconds', 'reposition_radius', 'max_navigation_retries',
            'reposition_acceptance_distance', 'navigation_ready_timeout_seconds', 'navigation_retry_delay_seconds'):
    brain.set_editor_property(key, sword_brain.get_editor_property(key))
brain.set_editor_property('role', unreal.NLEnemyRole.GUARD_CAPTAIN)
brain.set_editor_property('minimum_slot_wait_seconds', 1.4)
for key, value in timings.items():
    brain.set_editor_property(key, value)
vitals = cdo.get_editor_property('vitals')
for key, value in {'max_health': 30.0, 'max_guard': 40.0, 'damage_protection_seconds': 0.0}.items():
    vitals.set_editor_property(key, value)
guard = cdo.get_editor_property('captain_guard')
for key, value in {'maintenance_cost_per_second': 0.0, 'melee_block_guard_cost': 20.0,
                   'block_guard_cost': 20.0, 'perfect_window_seconds': 0.0,
                   'recovery_delay_seconds': 0.0, 'recovery_per_second': 40.0,
                   'guard_break_seconds': 1.2, 'minimum_facing_dot': .35, 'contact_padding': 3.0}.items():
    guard.set_editor_property(key, value)
field = cdo.get_editor_property('captain_guard_visual')
field.set_static_mesh(asset('/Engine/BasicShapes/Cylinder'))
field.set_material(0, ward_material)
source_movement = sword_cdo.get_component_by_class(unreal.CharacterMovementComponent)
movement = cdo.get_component_by_class(unreal.CharacterMovementComponent)
for key in ('max_walk_speed', 'rotation_rate', 'max_step_height', 'orient_rotation_to_movement',
            'use_rvo_avoidance', 'avoidance_consideration_radius'):
    movement.set_editor_property(key, source_movement.get_editor_property(key))
if not unreal.BlueprintEditorLibrary.compile_blueprint(bp) or not A.save_loaded_asset(bp, False):
    raise RuntimeError('Could not compile/save the configured captain prefab.')
captain_class = A.load_blueprint_class(PREFAB)
cdo = unreal.get_default_object(captain_class)

waves, wave_rows = [], []
for index in (1, 2):
    wave = make_data_asset('DA_WaveGuardCaptain' + str(index).zfill(2), ENCOUNTERS, wave_class)
    entries = []
    composition = [('GuardCaptain', captain_class, CAPTAIN_POINTS)]
    if index == 2:
        composition.append(('TalismanSupport', caster_class, CASTER_POINTS))
    for entry_id, enemy_class, locations in composition:
        entry = unreal.NLWaveSpawnEntry()
        for key, value in {'entry_id': unreal.Name(entry_id), 'enemy_class': enemy_class, 'count': 1,
                           'spawn_point_ids': [unreal.Name(point_id) for point_id, _ in locations]}.items():
            entry.set_editor_property(key, value)
        entries.append(entry)
    for key, value in {'wave_id': unreal.Name('Wave.GuardCaptain.' + str(index).zfill(2)),
                       'spawn_entries': entries, 'spawn_interval_seconds': .8,
                       'intermission_seconds': 3.0, 'max_alive': 2,
                       'max_spawn_retries': 3, 'retry_delay_seconds': .5}.items():
        wave.set_editor_property(key, value)
    if not A.save_loaded_asset(wave, False):
        raise RuntimeError('Could not save the captain wave.')
    waves.append(wave)
    wave_rows.append({'asset': path(wave), 'planned_count': len(entries),
                      'entries': [{'entry_id': str(entry.get_editor_property('entry_id')),
                                   'enemy_class': path(entry.get_editor_property('enemy_class'))}
                                  for entry in entries]})

if not (LEVEL.load_level(MAP) if A.does_asset_exist(MAP) else LEVEL.new_level_from_template(MAP, SOURCE_MAP)):
    raise RuntimeError('Could not create the independent captain lab.')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
mode_class = world.get_world_settings().get_editor_property('default_game_mode')
mode = unreal.get_default_object(mode_class) if mode_class else None
if not mode or mode.get_editor_property('default_pawn_class') != unreal.load_class(None, '/Script/experiment.NLDesktopPlayerCharacter'):
    raise RuntimeError('The captain lab must retain the Desktop player.')
if mode.get_editor_property('hud_class') != unreal.load_class(None, '/Script/experiment.NLCombatLabHUD'):
    raise RuntimeError('The captain lab must retain the combat HUD.')
training = unreal.load_class(None, '/Script/experiment.NLTrainingEnemy')
emitter = unreal.load_class(None, '/Script/experiment.NLTrainingProjectileEmitter')
removed, player_starts = [], []
for actor in ACTORS.get_all_level_actors():
    tags = [str(tag) for tag in actor.get_editor_property('tags')]
    obsolete = (isinstance(actor, unreal.NLEnemyCharacter)
                or actor.get_class() in (controller_class, training, emitter)
                or isinstance(actor, unreal.TextRenderActor)
                or any(tag in tags for tag in (MARKER_TAG, 'NL_MixedLabMarker', 'NL_WaveLabMarker', 'NL_ReadyEnemyPreview')))
    if obsolete:
        removed.append(actor.get_actor_label())
        if not ACTORS.destroy_actor(actor):
            raise RuntimeError('Could not remove inherited combat/marker actor.')
    elif isinstance(actor, unreal.PlayerStart):
        actor.set_actor_location(unreal.Vector(*PLAYER_POSITION), False, True)
        actor.set_actor_rotation(unreal.Rotator(), True)
        player_starts.append(actor.get_actor_label())
if not player_starts:
    raise RuntimeError('The captain lab requires a preserved PlayerStart.')

spawn_points = []
for point_id, location in POINTS:
    point = unreal.NLWaveSpawnPoint()
    point.set_editor_property('spawn_point_id', unreal.Name(point_id))
    yaw = math.degrees(math.atan2(PLAYER_POSITION[1] - location[1], PLAYER_POSITION[0] - location[0]))
    point.set_editor_property('spawn_transform', unreal.Transform(
        location=unreal.Vector(*location), rotation=unreal.Rotator(yaw=yaw), scale=unreal.Vector(1, 1, 1)))
    spawn_points.append(point)
controller = ACTORS.spawn_actor_from_class(controller_class, unreal.Vector(300, 0, 0))
if not controller:
    raise RuntimeError('Could not author the captain encounter.')
controller.set_actor_label('Encounter_GuardCaptain_ENEMY02B')
for key, value in {'waves': waves, 'spawn_points': spawn_points, 'seed': 20261016,
                   'corpse_hold_seconds': 2.0, 'max_spawns_per_tick': 1,
                   'level_id': unreal.Name('Level.CombatLab.GuardCaptain'),
                   'encounter_id': unreal.Name('Encounter.GuardCaptain'),
                   'content_revision': unreal.Name('GuardCaptain.ENEMY02B.1'),
                   'bEnableCheckpoints': True, 'show_ready_previews': True}.items():
    controller.set_editor_property(key, value)
markers = []
for point_id, location in POINTS:
    marker = ACTORS.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(location[0], location[1], .65))
    marker.set_actor_label(point_id + '_BirthArea')
    marker.set_editor_property('tags', [MARKER_TAG, point_id])
    marker.set_actor_scale3d(unreal.Vector(.7, .7, .01))
    marker.set_actor_enable_collision(False)
    component = marker.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(asset('/Engine/BasicShapes/Cylinder'))
    component.set_material(0, ward_material if point_id.startswith('CaptainFront')
                           else asset(COMBAT + '/Materials/M_TalismanCast'))
    component.set_collision_profile_name('NoCollision')
    component.set_editor_property('bCanEverAffectNavigation', False)
    component.set_editor_property('cast_shadow', False)
    markers.append(path(marker))

nav_bounds = []
for actor in ACTORS.get_all_level_actors():
    if isinstance(actor, unreal.NavMeshBoundsVolume):
        origin, extent = actor.get_actor_bounds(False)
        nav_bounds.append({'actor': path(actor), 'origin_cm': vector(origin), 'extent_cm': vector(extent)})
if not nav_bounds or any(not any(all(abs(location[axis] - row['origin_cm'][axis]) <= row['extent_cm'][axis]
                                   for axis in range(3)) for row in nav_bounds) for _, location in POINTS):
    raise RuntimeError('Captain spawn points require preserved navigation bounds.')
if snapshot_enemy(unreal.get_default_object(sword_class)) != preserved_sword or snapshot_enemy(unreal.get_default_object(caster_class)) != preserved_caster:
    raise RuntimeError('Existing sword/caster prefab changed during captain authoring.')
if abs(melee.get_editor_property('damage') - 10.0) > .001:
    raise RuntimeError('Player damage changed unexpectedly.')
if not LEVEL.save_current_level():
    raise RuntimeError('Could not save the independent captain map.')

report = {
    'date': '2026-10-16', 'task': 'ENEMY-02B', 'map': MAP, 'source_map_preserved': SOURCE_MAP,
    'game_mode': path(mode_class), 'player_starts': player_starts, 'prefab': path(bp),
    'captain': snapshot_enemy(cdo), 'attack_definition': path(definition),
    'captain_health': 30, 'captain_guard': 40, 'melee_guard_cost': 20,
    'captain_damage': 20, 'player_melee_damage': 10, 'counter_window_seconds': 1.2,
    'timings': timings, 'defensive_hold_seconds': 1.4,
    'defense': 'Finite forward ward; existing Guard/Resolver routes; side and legs remain open; no perfect reflection.',
    'animation': 'Existing sword animation at 2/3 speed; every brain stage scaled together, original notifies unchanged.',
    'waves': wave_rows, 'authored_wave_counts': [1, 2], 'authored_total_planned_count': 3,
    'maximum_alive': 2, 'show_ready_previews': True, 'auto_start': False,
    'controller': {'actor': path(controller), 'level_id': 'Level.CombatLab.GuardCaptain',
                   'encounter_id': 'Encounter.GuardCaptain', 'content_revision': 'GuardCaptain.ENEMY02B.1',
                   'checkpoint_enabled': True, 'state_before_start': str(controller.get_state())},
    'spawn_points': [{'id': point_id, 'capsule_position_cm': list(location)} for point_id, location in POINTS],
    'preserved_sword': preserved_sword, 'preserved_caster': preserved_caster,
    'navigation_bounds': nav_bounds, 'markers': markers, 'removed_inherited_actors': removed,
    'scope': 'Independent desktop map and captain assets saved. Current VR map unchanged. No gameplay inputs, tests or checkpoint disk exercise.',
}
(PROJECT / 'Docs/AI/GuardCaptainLabSaved-2026-10-16.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('GUARD_CAPTAIN_LAB_SAVED ' + MAP)
