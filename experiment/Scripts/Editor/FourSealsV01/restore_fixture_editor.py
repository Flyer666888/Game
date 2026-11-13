"""Emergency editor-identity restore after an interrupted integration fixture; no save or broad delete."""
import json
from pathlib import Path
import unreal
P=Path(r'D:\game design\experiment')
path=P/'Docs/Gameplay/FourSeals_v01/FixtureIsolation.json'
data=json.loads(path.read_text(encoding='utf-8'))
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert editor.get_game_world() is None,'End PIE first, then rerun this restore script'
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
directors=[a for a in actors.get_all_level_actors() if isinstance(a,unreal.NLLevelEncounterDirector)]
assert len(directors)==1
director=directors[0]
current=str(director.get_editor_property('level_id'))
assert current in (data['temporary_level_id'],data['original_level_id']),'Do not overwrite an external LevelId edit'
director.set_editor_property('level_id',data['original_level_id'])
data['restored_level_id']=str(director.get_editor_property('level_id'))
data['state']='emergency_identity_restored_no_save_or_file_deletion'
path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
