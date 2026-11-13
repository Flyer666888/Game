"""Assign reviewed upright clips to the eight gameplay enemy archetypes only."""
import hashlib,json,shutil
from pathlib import Path
import unreal
PROJECT=Path(r'D:\game design\experiment')
OUT=PROJECT/'Docs/Gameplay/RigPolish_v01'
ASSETS=unreal.EditorAssetLibrary
PREFIX='/Game/ReversedScale/Characters/WuxiaMale/Animations/'
PROPS=('idle_animation','walk_animation','attack_animation','cast_animation','hit_reaction_animation')
KEYS=('sword','talisman','rock_talisman','GM01','GM02','GM03','GM04','boss')
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None,'Stop PIE before changing defaults'
preview=json.loads((OUT/'BodyPreview.json').read_text(encoding='utf-8'))
assert preview['state']=='passed' and len(preview['captures'])==8,'Candidate pose preview did not finish'
candidates=json.loads((OUT/'UprightCandidatesReport.json').read_text(encoding='utf-8'))
assert candidates['status']=='passed' and len(candidates['clips'])==5,'Candidate pose numerical validation did not pass'
assert all(row['status']=='passed' and row['metadata_unchanged'] for row in candidates['clips'])
records=[]
for key in KEYS:
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    source=PROJECT/'Content'/Path(path.removeprefix('/Game/')+'.uasset')
    backup=OUT/'Backups'/'Assets'/source.relative_to(PROJECT/'Content')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(source,backup)
    bp=ASSETS.load_asset(path);default=unreal.get_default_object(ASSETS.load_blueprint_class(path))
    row={'enemy':key,'blueprint':path,'backup':str(backup),'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'animations':{}}
    for prop in PROPS:
        original=default.get_editor_property(prop)
        if not original:continue
        name=original.get_name().removesuffix('_Upright_v01')
        candidate=ASSETS.load_asset(PREFIX+name+'_Upright_v01')
        assert candidate and candidate.get_editor_property('skeleton')==original.get_editor_property('skeleton'),prop
        assert abs(candidate.get_play_length()-original.get_play_length())<.001,'Clip duration changed'
        row['animations'][prop]={'from':PREFIX+name,'to':candidate.get_path_name()}
        default.set_editor_property(prop,candidate)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert ASSETS.save_loaded_asset(bp,False),'Unable to save '+path
    check=unreal.get_default_object(ASSETS.load_blueprint_class(path))
    for prop,change in row['animations'].items():
        assert check.get_editor_property(prop).get_path_name()==change['to'],'Compiled defaults lost candidate '+prop
    records.append(row)
(OUT/'BodyAssignments.json').write_text(json.dumps({'state':'passed','enemies':records,'scope':'Only eight current Gameplay/V01 enemy blueprint animation defaults; original clips, mesh, skeleton, player and map unchanged.'},ensure_ascii=False,indent=2),encoding='utf-8')
