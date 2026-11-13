import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/PackDIntegration1104';A=unreal.EditorAssetLibrary
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
prepared=json.loads((O/'GameplayDPrepared.json').read_text())
applied=json.loads((O/'SelectedDApplied.json').read_text())
live=json.loads((O/'LiveD.json').read_text())
assert live['state']=='passed' and all(live['checks'].values())
rows=[]
for item in applied['enemies']:
    obj=unreal.get_default_object(A.load_blueprint_class(item['asset']));brain=obj.get_enemy_brain()
    assert obj.attack_animation.get_path_name()==prepared['animation']
    assert obj.attack_root_motion_curve.get_path_name()==prepared['root_curve']
    assert abs(brain.attack_range-200)<.01
    assert abs(brain.telegraph_seconds-.4)<.001 and abs(brain.attack_seconds-.4)<.001
    assert abs(brain.telegraph_seconds+brain.attack_seconds+brain.recover_seconds-obj.attack_animation.get_play_length())<.001
    assert obj.attack_animation.get_editor_property('skeleton')==obj.enemy_skeletal_mesh.skeleton
    rows.append({'asset':item['asset'],'attack':obj.attack_animation.get_path_name(),'curve':obj.attack_root_motion_curve.get_path_name()})
for path,expected in prepared['protected_sha256'].items():
    actual=hashlib.sha256((P/'Content'/(path.split('.')[0].removeprefix('/Game/')+'.uasset')).read_bytes()).hexdigest()
    assert actual==expected,path
selection=json.loads((O/'Selection.json').read_text())
selection['current_enemy'].update({'status':'applied_and_live_combat_verified','gameplay_asset':prepared['animation'],
    'ground_motion_curve':prepared['root_curve'],'hit_window':applied['hit_window'],'play_rate':1.0})
selection['scope']='D is assigned to current melee enemies. C and the original animation pack remain retained for later enemies; C requires reverse grip when integrated.'
(O/'Selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
report={'state':'verified','saved_enemies':rows,'original_rig_and_candidates_unchanged':True,
    'reserved_C_reverse_grip':selection['reserved_for_future_enemy'],
    'live_checks':live['checks'],'live_summary':live['root_motion_summary'],
    'fixture_isolation':live['fixture_isolation'],'entry':'D:/game design/experiment/Run_Gameplay_Demo.cmd',
    'feedback_image':str(O/'EnemyStrike.png')}
(O/'Delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
