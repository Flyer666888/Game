"""Connect the saved alchemy courtyard to four bounded rescue phases."""
import hashlib,json,shutil
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/GDDSession28B'
MAP='/Game/ReversedScale/Maps/L_NilinGameplayV01'
ROOT='/Game/ReversedScale/Gameplay/RitualV02'
ID='Objective.Nilin.AlchemyRescue';ATTACK_ID='Attack.Enemy.FormationBreaker.Ritual'
E=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
L=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACT=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
A=unreal.EditorAssetLibrary;TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
assert E.get_game_world() is None
mapfile=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
backup=O/'Backups/L_NilinGameplayV01.umap'
if not backup.exists():shutil.copy2(mapfile,backup)
assert L.load_level(MAP)
world=E.get_editor_world()
allactors=ACT.get_all_level_actors()
directors=[a for a in allactors if isinstance(a,unreal.NLLevelEncounterDirector)]
assert len(directors)==1
director=directors[0]
stages=list(director.get_editor_property('stages'))
stage_ids=('Cestablish','Cinterrupt','Csiege','Cunseal')
assert all(sum(str(s.stage_id)==i for s in stages)==1 for i in stage_ids)

def ensure_duplicate(source,path):
    if A.does_asset_exist(path):
        file=P/'Content'/(path[len('/Game/'):]+'.uasset')
        target=O/'Backups/RitualV02'/(path.rsplit('/',1)[1]+'.uasset')
        target.parent.mkdir(parents=True,exist_ok=True)
        if file.exists() and not target.exists():shutil.copy2(file,target)
        return A.load_asset(path)
    result=A.duplicate_asset(source,path)
    assert result,path
    return result

attack=ensure_duplicate('/Game/ReversedScale/Gameplay/RitualV01/DA_RitualHostileBolt',ROOT+'/DA_FormationBreakerBolt')
for k,v in {'stable_id':ATTACK_ID,'damage':8.0,'can_be_blocked':True,'can_be_parried':True,'can_be_reflected':True}.items():
    attack.set_editor_property(k,v)
assert A.save_loaded_asset(attack,False)
upgrade=ensure_duplicate('/Game/ReversedScale/Progression/DA_FirstAscentUpgrade',ROOT+'/DA_RescueAscentUpgrade')
for k,v in {'stable_id':'Progression.RescueAscent','enable_second_upgrade':True,
            'first_upgrade_threshold':40.0,'second_upgrade_threshold':100.0,
            'level_two_damage_multiplier':1.25,'level_three_damage_multiplier':1.5}.items():
    upgrade.set_editor_property(k,v)
assert A.save_loaded_asset(upgrade,False)
director.set_editor_property('upgrade_definition',upgrade)
bp_path=ROOT+'/BP_FormationBreaker'
bp=ensure_duplicate('/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_talisman',bp_path)
cdo=unreal.get_default_object(A.load_blueprint_class(bp_path))
brain=cdo.get_component_by_class(unreal.NLEnemyBrainComponent)
for k,v in {'role':unreal.NLEnemyRole.FORMATION_BREAKER,'formation_objective_id':ID,
            'attack_range':1000.0,'minimum_ranged_distance':350.0,'preferred_ranged_distance':650.0,
            'hold_ranged_position':False,'projectile_speed':1000.0,'target_aim_offset':unreal.Vector(0,0,55),
            'telegraph_seconds':1.8,'attack_seconds':1.7,'recover_seconds':1.2,
            'ranged_attack_definition':attack}.items():brain.set_editor_property(k,v)
cdo.set_editor_property('show_sword',False)
cdo.set_editor_property('enemy_attack_definition',attack)
cdo.get_component_by_class(unreal.NLCombatVitalsComponent).set_editor_property('max_health',45.0)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert A.save_loaded_asset(bp,False)
classes={key:A.load_blueprint_class(path) for key,path in {
    'sword':'/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_sword',
    'talisman':'/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_talisman',
    'breaker':bp_path}.items()}
assert all(classes.values())

goals=[a for a in allactors if isinstance(a,unreal.NLRitualObjective) and str(a.objective_stable_id)==ID]
assert len(goals)<=1,'Duplicate rescue goal'
goal=goals[0] if goals else ACT.spawn_actor_from_class(unreal.NLRitualObjective,unreal.Vector(0,28300,7200))
assert goal
goal.set_actor_label('NG_AlchemyRescue_Ritual')
goal.set_folder_path('NilinGameplay/RitualRescue')
goal.set_editor_property('tags',[unreal.Name('NLGameplay.RitualV02')])
for k,v in {'objective_stable_id':ID,'max_integrity':100.0,'effective_rescue_seconds':240.0,
            'start_active':False,'allowed_attack_definition_ids':[ATTACK_ID]}.items():goal.set_editor_property(k,v)
goal.set_actor_location(unreal.Vector(0,28300,7200),False,True)
# Reuse the existing concentric ritual rings and friend marker; no extra obstacle.
goal.get_editor_property('ritual_visual').set_visibility(False)
goal.get_editor_property('status_text').set_relative_location(unreal.Vector(0,0,235),False,True)
goal.get_editor_property('status_text').set_world_size(18.0)
goal.get_editor_property('status_text').set_text('DEFEND THE RITUAL\nINTEGRITY 100 / 100\nRESCUE 0%')
goal.get_editor_property('status_text').set_relative_rotation(unreal.Rotator(yaw=-90),False,True)
friend_labels=[]
for a in allactors:
    if a.get_actor_label().startswith('NB_C_Friend_'):
        a.set_actor_enable_collision(False)
        friend_labels.append(a.get_actor_label())

# These are bounded candidate plans, not a promise to spawn all 80 enemies.
compositions=[{'sword':8,'talisman':2}, {'sword':7,'talisman':2,'breaker':1},
              {'sword':6,'talisman':3,'breaker':1}, {'sword':6,'talisman':2,'breaker':2}]
prompts=['Protect your friend. Keep the ritual intact.',
         'Hit purple casters to stop their ritual attacks.',
         'Hold the court. Interrupt the ritual casters.',
         'Complete the rescue, then clear all threats.']
report_stages=[]
for index,stage_id in enumerate(stage_ids):
    stage=next(s for s in stages if str(s.stage_id)==stage_id)
    stage.set_editor_property('objective_stable_id',ID)
    stage.set_editor_property('objective_progress_target',float((index+1)*25))
    stage.set_editor_property('continue_objective_from_previous_stage',index>0)
    if index==3:stage.set_editor_property('minimum_upgrade_level_on_complete',3)
    stage.set_editor_property('instruction_text',unreal.Text(prompts[index]))
    points=list(stage.spawn_points)
    assert len(points)==8
    waves=[]
    for wave_index in range(2):
        name=f'DA_Ritual_{stage_id}_W{wave_index+1:02d}'
        path=ROOT+'/Waves/'+name
        if A.does_asset_exist(path):
            asset=A.load_asset(path)
            file=P/'Content'/(path[len('/Game/'):]+'.uasset')
            target=O/'Backups/RitualV02'/file.name
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(file,target)
        else:
            factory=unreal.DataAssetFactory();factory.set_editor_property('data_asset_class',unreal.NLWaveDefinition)
            asset=TOOLS.create_asset(name,ROOT+'/Waves',unreal.NLWaveDefinition,factory)
        assert asset
        entries=[]
        for role,count in compositions[index].items():
            entry=unreal.NLWaveSpawnEntry()
            entry.set_editor_property('entry_id',f'{stage_id}.W{wave_index+1:02d}.{role}')
            entry.set_editor_property('enemy_class',classes[role]);entry.set_editor_property('count',count)
            indices=(2,3) if role=='breaker' else ((0,1,6,7) if role=='sword' else (2,3,4,5))
            entry.set_editor_property('spawn_point_ids',[points[i].spawn_point_id for i in indices])
            entries.append(entry)
        for k,v in {'wave_id':f'Ritual.{stage_id}.W{wave_index+1:02d}','spawn_entries':entries,
                    'spawn_interval_seconds':4.0,'intermission_seconds':2.5,'max_alive':4,
                    'max_spawn_retries':24,'retry_delay_seconds':.5}.items():asset.set_editor_property(k,v)
        assert A.save_loaded_asset(asset,False);waves.append(asset)
    stage.set_editor_property('waves',waves)
    report_stages.append({'id':stage_id,'target_percent':(index+1)*25,'continue_previous':index>0,
                           'candidate_limit':20,'composition_per_wave':compositions[index],
                           'spawn_interval_seconds':4,'max_alive':4,'waves':[w.get_path_name() for w in waves]})
director.set_editor_property('stages',stages)
assert L.save_current_level()
report={'success':True,'map':MAP,'objective_id':ID,'objective_location_cm':[0,28300,7200],
        'effective_seconds':240,'integrity':100,'stages':report_stages,'candidate_limit_alchemy':80,
        'main_map_candidate_limit':145,'spawn_cap_note':'Progress thresholds stop future spawning; these numbers are finite upper bounds.',
        'friend_visual_collision_disabled':friend_labels,'breaker_blueprint':bp_path,
        'attack_definition':attack.get_path_name(),'upgrade_definition':upgrade.get_path_name(),
        'upgrade_thresholds':[40,100],'upgrade_damage_multipliers':[1.0,1.25,1.5],
        'level_two_end_minimum_upgrade':3,'original_map_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
        'saved_map_sha256':hashlib.sha256(mapfile.read_bytes()).hexdigest()}
(O/'RitualCourtAuthored.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
camera=unreal.Vector(1000,27300,7900);target=unreal.Vector(0,29400,7350)
E.set_level_viewport_camera_info(camera,unreal.MathLibrary.find_look_at_rotation(camera,target))
unreal.AutomationLibrary.take_high_res_screenshot(1600,1000,str(O/'AlchemyAuthored.png'))
