"""Import reviewed compact sword rotations onto an independent animation copy."""
import hashlib,json
from pathlib import Path
import unreal
PROJECT=Path(unreal.Paths.project_dir()).resolve()
OUT=PROJECT/'ArtSource/WuxiaMale/RigPolishV03/Attack'
A=unreal.EditorAssetLibrary
data=json.loads((OUT/'CompactAttackPoses.json').read_text(encoding='utf-8'))
offline=json.loads((OUT/'CompactAttackMetrics.json').read_text(encoding='utf-8'))
clip=data['clips'][0]
DEST='/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Compact_v03'
SOURCE='/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Upright_v01'
assert clip['asset']==DEST and clip['source_asset']==SOURCE
assert offline['unchanged_lower_body_error']==offline['unchanged_local_translation_scale_error']==0
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None,'Stop PIE first'
source=A.load_asset(SOURCE);mesh=A.load_asset('/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Shoulder_v02')
assert source and mesh and source.get_editor_property('skeleton')==mesh.get_editor_property('skeleton')
source_file=PROJECT/'Content'/(SOURCE.removeprefix('/Game/')+'.uasset')
source_hash=hashlib.sha256(source_file.read_bytes()).hexdigest()
def signature(anim):
    model=anim.controller.get_model_interface();fps=model.get_frame_rate();events=[]
    for track in unreal.AnimationLibrary.get_animation_notify_track_names(anim):
        for event in unreal.AnimationLibrary.get_animation_notify_events_for_track(anim,track):
            state=event.get_editor_property('notify_state_class');notify=event.get_editor_property('notify')
            events.append({'track':str(track),'name':str(event.get_editor_property('notify_name')),
                'start':unreal.AnimationLibrary.get_anim_notify_event_trigger_time(event),
                'duration':unreal.AnimationLibrary.get_anim_notify_event_duration(event),
                'state_class':state.get_class().get_path_name() if state else None,
                'notify_class':notify.get_class().get_path_name() if notify else None})
    return {'duration':anim.get_play_length(),'frame_rate':[fps.numerator,fps.denominator],
        'frames':model.get_number_of_frames(),'keys':model.get_number_of_keys(),
        'tracks':sorted(map(str,model.get_bone_track_names())),
        'root_motion':anim.get_editor_property('enable_root_motion'),'rate_scale':anim.get_editor_property('rate_scale'),
        'notifies':events,'skeleton':anim.get_editor_property('skeleton').get_path_name()}
before=signature(source)
assert before['frames']==70 and before['keys']==len(clip['samples'])==71
assert abs(before['duration']-clip['duration'])<.0001
animation=A.load_asset(DEST) if A.does_asset_exist(DEST) else A.duplicate_asset(SOURCE,DEST)
assert animation
controller=animation.controller;controller.open_bracket('Compact frontal sword cut with preserved attack notify',False)
try:
    for bone in data['changed_tracks']:
        keys=[sample['local'][bone] for sample in clip['samples']]
        assert controller.set_bone_track_keys(bone,[unreal.Vector(*key['p']) for key in keys],
            [unreal.Quat(*key['q']) for key in keys],[unreal.Vector(*key['s']) for key in keys],False),bone
finally:controller.close_bracket(False)
assert signature(animation)==before,'Attack metadata/notify changed'
animation.set_preview_skeletal_mesh(mesh)
assert A.save_loaded_asset(animation,False)
assert hashlib.sha256(source_file.read_bytes()).hexdigest()==source_hash,'Original attack changed'
opts=unreal.AnimPoseEvaluationOptions();opts.evaluation_type=unreal.AnimDataEvalType.COMPRESSED;opts.optional_skeletal_mesh=mesh
opts.should_retarget=False;opts.extract_root_motion=False
def record(t):
    p,q,s=t.translation,t.rotation,t.scale3d
    return {'p':[p.x,p.y,p.z],'q':[q.x,q.y,q.z,q.w],'s':[s.x,s.y,s.z]}
def distance(a,b):return sum((x-y)**2 for x,y in zip(a,b))**.5
runtime=[];rows=[]
for sample in clip['samples']:
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(animation,sample['time'],opts)
    original=unreal.AnimPoseExtensions.get_anim_pose_at_time(source,sample['time'],opts)
    assert unreal.AnimPoseExtensions.is_valid(pose)
    item={'time':sample['time'],'local':{},'world':{}}
    errors=[];feet=[]
    for bone in sample['local']:
        item['local'][bone]=record(unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.LOCAL))
        item['world'][bone]=record(unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD))
        errors.append(distance(item['world'][bone]['p'],sample['world'][bone]['p']))
        if bone in ('root','pelvis','thigh_l','thigh_r','calf_l','calf_r','foot_l','foot_r','ball_l','ball_r'):
            old=record(unreal.AnimPoseExtensions.get_bone_pose(original,bone,unreal.AnimPoseSpaces.WORLD))
            feet.append(distance(item['world'][bone]['p'],old['p']))
    runtime.append(item);rows.append({'time':sample['time'],'max_imported_bone_position_error_cm':max(errors),'max_lower_body_position_error_cm':max(feet)})
max_error=max(r['max_imported_bone_position_error_cm'] for r in rows)
max_foot=max(r['max_lower_body_position_error_cm'] for r in rows)
assert max_error<.25 and max_foot<.1,(max_error,max_foot)
runtime_data=dict(data);runtime_clip=dict(clip);runtime_clip['samples']=runtime;runtime_data['clips']=[runtime_clip]
runtime_data['mesh']=mesh.get_path_name();runtime_data['evaluation']='UE compressed animation, all 71 frames'
(OUT/'CompactAttackRuntimePoses.json').write_text(json.dumps(runtime_data,separators=(',',':')),encoding='utf-8')
report={'state':'passed','asset':animation.get_path_name(),'source':source.get_path_name(),'source_sha256':source_hash,
    'mesh':mesh.get_path_name(),'metadata_unchanged':True,'source_signature':before,'candidate_signature':signature(animation),
    'changed_tracks':data['changed_tracks'],'maximum_imported_bone_error_cm':max_error,'maximum_lower_body_error_cm':max_foot,
    'compressed_pose_checks':rows,'scope':'Independent candidate only. Original animation, mesh, level and BP references unchanged.'}
(OUT/'CompactAttackImported.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('COMPACT_ATTACK_IMPORTED '+DEST)
