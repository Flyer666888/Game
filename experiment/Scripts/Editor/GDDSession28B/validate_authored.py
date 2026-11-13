"""Read back authored main-map phase data and verify geometry around the objective."""
import hashlib,json
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/GDDSession28B'
A=unreal.EditorAssetLibrary;L=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
E=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert E.get_game_world() is None
assert L.load_level('/Game/ReversedScale/Maps/L_NilinGameplayV01')
world=E.get_editor_world()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
director=next(a for a in actors if isinstance(a,unreal.NLLevelEncounterDirector))
goals=[a for a in actors if isinstance(a,unreal.NLRitualObjective) and str(a.objective_stable_id)=='Objective.Nilin.AlchemyRescue']
assert len(goals)==1
goal=goals[0]
assert not goal.start_active and goal.effective_rescue_seconds==240 and goal.max_integrity==100
pos=goal.get_actor_location()
assert abs(pos.x)<.1 and abs(pos.y-28300)<.1 and abs(pos.z-7200)<.1
assert list(map(str,goal.allowed_attack_definition_ids))==['Attack.Enemy.FormationBreaker.Ritual']
stages=list(director.stages);assert len(stages)==16
ids=('Cestablish','Cinterrupt','Csiege','Cunseal')
old=json.loads((P/'Docs/Gameplay/GDDSession28/MeleeGDDAlignment.json').read_text(encoding='utf-8-sig'))
old={r['stage_id']:r['waves'] for r in old['main_map_stages']}
total=0;court_total=0;geometry=[]
for s in stages:
    count=sum(e.count for w in s.waves for e in w.spawn_entries);total+=count
    if str(s.stage_id) not in ids:
        assert [w.get_path_name() for w in s.waves]==old[str(s.stage_id)]
        continue
    i=ids.index(str(s.stage_id));court_total+=count
    assert s.objective_progress_target==(i+1)*25
    assert s.continue_objective_from_previous_stage==(i>0)
    assert str(s.objective_stable_id)=='Objective.Nilin.AlchemyRescue'
    assert str(s.required_stage_id)==('R03' if i==0 else ids[i-1])
    assert len(s.waves)==2 and count==20
    for w in s.waves:assert w.max_alive==4 and w.spawn_interval_seconds==4
    if i==3:assert s.minimum_upgrade_level_on_complete==3
    for point in s.spawn_points:
        pos=point.spawn_transform.translation
        hit=unreal.SystemLibrary.capsule_trace_single(world,pos,pos+unreal.Vector(0,0,1),28,88,
            unreal.TraceTypeQuery.ECC_VISIBILITY,False,[],unreal.DrawDebugTrace.NONE)
        assert not hit, f'Blocked spawn {point.spawn_point_id}: {hit}'
        geometry.append({'spawn':str(point.spawn_point_id),'capsule_clear':True})
assert total==145 and court_total==80
cdo=unreal.get_default_object(A.load_blueprint_class('/Game/ReversedScale/Gameplay/RitualV02/BP_FormationBreaker'))
brain=cdo.get_component_by_class(unreal.NLEnemyBrainComponent)
assert brain.role==unreal.NLEnemyRole.FORMATION_BREAKER
assert str(brain.formation_objective_id)==str(goal.objective_stable_id)
assert abs(brain.telegraph_seconds-1.8)<.001 and abs(brain.attack_seconds-1.7)<.001
assert cdo.get_component_by_class(unreal.NLCombatVitalsComponent).max_health==45
assert brain.ranged_attack_definition.damage==8
upgrade=director.upgrade_definition
assert upgrade.enable_second_upgrade and upgrade.first_upgrade_threshold==40 and upgrade.second_upgrade_threshold==100
assert upgrade.level_three_damage_multiplier==1.5
report={'success':True,'stages':16,'phase_targets':[25,50,75,100],'candidate_limit':total,
        'alchemy_candidate_limit':court_total,'non_alchemy_wave_references_unchanged':True,
        'goal_location':[0,28300,7200],'effective_seconds':240,'max_integrity':100,
        'breaker_health':45,'breaker_ritual_damage':8,'geometry':geometry,
        'upgrade_thresholds':[40,100],'upgrade_minimum_at_rescue_end':3,
        'map_sha256':hashlib.sha256((P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap').read_bytes()).hexdigest()}
(O/'AuthoredValidation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
