"""Separate D's ground travel from its body pose, preserving their combined motion."""
import unreal,json,hashlib,math
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/PackDIntegration1104'
REVIEW=P/'Docs/Gameplay/PackSlashReview1104';A=unreal.EditorAssetLibrary
BASE='/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07'
DEST=BASE+'/PackCombat/D'
SOURCE=BASE+'/PackSlashCandidates/V3/Pack_Anim_CSATLI_04'
CLIP=DEST+'/A_Wuxia_Attack_PackD'
CURVE=DEST+'/CV_PackD_GroundTravel'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
mesh=A.load_asset(BASE+'/SK_WuxiaMale_Native_v07');source=A.load_asset(SOURCE)
assert mesh and source
protected=[mesh,mesh.skeleton,source,A.load_asset(BASE+'/PackSlashCandidates/V3/Pack_Anim_CSATLI_03'),A.load_asset('/Game/Animations/Sword/Anim_CSATLI_04')]
def hashes():
    return {a.get_path_name():hashlib.sha256((P/'Content'/(a.get_path_name().split('.')[0].removeprefix('/Game/')+'.uasset')).read_bytes()).hexdigest() for a in protected}
before=hashes()
assert not A.does_asset_exist(CLIP),'New gameplay clip already exists; inspect before replacing.'
anim=A.duplicate_asset(SOURCE,CLIP);assert anim
source_data=json.loads((REVIEW/'SourceMotion.json').read_text())
source_motion=next(c for c in source_data['clips'] if c['name']=='Anim_CSATLI_04')
ratio=json.loads((REVIEW/'RetargetDirectionAuditV3.json').read_text())['target_to_source_pelvis_height_ratio']
duration=source.get_play_length();n=unreal.AnimationLibrary.get_num_frames(source)
assert len(source_motion['frames'])==n+1
initial=source_motion['frames'][0]['bones']['root']['p']
ground=[]
for i,frame in enumerate(source_motion['frames']):
    r=frame['bones']['root'];p=r['p']
    assert abs(r['q'][2])<.001 and abs(r['q'][0])+abs(r['q'][1])<.001,'Unexpected source root rotation'
    ground.append(unreal.Vector((p[1]-initial[1])*ratio,-(p[0]-initial[0])*ratio,0))
csv=O/'CV_PackD_GroundTravel.csv'
csv.write_text('\n'.join(f'{duration*i/n:.9f},{g.x:.9f},{g.y:.9f},0' for i,g in enumerate(ground))+'\n',encoding='utf-8')
factory=unreal.CSVImportFactory()
settings=unreal.CSVImportSettings()
settings.import_type=unreal.CSVImportType.ECSV_CURVE_VECTOR
settings.import_curve_interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR
factory.automated_import_settings=settings
task=unreal.AssetImportTask();task.filename=str(csv);task.destination_path=DEST
task.destination_name=CURVE.rsplit('/',1)[-1];task.factory=factory
task.automated=True;task.replace_existing=False;task.save=True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
curve=A.load_asset(CURVE);assert isinstance(curve,unreal.CurveVector),(task.imported_object_paths,CURVE)
opt=unreal.AnimPoseEvaluationOptions();opt.evaluation_type=unreal.AnimDataEvalType.RAW
opt.optional_skeletal_mesh=mesh;opt.should_retarget=False;opt.extract_root_motion=False
roots=[]
for i in range(n+1):
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(source,duration*i/n,opt)
    roots.append(unreal.AnimPoseExtensions.get_bone_pose(pose,'Hips',unreal.AnimPoseSpaces.LOCAL))
controller=anim.controller;controller.open_bracket('Separate authored ground travel for swept capsule movement',False)
try:
    assert controller.set_bone_track_keys('Hips',[r.translation-g for r,g in zip(roots,ground)],
        [r.rotation for r in roots],[r.scale3d for r in roots],False)
finally:controller.close_bracket(False)
anim.set_editor_property('enable_root_motion',False)
anim.set_editor_property('force_root_lock',False)
anim.set_preview_skeletal_mesh(mesh)
# Gameplay damage events are added once timing is selected; originals stay untouched.
for track in unreal.AnimationLibrary.get_animation_notify_track_names(anim):
    unreal.AnimationLibrary.remove_animation_notify_events_by_track(anim,track)
assert A.save_loaded_asset(anim,False)
max_error=0.;max_curve_error=0.
bones=['Hips','Head','RightHand','LeftHand','RightFoot','LeftFoot']
for i in range(2*n+1):
    t=duration*i/(2*n)
    original=unreal.AnimPoseExtensions.get_anim_pose_at_time(source,t,opt)
    actual=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,t,opt)
    delta=curve.get_vector_value(t)
    for bone in bones:
        a=unreal.AnimPoseExtensions.get_bone_pose(original,bone,unreal.AnimPoseSpaces.WORLD)
        b=unreal.AnimPoseExtensions.get_bone_pose(actual,bone,unreal.AnimPoseSpaces.WORLD)
        max_error=max(max_error,(a.translation-b.translation-delta).length())
    if i%2==0:max_curve_error=max(max_curve_error,(delta-ground[i//2]).length())
assert max_error<.02 and max_curve_error<.002,(max_error,max_curve_error)
assert hashes()==before,'Protected original asset changed'
report={'state':'prepared','animation':anim.get_path_name(),'source':source.get_path_name(),'root_curve':curve.get_path_name(),
        'duration':duration,'frames':n,'root_distance_cm':ground[-1].x,'reconstruction_max_error_cm':max_error,
        'curve_key_max_error_cm':max_curve_error,'protected_sha256':before,
        'note':'Only new gameplay Hips planar translation split. Actor curve plus body pose reconstructs selected D; rotations/scales/timing unchanged.'}
(O/'GameplayDPrepared.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
