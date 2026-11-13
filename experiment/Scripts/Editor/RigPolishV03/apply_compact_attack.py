"""Assign only the reviewed compact attack to the four current sword archetypes."""
import hashlib,json,shutil
from pathlib import Path
import unreal
PROJECT=Path(unreal.Paths.project_dir()).resolve()
OUT=PROJECT/'Docs/Gameplay/RigPolish_v03'
ART=PROJECT/'ArtSource/WuxiaMale/RigPolishV03/Attack'
A=unreal.EditorAssetLibrary
ROOT='/Game/ReversedScale/Characters/WuxiaMale/Animations/'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
preview=json.loads((OUT/'AttackComparison.json').read_text(encoding='utf-8'))
assert preview['state']=='passed' and not preview.get('failures')
for file in (ART/'CompactAttackImported.json',ART/'CompactAttackRuntimeSkin.json',OUT/'CompactAttackValidation.json'):
    report=json.loads(file.read_text(encoding='utf-8'))
    assert report['state']=='passed' and not report.get('failures'),str(file)
candidate=A.load_asset(ROOT+'Wuxia_Attack_Sword_Compact_v03')
source=A.load_asset(ROOT+'Wuxia_Attack_Sword_Upright_v01')
assert candidate and source
assert candidate.get_editor_property('skeleton')==source.get_editor_property('skeleton')
assert abs(candidate.get_play_length()-source.get_play_length())<.0001
def notifies(animation):
    rows=[]
    for track in unreal.AnimationLibrary.get_animation_notify_track_names(animation):
        for event in unreal.AnimationLibrary.get_animation_notify_events_for_track(animation,track):
            state=event.get_editor_property('notify_state_class')
            rows.append((str(track),str(event.get_editor_property('notify_name')),
                unreal.AnimationLibrary.get_anim_notify_event_trigger_time(event),
                unreal.AnimationLibrary.get_anim_notify_event_duration(event),state.get_class().get_path_name() if state else None))
    return rows
assert notifies(source)==notifies(candidate)
records=[]
for key in ('sword','GM01','GM04','boss'):
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    file=PROJECT/'Content'/(path.removeprefix('/Game/')+'.uasset')
    backup=OUT/'Backups/Assets'/file.relative_to(PROJECT/'Content')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(file,backup)
    bp=A.load_asset(path);default=unreal.get_default_object(A.load_blueprint_class(path))
    original=default.get_editor_property('attack_animation')
    assert original in (source,candidate),'Unexpected user attack change: '+path
    preserved={p:default.get_editor_property(p) for p in ('enemy_skeletal_mesh','idle_animation','walk_animation','cast_animation','hit_reaction_animation','death_animation','sword_grip_transform','grip_morph_name','grip_morph_weight')}
    default.set_editor_property('attack_animation',candidate)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert A.save_loaded_asset(bp,False),path
    check=unreal.get_default_object(A.load_blueprint_class(path))
    assert check.get_editor_property('attack_animation')==candidate
    for prop,value in preserved.items():assert check.get_editor_property(prop)==value,prop
    records.append({'enemy':key,'blueprint':path,'from':source.get_path_name(),'to':candidate.get_path_name(),
        'backup':str(backup),'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest()})
(OUT/'AttackAssignments.json').write_text(json.dumps({'state':'passed','enemies':records,'notifies_preserved':True,
    'scope':'Only attack_animation defaults on four sword-using Gameplay/V01 enemies. No caster, timing, damage, range, other motion, mesh or map changes.'},ensure_ascii=False,indent=2),encoding='utf-8')
