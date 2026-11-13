"""Verify actual saved encounter assets, spawn clearance, and local navigation."""
import unreal,os,json,datetime,hashlib,sys,math
ROOT=r'D:\game design\experiment';OUT=os.path.join(ROOT,'Docs','Gameplay','EncounterRecovery_v01')
sys.path.insert(0,os.path.join(ROOT,'Scripts','Editor','Gameplay'))
import navigation_setup_v01
nav=navigation_setup_v01.get_navigation_install_report()
if nav['state']=='not_started':
    # A fresh editor has no authoring session. Check the persisted baked map itself.
    cold_world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    cold_navs=[a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.RecastNavMesh)]
    assert len(cold_navs)==1 and not unreal.NavigationSystemV1.is_navigation_being_built_or_locked(cold_world)
    assert cold_navs[0].get_editor_property('runtime_generation')==unreal.RuntimeGenerationType.STATIC
    assert not cold_navs[0].get_editor_property('force_rebuild_on_load')
    nav={'state':'ready_for_validation','source':'Saved static navigation readback in a fresh editor','runtime_generation':'Static','force_rebuild_on_load':False}
json.dump(nav,open(os.path.join(OUT,'NavigationBuild.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
assert nav['state']=='ready_for_validation',{k:nav.get(k) for k in ('state','error','traceback')}
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);world=ed.get_editor_world()
assert not ed.get_game_world() and 'L_NilinGameplayV01' in world.get_path_name()
cfg=json.load(open(os.path.join(OUT,'EncounterConfig.json'),encoding='utf-8'))
director=next(a for a in actors.get_all_level_actors() if a.get_class().get_name()=='NLLevelEncounterDirector')
actual=director.get_editor_property('stages');assert len(actual)==16
checks=[];failures=[]
v=lambda p:unreal.Vector(*[float(k)*100 for k in p])
for stage in cfg['stages']:
    entry=v(stage['entry_ground_m'])
    for point in stage['spawn_points']:
        ground=v(point['ground_m'])
        projected=unreal.NavigationSystemV1.project_point_to_navigation(world,ground,None,None,unreal.Vector(100,100,250))
        valid=projected is not None and math.dist((projected.x,projected.y,projected.z),(ground.x,ground.y,ground.z))<200
        record={'stage':stage['id'],'point':point['id'],'navigation_projection_matches':valid,
            'projected_cm':[projected.x,projected.y,projected.z] if projected is not None else None,'path_valid':False}
        if valid:
            path=unreal.NavigationSystemV1.find_path_to_location_synchronously(world,entry,projected)
            record['path_valid']=path is not None and path.is_valid() and not path.is_partial()
        checks.append(record)
        if not valid or not record['path_valid']:failures.append(record)
assert not failures,failures
assert level.save_current_level()
unreal.SystemLibrary.execute_console_command(world,'MAP CHECK')
report={'map':cfg['map'],'saved':True,'time':datetime.datetime.now().isoformat(),'success':not failures,
    'stage_count':len(actual),'wave_count':sum(len(s['waves']) for s in cfg['stages']),'enemy_budget':cfg['total_enemy_budget'],
    'navigation_points_and_entry_paths':checks,'failures':failures,'nav_build':nav['state']}
json.dump(report,open(os.path.join(OUT,'MapValidation.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
build=json.load(open(os.path.join(OUT,'MapBuild.json'),encoding='utf-8'));build['state']='saved_and_validated';build['saved_at']=report['time']
source_file=os.path.join(ROOT,'Content','ReversedScale','Maps','L_NilinBlockoutV10.umap')
assert hashlib.sha256(open(source_file,'rb').read()).hexdigest()==build['source_map_sha256']
json.dump(build,open(os.path.join(OUT,'MapBuild.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
unreal.log('NILIN_GAMEPLAY_NAV_SPAWNS_VALIDATED')
