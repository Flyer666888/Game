"""Author an isolated OBJ-01 lab. Main gameplay, navigation and save contexts are untouched."""
import hashlib,json,shutil
from pathlib import Path
import unreal

P=Path(unreal.Paths.project_dir()).resolve()
OUT=P/'Docs/Gameplay/RitualObjective_v01';OUT.mkdir(parents=True,exist_ok=True)
SOURCE='/Game/ReversedScale/Maps/L_CombatLabLite'
MAP='/Game/ReversedScale/Maps/L_RitualObjectiveV01'
ASSET='/Game/ReversedScale/Gameplay/RitualV01'
A=unreal.EditorAssetLibrary
L=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
EDITOR=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
assert EDITOR.get_game_world() is None,'Stop PIE before authoring the independent lab'
classes={name:unreal.load_class(None,'/Script/experiment.'+name) for name in (
    'NLRitualObjective','NLRitualLabController','NLRitualLabHUD','NLDesktopPlayerCharacter',
    'NLTrainingEnemy','NLTrainingProjectileEmitter')}
assert all(classes.values()),'Compile OBJ-01 source before authoring its lab'
source_file=P/'Content/ReversedScale/Maps/L_CombatLabLite.umap'
source_hash=hashlib.sha256(source_file.read_bytes()).hexdigest()
lab_file=P/'Content/ReversedScale/Maps/L_RitualObjectiveV01.umap'
if lab_file.exists():
    backup=OUT/'Backups/L_RitualObjectiveV01.before.umap';backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(lab_file,backup)
assert L.load_level(MAP) if A.does_asset_exist(MAP) else L.new_level_from_template(MAP,SOURCE)

# Only this independent copy is edited. Keep its small floor, sky and temple gate.
for actor in list(ACTORS.get_all_level_actors()):
    if actor.actor_has_tag('NLRitualLabV01') or isinstance(actor,(unreal.SkeletalMeshActor,unreal.TextRenderActor)):
        ACTORS.destroy_actor(actor)
for actor in ACTORS.get_all_level_actors():
    assert actor.get_class().get_name() not in ('NLEncounterController','NLLevelEncounterDirector'),'Unexpected encounter/save owner in lab template'

mode_path=ASSET+'/BP_RitualObjectiveLabMode'
if not A.does_asset_exist(mode_path):
    factory=unreal.BlueprintFactory();factory.set_editor_property('parent_class',unreal.GameModeBase)
    assert TOOLS.create_asset('BP_RitualObjectiveLabMode',ASSET,unreal.Blueprint,factory)
mode=A.load_asset(mode_path);mode_class=A.load_blueprint_class(mode_path);default=unreal.get_default_object(mode_class)
default.set_editor_property('default_pawn_class',classes['NLDesktopPlayerCharacter'])
default.set_editor_property('hud_class',classes['NLRitualLabHUD'])
default.set_editor_property('start_players_as_spectators',False)
unreal.BlueprintEditorLibrary.compile_blueprint(mode);assert A.save_loaded_asset(mode,False)
world=EDITOR.get_editor_world();world.get_world_settings().set_editor_property('default_game_mode',mode_class)

def spawn(cls,label,location,yaw=0):
    actor=ACTORS.spawn_actor_from_class(cls,unreal.Vector(*location),unreal.Rotator(yaw=yaw));assert actor,label
    actor.set_actor_label(label);actor.set_folder_path('RitualObjectiveLab')
    actor.set_editor_property('tags',[unreal.Name('NLRitualLabV01')]);return actor

definition_path=ASSET+'/DA_RitualHostileBolt'
if not A.does_asset_exist(definition_path):
    source=A.load_asset('/Game/ReversedScale/Combat/DA_TrainingProjectile_Reflectable') or A.load_asset('/Game/ReversedScale/Combat/DA_TrainingProjectile')
    assert source,'Missing existing projectile definition'
    assert A.duplicate_asset(source.get_path_name().split('.')[0],definition_path)
definition=A.load_asset(definition_path)
for name,value in {'stable_id':'Attack.Enemy.RitualLabBolt','damage':10.0,'can_be_blocked':True,'can_be_parried':True,'can_be_reflected':True}.items():
    definition.set_editor_property(name,value)
assert A.save_loaded_asset(definition,False)

goal=spawn(classes['NLRitualObjective'],'Ritual_IntegrityAndRescue',(100,0,0))
goal.set_editor_property('objective_stable_id','Objective.Lab.RitualV01')
goal.set_editor_property('max_integrity',100.0)
goal.set_editor_property('effective_rescue_seconds',240.0)
goal.set_editor_property('start_active',False)
goal.set_editor_property('allowed_attack_definition_ids',['Attack.Enemy.RitualLabBolt'])
casters=[]
for index,position in enumerate(((450,-300,0),(450,300,0)),1):
    caster=spawn(classes['NLTrainingEnemy'],'Interference_Target_%02d'%index,position,180)
    caster.get_editor_property('vitals').set_editor_property('max_health',30.0)
    casters.append(caster)
launcher=spawn(classes['NLTrainingProjectileEmitter'],'Ritual_HostileLauncher',(950,0,0),180)
for name,value in {'attack_definition':definition,'target_actor':goal,'target_chest_offset':unreal.Vector(0,0,55),
    'telegraph_seconds':1.2,'fire_interval_seconds':6.0,'projectile_speed':500.0,'projectile_radius':6.0,'projectile_lifetime':6.0}.items():
    launcher.set_editor_property(name,value)
launcher.get_editor_property('vitals').set_editor_property('max_health',30.0)
trial=spawn(classes['NLRitualLabController'],'Ritual_IndependentTrial',(0,0,0))
trial.set_editor_property('objective',goal);trial.set_editor_property('interference_actors',casters)
trial.set_editor_property('required_threat_actors',casters+[launcher]);trial.set_editor_property('launchers',[launcher])
trial.set_editor_property('lab_rescue_seconds',30.0);trial.set_editor_property('auto_start',False)

starts=[a for a in ACTORS.get_all_level_actors() if isinstance(a,unreal.PlayerStart)]
start=starts[0] if starts else spawn(unreal.PlayerStart,'Ritual_PlayerStart',(-450,-450,91),35)
start.set_actor_location(unreal.Vector(-450,-450,91),False,True);start.set_actor_rotation(unreal.Rotator(yaw=35),False)
for other in starts[1:]:ACTORS.destroy_actor(other)
help_actor=spawn(unreal.TextRenderActor,'Ritual_LabInstructions',(1050,0,360),180)
help_text=help_actor.get_component_by_class(unreal.TextRenderComponent)
help_text.set_text('RITUAL OBJECTIVE LAB\nF5 Begin | F6 Full retry\nDefeat both interference targets, protect the ritual, then clear threats.\nAccelerated lab: 30 effective seconds. Production default: 240 seconds.')
help_text.set_world_size(17);help_text.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
help_text.set_text_render_color(unreal.Color(230,225,180,255))
assert L.save_current_level()
assert hashlib.sha256(source_file.read_bytes()).hexdigest()==source_hash,'Original lab template changed'
report={'state':'authored','map':MAP,'source_map':SOURCE,'source_map_sha256':source_hash,'source_unchanged':True,
    'objective':goal.get_path_name(),'trial':trial.get_path_name(),'game_mode':mode_path,'hostile_definition':definition_path,
    'interference_targets':[a.get_path_name() for a in casters],'launcher':launcher.get_path_name(),
    'gdd_default_effective_seconds':240,'lab_accelerated_effective_seconds':30,'controls':{'F5':'Begin trial','F6':'Full trial retry','P':'Pause'},
    'no_existing_encounter_or_level_director':True,'save_scope':'No disk save writes; objective snapshot API is exercised separately.',
    'scope':'OBJ-01 independent prototype. Stationary targets represent registered interference; this is not ENEMY-03 caster AI or a completed Level 02.'}
(OUT/'LabAuthored.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('RITUAL_OBJECTIVE_LAB_AUTHORED '+MAP)
