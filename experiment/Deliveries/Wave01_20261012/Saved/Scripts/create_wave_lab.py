"""Author WAVE-01 in a separate map; never start or simulate the encounter."""
import json
import math
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir())
A = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SOURCE_MAP = '/Game/ReversedScale/Maps/L_CombatLabSwordDuel'
MAP = '/Game/ReversedScale/Maps/L_CombatLabWaves'
ENCOUNTER_ROOT = '/Game/ReversedScale/Encounters'
PREFAB = '/Game/ReversedScale/Characters/WuxiaMale/BP_EnemySwordDisciple'
EXPECTED_MESH = '/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Combat'
EXPECTED_DEATH = '/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Grounded'
EXPECTED_WEAPON = '/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player'
MARKER_TAG = 'NL_WaveLabMarker'
PLAYER_POSITION = (30.0, -170.0, 90.4)
# Each transform is the world capsule centre, including the full authored Z.
# These points occupy the flat floor west of the gate/pillars at X=1200.
POINT_LOCATIONS = (
    ('SwordSpawn01', (430.0, -280.0, 90.4)),
    ('SwordSpawn02', (620.0, 40.0, 90.4)),
    ('SwordSpawn03', (470.0, 190.0, 90.4)),
    ('SwordSpawn04', (760.0, -240.0, 90.4)),
    ('SwordSpawn05', (820.0, 190.0, 90.4)),
)


def path(obj):
    return obj.get_path_name() if obj else None


def vector(value):
    return [value.x, value.y, value.z]


def transform_record(value):
    return {'location_cm': vector(value.translation),
            'rotation_quaternion_xyzw': [value.rotation.x, value.rotation.y,
                                         value.rotation.z, value.rotation.w],
            'scale': vector(value.scale3d)}


def asset(path_name):
    obj = A.load_asset(path_name)
    if not obj:
        raise RuntimeError('Required preserved asset is missing: ' + path_name)
    return obj


wave_class = unreal.load_class(None, '/Script/experiment.NLWaveDefinition')
controller_class = unreal.load_class(None, '/Script/experiment.NLEncounterController')
enemy_class = unreal.load_class(None, '/Script/experiment.NLEnemyCharacter')
training_class = unreal.load_class(None, '/Script/experiment.NLTrainingEnemy')
emitter_class = unreal.load_class(None, '/Script/experiment.NLTrainingProjectileEmitter')
prefab_class = A.load_blueprint_class(PREFAB)
if not all((wave_class, controller_class, enemy_class, training_class, emitter_class, prefab_class)):
    raise RuntimeError('Compile the encounter classes and preserve the sword prefab before authoring WAVE-01.')
if not hasattr(unreal, 'NLWaveSpawnEntry') or not hasattr(unreal, 'NLWaveSpawnPoint'):
    raise RuntimeError('The compiled wave entry and spawn point Python wrappers are unavailable.')
if not A.does_asset_exist(SOURCE_MAP):
    raise RuntimeError('The preserved SwordDuel map is required.')

# Inspect current class defaults. Historical prefab JSON predates Grounded death.
# The author does not write to this Blueprint, its components, mesh or animation.
selected_report_file = PROJECT / 'Docs/AI/SelectedDeathSaved-2026-10-12.json'
prefab_report_file = PROJECT / 'Docs/AI/SwordDisciplePrefabSaved.json'
selected_report = json.loads(selected_report_file.read_text(encoding='utf-8'))
prefab_report = json.loads(prefab_report_file.read_text(encoding='utf-8'))
cdo = unreal.get_default_object(prefab_class)
mesh_component = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
sword = cdo.get_editor_property('sword')
mesh = cdo.get_editor_property('enemy_skeletal_mesh')
death = cdo.get_editor_property('death_animation')
grip = cdo.get_editor_property('sword_grip_transform')
refs = {name: path(cdo.get_editor_property(name)) for name in (
    'enemy_skeletal_mesh', 'idle_animation', 'walk_animation', 'attack_animation',
    'hit_reaction_animation', 'death_animation')}
if mesh != asset(EXPECTED_MESH) or mesh_component.get_editor_property('skeletal_mesh_asset') != mesh:
    raise RuntimeError('The sword prefab must retain the current Combat mesh on its native mesh component.')
if death != asset(EXPECTED_DEATH) or path(death) != selected_report['asset']:
    raise RuntimeError('The sword prefab must use the current saved Wuxia_Death_Grounded animation.')
if death.get_editor_property('skeleton') != mesh.get_editor_property('skeleton'):
    raise RuntimeError('The preserved mesh and selected death skeletons differ.')
if sword.get_editor_property('static_mesh') != asset(EXPECTED_WEAPON):
    raise RuntimeError('The sword prefab must retain its current Yueyao weapon.')
if str(cdo.get_editor_property('grip_morph_name')) != prefab_report['grip_morph_name']:
    raise RuntimeError('The current prefab grip morph differs from the preserved prefab.')
if abs(cdo.get_editor_property('grip_morph_weight') - 1.0) > 0.001:
    raise RuntimeError('The current prefab must preserve its full grip morph weight.')
if any(abs(actual - expected) > 0.01 for actual, expected in
       zip(vector(grip.translation), prefab_report['grip_location_cm'])):
    raise RuntimeError('The current prefab grip location differs from the preserved prefab.')
brain = cdo.get_enemy_brain()
prefab_snapshot = {
    'blueprint': path(asset(PREFAB)), 'generated_class': path(prefab_class),
    'cdo_refs': refs, 'mesh_component_asset': path(mesh_component.get_editor_property('skeletal_mesh_asset')),
    'mesh_component_relative_transform': transform_record(mesh_component.get_relative_transform()),
    'sword_mesh': path(sword.get_editor_property('static_mesh')),
    'sword_grip_transform': transform_record(grip),
    'sword_component_relative_transform': transform_record(sword.get_relative_transform()),
    'grip_morph_name': str(cdo.get_editor_property('grip_morph_name')),
    'grip_morph_weight': cdo.get_editor_property('grip_morph_weight'),
    'death_duration_seconds': death.get_play_length(),
    'brain': {name: brain.get_editor_property(name) for name in (
        'telegraph_seconds', 'attack_seconds', 'recover_seconds', 'spawn_grace_seconds', 'attack_range')},
    'max_walk_speed_cm_s': cdo.get_component_by_class(unreal.CharacterMovementComponent).get_editor_property('max_walk_speed'),
    'max_health': cdo.get_editor_property('vitals').get_editor_property('max_health'),
    'attack_definition': path(cdo.get_editor_property('blade').get_editor_property('attack_definition')),
    'selected_death_report': str(selected_report_file),
    'historical_prefab_report': str(prefab_report_file),
    'historical_prefab_death': prefab_report['cdo_refs']['death_animation'],
    'current_death_matches_selected_report': True,
    'read_only_cdo_inspection': True,
}

for index, (_, location) in enumerate(POINT_LOCATIONS):
    if not (-1100.0 < location[0] < 1000.0 and -1100.0 < location[1] < 1100.0):
        raise RuntimeError('Authored point must stay inside the flat floor, clear of the gate.')
    for _, earlier_location in POINT_LOCATIONS[:index]:
        if math.dist(location[:2], earlier_location[:2]) < 90.0:
            raise RuntimeError('Authored capsule spawn points must be at least 90 cm apart.')

point_ids = [unreal.Name(name) for name, _ in POINT_LOCATIONS]
waves = []
wave_rows = []
for index, count in ((1, 2), (2, 3)):
    destination = ENCOUNTER_ROOT + '/DA_WaveSword' + str(index).zfill(2)
    definition = A.load_asset(destination) if A.does_asset_exist(destination) else None
    if not definition:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property('data_asset_class', wave_class)
        definition = TOOLS.create_asset(destination.rsplit('/', 1)[1], ENCOUNTER_ROOT, wave_class, factory)
    if not definition or definition.get_class() != wave_class:
        raise RuntimeError('Could not create the new wave definition: ' + destination)
    entry = unreal.NLWaveSpawnEntry()
    for name, value in {'entry_id': unreal.Name('SwordDisciple'), 'enemy_class': prefab_class,
                        'count': count, 'spawn_point_ids': point_ids}.items():
        entry.set_editor_property(name, value)
    for name, value in {'wave_id': unreal.Name('Wave.Sword.' + str(index).zfill(2)),
                        'spawn_entries': [entry], 'spawn_interval_seconds': 0.8,
                        'intermission_seconds': 3.0, 'max_alive': 3,
                        'max_spawn_retries': 3, 'retry_delay_seconds': 0.5}.items():
        definition.set_editor_property(name, value)
    if not A.save_loaded_asset(definition, False):
        raise RuntimeError('Could not save wave definition: ' + destination)
    waves.append(definition)
    entries = definition.get_editor_property('spawn_entries')
    wave_rows.append({
        'asset': path(definition), 'wave_id': str(definition.get_editor_property('wave_id')),
        'planned_count': sum(e.get_editor_property('count') for e in entries),
        'spawn_entries': [{'entry_id': str(e.get_editor_property('entry_id')),
                           'enemy_class': path(e.get_editor_property('enemy_class')),
                           'count': e.get_editor_property('count'),
                           'spawn_point_ids': [str(n) for n in e.get_editor_property('spawn_point_ids')]}
                          for e in entries],
        **{name: definition.get_editor_property(name) for name in (
            'spawn_interval_seconds', 'intermission_seconds', 'max_alive',
            'max_spawn_retries', 'retry_delay_seconds')},
    })

ok = LEVEL.load_level(MAP) if A.does_asset_exist(MAP) else LEVEL.new_level_from_template(MAP, SOURCE_MAP)
if not ok:
    raise RuntimeError('Could not create/load the separate WAVE-01 map.')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
settings = world.get_world_settings()
mode_class = settings.get_editor_property('default_game_mode')
if not mode_class:
    raise RuntimeError('The copied map must retain its Desktop GameMode.')
mode_cdo = unreal.get_default_object(mode_class)
if mode_cdo.get_editor_property('default_pawn_class') != unreal.load_class(None, '/Script/experiment.NLDesktopPlayerCharacter'):
    raise RuntimeError('The copied map must retain the Desktop combat player.')
if mode_cdo.get_editor_property('hud_class') != unreal.load_class(None, '/Script/experiment.NLCombatLabHUD'):
    raise RuntimeError('The copied map must retain the combat HUD.')
removed = []
player_starts = []
for actor in ACTORS.get_all_level_actors():
    tags = [str(tag) for tag in actor.get_editor_property('tags')]
    if actor.get_class() in (enemy_class, prefab_class, training_class, emitter_class, controller_class) or MARKER_TAG in tags:
        removed.append({'label': actor.get_actor_label(), 'class': path(actor.get_class())})
        if not ACTORS.destroy_actor(actor):
            raise RuntimeError('Could not clear inherited combat actor: ' + actor.get_actor_label())
    elif isinstance(actor, unreal.PlayerStart):
        actor.set_actor_location(unreal.Vector(*PLAYER_POSITION), False, True)
        actor.set_actor_rotation(unreal.Rotator(), True)
        player_starts.append({'label': actor.get_actor_label(), 'location_cm': vector(actor.get_actor_location()),
                              'rotation': str(actor.get_actor_rotation())})
if not player_starts:
    raise RuntimeError('The copied map must retain its PlayerStart.')

spawn_points = []
for name, location in POINT_LOCATIONS:
    yaw = math.degrees(math.atan2(PLAYER_POSITION[1] - location[1], PLAYER_POSITION[0] - location[0]))
    half_angle = math.radians(yaw) * 0.5
    rotation = unreal.Quat(0.0, 0.0, math.sin(half_angle), math.cos(half_angle)).rotator()
    point = unreal.NLWaveSpawnPoint()
    point.set_editor_property('spawn_point_id', unreal.Name(name))
    point.set_editor_property('spawn_transform', unreal.Transform(
        location=unreal.Vector(*location), rotation=rotation, scale=unreal.Vector(1.0, 1.0, 1.0)))
    spawn_points.append(point)
controller = ACTORS.spawn_actor_from_class(controller_class, unreal.Vector(300.0, 0.0, 0.0))
if not controller:
    raise RuntimeError('Could not author the encounter controller.')
controller.set_actor_label('Encounter_WAVE_01')
for name, value in {'waves': waves, 'spawn_points': spawn_points, 'seed': 20261012,
                    'corpse_hold_seconds': 2.0, 'max_spawns_per_tick': 1}.items():
    controller.set_editor_property(name, value)

# Map-owned visual markers use existing assets and never obstruct capsules/nav.
markers = []
marker_mesh = asset('/Engine/BasicShapes/Cylinder')
marker_material = asset('/Game/ReversedScale/Combat/Materials/M_BladeQi')
for index, (point_id, location) in enumerate(POINT_LOCATIONS, 1):
    marker = ACTORS.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(location[0], location[1], 0.65))
    if not marker:
        raise RuntimeError('Could not author the spawn-area marker.')
    marker.set_actor_label('Wave01_SpawnArea_' + str(index).zfill(2))
    marker.set_editor_property('tags', [MARKER_TAG, 'NL_WaveSpawnArea', point_id])
    marker.set_actor_scale3d(unreal.Vector(0.7, 0.7, 0.01))
    marker.set_actor_enable_collision(False)
    component = marker.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(marker_mesh)
    component.set_material(0, marker_material)
    component.set_collision_profile_name('NoCollision')
    component.set_editor_property('bCanEverAffectNavigation', False)
    component.set_editor_property('cast_shadow', False)
    markers.append({'label': marker.get_actor_label(), 'point_id': point_id,
                    'meaning': '剑士出生区', 'actor': path(marker),
                    'location_cm': vector(marker.get_actor_location()),
                    'collision_profile': str(component.get_collision_profile_name()),
                    'affects_navigation': component.get_editor_property('bCanEverAffectNavigation')})
info = ACTORS.spawn_actor_from_class(unreal.TextRenderActor, unreal.Vector(940.0, 0.0, 285.0), unreal.Rotator(yaw=180.0))
if not info:
    raise RuntimeError('Could not author the wave information marker.')
info.set_actor_label('Wave01_Info')
info.set_editor_property('tags', [MARKER_TAG])
info.set_actor_enable_collision(False)
text_component = info.get_component_by_class(unreal.TextRenderComponent)
text_component.set_text('WAVE-01 | SWORD DISCIPLES\nG Start / Cancel | R Retry | P Pause\nWave 1: 2   |   Wave 2: 3')
text_component.set_world_size(23.0)
text_component.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
text_component.set_text_render_color(unreal.Color(155, 235, 205, 255))
text_component.set_collision_profile_name('NoCollision')
text_component.set_editor_property('bCanEverAffectNavigation', False)
markers.append({'label': info.get_actor_label(), 'actor': path(info),
                'text': str(text_component.get_editor_property('text')),
                'location_cm': vector(info.get_actor_location()), 'collision_profile': 'NoCollision'})

level_actors = ACTORS.get_all_level_actors()
nav_bounds = []
nav_data = []
environment = []
for actor in level_actors:
    if isinstance(actor, unreal.NavMeshBoundsVolume):
        origin, extent = actor.get_actor_bounds(False)
        nav_bounds.append({'label': actor.get_actor_label(), 'actor': path(actor),
                           'origin_cm': vector(origin), 'extent_cm': vector(extent)})
    elif isinstance(actor, unreal.RecastNavMesh):
        nav_data.append({'actor': path(actor), 'agent_radius_cm': actor.get_editor_property('AgentRadius'),
                         'agent_height_cm': actor.get_editor_property('AgentHeight')})
    elif actor.get_actor_label() in ('CombatFloor', 'Shanmen_Gate', 'GatePillar_Left', 'GatePillar_Right',
                                     'CombatLab_Sun', 'CombatLab_Sky', 'PreviewSky'):
        environment.append({'label': actor.get_actor_label(), 'actor': path(actor),
                            'class': path(actor.get_class()), 'location_cm': vector(actor.get_actor_location())})
if not nav_bounds:
    raise RuntimeError('The copied SwordDuel navigation bounds must remain in WAVE-01.')
if not LEVEL.save_current_level():
    raise RuntimeError('Could not save the new WAVE-01 map.')

controller_scalars = {name: controller.get_editor_property(name) for name in (
    'seed', 'corpse_hold_seconds', 'max_spawns_per_tick')}
point_rows = [{'spawn_point_id': str(p.get_editor_property('spawn_point_id')),
               'capsule_world_transform': transform_record(p.get_editor_property('spawn_transform'))}
              for p in controller.get_editor_property('spawn_points')]
report = {
    'date': '2026-10-12', 'slice': 'WAVE-01', 'map': MAP, 'world': path(world),
    'source_map_preserved': SOURCE_MAP,
    'game_mode': path(mode_class), 'player_class': path(mode_cdo.get_editor_property('default_pawn_class')),
    'hud_class': path(mode_cdo.get_editor_property('hud_class')), 'player_starts': player_starts,
    'initial_camera_target_z_cm': 146.81583,
    'controller': {'actor': path(controller), 'class': path(controller_class),
                   'label': controller.get_actor_label(), **controller_scalars,
                   'waves': [path(w) for w in controller.get_editor_property('waves')],
                   'state_before_start': str(controller.get_state()),
                   'runtime_planned_count_before_start': controller.get_planned_count(),
                   'spawned_count_before_start': controller.get_spawned_count(),
                   'alive_count_before_start': controller.get_alive_count()},
    'waves': wave_rows, 'authored_planned_counts': [row['planned_count'] for row in wave_rows],
    'authored_total_planned_count': sum(row['planned_count'] for row in wave_rows),
    'spawn_points': point_rows, 'spawn_transform_semantics': 'World capsule origin; no additional height offset.',
    'markers': markers, 'removed_inherited_combat_actors': removed,
    'navigation_bounds_preserved': nav_bounds, 'navigation_data_preserved': nav_data,
    'navigation_config': path(settings.get_editor_property('navigation_system_config')),
    'environment_preserved': environment, 'enemy_prefab': prefab_snapshot,
    'initial_enemy_count': sum(actor.get_class() in (enemy_class, prefab_class, training_class) for actor in level_actors),
    'auto_start': False, 'controls': 'G start/cancel; R reset for retry; P/Esc pause; WASD move; mouse look; LMB slash; RMB mirror; E blade qi.',
    'scope': 'Saved map and wave configuration with read-only prefab inspection. Encounter was never started. WAVE gameplay acceptance remains pending user play.',
}
output = PROJECT / 'Docs/AI/WaveLabSaved-2026-10-12.json'
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('WAVE_LAB_SAVED ' + MAP)
