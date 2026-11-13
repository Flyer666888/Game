"""Author the independent SAVE-01 desktop scene without starting gameplay."""
import json
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir())
ASSETS = unreal.EditorAssetLibrary
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SOURCE = '/Game/ReversedScale/Maps/L_CombatLabWaves'
MAP = '/Game/ReversedScale/Maps/L_CombatLabCheckpoint'
controller_class = unreal.load_class(None, '/Script/experiment.NLEncounterController')
if not controller_class or not unreal.load_class(None, '/Script/experiment.NLCheckpointService'):
    raise RuntimeError('Compile checkpoint source before creating the checkpoint scene.')
ok = LEVEL.load_level(MAP) if ASSETS.does_asset_exist(MAP) else LEVEL.new_level_from_template(MAP, SOURCE)
if not ok:
    raise RuntimeError('Could not create the independent checkpoint map.')
controllers = [actor for actor in ACTORS.get_all_level_actors() if actor.get_class() == controller_class]
if len(controllers) != 1:
    raise RuntimeError('The checkpoint lab requires one authored encounter controller.')
controller = controllers[0]
for name, value in {
    'level_id': 'Level.CombatLab.Checkpoint',
    'encounter_id': 'Encounter.SwordWaves',
    'content_revision': 'SwordWaves.SAVE01.1',
    'bEnableCheckpoints': True,
}.items():
    controller.set_editor_property(name, value)
controller.set_actor_label('Encounter_CheckpointTrial')

for actor in ACTORS.get_all_level_actors():
    if actor.get_actor_label() == 'Wave01_Info':
        actor.set_actor_label('CheckpointTrial_Info')
        actor.get_component_by_class(unreal.TextRenderComponent).set_text(
            'CHECKPOINT TRIAL\nG Enter / Cancel | R Retry section\nWave 1: 2 | Wave 2: 3')

if not LEVEL.save_current_level():
    raise RuntimeError('Could not save the checkpoint map.')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
enemy_class = unreal.load_class(None, '/Script/experiment.NLEnemyCharacter')
prefab = ASSETS.load_blueprint_class('/Game/ReversedScale/Characters/WuxiaMale/BP_EnemySwordDisciple')
prefab_cdo = unreal.get_default_object(prefab)
report = {
    'date': '2026-10-13', 'task': 'SAVE-01', 'map': MAP, 'source_map_preserved': SOURCE,
    'controller': {name: str(controller.get_editor_property(name)) for name in (
        'level_id', 'encounter_id', 'content_revision', 'bEnableCheckpoints')},
    'controller_actor': controller.get_path_name(),
    'waves': [value.get_path_name() for value in controller.get_editor_property('waves')],
    'wave_counts': [sum(entry.get_editor_property('count') for entry in value.get_editor_property('spawn_entries'))
                    for value in controller.get_editor_property('waves')],
    'spawn_point_count': len(controller.get_editor_property('spawn_points')),
    'seed': controller.get_editor_property('seed'),
    'enemy_prefab': prefab.get_path_name(),
    'preserved_death': prefab_cdo.get_editor_property('death_animation').get_path_name(),
    'preserved_grip_weight': prefab_cdo.get_editor_property('grip_morph_weight'),
    'initial_authored_enemy_count': sum(isinstance(actor, unreal.NLEnemyCharacter) for actor in ACTORS.get_all_level_actors()),
    'game_mode': world.get_world_settings().get_editor_property('default_game_mode').get_path_name(),
    'save_scope': 'USaveGame section entry at wave boundaries, current living entry health/guard and desktop root/control rotation; no arbitrary mid-swing/projectile state.',
    'capture_scope': 'Editor authoring only. No save write, load/restore action, enemy spawning, damage or gameplay input.',
}
(ROOT / 'Docs/AI/CheckpointLabSaved-2026-10-13.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('CHECKPOINT_LAB_SAVED ' + MAP)
