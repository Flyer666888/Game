"""Read saved input/attack assets and native defaults; does not edit any asset."""
import unreal,json,os,math,datetime,traceback
OUT=r'D:\game design\experiment\Docs\Combat\SwordQiTemplate'
os.makedirs(OUT,exist_ok=True)
report={'checked_at':datetime.datetime.now().isoformat(),'source':'UE 5.8 saved assets and native class defaults','hardware_playtest':False}
try:
    vr_class=unreal.load_class(None,'/Script/experiment.NLVRPlayerCharacter')
    gm_class=unreal.load_class(None,'/Script/experiment.NLVRGameMode')
    vr=unreal.get_default_object(vr_class);gm=unreal.get_default_object(gm_class)
    report['default_vr_pawn']=gm.get_editor_property('default_pawn_class').get_path_name()
    report['native_defaults']={name:vr.get_editor_property(name) for name in ('blade_qi_speed_cm_per_sec','blade_qi_radius_cm','blade_qi_range_cm','blade_qi_muzzle_offset_cm','blade_qi_input_buffer_seconds','blade_qi_minimum_swing_speed_cm_per_sec')}
    report['projectile_class']=vr.get_editor_property('blade_qi_projectile_class').get_path_name()
    definition=unreal.load_asset('/Game/ReversedScale/Combat/DA_PlayerBladeQi')
    report['attack']={'asset':definition.get_path_name(),'id':str(definition.get_editor_property('stable_id')),'damage':definition.get_editor_property('damage'),'cooldown_seconds':definition.get_editor_property('cooldown_seconds')}
    context=unreal.load_asset('/Game/ReversedScale/Player/VR/Input/IMC_NilinVR')
    bindings=[]
    # UE5.8 stores defaults in this struct; the legacy Mappings array is empty.
    for mapping in context.get_editor_property('default_key_mappings').get_editor_property('mappings'):
        action=mapping.get_editor_property('action')
        if action and action.get_name()=='IA_VRBladeQi':
            key=mapping.get_editor_property('key')
            bindings.append({'action':action.get_path_name(),'key':str(key.get_editor_property('key_name'))})
    report['right_trigger_bindings']=bindings
    assert report['default_vr_pawn']=='/Script/experiment.NLVRPlayerCharacter'
    assert report['native_defaults']['blade_qi_input_buffer_seconds']==.25
    assert report['attack']['id'] and report['attack']['damage']>0 and math.isfinite(report['attack']['cooldown_seconds'])
    assert bindings and all('Right' in b['key'] and 'Trigger' in b['key'] for b in bindings)
    report['success']=True
except Exception:
    report['success']=False;report['error']=traceback.format_exc()
finally:
    json.dump(report,open(os.path.join(OUT,'AssetInspection.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
if not report['success']:raise RuntimeError(report['error'])
unreal.log('NILIN_SWORD_QI_ASSETS_OK')
