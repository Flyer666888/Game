"""Save a reusable sword disciple Blueprint without replacing level actors."""
import json
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir())
ROOT = '/Game/ReversedScale/Characters/WuxiaMale'
DEST = ROOT + '/BP_EnemySwordDisciple'
SOURCE_MAP = '/Game/ReversedScale/Maps/L_CombatLabSwordDuel'
A = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
reports = sorted((PROJECT / 'Docs/AI').glob('NaturalGripSaved*.json'))
if not reports:
    raise RuntimeError('The saved natural death and grip report is required.')
saved = json.loads(reports[-1].read_text(encoding='utf-8'))
native = unreal.load_class(None, '/Script/experiment.NLEnemyCharacter')
if not native or not LEVEL.load_level(SOURCE_MAP):
    raise RuntimeError('Cannot load the native enemy or source level.')
sources = sorted((actor for actor in ACTORS.get_all_level_actors()
                  if actor.get_class() == native), key=lambda actor: actor.get_actor_label())
if not sources:
    raise RuntimeError('The source level has no native sword disciple.')
source = sources[0]
bp = A.load_asset(DEST) if A.does_asset_exist(DEST) else None
if not bp:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', native)
    bp = TOOLS.create_asset('BP_EnemySwordDisciple', ROOT, unreal.Blueprint, factory)
if not bp or not unreal.BlueprintEditorLibrary.compile_blueprint(bp):
    raise RuntimeError('Cannot create or compile the sword disciple Blueprint.')
cdo = unreal.get_default_object(A.load_blueprint_class(DEST))

def asset(path):
    value = A.load_asset(path)
    if not value:
        raise RuntimeError('Missing prefab asset: ' + path)
    return value

mesh = asset(saved['mesh'])
death = asset(saved['death_asset'])
grip_transform = unreal.Transform(location=unreal.Vector(*saved['grip_location_cm']),
                                 rotation=unreal.Quat(*saved['grip_quaternion_xyzw']).rotator(),
                                 scale=unreal.Vector(1, 1, 1))
actor_values = {
    'enemy_skeletal_mesh': mesh,
    'sword_grip_transform': grip_transform,
    'grip_morph_name': saved['grip_morph_name'],
    'grip_morph_weight': float(saved['grip_weight']),
    'idle_animation': asset(ROOT + '/Animations/Wuxia_Idle_Planted'),
    'walk_animation': asset(ROOT + '/Animations/Wuxia_Walk_Sword'),
    'attack_animation': asset(ROOT + '/Animations/Wuxia_Attack_Sword'),
    'hit_reaction_animation': asset(ROOT + '/Animations/Wuxia_Hit_Sword'),
    'death_animation': death,
}
for name, value in actor_values.items():
    cdo.set_editor_property(name, value)
mesh_component = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
mesh_component.set_skeletal_mesh_asset(mesh)
mesh_component.set_relative_transform(source.get_component_by_class(unreal.SkeletalMeshComponent).get_relative_transform(), False, True)
sword = cdo.get_editor_property('sword')
sword.set_static_mesh(asset('/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player'))
sword.set_relative_transform(grip_transform, False, True)

# Copy scalar/struct/asset values into the Blueprint's own native subobjects.
# Never assign source actor component pointers to the class default object.
brain_names = ('role', 'attack_range', 'spawn_grace_seconds', 'reposition_radius',
               'max_navigation_retries', 'reposition_acceptance_distance')
source_brain = source.get_enemy_brain()
brain = cdo.get_enemy_brain()
for name in brain_names:
    brain.set_editor_property(name, source_brain.get_editor_property(name))
for name, value in {'telegraph_seconds': .8, 'attack_seconds': .23,
                    'recover_seconds': 1.3033333}.items():
    brain.set_editor_property(name, value)
for name in ('max_health', 'max_guard', 'damage_protection_seconds'):
    cdo.get_editor_property('vitals').set_editor_property(
        name, source.get_editor_property('vitals').get_editor_property(name))
cdo.get_editor_property('combat_identity').set_editor_property(
    'faction', source.get_editor_property('combat_identity').get_editor_property('faction'))
cdo.get_editor_property('blade').set_editor_property(
    'attack_definition', asset('/Game/ReversedScale/Combat/DA_EnemySword'))
source_movement = source.get_component_by_class(unreal.CharacterMovementComponent)
movement = cdo.get_component_by_class(unreal.CharacterMovementComponent)
for name in ('max_walk_speed', 'rotation_rate', 'max_step_height',
             'orient_rotation_to_movement', 'use_rvo_avoidance', 'avoidance_consideration_radius'):
    movement.set_editor_property(name, source_movement.get_editor_property(name))

if not unreal.BlueprintEditorLibrary.compile_blueprint(bp):
    raise RuntimeError('The configured sword disciple Blueprint did not compile.')
if not A.save_loaded_asset(bp, False):
    raise RuntimeError('Could not save the sword disciple Blueprint.')
cdo = unreal.get_default_object(A.load_blueprint_class(DEST))
brain = cdo.get_enemy_brain()
refs = {name: cdo.get_editor_property(name).get_path_name()
        for name in ('enemy_skeletal_mesh', 'idle_animation', 'walk_animation',
                     'attack_animation', 'hit_reaction_animation', 'death_animation')}
transform = cdo.get_editor_property('sword_grip_transform')
report = {
    'blueprint': bp.get_path_name(), 'generated_class': cdo.get_class().get_path_name(),
    'parent_class': native.get_path_name(), 'source_map': SOURCE_MAP,
    'source_actor': source.get_actor_label(), 'source_report': str(reports[-1]),
    'cdo_refs': refs,
    'mesh_component_asset': cdo.get_component_by_class(unreal.SkeletalMeshComponent).get_editor_property('skeletal_mesh_asset').get_path_name(),
    'grip_morph_name': str(cdo.get_editor_property('grip_morph_name')),
    'grip_morph_weight': cdo.get_editor_property('grip_morph_weight'),
    'grip_location_cm': [transform.translation.x, transform.translation.y, transform.translation.z],
    'grip_quaternion_xyzw': [transform.rotation.x, transform.rotation.y, transform.rotation.z, transform.rotation.w],
    'brain': {name: brain.get_editor_property(name) for name in
              ('telegraph_seconds', 'attack_seconds', 'recover_seconds', 'spawn_grace_seconds', 'attack_range')},
    'max_walk_speed': cdo.get_component_by_class(unreal.CharacterMovementComponent).get_editor_property('max_walk_speed'),
    'attack_definition': cdo.get_editor_property('blade').get_editor_property('attack_definition').get_path_name(),
    'health': cdo.get_editor_property('vitals').get_editor_property('max_health'),
    'saved': True, 'level_actors_replaced': False,
    'scope': 'Reusable prefab authoring; no gameplay input or tests run.',
}
(PROJECT / 'Docs/AI/SwordDisciplePrefabSaved.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('SWORD_DISCIPLE_PREFAB_SAVED ' + DEST)
