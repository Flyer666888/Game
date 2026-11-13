"""Apply the visually reviewed hand variants to the current four melee enemies."""
import unreal,json,hashlib,shutil
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/HandGripPolish1104';A=unreal.EditorAssetLibrary
C=json.loads((O/'FitCandidate.json').read_text(encoding='utf-8-sig'))
prepared=json.loads((O/('Prepared_'+C['id']+'.json')).read_text(encoding='utf-8-sig'))
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
properties={'attack':'attack_animation','idle':'idle_animation','walk':'walk_animation','hit':'hit_reaction_animation','death':'death_animation','cast':'cast_animation'}
g=C['grip'];grip=unreal.Transform(location=unreal.Vector(*g['p']),scale=unreal.Vector(*g['s']));grip.rotation=unreal.Quat(*g['q'])
sword=unreal.load_asset(json.loads((O/'HiltImported.json').read_text(encoding='utf-8-sig'))['asset'])
rows=[]
for key in ['sword','GM01','GM04','boss']:
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    bp=A.load_asset(path);obj=unreal.get_default_object(A.load_blueprint_class(path));brain=obj.get_enemy_brain()
    before={p:obj.get_editor_property(p).get_path_name() for p in properties.values()}
    curve=obj.attack_root_motion_curve;timing=[brain.telegraph_seconds,brain.attack_seconds,brain.recover_seconds,brain.attack_range]
    file=P/'Content'/(path.removeprefix('/Game/')+'.uasset');backup=O/'Backups'/'Content'/file.relative_to(P/'Content')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(file,backup)
    for k,prop in properties.items():
        row=prepared['clips'][k];assert before[prop] in [row['source'],row['asset']],(key,prop,before[prop])
        anim=A.load_asset(row['asset']);assert anim.get_editor_property('skeleton')==obj.enemy_skeletal_mesh.skeleton
        obj.set_editor_property(prop,anim)
    obj.set_editor_property('sword_attach_bone','RightHand');obj.set_editor_property('sword_grip_transform',grip)
    obj.sword.set_static_mesh(sword)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp);assert A.save_loaded_asset(bp,False)
    check=unreal.get_default_object(A.load_blueprint_class(path));b=check.get_enemy_brain()
    assert check.attack_root_motion_curve==curve
    assert check.sword.static_mesh==sword,'Blueprint compilation discarded the fitted sword'
    assert [b.telegraph_seconds,b.attack_seconds,b.recover_seconds,b.attack_range]==timing
    assert all(check.get_editor_property(prop).get_path_name()==prepared['clips'][k]['asset'] for k,prop in properties.items())
    rows.append({'enemy':key,'asset':path,'before':before,'backup':str(backup),'attack':check.attack_animation.get_path_name(),
                 'root_curve':curve.get_path_name(),'timing_and_range':timing,'grip':g,'sword':sword.get_path_name()})
(O/'Applied.json').write_text(json.dumps({'state':'applied','candidate':C,'enemies':rows},ensure_ascii=False,indent=2),encoding='utf-8')
