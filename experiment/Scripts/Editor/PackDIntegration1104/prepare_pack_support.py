"""Prepare package idle/walk that share D's source hand orientation.

Only new Support_ clips are saved. Reuses the validated V3 retargeter read-only;
the native mesh, skeleton, original animations and IK configuration are protected.
Native local bind units are restored after the retarget processor's scale bake.
Planar source root travel is removed so CharacterMovement drives the walk capsule.
"""
import hashlib,json,math
from pathlib import Path
import unreal

P=Path(unreal.Paths.project_dir()).resolve()
O=P/'Docs/Gameplay/PackDIntegration1104';O.mkdir(parents=True,exist_ok=True)
A=unreal.EditorAssetLibrary
BASE='/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07'
DEST=BASE+'/PackCombat/Support'
RTG=BASE+'/PackSlashCandidates/V3/RetargetSetup/RTG_Pack_Native41_1104'
SPECS={'idle':'Anim_CSST','walk':'Anim_CS_W_FWD'}
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None

def rec(t):
    return {'p':[t.translation.x,t.translation.y,t.translation.z],
            'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w],
            's':[t.scale3d.x,t.scale3d.y,t.scale3d.z]}

def qmul(a,b):
    x,y,z,w=a;X,Y,Z,W=b
    return (w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z)

def quat_tuple(q):return (q.x,q.y,q.z,q.w)
def quat(values):return unreal.Quat(x=values[0],y=values[1],z=values[2],w=values[3])
def asset_hashes(objects):
    result={}
    for obj in objects:
        package=obj.get_path_name().split('.')[0]
        path=P/'Content'/(package.removeprefix('/Game/')+'.uasset')
        assert path.is_file(),str(path)
        result[package]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result

source_mesh=A.load_asset('/Game/Character/Mesh/SK_Mannequin')
target_mesh=A.load_asset(BASE+'/SK_WuxiaMale_Native_v07')
retargeter=A.load_asset(RTG)
assert source_mesh and target_mesh and retargeter
source_skeleton=source_mesh.get_editor_property('skeleton')
target_skeleton=target_mesh.get_editor_property('skeleton')
rc=unreal.IKRetargeterController.get_controller(retargeter)
source_rig=rc.get_ik_rig(unreal.RetargetSourceOrTarget.SOURCE)
target_rig=rc.get_ik_rig(unreal.RetargetSourceOrTarget.TARGET)
assert source_rig and target_rig
fk_settings=rc.get_op_controller(1).get_settings()
assert all(c.rotation_mode==unreal.FKChainRotationMode.ONE_TO_ONE for c in fk_settings.chains_to_retarget)
originals={kind:A.load_asset('/Game/Animations/Sword/'+name) for kind,name in SPECS.items()}
assert all(originals.values())
protected=[source_mesh,target_mesh,source_skeleton,target_skeleton,retargeter,source_rig,target_rig,*originals.values()]
before=asset_hashes(protected)
for name in SPECS.values():
    assert not A.does_asset_exist(DEST+'/Support_'+name),'Support clip already exists; inspect before replacing: '+name

LOCAL=unreal.AnimPoseSpaces.LOCAL;WORLD=unreal.AnimPoseSpaces.WORLD
reference=unreal.AnimPoseExtensions.get_reference_pose(target_skeleton)
names=list(unreal.AnimPoseExtensions.get_bone_names(reference))
assert len(names)==41
local_ref={str(b):unreal.AnimPoseExtensions.get_bone_pose(reference,b,LOCAL) for b in names}
world_ref={str(b):unreal.AnimPoseExtensions.get_bone_pose(reference,b,WORLD) for b in names}
assert abs(local_ref['Hips'].scale3d.x-100)<.01
source_ref=unreal.AnimPoseExtensions.get_reference_pose(source_skeleton)
source_pelvis=unreal.AnimPoseExtensions.get_bone_pose(source_ref,'pelvis',WORLD).translation.z
ratio=world_ref['Hips'].translation.z/source_pelvis
assert abs(ratio-1.0886276993004262)<1e-4,'Reference rig differs from approved V3'
half=math.sqrt(.5);yaw_minus_90=(0,0,-half,half)

def options(mesh):
    o=unreal.AnimPoseEvaluationOptions();o.evaluation_type=unreal.AnimDataEvalType.RAW
    o.optional_skeletal_mesh=mesh;o.should_retarget=False;o.extract_root_motion=False
    return o
source_options=options(source_mesh);target_options=options(target_mesh)
inputs=unreal.IKRetargetBatchOperationInputs()
inputs.assets_to_retarget=[A.find_asset_data('/Game/Animations/Sword/'+n) for n in SPECS.values()]
inputs.source_mesh=source_mesh;inputs.target_mesh=target_mesh;inputs.ik_retarget_asset=retargeter
inputs.target_path=DEST;inputs.prefix='Support_';inputs.include_referenced_assets=False
inputs.overwrite_existing_files=False
result=unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
anims=[d.get_asset() for d in result if isinstance(d.get_asset(),unreal.AnimSequence)]
assert len(anims)==2
report={'state':'preparing','mesh':target_mesh.get_path_name(),'skeleton':target_skeleton.get_path_name(),
        'retargeter':RTG,'retargeter_modified':False,'source_to_native_pelvis_ratio':ratio,
        'grip_reference':'Docs/Gameplay/PackSlashReview1104/GripAuditConclusion.json',
        'clips':{},'protected_sha256_before':before,
        'note':'Original source performance and joint rotations retained; planar ground origin/travel removed from Hips, preserving vertical bob and anatomical pelvis offsets. Capsule locomotion supplies walk travel.'}
pose_report={'mesh':target_mesh.get_path_name(),'clips':{}}

for anim in anims:
    source_name=anim.get_name().removeprefix('Support_')
    kind=next(k for k,n in SPECS.items() if n==source_name)
    original=originals[kind]
    assert anim.get_path_name().startswith(DEST+'/')
    assert anim.get_editor_property('skeleton')==target_skeleton
    duration=anim.get_play_length();count=unreal.AnimationLibrary.get_num_frames(anim)
    assert duration>0 and count>0 and abs(duration-original.get_play_length())<.0001
    keys={str(b):[] for b in names};source_roots=[];ground=[];source_pelvis_keys=[]
    for i in range(count+1):
        t=duration*i/count
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,t,target_options)
        source_pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(original,t,source_options)
        assert unreal.AnimPoseExtensions.is_valid(pose) and unreal.AnimPoseExtensions.is_valid(source_pose)
        r=unreal.AnimPoseExtensions.get_bone_pose(source_pose,'root',WORLD)
        source_roots.append(rec(r))
        ground.append(unreal.Vector(r.translation.y*ratio,-r.translation.x*ratio,0))
        source_pelvis_keys.append(unreal.AnimPoseExtensions.get_bone_pose(source_pose,'pelvis',WORLD).translation)
        for b in names:keys[str(b)].append(unreal.AnimPoseExtensions.get_bone_pose(pose,b,LOCAL))
    uncorrected_scale=rec(keys['Hips'][0])['s']
    q0=source_roots[0]['q']
    root_rotation_change=max(math.degrees(2*math.acos(min(1,abs(sum(a*b for a,b in zip(q0,r['q'])))))) for r in source_roots)
    assert root_rotation_change<.1,'Unexpected turning locomotion; do not silently remove root yaw'
    controller=anim.controller
    existing_tracks={str(n) for n in unreal.AnimationLibrary.get_animation_track_names(anim)}
    controller.open_bracket('Restore native units and separate capsule locomotion',False)
    try:
        for b in names:
            name=str(b);values=keys[name]
            if name=='Hips':
                positions=[unreal.Vector(t.translation.y,-t.translation.x,t.translation.z)-g for t,g in zip(values,ground)]
                rotations=[quat(qmul(yaw_minus_90,quat_tuple(t.rotation))) for t in values]
            else:
                positions=[local_ref[name].translation for _ in values]
                rotations=[t.rotation for t in values]
            scales=[local_ref[name].scale3d for _ in values]
            if name not in existing_tracks:controller.add_bone_curve(b,False)
            assert controller.set_bone_track_keys(b,positions,rotations,scales,False),name
    finally:controller.close_bracket(False)
    anim.set_editor_property('enable_root_motion',False)
    anim.set_editor_property('force_root_lock',False)
    anim.set_preview_skeletal_mesh(target_mesh)
    assert A.save_loaded_asset(anim,False)
    frames=[];max_pelvis_error=0.
    for i in range(count+1):
        t=duration*i/count
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,t,target_options)
        bones={str(b):rec(unreal.AnimPoseExtensions.get_bone_pose(pose,b,WORLD)) for b in names}
        assert all(math.isfinite(x) for bone in bones.values() for group in bone.values() for x in group)
        assert max(abs(x-100) for x in bones['Hips']['s'])<.01
        sp=source_pelvis_keys[i];g=ground[i]
        expected=[sp.y*ratio-g.x,-sp.x*ratio-g.y,sp.z*ratio]
        max_pelvis_error=max(max_pelvis_error,math.dist(expected,bones['Hips']['p']))
        frames.append({'t':t,'ground_removed_cm':[g.x,g.y,g.z],'bones':bones})
    assert max_pelvis_error<.1,'Body pelvis motion no longer matches source relative to ground root'
    delta=ground[-1]-ground[0]
    planar_distance=math.hypot(delta.x,delta.y)
    source_speed=planar_distance/duration
    if kind=='walk':
        assert delta.x>1 and source_speed>10,'Forward walk must contain measurable authored root travel'
        assert abs(delta.y)<max(2,abs(delta.x)*.05),'Forward walk has unexpected lateral drift'
        report['walk_animation_speed']=source_speed
    hips=[f['bones']['Hips']['p'] for f in frames]
    feet={name:[f['bones'][name]['p'][2] for f in frames] for name in ['LeftFoot','RightFoot','LeftToeBase','RightToeBase']}
    row={'asset':anim.get_path_name(),'source':original.get_path_name(),'duration':duration,'frames':count,
         'skeleton':target_skeleton.get_path_name(),'root_scale_before_repair':uncorrected_scale,
         'root_scale_after_repair':frames[0]['bones']['Hips']['s'],
         'source_ground_origin_cm':[ground[0].x,ground[0].y,ground[0].z],
         'removed_ground_delta_cm':[delta.x,delta.y,delta.z],
         'source_ground_speed_cm_s':source_speed,'source_root_rotation_change_degrees':root_rotation_change,
         'preserved_pelvis_relative_to_ground_max_error_cm':max_pelvis_error,
         'in_place_hips_range_cm':[max(p[j] for p in hips)-min(p[j] for p in hips) for j in range(3)],
         'foot_bone_height_ranges_cm':{name:[min(v),max(v)] for name,v in feet.items()},
         'loop_hips_position_gap_cm':math.dist(hips[0],hips[-1])}
    report['clips'][kind]=row;pose_report['clips'][kind]=dict(row,samples=frames)

after=asset_hashes(protected)
assert before==after,'Protected source/rig asset changed'
assert set(report['clips'])=={'idle','walk'}
report.update({'state':'prepared','protected_sha256_after':after,'all_protected_assets_unchanged':True})
(O/'SupportPrepared.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'SupportMotion.json').write_text(json.dumps(pose_report,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
unreal.log('PACK_SUPPORT_READY '+str(O/'SupportPrepared.json'))
