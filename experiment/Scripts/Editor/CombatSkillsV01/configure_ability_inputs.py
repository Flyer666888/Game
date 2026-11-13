"""Add two semantic skills to the existing OpenXR context, preserving unrelated mappings."""
import hashlib,json,shutil
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve()
O=P/'Docs/Gameplay/CombatSkills_v01';O.mkdir(parents=True,exist_ok=True)
A=unreal.EditorAssetLibrary;T=unreal.AssetToolsHelpers.get_asset_tools()
ROOT='/Game/ReversedScale/Player/VR/Input'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
def backup(path):
    source=P/'Content'/(path.removeprefix('/Game/')+'.uasset')
    target=O/'Backups/Assets'/source.relative_to(P/'Content')
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.exists() and not target.exists():shutil.copy2(source,target)
    return {'asset':path,'backup':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()} if target.exists() else None
records=[];actions={}
for name,description in [('IA_VRPulse','Off-hand primary: Pulse; Ready: start'),('IA_VRBurst','Main-hand primary: Burst; Ready: start; paused/dead: retry')]:
    path=ROOT+'/'+name;backup(path)
    action=A.load_asset(path)
    if not action:
        factory=unreal.DataAssetFactory();factory.set_editor_property('data_asset_class',unreal.InputAction)
        action=T.create_asset(name,ROOT,unreal.InputAction,factory)
    assert isinstance(action,unreal.InputAction)
    for field,value in {'value_type':unreal.InputActionValueType.BOOLEAN,'action_description':description,
        'trigger_when_paused':name=='IA_VRBurst','consume_input':True,
        'consumes_action_and_axis_mappings':False,'triggers':[],'modifiers':[]}.items():
        action.set_editor_property(field,value)
    actions[name]=action
context_path=ROOT+'/IMC_NilinVR';records.append(backup(context_path))
context=A.load_asset(context_path);assert isinstance(context,unreal.InputMappingContext)
old=list(context.get_editor_property('default_key_mappings').get_editor_property('mappings'))
primary={}
for profile in ('OculusTouch','PICO','HPMixedRealityController'):
    primary[profile+'_Left_X_Click']='IA_VRPulse';primary[profile+'_Right_A_Click']='IA_VRBurst'
primary['ValveIndex_Left_A_Click']='IA_VRPulse';primary['ValveIndex_Right_A_Click']='IA_VRBurst'
for profile in ('Vive','MixedReality'):
    primary[profile+'_Left_Grip_Click']='IA_VRPulse';primary[profile+'_Right_Grip_Click']='IA_VRBurst'
mappings=[];removed=[]
for mapping in old:
    action=mapping.get_editor_property('action');key=str(mapping.get_editor_property('key').get_editor_property('key_name'))
    name=action.get_name() if action else ''
    if name in actions or (name=='IA_VRStart' and key in primary) or (name=='IA_VRReset' and key in primary):
        removed.append({'action':name,'key':key});continue
    mappings.append(mapping)
added=[];skipped=[]
for key_name,name in primary.items():
    key=unreal.Key();key.set_editor_property('key_name',unreal.Name(key_name))
    if not unreal.InputLibrary.key_is_valid(key):skipped.append(key_name);continue
    mapping=unreal.EnhancedActionKeyMapping();mapping.set_editor_property('action',actions[name]);mapping.set_editor_property('key',key)
    mappings.append(mapping);added.append({'action':name,'key':key_name})
assert any(r['action']=='IA_VRPulse' for r in added) and any(r['action']=='IA_VRBurst' for r in added)
data=unreal.InputMappingContextMappingData();data.set_editor_property('mappings',mappings);context.set_editor_property('default_key_mappings',data)
for asset in [*actions.values(),context]:assert A.save_loaded_asset(asset,False)
# Single ownership is essential: the Ready press routes to start and returns before any ability use.
by_key={}
for mapping in context.get_editor_property('default_key_mappings').get_editor_property('mappings'):
    key=str(mapping.get_editor_property('key').get_editor_property('key_name'))
    by_key.setdefault(key,[]).append(mapping.get_editor_property('action').get_name())
for key in primary:
    assert not (set(by_key.get(key,[])) & {'IA_VRStart','IA_VRReset'}),key+' still has a competing start/reset action'
enemy_records=[]
for key in ('sword','talisman','rock_talisman','GM01','GM02','GM03','GM04','boss'):
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key;records.append(backup(path))
    bp=A.load_asset(path);default=unreal.get_default_object(A.load_blueprint_class(path))
    brain=default.get_enemy_brain();scale=0.0 if key=='boss' else .5 if key.startswith('GM') else 1.0
    brain.set_editor_property('area_control_response_scale',scale)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp);assert A.save_loaded_asset(bp,False)
    check=unreal.get_default_object(A.load_blueprint_class(path)).get_enemy_brain()
    assert abs(check.get_editor_property('area_control_response_scale')-scale)<.0001
    enemy_records.append({'enemy':key,'control_response_scale':scale})
report={'state':'passed','context':context_path,'added_mappings':added,'removed_conflicting_mappings':removed,
    'skipped_optional_keys':skipped,'mapping_count':len(mappings),'enemies':enemy_records,'backups':records,
    'input_routing':'A/X primary has one InputAction. Ready press starts and returns; running press activates ability. Wand right grip retries only when paused/dead/finished.',
    'gdd_defaults':{'pulse_cooldown_seconds':8,'pulse_radius_cm':250},
    'prototype_tuning_not_fixed_by_gdd':{'burst_max_energy':100,'hit_energy':3,'defeat_energy':15,'perfect_parry_energy':12,
        'burst_radius_cm':400,'pulse_stagger_seconds':1,'burst_stagger_seconds':2,'pulse_knockback_cm':60,'burst_knockback_cm':100},
    'hardware_validation':'Input assets only; actual controller behavior still requires tracked play.'}
(O/'AbilityInputAssets.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
