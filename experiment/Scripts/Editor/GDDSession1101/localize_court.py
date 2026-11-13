"""Polish the authored alchemy instructions after the isolated runtime ends."""
import hashlib,json,shutil
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/GDDSession1101'
E=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
L=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert E.get_game_world() is None
assert L.load_level('/Game/ReversedScale/Maps/L_NilinGameplayV01')
director=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if isinstance(a,unreal.NLLevelEncounterDirector))
assert str(director.level_id)=='Level.Nilin.Playable'
stages=list(director.stages);assert len(stages)==16
mapfile=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
backup=O/'Backups/L_NilinGameplayV01_BeforeLocalizedHints.umap'
backup.parent.mkdir(parents=True,exist_ok=True)
if not backup.exists():shutil.copy2(mapfile,backup)
messages={'Cestablish':'守住法阵，保护挚友，解救进度达到25%。',
          'Cinterrupt':'破阵修士会干扰解救，击中即可打断施法。',
          'Csiege':'兼顾近身敌人与破阵修士，守住法阵完整度。',
          'Cunseal':'完成解封后清除残敌，救出挚友。'}
for s in stages:
    if str(s.stage_id) in messages:s.instruction_text=unreal.Text(messages[str(s.stage_id)])
director.stages=stages
goal=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
          if isinstance(a,unreal.NLRitualObjective) and str(a.objective_stable_id)=='Objective.Nilin.AlchemyRescue')
goal.status_text.set_world_size(10.0)
assert L.save_current_level()
(O/'LocalizedHints.json').write_text(json.dumps({'success':True,'messages':messages,
    'map_sha256':hashlib.sha256(mapfile.read_bytes()).hexdigest()},ensure_ascii=False,indent=2),encoding='utf-8')
