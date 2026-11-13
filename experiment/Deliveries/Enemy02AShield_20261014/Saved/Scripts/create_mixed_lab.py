"""Author the independent ENEMY02A mixed encounter without starting gameplay."""
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
SOURCE_MAP = '/Game/ReversedScale/Maps/L_CombatLabCheckpoint'
MAP = '/Game/ReversedScale/Maps/L_CombatLabMixed'
CHARACTER_ROOT = '/Game/ReversedScale/Characters/WuxiaMale'
COMBAT_ROOT = '/Game/ReversedScale/Combat'
ENCOUNTER_ROOT = '/Game/ReversedScale/Encounters'
SWORD_PREFAB = CHARACTER_ROOT + '/BP_EnemySwordDisciple'
CASTER_PREFAB = CHARACTER_ROOT + '/BP_EnemyTalismanDisciple'
EXPECTED_MESH = CHARACTER_ROOT + '/SK_WuxiaMale_Combat'
EXPECTED_DEATH = CHARACTER_ROOT + '/Animations/Wuxia_Death_Grounded'
CAST_ANIMATION = CHARACTER_ROOT + '/Animations/Wuxia_Cast_Talisman'
MARKER_TAG = 'NL_MixedLabMarker'
PLAYER_POSITION = (30.0, -170.0, 90.4)
SWORD_POINTS = (
    ('MixedSword01', (430.0, -280.0, 90.4)),
    ('MixedSword02', (620.0, 40.0, 90.4)),
    ('MixedSword03', (470.0, 190.0, 90.4)),
)
CASTER_POINTS = (
    ('MixedCaster01', (900.0, -280.0, 90.4)),
    ('MixedCaster02', (950.0, 220.0, 90.4)),
)
POINTS = SWORD_POINTS + CASTER_POINTS


def path(value): return value.get_path_name() if value else None
def vector(value): return [value.x, value.y, value.z]
def transform_record(value):
    return {'location_cm': vector(value.translation),
            'rotation_quaternion_xyzw': [value.rotation.x, value.rotation.y, value.rotation.z, value.rotation.w],
            'scale': vector(value.scale3d)}
def asset(destination):
    value = A.load_asset(destination)
    if not value:
        raise RuntimeError('Required asset is missing: ' + destination)
    return value


def material(name, color, emissive):
    destination = COMBAT_ROOT + '/Materials/' + name
    value = A.load_asset(destination) if A.does_asset_exist(destination) else None
    if not value:
        value = TOOLS.create_asset(name, COMBAT_ROOT + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
    if not value:
        raise RuntimeError('Could not create the new talisman material: ' + destination)
    # Only these two new materials are writable. The source combat materials stay intact.
    LIB.delete_all_material_expressions(value)
    value.set_editor_property('two_sided', True)
    base = LIB.create_material_expression(value, unreal.MaterialExpressionVectorParameter)
    base.set_editor_property('parameter_name', 'Color')
    base.set_editor_property('default_value', unreal.LinearColor(*color, 1.0))
    LIB.connect_material_property(base, '', unreal.MaterialProperty.MP_BASE_COLOR)
    glow_strength = LIB.create_material_expression(value, unreal.MaterialExpressionScalarParameter)
    glow_strength.set_editor_property('parameter_name', 'GlowStrength')
    glow_strength.set_editor_property('default_value', emissive)
    glow = LIB.create_material_expression(value, unreal.MaterialExpressionMultiply)
    LIB.connect_material_expressions(base, '', glow, 'A')
    LIB.connect_material_expressions(glow_strength, '', glow, 'B')
    LIB.connect_material_property(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    roughness = LIB.create_material_expression(value, unreal.MaterialExpressionConstant)
    roughness.set_editor_property('r', .55)
    LIB.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
    LIB.recompile_material(value)
    if not A.save_loaded_asset(value, False):
        raise RuntimeError('Could not save talisman material: ' + destination)
    return value


def sword_snapshot(cdo):
    mesh_component = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
    sword = cdo.get_editor_property('sword')
    return {
        'generated_class': path(cdo.get_class()),
        'refs': {name: path(cdo.get_editor_property(name)) for name in (
            'enemy_skeletal_mesh', 'idle_animation', 'walk_animation', 'attack_animation',
            'hit_reaction_animation', 'death_animation')},
        'mesh_component_asset': path(mesh_component.get_editor_property('skeletal_mesh_asset')),
        'mesh_component_transform': transform_record(mesh_component.get_relative_transform()),
        'sword_mesh': path(sword.get_editor_property('static_mesh')),
        'sword_grip_transform': transform_record(cdo.get_editor_property('sword_grip_transform')),
        'sword_component_transform': transform_record(sword.get_relative_transform()),
        'grip_morph_name': str(cdo.get_editor_property('grip_morph_name')),
        'grip_morph_weight': cdo.get_editor_property('grip_morph_weight'),
        'blade_definition': path(cdo.get_editor_property('blade').get_editor_property('attack_definition')),
    }


native = unreal.load_class(None, '/Script/experiment.NLEnemyCharacter')
controller_class = unreal.load_class(None, '/Script/experiment.NLEncounterController')
wave_class = unreal.load_class(None, '/Script/experiment.NLWaveDefinition')
attack_class = unreal.load_class(None, '/Script/experiment.NLAttackDefinition')
talisman_class = unreal.load_class(None, '/Script/experiment.NLTalismanAttackComponent')
checkpoint_class = unreal.load_class(None, '/Script/experiment.NLCheckpointService')
sword_class = A.load_blueprint_class(SWORD_PREFAB)
if not all((native, controller_class, wave_class, attack_class, talisman_class, checkpoint_class, sword_class)):
    raise RuntimeError('Compile ENEMY02A and preserve the sword prefab before authoring the mixed scene.')
if not hasattr(unreal, 'NLWaveSpawnEntry') or not hasattr(unreal, 'NLWaveSpawnPoint'):
    raise RuntimeError('Compiled wave Python wrappers are required.')
if not hasattr(unreal.NLEnemyRole, 'TALISMAN_CASTER'):
    raise RuntimeError('The compiled TalismanCaster role wrapper is required.')
if not A.does_asset_exist(SOURCE_MAP):
    raise RuntimeError('The independent checkpoint source map is required.')
sword_cdo = unreal.get_default_object(sword_class)
preserved_sword = sword_snapshot(sword_cdo)
mesh, death, cast = asset(EXPECTED_MESH), asset(EXPECTED_DEATH), asset(CAST_ANIMATION)
if preserved_sword['refs']['enemy_skeletal_mesh'] != path(mesh):
    raise RuntimeError('The preserved sword prefab must retain the current Combat mesh.')
if preserved_sword['refs']['death_animation'] != path(death):
    raise RuntimeError('The preserved sword prefab must retain Grounded death.')
if abs(preserved_sword['grip_morph_weight']-1.0) > .001:
    raise RuntimeError('The preserved sword prefab must retain grip morph weight 1.')
if cast.get_editor_property('skeleton') != mesh.get_editor_property('skeleton'):
    raise RuntimeError('The new cast animation must use the current enemy skeleton.')

paper_material = material('M_TalismanPaper', (.82, .62, .09), 1.0)
cast_material = material('M_TalismanCast', (.16, .82, .30), 2.0)
definition_destination = COMBAT_ROOT + '/DA_EnemyTalisman'
definition = A.load_asset(definition_destination) if A.does_asset_exist(definition_destination) else None
if not definition:
    factory = unreal.DataAssetFactory()
    factory.set_editor_property('data_asset_class', attack_class)
    definition = TOOLS.create_asset('DA_EnemyTalisman', COMBAT_ROOT, attack_class, factory)
if not definition or definition.get_class() != attack_class:
    raise RuntimeError('Could not create the new talisman attack definition.')
attack_values = {
    'stable_id': unreal.Name('Attack.Enemy.TalismanDisciple'), 'damage': 10.0,
    'telegraph_seconds': 1.1, 'active_window_seconds': .15, 'cooldown_seconds': 2.0,
    'can_be_blocked': True, 'can_be_parried': False, 'can_be_reflected': True,
    'can_be_interrupted': True, 'hit_feedback_tag': unreal.Name('Combat.Hit.EnemyTalisman'),
}
for name, value in attack_values.items():
    definition.set_editor_property(name, value)
if not A.save_loaded_asset(definition, False):
    raise RuntimeError('Could not save the talisman attack definition.')

bp = A.load_asset(CASTER_PREFAB) if A.does_asset_exist(CASTER_PREFAB) else None
if not bp:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', native)
    bp = TOOLS.create_asset('BP_EnemyTalismanDisciple', CHARACTER_ROOT, unreal.Blueprint, factory)
if not bp or unreal.BlueprintEditorLibrary.get_blueprint_parent_class(bp) != native:
    raise RuntimeError('The reusable caster Blueprint must directly inherit native NLEnemyCharacter.')
if not unreal.BlueprintEditorLibrary.compile_blueprint(bp):
    raise RuntimeError('Could not compile the new caster Blueprint.')
caster_class = A.load_blueprint_class(CASTER_PREFAB)
if not caster_class:
    raise RuntimeError('The compiled caster Blueprint must expose its generated class.')
cdo = unreal.get_default_object(caster_class)
if not isinstance(cdo, unreal.NLEnemyCharacter):
    raise RuntimeError('The compiled caster class default must be a native-derived NLEnemyCharacter.')
actor_values = {
    'enemy_skeletal_mesh': mesh,
    'idle_animation': sword_cdo.get_editor_property('idle_animation'),
    'walk_animation': sword_cdo.get_editor_property('walk_animation'),
    'attack_animation': cast, 'cast_animation': cast,
    'hit_reaction_animation': sword_cdo.get_editor_property('hit_reaction_animation'),
    'death_animation': death, 'bShowSword': False,
    'enemy_attack_definition': definition,
    'sword_grip_transform': sword_cdo.get_editor_property('sword_grip_transform'),
    'grip_morph_name': sword_cdo.get_editor_property('grip_morph_name'),
    'grip_morph_weight': 0.0,
}
for name, value in actor_values.items():
    cdo.set_editor_property(name, value)
caster_mesh = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
caster_mesh.set_skeletal_mesh_asset(mesh)
caster_mesh.set_relative_transform(sword_cdo.get_component_by_class(unreal.SkeletalMeshComponent).get_relative_transform(), False, True)
cdo.get_editor_property('sword').set_visibility(False, True)
cdo.get_editor_property('sword').set_hidden_in_game(True, True)
cdo.get_editor_property('blade').set_editor_property('attack_definition', definition)
brain = cdo.get_enemy_brain()
brain_values = {
    'role': unreal.NLEnemyRole.TALISMAN_CASTER,
    'spawn_grace_seconds': .35, 'attack_range': 1100.0,
    'minimum_ranged_distance': 450.0, 'preferred_ranged_distance': 700.0,
    'telegraph_seconds': 1.1, 'attack_seconds': .15, 'recover_seconds': 2.0,
    'projectile_speed': 700.0, 'ranged_attack_definition': definition,
    'target_aim_offset': unreal.Vector(0.0, 0.0, 40.0),
}
for name, value in brain_values.items():
    brain.set_editor_property(name, value)
for name in ('reposition_radius', 'max_navigation_retries', 'reposition_acceptance_distance'):
    brain.set_editor_property(name, sword_cdo.get_enemy_brain().get_editor_property(name))
talisman = cdo.get_editor_property('talisman_attack')
if not talisman or talisman.get_class() != talisman_class:
    raise RuntimeError('The caster must own the native talisman attack component.')
for name, value in {'projectile_radius': 7.0, 'projectile_lifetime_seconds': 4.0,
                    'muzzle_socket_name': unreal.Name('hand_l'),
                    'talisman_material': paper_material, 'cast_glow_material': cast_material,
                    'projectile_material': cast_material}.items():
    talisman.set_editor_property(name, value)
for name in ('max_health', 'max_guard', 'damage_protection_seconds'):
    cdo.get_editor_property('vitals').set_editor_property(name, sword_cdo.get_editor_property('vitals').get_editor_property(name))
cdo.get_editor_property('combat_identity').set_editor_property('faction',
    sword_cdo.get_editor_property('combat_identity').get_editor_property('faction'))
movement = cdo.get_component_by_class(unreal.CharacterMovementComponent)
source_movement = sword_cdo.get_component_by_class(unreal.CharacterMovementComponent)
for name in ('max_walk_speed', 'rotation_rate', 'max_step_height', 'orient_rotation_to_movement',
             'use_rvo_avoidance', 'avoidance_consideration_radius'):
    movement.set_editor_property(name, source_movement.get_editor_property(name))
if not unreal.BlueprintEditorLibrary.compile_blueprint(bp) or not A.save_loaded_asset(bp, False):
    raise RuntimeError('Could not compile/save the configured caster prefab.')
caster_class = A.load_blueprint_class(CASTER_PREFAB)
cdo = unreal.get_default_object(caster_class)

for index, (_, location) in enumerate(POINTS):
    if not (-1100.0 < location[0] < 1000.0 and -1100.0 < location[1] < 1100.0):
        raise RuntimeError('Spawn point must stay inside the floor west of the X=1200 gate.')
    if any(math.dist(location[:2], earlier[:2]) < 90.0 for _, earlier in POINTS[:index]):
        raise RuntimeError('Spawn point capsule centres must be at least 90 cm apart.')
waves, wave_rows = [], []
for index, sword_count in ((1, 1), (2, 2)):
    destination = ENCOUNTER_ROOT + '/DA_WaveMixed' + str(index).zfill(2)
    wave = A.load_asset(destination) if A.does_asset_exist(destination) else None
    if not wave:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property('data_asset_class', wave_class)
        wave = TOOLS.create_asset(destination.rsplit('/', 1)[1], ENCOUNTER_ROOT, wave_class, factory)
    if not wave or wave.get_class() != wave_class:
        raise RuntimeError('Could not create a mixed wave definition: ' + destination)
    entries = []
    for entry_id, enemy_class, count, allowed_points in (
        ('SwordDisciple', sword_class, sword_count, SWORD_POINTS),
        ('TalismanDisciple', caster_class, 1, CASTER_POINTS),
    ):
        entry = unreal.NLWaveSpawnEntry()
        for name, value in {'entry_id': unreal.Name(entry_id), 'enemy_class': enemy_class,
                            'count': count, 'spawn_point_ids': [unreal.Name(point_id) for point_id, _ in allowed_points]}.items():
            entry.set_editor_property(name, value)
        entries.append(entry)
    for name, value in {'wave_id': unreal.Name('Wave.Mixed.' + str(index).zfill(2)),
                        'spawn_entries': entries, 'spawn_interval_seconds': .8,
                        'intermission_seconds': 3.0, 'max_alive': 3,
                        'max_spawn_retries': 3, 'retry_delay_seconds': .5}.items():
        wave.set_editor_property(name, value)
    if not A.save_loaded_asset(wave, False):
        raise RuntimeError('Could not save mixed wave: ' + destination)
    waves.append(wave)
    wave_rows.append({'asset': path(wave), 'wave_id': str(wave.get_editor_property('wave_id')),
                      'planned_count': sword_count + 1, 'max_alive': 3,
                      'entries': [{'entry_id': str(entry.get_editor_property('entry_id')),
                                   'enemy_class': path(entry.get_editor_property('enemy_class')),
                                   'count': entry.get_editor_property('count'),
                                   'spawn_point_ids': [str(point) for point in entry.get_editor_property('spawn_point_ids')]}
                                  for entry in entries]})

ok = LEVEL.load_level(MAP) if A.does_asset_exist(MAP) else LEVEL.new_level_from_template(MAP, SOURCE_MAP)
if not ok:
    raise RuntimeError('Could not create/load the independent mixed map.')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
settings = world.get_world_settings()
mode_class = settings.get_editor_property('default_game_mode')
mode = unreal.get_default_object(mode_class) if mode_class else None
if not mode or mode.get_editor_property('default_pawn_class') != unreal.load_class(None, '/Script/experiment.NLDesktopPlayerCharacter'):
    raise RuntimeError('The mixed map must retain its Desktop combat player.')
if mode.get_editor_property('hud_class') != unreal.load_class(None, '/Script/experiment.NLCombatLabHUD'):
    raise RuntimeError('The mixed map must retain the combat HUD.')
training_class = unreal.load_class(None, '/Script/experiment.NLTrainingEnemy')
emitter_class = unreal.load_class(None, '/Script/experiment.NLTrainingProjectileEmitter')
removed, player_starts = [], []
for actor in ACTORS.get_all_level_actors():
    tags = [str(tag) for tag in actor.get_editor_property('tags')]
    inherited_combat = (isinstance(actor, unreal.NLEnemyCharacter)
                        or actor.get_class() in (controller_class, training_class, emitter_class))
    inherited_marker = 'NL_WaveLabMarker' in tags or MARKER_TAG in tags
    # The HUD owns instructions. The copied map's world text is removed.
    if inherited_combat or inherited_marker or isinstance(actor, unreal.TextRenderActor):
        removed.append({'label': actor.get_actor_label(), 'class': path(actor.get_class())})
        if not ACTORS.destroy_actor(actor):
            raise RuntimeError('Could not remove inherited combat/presentation actor.')
    elif isinstance(actor, unreal.PlayerStart):
        actor.set_actor_location(unreal.Vector(*PLAYER_POSITION), False, True)
        actor.set_actor_rotation(unreal.Rotator(), True)
        player_starts.append({'label': actor.get_actor_label(), 'location_cm': vector(actor.get_actor_location())})
if not player_starts:
    raise RuntimeError('The mixed map must retain a PlayerStart.')

spawn_points = []
for point_id, location in POINTS:
    yaw = math.degrees(math.atan2(PLAYER_POSITION[1]-location[1], PLAYER_POSITION[0]-location[0]))
    point = unreal.NLWaveSpawnPoint()
    point.set_editor_property('spawn_point_id', unreal.Name(point_id))
    point.set_editor_property('spawn_transform', unreal.Transform(
        location=unreal.Vector(*location), rotation=unreal.Rotator(yaw=yaw), scale=unreal.Vector(1.0, 1.0, 1.0)))
    spawn_points.append(point)
controller = ACTORS.spawn_actor_from_class(controller_class, unreal.Vector(300.0, 0.0, 0.0))
if not controller:
    raise RuntimeError('Could not author the new mixed encounter controller.')
controller.set_actor_label('Encounter_MixedDisciples_ENEMY02A')
for name, value in {'waves': waves, 'spawn_points': spawn_points, 'seed': 20261013,
                    'corpse_hold_seconds': 2.0, 'max_spawns_per_tick': 1,
                    'level_id': unreal.Name('Level.CombatLab.Mixed'),
                    'encounter_id': unreal.Name('Encounter.MixedDisciples'),
                    'content_revision': unreal.Name('MixedDisciples.ENEMY02A.1'),
                    'bEnableCheckpoints': True}.items():
    controller.set_editor_property(name, value)

markers = []
for point_id, location in POINTS:
    is_caster = point_id.startswith('MixedCaster')
    marker = ACTORS.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(location[0], location[1], .65))
    if not marker:
        raise RuntimeError('Could not author a mixed spawn marker.')
    marker.set_actor_label(point_id + '_BirthArea')
    marker.set_editor_property('tags', [MARKER_TAG, 'NL_MixedSpawnArea', point_id])
    marker.set_actor_scale3d(unreal.Vector(.7, .7, .01))
    marker.set_actor_enable_collision(False)
    component = marker.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(asset('/Engine/BasicShapes/Cylinder'))
    component.set_material(0, cast_material if is_caster else asset(COMBAT_ROOT + '/Materials/M_BladeQi'))
    component.set_collision_profile_name('NoCollision')
    component.set_editor_property('bCanEverAffectNavigation', False)
    component.set_editor_property('cast_shadow', False)
    markers.append({'point_id': point_id, 'meaning': '符箓弟子出生区' if is_caster else '剑士出生区',
                    'color': 'green' if is_caster else 'blue', 'actor': path(marker),
                    'location_cm': vector(marker.get_actor_location()), 'collision_profile': 'NoCollision',
                    'affects_navigation': False})

nav_bounds = []
for actor in ACTORS.get_all_level_actors():
    if isinstance(actor, unreal.NavMeshBoundsVolume):
        origin, extent = actor.get_actor_bounds(False)
        nav_bounds.append({'actor': path(actor), 'origin_cm': vector(origin), 'extent_cm': vector(extent)})
if not nav_bounds:
    raise RuntimeError('The mixed map requires preserved navigation bounds.')
for _, location in POINTS:
    if not any(all(abs(location[axis]-row['origin_cm'][axis]) <= row['extent_cm'][axis]
                   for axis in range(3)) for row in nav_bounds):
        raise RuntimeError('Every mixed spawn point must lie inside the preserved navigation bounds.')
if sword_snapshot(unreal.get_default_object(sword_class)) != preserved_sword:
    raise RuntimeError('The preserved sword prefab changed during independent caster authoring.')
if not LEVEL.save_current_level():
    raise RuntimeError('Could not save the independent mixed map.')

brain = cdo.get_enemy_brain()
report = {
    'date': '2026-10-13', 'task': 'ENEMY02A', 'map': MAP, 'source_map_preserved': SOURCE_MAP,
    'game_mode': path(mode_class), 'player_starts': player_starts,
    'controller': {'actor': path(controller), 'level_id': str(controller.get_editor_property('level_id')),
                   'encounter_id': str(controller.get_editor_property('encounter_id')),
                   'content_revision': str(controller.get_editor_property('content_revision')),
                   'checkpoint_enabled': controller.get_editor_property('bEnableCheckpoints'),
                   'seed': controller.get_editor_property('seed'),
                   'state_before_start': str(controller.get_state()),
                   'spawned_count_before_start': controller.get_spawned_count(),
                   'alive_count_before_start': controller.get_alive_count()},
    'waves': wave_rows, 'authored_wave_counts': [2, 3], 'authored_total_planned_count': 5,
    'maximum_alive': 3, 'auto_start': False,
    'spawn_points': [{'spawn_point_id': str(point.get_editor_property('spawn_point_id')),
                      'capsule_world_transform': transform_record(point.get_editor_property('spawn_transform'))}
                     for point in spawn_points],
    'spawn_transform_semantics': 'World capsule centre; exact authored Z=90.4 cm, no extra height offset.',
    'markers': markers, 'removed_inherited_actors': removed, 'navigation_bounds_preserved': nav_bounds,
    'initial_authored_enemy_count': sum(isinstance(actor, unreal.NLEnemyCharacter) for actor in ACTORS.get_all_level_actors()),
    'sword_prefab_preserved': preserved_sword,
    'caster_prefab': {'blueprint': path(bp), 'generated_class': path(caster_class), 'parent_class': path(native),
                      'role': str(brain.get_editor_property('role')), 'mesh': path(cdo.get_editor_property('enemy_skeletal_mesh')),
                      'death_animation': path(cdo.get_editor_property('death_animation')),
                      'cast_animation': path(cdo.get_editor_property('cast_animation')),
                      'show_sword': cdo.get_editor_property('bShowSword'),
                      'grip_morph_weight': cdo.get_editor_property('grip_morph_weight'),
                      'definition': path(cdo.get_editor_property('enemy_attack_definition')),
                      'brain': {name: brain.get_editor_property(name) for name in (
                          'attack_range', 'minimum_ranged_distance', 'preferred_ranged_distance',
                          'telegraph_seconds', 'attack_seconds', 'recover_seconds', 'projectile_speed')},
                      'target_aim_offset_cm': vector(brain.get_editor_property('target_aim_offset')),
                      'muzzle_socket': str(cdo.get_editor_property('talisman_attack').get_editor_property('muzzle_socket_name'))},
    'attack_definition': {name: str(definition.get_editor_property(name)) if name in ('stable_id', 'hit_feedback_tag')
                          else definition.get_editor_property(name) for name in attack_values},
    'materials': [path(paper_material), path(cast_material)],
    'scope': 'Only independent map, caster prefab, two wave definitions, attack definition, two materials and reports. No gameplay inputs, starts, retries, damage, disk checkpoint writes or automated tests.'
}
(PROJECT / 'Docs/AI/MixedLabSaved-2026-10-13.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('MIXED_LAB_SAVED ' + MAP)
