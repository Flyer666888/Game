"""Create isolated grip variants; originals, skeleton and approved body tracks stay intact."""
import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/HandGripPolish1104'
A=unreal.EditorAssetLibrary;L=unreal.AnimationLibrary;E=unreal.AnimPoseExtensions
C=json.loads((O/'FitCandidate.json').read_text(encoding='utf-8-sig'))
samples=json.loads((O/'PoseSamples.json').read_text(encoding='utf-8-sig'))
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
mesh=A.load_asset(samples['mesh']);opts=unreal.AnimPoseEvaluationOptions()
opts.evaluation_type=unreal.AnimDataEvalType.RAW;opts.optional_skeletal_mesh=mesh
opts.should_retarget=False;opts.extract_root_motion=False
fingers=C['finger_local_quaternions'];assert fingers and all(b.startswith('RightHandIndex') or b.startswith('RightHandThumb') for b in fingers)
base='/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/HandGripPolish/'+C['id']
rows={};checks={'protected_originals_unchanged':False}
for key,data in samples['clips'].items():
    source=A.load_asset(data['asset']);dest=base+'/A_Wuxia_'+key.title()+'_'+C['id']
    assert not A.does_asset_exist(dest),dest
    anim=A.duplicate_asset(data['asset'],dest);assert anim
    n=L.get_num_frames(source);duration=source.get_play_length()
    poses=[E.get_anim_pose_at_time(source,duration*i/n,opts) for i in range(n+1)]
    edits=dict(fingers);wrist=C.get('wrist_post_rotation_xyzw',{}).get(key)
    if wrist:edits['RightHand']=None
    controller=anim.controller;controller.open_bracket('Fit the existing hand to the actual sword handle',False)
    try:
        for bone,rotation in edits.items():
            transforms=[E.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.LOCAL) for pose in poses]
            rotations=[t.rotation*unreal.Quat(*wrist) for t in transforms] if bone=='RightHand' else [unreal.Quat(*rotation)]*(n+1)
            assert controller.set_bone_track_keys(bone,[t.translation for t in transforms],rotations,[t.scale3d for t in transforms],False)
    finally:controller.close_bracket(False)
    anim.set_preview_skeletal_mesh(mesh);assert A.save_loaded_asset(anim,False)
    max_p=0.;max_q=0.;max_s=0.
    for i,original in enumerate(poses):
        actual=E.get_anim_pose_at_time(anim,duration*i/n,opts)
        for bone in E.get_bone_names(original):
            before=E.get_bone_pose(original,bone,unreal.AnimPoseSpaces.LOCAL)
            after=E.get_bone_pose(actual,bone,unreal.AnimPoseSpaces.LOCAL)
            max_p=max(max_p,(before.translation-after.translation).length())
            max_s=max(max_s,(before.scale3d-after.scale3d).length())
            if str(bone) not in edits:
                qa=before.rotation;qb=after.rotation
                dot=abs(qa.x*qb.x+qa.y*qb.y+qa.z*qb.z+qa.w*qb.w)
                max_q=max(max_q,abs(1-dot))
    assert max_p<.001 and max_s<.001 and max_q<.00001,(key,max_p,max_s,max_q)
    assert abs(anim.get_play_length()-duration)<.0001
    rows[key]={'asset':anim.get_path_name(),'source':source.get_path_name(),'duration':duration,'frames':n,
               'max_local_position_error':max_p,'max_local_scale_error':max_s,'max_unchanged_rotation_error':max_q,
               'edited_bones':list(edits),'notify_count':len(L.get_animation_notify_events(anim))}
for path,sha in samples['protected_sha256'].items():
    file=P/'Content'/(path.split('.')[0].removeprefix('/Game/')+'.uasset')
    assert hashlib.sha256(file.read_bytes()).hexdigest()==sha,path
checks['protected_originals_unchanged']=True
(O/('Prepared_'+C['id']+'.json')).write_text(json.dumps({'state':'prepared','candidate':C,'clips':rows,'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
