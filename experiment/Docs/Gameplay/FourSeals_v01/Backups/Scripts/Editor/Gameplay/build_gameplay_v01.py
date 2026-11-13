"""Create an independent playable copy of V10; never overwrite the whitebox source."""
import unreal,sys,os,json,math,hashlib,datetime,importlib
ROOT=r'D:\game design\experiment'
BASE=os.path.join(ROOT,'Scripts','Editor','Gameplay')
OUT=os.path.join(ROOT,'Docs','Gameplay','EncounterRecovery_v01')
SOURCE='/Game/ReversedScale/Maps/L_NilinBlockoutV10'
MAP='/Game/ReversedScale/Maps/L_NilinGameplayV01'
ASSET='/Game/ReversedScale/Gameplay/V01'
sys.path.insert(0,BASE)
import encounter_config_v01,navigation_setup_v01
importlib.reload(encounter_config_v01)
importlib.reload(navigation_setup_v01)
cfg=encounter_config_v01.make_config()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assets=unreal.EditorAssetLibrary
tools=unreal.AssetToolsHelpers.get_asset_tools()
os.makedirs(OUT,exist_ok=True)
assert not editor.get_game_world(),'Stop PIE before editing'
source_file=os.path.join(ROOT,'Content','ReversedScale','Maps','L_NilinBlockoutV10.umap')
source_hash=hashlib.sha256(open(source_file,'rb').read()).hexdigest()
if not assets.does_asset_exist(MAP):
    if not editor.get_editor_world().get_path_name().startswith(SOURCE+'.'):
        assert level.load_level(SOURCE)
    assert unreal.EditorLoadingAndSavingUtils.save_map(editor.get_editor_world(),MAP),'Cannot create independent map'
if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):assert level.load_level(MAP)
world=editor.get_editor_world()
def vec(p):return unreal.Vector(*[float(t)*100 for t in p])
def tag(a,label):
    a.set_actor_label('NG_'+label);a.set_folder_path('NilinGameplay/Encounters')
    a.set_editor_property('tags',[unreal.Name('NLGameplayV01')]);return a

removed=[]
if not any(a.actor_has_tag('NLGameplay.ConvertedV01') for a in actors.get_all_level_actors()):
    scene=json.load(open(os.path.join(ROOT,'Docs','LevelDesign','Blockout_v05','SceneBuild.json'),encoding='utf-8'))
    index_removals={}
    body_tokens=('_Leg','_Robe','_Shoulder','_Head','_Topknot','_Sash','_Arm','_Sword','_Talisman','_Censer','_WindStaff')
    for r in scene['records']:
        if r.get('cluster') and r['name'].startswith(('GM01_','GM02_','GM03_','GM04_','D_Boss_')) and any(t in r['name'] for t in body_tokens):
            index_removals.setdefault(r['cluster'],[]).append(r['index'])
    for a in list(actors.get_all_level_actors()):
        name=a.get_actor_label();c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
        if c and name in index_removals:
            for i in sorted(set(index_removals[name]),reverse=True):c.remove_instance(i)
        mesh=a.get_component_by_class(unreal.StaticMeshComponent)
        mats=[mesh.get_material(i).get_name() if mesh.get_material(i) else '' for i in range(mesh.get_num_materials())] if mesh else []
        ranged=str(a.get_folder_path())=='Nilin_V10/RangedWalkways'
        dummy=any(m in ('M_Dummy','M_Enemy') for m in mats)
        ranged_prop=ranged and any(m in ('M_Wood','M_Warm','M_Trim') for m in mats)
        footprint=name.endswith(('GM01_Footprint','GM02_Footprint','GM03_Footprint','GM04_Footprint','D_Boss_Footprint'))
        if dummy or ranged_prop or footprint:
            removed.append(name);actors.destroy_actor(a)
    sentinel=actors.spawn_actor_from_class(unreal.TargetPoint,unreal.Vector())
    sentinel.set_actor_label('NG_SourceConverted');sentinel.set_editor_property('tags',[unreal.Name('NLGameplay.ConvertedV01')])
for a in list(actors.get_all_level_actors()):
    if a.actor_has_tag('NLGameplayV01'):actors.destroy_actor(a)

enemy_classes={}
def make_enemy(key,parent_path,health,hold=False):
    path=ASSET+'/Enemies/BP_Level_'+key
    bp=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset(parent_path,path)
    assert bp,'Missing source enemy blueprint '+parent_path
    cls=assets.load_blueprint_class(path);default=unreal.get_default_object(cls)
    vitals=default.get_component_by_class(unreal.load_class(None,'/Script/experiment.NLCombatVitalsComponent'))
    vitals.set_editor_property('max_health',float(health))
    brain=default.get_component_by_class(unreal.load_class(None,'/Script/experiment.NLEnemyBrainComponent'))
    if key in ('talisman','rock_talisman','GM02','GM03'):
        brain.set_editor_property('role',unreal.NLEnemyRole.TALISMAN_CASTER)
        brain.set_editor_property('attack_range',2800.0)
        brain.set_editor_property('minimum_ranged_distance',120.0)
        brain.set_editor_property('preferred_ranged_distance',1200.0)
        brain.set_editor_property('projectile_speed',1000.0)
        brain.set_editor_property('telegraph_seconds',1.2)
        brain.set_editor_property('hold_ranged_position',bool(hold))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert assets.save_loaded_asset(bp,False)
    return assets.load_blueprint_class(path)

sword='/Game/ReversedScale/Characters/WuxiaMale/BP_EnemySwordDisciple'
caster='/Game/ReversedScale/Characters/WuxiaMale/BP_EnemyTalismanDisciple'
captain='/Game/ReversedScale/Characters/WuxiaMale/BP_EnemyGuardCaptain'
for key,parent,hp,hold in [('sword',sword,30,False),('talisman',caster,30,False),('rock_talisman',caster,30,True),
    ('GM01',captain,90,False),('GM02',caster,90,False),('GM03',caster,110,False),('GM04',captain,120,False),('boss',captain,240,False)]:
    enemy_classes[key]=make_enemy(key,parent,hp,hold)

floor_checks=[];adjustments=[];used=[]
def admitted_ground(desired,preserve=False):
    candidates=[(0,0)] if preserve else [(0,0)]+[(r*math.cos(a*math.pi/4),r*math.sin(a*math.pi/4)) for r in (1.5,3.0,4.5) for a in range(8)]
    for dx,dy in candidates:
        q=[desired[0]+dx,desired[1]+dy,desired[2]]
        hit=unreal.SystemLibrary.line_trace_single(world,vec((q[0],q[1],q[2]+.5)),vec((q[0],q[1],q[2]-.7)),unreal.TraceTypeQuery.ECC_VISIBILITY,False,[],unreal.DrawDebugTrace.NONE)
        if not hit:continue
        t=hit.to_tuple();point=t[5]
        if abs(point.z/100-q[2])>.12:continue
        p=[q[0],q[1],point.z/100];center=vec((p[0],p[1],p[2]+.91))
        blocked=unreal.SystemLibrary.capsule_trace_single(world,center,center+unreal.Vector(0,0,1),28,88,unreal.TraceTypeQuery.ECC_VISIBILITY,False,[],unreal.DrawDebugTrace.NONE)
        if blocked:continue
        if any(math.dist(p,k)<.80 for k in used):continue
        used.append(p)
        floor_checks.append({'requested_m':desired,'actual_m':p,'capsule_clear':True,'floor_actor':t[9].get_actor_label() if t[9] else None})
        if dx or dy:adjustments.append({'from':desired,'to':p})
        return p
    raise RuntimeError('No supported, clear capsule spawn near '+str(desired))

director=tag(actors.spawn_actor_from_class(unreal.load_class(None,'/Script/experiment.NLLevelEncounterDirector'),unreal.Vector()),'LevelEncounters')
stages=[]
names={'GM01':'问剑宗师','GM02':'镇符宗师','GM03':'丹火宗师','GM04':'御风宗师'}
for si,s in enumerate(cfg['stages']):
    used=[]
    if s['id'] in names:s['label']='御风桥 · '+names[s['id']]
    stage=unreal.NLLevelEncounterStage()
    stage.set_editor_property('stage_id',s['id']);stage.set_editor_property('display_name',unreal.Text(s['label']))
    stage.set_editor_property('required_stage_id',s['required'] or 'None')
    stage.set_editor_property('trigger_center',vec(s['trigger_center_m'])+unreal.Vector(0,0,88))
    stage.set_editor_property('trigger_extent',vec(s['trigger_extent_m']))
    stage.set_editor_property('entry_transform',unreal.Transform(location=vec(s['entry_ground_m'])+unreal.Vector(0,0,91),rotation=unreal.Rotator(yaw=s['entry_yaw'])))
    points=[]
    for p in s['spawn_points']:
        p['ground_m']=admitted_ground(p['ground_m'],s.get('preserve_saved_spawn_ground',False))
        point=unreal.NLWaveSpawnPoint()
        point.set_editor_property('spawn_point_id',p['id'])
        point.set_editor_property('spawn_transform',unreal.Transform(location=vec(p['ground_m'])+unreal.Vector(0,0,90),rotation=unreal.Rotator(yaw=p['yaw'])))
        points.append(point)
    stage.set_editor_property('spawn_points',points)
    waves=[]
    for w in s['waves']:
        path=ASSET+'/Waves/DA_'+w['id']
        if assets.does_asset_exist(path):wave=assets.load_asset(path)
        else:
            factory=unreal.DataAssetFactory();factory.set_editor_property('data_asset_class',unreal.load_class(None,'/Script/experiment.NLWaveDefinition'))
            wave=tools.create_asset('DA_'+w['id'],ASSET+'/Waves',None,factory)
        assert wave,'Wave asset creation failed'
        entry=unreal.NLWaveSpawnEntry();entry.set_editor_property('entry_id',w['id']+'_Enemies')
        key='rock_talisman' if s.get('stationary_ranged') else w['entry_class_key']
        entry.set_editor_property('enemy_class',enemy_classes[key]);entry.set_editor_property('count',w['count']);entry.set_editor_property('spawn_point_ids',w['point_ids'])
        wave.set_editor_property('wave_id',w['id']);wave.set_editor_property('spawn_entries',[entry])
        for name,value in [('spawn_interval_seconds',w['spawn_interval']),('intermission_seconds',w['intermission']),('max_alive',w['max_alive']),('max_spawn_retries',24),('retry_delay_seconds',.5)]:wave.set_editor_property(name,value)
        assert assets.save_loaded_asset(wave,False);waves.append(wave)
    stage.set_editor_property('waves',waves);stage.set_editor_property('warning_seconds',2.0);stage.set_editor_property('seed',20261023+si)
    if s.get('master_id'):stage.set_editor_property('master_id',s['master_id']);stage.set_editor_property('seal_id',s['seal_id'])
    stages.append(stage)
director.set_editor_property('stages',stages)
world.get_world_settings().set_editor_property('default_game_mode',unreal.load_class(None,'/Script/experiment.NLLevelCombatGameMode'))
starts=[a for a in actors.get_all_level_actors() if isinstance(a,unreal.PlayerStart)]
start=starts[0] if starts else actors.spawn_actor_from_class(unreal.PlayerStart,unreal.Vector())
start.set_actor_location(vec((0,-25,0))+unreal.Vector(0,0,91),False,True);start.set_actor_rotation(unreal.Rotator(yaw=90),False)
for extra in starts[1:]:actors.destroy_actor(extra)

areas=[{'name':'A_Court','center_m':[0,0,0],'size_m':[64,62,3]},
       {'name':'B_Court','center_m':[0,140,30],'size_m':[64,64,8]},
       {'name':'C_Court','center_m':[0,300,72],'size_m':[70,70,5]},
       {'name':'Summit','center_m':[-208,620,132],'size_m':[100,100,5]}]
layout=json.load(open(os.path.join(ROOT,'Docs','LevelDesign','Blockout_v05','LayoutSpec.json'),encoding='utf-8'))
for r in layout['ranged_encounters']['stations']:
    x,y,z=r['route_rest'];areas.append({'name':r['id'],'center_m':[r['side']*8,y,z+1],'size_m':[30,26,10]})
for r in layout['grandmaster_arenas']:areas.append({'name':r['id'],'center_m':r['center'],'size_m':[32,38,5]})
assert hashlib.sha256(open(source_file,'rb').read()).hexdigest()==source_hash,'Source whitebox changed'
json.dump(cfg,open(os.path.join(OUT,'EncounterConfig.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
report={'state':'navigation_pending','map':MAP,'source_map':SOURCE,'source_map_sha256':source_hash,'source_unchanged':True,
        'stage_count':len(stages),'waves':sum(len(s['waves']) for s in cfg['stages']),'enemy_budget':cfg['total_enemy_budget'],
        'spawn_admission_checks':floor_checks,'spawn_adjustments':adjustments,'removed_static_silhouettes':removed,'time':datetime.datetime.now().isoformat()}
json.dump(report,open(os.path.join(OUT,'MapBuild.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
navigation_setup_v01.install_navigation(areas)
unreal.log('NILIN_GAMEPLAY_MAP_AUTHORED_NAV_PENDING')
