"""Wire canonical quest seals into the existing playable map; never rebuild its whitebox/navigation."""
import hashlib,json,shutil
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve()
O=P/'Docs/Gameplay/FourSeals_v01';O.mkdir(parents=True,exist_ok=True)
MAP='/Game/ReversedScale/Maps/L_NilinGameplayV01'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert editor.get_game_world() is None,'Stop PIE first'
cfg=json.loads((P/'Docs/Gameplay/EncounterRecovery_v01/EncounterConfig.json').read_text(encoding='utf-8'))
definitions={s['id']:s for s in cfg['stages']}
mapfile=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
backup=O/'Backups/Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
backup.parent.mkdir(parents=True,exist_ok=True)
if not backup.exists():shutil.copy2(mapfile,backup)
if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):assert level.load_level(MAP)
directors=[a for a in actors.get_all_level_actors() if isinstance(a,unreal.NLLevelEncounterDirector)]
assert len(directors)==1,'Expected the existing single director'
director=directors[0]
stages=list(director.get_editor_property('stages'))
assert len(stages)==len(definitions)==16
records=[]
for stage in stages:
    key=str(stage.get_editor_property('stage_id'));source=definitions[key]
    previous={'master_id':str(stage.get_editor_property('master_id')),'seal_id':str(stage.get_editor_property('seal_id')),
        'required_seal_ids':list(map(str,stage.get_editor_property('required_seal_ids')))}
    stage.set_editor_property('master_id',source.get('master_id','None'))
    stage.set_editor_property('seal_id',source.get('seal_id','None'))
    stage.set_editor_property('required_seal_ids',source.get('required_seal_ids',[]))
    records.append({'stage':key,'before':previous,'after':{
        'master_id':str(stage.get_editor_property('master_id')),'seal_id':str(stage.get_editor_property('seal_id')),
        'required_seal_ids':list(map(str,stage.get_editor_property('required_seal_ids')))}})
director.set_editor_property('stages',stages)
assert sum(bool(r['after']['required_seal_ids']) for r in records)==1
assert sum(r['after']['seal_id'] not in ('None','') for r in records)==4
assert level.save_current_level()
(O/'MapWiring.json').write_text(json.dumps({'state':'passed','map':MAP,'backup':str(backup),
    'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'records':records,
    'scope':'Existing stage quest identities and Boss RequiredSealIds only. No spawn, wave, actor transform, whitebox or navigation rebuild.'},ensure_ascii=False,indent=2),encoding='utf-8')
