"""Bind the user-selected D to current melee enemies; retain C for future reverse-grip enemies."""
import unreal,json,hashlib,shutil
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/PackDIntegration1104'
A=unreal.EditorAssetLibrary;L=unreal.AnimationLibrary
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
prepared=json.loads((O/'GameplayDPrepared.json').read_text())
timing=json.loads((O/'TimingRecommendation.json').read_text())
g=json.loads((P/'Docs/Gameplay/PackSlashReview1104/CaptureConfig.json').read_text(encoding='utf-8-sig'))['grip_override']
anim=A.load_asset(prepared['animation']);curve=A.load_asset(prepared['root_curve']);assert anim and curve
start,end=timing['hit_window'];assert 0<start<end<anim.get_play_length()
tracks=L.get_animation_notify_track_names(anim)
if not tracks:L.add_animation_notify_track(anim,'AttackWindow',unreal.LinearColor(1,.2,0,1));tracks=L.get_animation_notify_track_names(anim)
for track in tracks:L.remove_animation_notify_events_by_track(anim,track)
assert L.add_animation_notify_state_event(anim,tracks[0],start,end-start,unreal.NLEnemyAttackWindowNotifyState)
assert A.save_loaded_asset(anim,False)
grip=unreal.Transform(location=unreal.Vector(*g['translation']),scale=unreal.Vector(*g['scale']))
grip.rotation=unreal.Quat(*g['quaternion_xyzw'])
rows=[]
for key in ['sword','GM01','GM04','boss']:
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    file=P/'Content'/(path.removeprefix('/Game/')+'.uasset')
    backup=O/'Backups'/'Content'/file.relative_to(P/'Content')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(file,backup)
    bp=A.load_asset(path);obj=unreal.get_default_object(A.load_blueprint_class(path));brain=obj.get_enemy_brain()
    assert not brain.is_ranged_role()
    before={'attack':str(obj.attack_animation),'curve':str(obj.attack_root_motion_curve),
        'range':brain.attack_range,'timing':[brain.telegraph_seconds,brain.attack_seconds,brain.recover_seconds],
        'grip':str(obj.sword_grip_transform),'idle':str(obj.idle_animation),'walk':str(obj.walk_animation)}
    assert obj.enemy_skeletal_mesh.skeleton==anim.get_editor_property('skeleton')
    obj.set_editor_property('attack_animation',anim)
    obj.set_editor_property('attack_root_motion_curve',curve)
    obj.set_editor_property('sword_attach_bone','RightHand')
    obj.set_editor_property('sword_grip_transform',grip)
    brain.set_editor_property('telegraph_seconds',start)
    brain.set_editor_property('attack_seconds',end-start)
    brain.set_editor_property('recover_seconds',anim.get_play_length()-end)
    brain.set_editor_property('attack_range',timing['attack_range_cm'])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    check=unreal.get_default_object(A.load_blueprint_class(path))
    assert check.attack_animation==anim and check.attack_root_motion_curve==curve
    assert A.save_loaded_asset(bp,False)
    rows.append({'enemy':key,'asset':path,'backup':str(backup),'before':before,'animation':anim.get_path_name(),
        'root_curve':curve.get_path_name(),'range':check.get_enemy_brain().attack_range,
        'saved_sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
for path,sha in prepared['protected_sha256'].items():
    file=P/'Content'/(path.split('.')[0].removeprefix('/Game/')+'.uasset')
    assert hashlib.sha256(file.read_bytes()).hexdigest()==sha,path
report={'state':'applied','selected':'D','preserved_future':'C; reverse grip required; not assigned to current enemies',
        'grip':g,'duration':anim.get_play_length(),'hit_window':[start,end],'play_rate':1.,'enemies':rows}
(O/'SelectedDApplied.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
