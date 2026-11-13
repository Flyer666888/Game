"""Save a separate animation authoring stage; do not invoke gameplay combat."""
import json
import math
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir())
A = unreal.EditorAssetLibrary
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SOURCE_MAP = '/Game/ReversedScale/Maps/L_CombatLabSwordDuel'
MAP = '/Game/ReversedScale/Maps/L_DeathAuthorPreview'
CHARACTER = '/Game/ReversedScale/Characters/WuxiaMale'
ANIMATION = CHARACTER + '/Animations/Wuxia_Death_Grounded'
MESH = CHARACTER + '/SK_WuxiaMale_Combat'
WEAPON = '/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player'

grip_reports = sorted((PROJECT / 'Docs/AI').glob('NaturalGripSaved*.json'))
if not grip_reports:
    raise RuntimeError('The saved natural grip placement is needed to author the prop attachment.')
grip = json.loads(grip_reports[-1].read_text(encoding='utf-8'))
grip_author = json.loads((PROJECT / 'ArtSource/WuxiaMale/GripRefinement/GripAuthoringSummary.json').read_text(encoding='utf-8'))
grip_scale = grip.get('grip_scale', grip_author['sword_relative_scale'])
animation = A.load_asset(ANIMATION)
skin = A.load_asset(MESH)
weapon_asset = A.load_asset(WEAPON)
if not all((animation, skin, weapon_asset)):
    raise RuntimeError('The selected Grounded animation, Combat skin and existing sword must be saved first.')

enemy_classes = [unreal.load_class(None, '/Script/experiment.' + name)
                 for name in ('NLEnemyCharacter', 'NLTrainingEnemy', 'NLTrainingProjectileEmitter')]
if not LEVEL.load_level(SOURCE_MAP):
    raise RuntimeError('Cannot read the source sword duel scene.')
sources = sorted((actor for actor in ACTORS.get_all_level_actors()
                  if actor.get_class() == enemy_classes[0]), key=lambda actor: actor.get_actor_label())
if not sources:
    raise RuntimeError('Source scene has no sword disciple from which to copy the visual world transform.')
source = sources[0]
source_component = source.get_component_by_class(unreal.SkeletalMeshComponent)
source_position = source_component.get_world_location()
source_rotation = source_component.get_world_rotation()
source_scale = source_component.get_world_scale()
forward = source.get_actor_forward_vector()
right = source.get_actor_right_vector()
base = unreal.Vector(source_position.x, source_position.y, 0.0)

# Every mutation below applies only to the new authoring map.
if A.does_asset_exist(MAP):
    if not LEVEL.load_level(MAP):
        raise RuntimeError('Cannot load the existing independent authoring scene.')
else:
    if not LEVEL.new_level_from_template(MAP, SOURCE_MAP):
        raise RuntimeError('Cannot copy the sword arena into a separate authoring scene.')
for actor in ACTORS.get_all_level_actors():
    if (actor.get_class() in enemy_classes or actor.actor_has_tag('NL_DeathAuthorPreview')
        or actor.actor_has_tag('NL_DeathAuthorWeapon') or actor.actor_has_tag('NL_DeathAuthorCamera')):
        ACTORS.destroy_actor(actor)

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
world.get_world_settings().set_editor_property('default_game_mode', unreal.GameModeBase)
visual = ACTORS.spawn_actor_from_class(unreal.SkeletalMeshActor, base, source_rotation)
if not visual:
    raise RuntimeError('Cannot create the independent skeletal animation actor.')
visual.set_actor_label('SelectedDeathAuthorVisual')
visual.set_editor_property('tags', ['NL_DeathAuthorPreview'])
visual.set_actor_scale3d(source_scale)
mesh = visual.get_component_by_class(unreal.SkeletalMeshComponent)
mesh.set_skeletal_mesh_asset(skin)
mesh.set_mobility(unreal.ComponentMobility.MOVABLE)
mesh.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
mesh.override_animation_data(animation, False, True, 0.0, 1.0)
mesh.set_morph_target('EnemyGrip_R', 1.0)

prop = ACTORS.spawn_actor_from_class(unreal.StaticMeshActor, base, source_rotation)
if not prop:
    raise RuntimeError('Cannot create the independent hand-held sword actor.')
prop.set_actor_label('SelectedDeathAuthorSword')
prop.set_editor_property('tags', ['NL_DeathAuthorWeapon'])
prop_component = prop.get_component_by_class(unreal.StaticMeshComponent)
prop_component.set_static_mesh(weapon_asset)
prop_component.set_mobility(unreal.ComponentMobility.MOVABLE)
prop_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
if not prop.attach_to_component(mesh, 'hand_r', unreal.AttachmentRule.KEEP_RELATIVE,
                                unreal.AttachmentRule.KEEP_RELATIVE,
                                unreal.AttachmentRule.KEEP_RELATIVE, False):
    raise RuntimeError('The preview sword could not attach to the existing right hand bone.')
prop_component.set_relative_transform(unreal.Transform(
    location=unreal.Vector(*grip['grip_location_cm']),
    rotation=unreal.Quat(*grip['grip_quaternion_xyzw']).rotator(),
    scale=unreal.Vector(*grip_scale)), False, True)

camera_position = base + forward * 480.0 + right * 240.0 + unreal.Vector(0.0, 0.0, 210.0)
focus = base + forward * 65.0 + unreal.Vector(0.0, 0.0, 65.0)
direction = focus - camera_position
camera_rotation = unreal.Rotator(pitch=math.degrees(math.atan2(direction.z,
                                  math.hypot(direction.x, direction.y))),
                                 yaw=math.degrees(math.atan2(direction.y, direction.x)), roll=0.0)
camera = ACTORS.spawn_actor_from_class(unreal.CameraActor, camera_position, camera_rotation)
if not camera:
    raise RuntimeError('Cannot create the animation authoring camera.')
camera.set_actor_label('SelectedDeathAuthorCamera')
camera.set_editor_property('tags', ['NL_DeathAuthorCamera'])
camera.set_editor_property('auto_activate_for_player', unreal.AutoReceiveInput.PLAYER0)
camera_component = camera.get_component_by_class(unreal.CameraComponent)
camera_component.set_editor_property('field_of_view', 55.0)
# A square authoring view at this distance accommodates standing height and
# the complete prone body while preserving the specified 55-degree lens.
camera_component.set_editor_property('aspect_ratio', 1.0)
camera_component.set_editor_property('constrain_aspect_ratio', True)

if not LEVEL.save_current_level():
    raise RuntimeError('Cannot save the independent animation authoring map.')

def vector(v):
    return [v.x, v.y, v.z]

report = {
    'date': '2026-10-12', 'map': MAP, 'source_map_preserved': SOURCE_MAP,
    'animation': animation.get_path_name(), 'duration_seconds': animation.get_play_length(),
    'mesh': skin.get_path_name(), 'visual_actor': visual.get_path_name(),
    'base_world_cm': vector(base), 'mesh_world_rotation_deg': [source_rotation.pitch, source_rotation.yaw, source_rotation.roll],
    'mesh_world_scale': vector(source_scale), 'feet_floor_cm': 0.0,
    'serialized_single_node_playing': True, 'serialized_looping': False,
    'weapon': weapon_asset.get_path_name(), 'weapon_actor': prop.get_path_name(),
    'weapon_socket': 'hand_r', 'grip_location_cm': grip['grip_location_cm'],
    'grip_quaternion_xyzw': grip['grip_quaternion_xyzw'], 'grip_scale': grip_scale,
    'grip_morph': 'EnemyGrip_R', 'grip_weight': 1.0,
    'grip_runtime_override': 'SetMorphTarget override is transient; capture_selected_death_author.py applies it as soon as the preview world is available.',
    'camera_world_cm': vector(camera_position), 'camera_focus_cm': vector(focus),
    'camera_fov': 55.0, 'camera_aspect_ratio': 1.0, 'camera_auto_player': 0,
    'game_mode': 'GameModeBase',
    'scope': 'Independent skeletal animation authoring presentation. No combat actor, damage, brain or gameplay acceptance path is invoked.'
}
(PROJECT / 'Docs/AI/SelectedDeathAuthorPreviewSaved.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('SELECTED_DEATH_AUTHOR_PREVIEW_SAVED ' + MAP)
