"""Read the authored spawn points and wave assignments from the saved gameplay map."""
import hashlib
import json
from pathlib import Path
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
map_asset = '/Game/ReversedScale/Maps/L_NilinGameplayV01'
map_file = project / 'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
output = project / 'Docs/Gameplay/SpawnReview1104/SpawnLayout.json'
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def vector(value):
    return [float(value.x), float(value.y), float(value.z)]


def enemy_role(enemy_class):
    name = enemy_class.get_name()
    if name.startswith('BP_Level_GM'):
        return 'master'
    if name.startswith('BP_Level_boss'):
        return 'boss'
    brain = unreal.get_default_object(enemy_class).get_enemy_brain()
    if brain.role == unreal.NLEnemyRole.FORMATION_BREAKER:
        return 'formation_breaker'
    return 'talisman' if brain.is_ranged_role() else 'sword'


assert editor.get_game_world() is None
before = hashlib.sha256(map_file.read_bytes()).hexdigest()
assert level.load_level(map_asset)
all_actors = actors.get_all_level_actors()
director, = (actor for actor in all_actors if isinstance(actor, unreal.NLLevelEncounterDirector))
stages = []
for definition in director.get_editor_property('stages'):
    points = {}
    for point in definition.get_editor_property('spawn_points'):
        point_id = str(point.get_editor_property('spawn_point_id'))
        transform = point.get_editor_property('spawn_transform')
        points[point_id] = {'id': point_id, 'position': vector(transform.translation), 'roles': []}
    waves = []
    for wave in definition.get_editor_property('waves'):
        groups = []
        for group in wave.get_editor_property('spawn_entries'):
            enemy_class = group.get_editor_property('enemy_class')
            role = enemy_role(enemy_class)
            ids = [str(point_id) for point_id in group.get_editor_property('spawn_point_ids')]
            groups.append({'role': role, 'count': group.get_editor_property('count'), 'points': ids})
            for point_id in ids:
                if role not in points[point_id]['roles']:
                    points[point_id]['roles'].append(role)
        waves.append({'id': str(wave.get_editor_property('wave_id')),
                      'max_alive': wave.get_editor_property('max_alive'), 'groups': groups})
    stages.append({'id': str(definition.get_editor_property('stage_id')),
                   'label': str(definition.get_editor_property('display_name')),
                   'entry': vector(definition.get_editor_property('entry_transform').translation),
                   'trigger_center': vector(definition.get_editor_property('trigger_center')),
                   'trigger_extent': vector(definition.get_editor_property('trigger_extent')),
                   'points': list(points.values()), 'waves': waves})
starts = [vector(actor.get_actor_location()) for actor in all_actors if isinstance(actor, unreal.PlayerStart)]
assert len(stages) == 16 and len(starts) == 1
assert all(point['roles'] for stage in stages for point in stage['points'])
assert hashlib.sha256(map_file.read_bytes()).hexdigest() == before
report = {'map': map_asset, 'map_sha256': before, 'units': 'cm', 'player_start': starts[0], 'stages': stages}
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
