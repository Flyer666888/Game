"""Import the independent restrained-death candidate; never change gameplay.

Run in the project editor only after reviewing the offline pose/contact report.
NL_DEATH_PREVIEW_MESH may name a same-skeleton shoulder candidate mesh.
"""
import json,os
from pathlib import Path
import unreal

PROJECT=Path(unreal.Paths.project_dir())
OUT=PROJECT/'ArtSource/WuxiaMale/RigPolishV02/Death'
data=json.loads((OUT/'RestrainedDeathPoses.json').read_text(encoding='utf-8'))
contacts=json.loads((OUT/'RestrainedDeathContacts.json').read_text(encoding='utf-8'))
clip=data['clips'][0]
ROOT='/Game/ReversedScale/Characters/WuxiaMale'
DEST=ROOT+'/Animations/Wuxia_Death_Restrained_v02'
SOURCE=ROOT+'/Animations/Wuxia_Death_Grounded'
A=unreal.EditorAssetLibrary
if contacts['state']!='passed' or contacts['minimum_skin_height_cm']<-.005 or contacts['minimum_sword_height_cm']<-.005:
    raise RuntimeError('Offline actual-skin contact evidence did not pass')
if clip['asset']!=DEST or clip['name']!='Wuxia_Death_Restrained_v02':
    raise RuntimeError('This importer is restricted to its new candidate asset')
default_mesh=ROOT+'/SK_WuxiaMale_Shoulder_v02' if A.does_asset_exist(ROOT+'/SK_WuxiaMale_Shoulder_v02') else ROOT+'/SK_WuxiaMale_Combat'
mesh=A.load_asset(os.environ.get('NL_DEATH_PREVIEW_MESH',default_mesh))
if not mesh:raise RuntimeError('A same-skeleton preview mesh is required')
skeleton=mesh.get_editor_property('skeleton')
if skeleton.get_path_name()!=data['skeleton']:raise RuntimeError('Candidate skeleton differs from the current enemy skeleton')
if len(clip['samples'])!=int(clip['frames'])+1:raise RuntimeError('Incomplete pose samples')
animation=A.load_asset(DEST) if A.does_asset_exist(DEST) else A.duplicate_asset(SOURCE,DEST)
if not animation:raise RuntimeError('Could not create independent restrained-death asset')
animation.set_editor_property('enable_root_motion',False)
animation.set_editor_property('force_root_lock',False)
animation.set_editor_property('rate_scale',1.)
controller=animation.controller
morph_names={str(m.get_name()) for m in mesh.get_editor_property('morph_targets')}
curves=dict(clip['morph_curves'])
for name,value in data.get('preview_morph_overrides',{}).items():
    curves.setdefault(name,[{'time':s['time'],'value':float(value)} for s in clip['samples']])
missing=set(curves)-morph_names
empty_allowed={'EnemyDeathRobe_1','EnemyDeathRobe_2','EnemyDeathRobe_3'}
verified_empty={name for name in empty_allowed if name in data.get('morph_deltas',{}) and
                all(abs(float(component))<=1e-8 for delta in data['morph_deltas'][name] for component in delta['delta'])}
if missing-verified_empty:raise RuntimeError('Candidate preview mesh is missing required morphs: '+str(sorted(missing-verified_empty)))
skipped_empty=sorted(missing&verified_empty)
for name in skipped_empty:curves.pop(name)
controller.open_bracket('Restrained death: compact collapse and grounded terminal hold',False)
try:
    controller.set_frame_rate(unreal.FrameRate(numerator=int(data['fps']),denominator=1),False)
    controller.set_number_of_frames(unreal.FrameNumber(value=int(clip['frames'])),False)
    controller.remove_all_curves_of_type(unreal.RawCurveTrackTypes.RCT_FLOAT,False)
    for bone in clip['samples'][0]['local']:
        keys=[s['local'][bone] for s in clip['samples']]
        if not controller.set_bone_track_keys(bone,[unreal.Vector(*k['p']) for k in keys],
                    [unreal.Quat(*k['q']) for k in keys],[unreal.Vector(*k['s']) for k in keys],False):
            raise RuntimeError('Could not author death track '+bone)
    for name,values in curves.items():
        identifier=unreal.AnimationCurveIdentifier();identifier.set_curve_identifier(name,unreal.RawCurveTrackTypes.RCT_FLOAT)
        if not controller.add_curve(identifier,4,False):raise RuntimeError('Could not create curve '+name)
        keys=[unreal.RichCurveKey(time=float(k['time']),value=float(k['value']),interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR) for k in values]
        if not controller.set_curve_keys(identifier,keys,False):raise RuntimeError('Could not author curve '+name)
finally:controller.close_bracket(False)
for track in unreal.AnimationLibrary.get_animation_notify_track_names(animation):
    unreal.AnimationLibrary.remove_animation_notify_events_by_track(animation,track)
if not A.save_loaded_asset(animation,False):raise RuntimeError('Could not save restrained death candidate')
opts=unreal.AnimPoseEvaluationOptions();opts.evaluation_type=unreal.AnimDataEvalType.COMPRESSED;opts.optional_skeletal_mesh=mesh
checks=[];runtime_samples=[]
def record(transform):
    p,q,s=transform.translation,transform.rotation,transform.scale3d
    return {'p':[p.x,p.y,p.z],'q':[q.x,q.y,q.z,q.w],'s':[s.x,s.y,s.z]}
for sample in clip['samples']:
    seconds=float(sample['time'])
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(animation,seconds,opts)
    bones={};errors=[];runtime={'time':seconds,'local':{},'world':{},'morph_weights':{}}
    for bone in sample['local']:
        runtime['local'][bone]=record(unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.LOCAL))
        transform=unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD)
        runtime['world'][bone]=record(transform)
        position=[transform.translation.x,transform.translation.y,transform.translation.z]
        bones[bone]=position
        errors.append(sum((a-b)**2 for a,b in zip(position,sample['world'][bone]['p']))**.5)
    for name in curves:
        runtime['morph_weights'][name]=float(unreal.AnimPoseExtensions.get_curve_weight(pose,name))
    for name in skipped_empty:runtime['morph_weights'][name]=0.
    runtime_samples.append(runtime)
    checks.append({'time':seconds,'maximum_bone_position_error_cm':max(errors),'bones_cm':bones})
runtime_data=dict(data);runtime_clip=dict(clip);runtime_clip['samples']=runtime_samples;runtime_data['clips']=[runtime_clip]
runtime_data['mesh']=mesh.get_path_name();runtime_data['evaluation']='UE compressed animation, every authored frame'
(OUT/'RestrainedDeathRuntimePoses.json').write_text(json.dumps(runtime_data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
report={'asset':animation.get_path_name(),'source_asset_preserved':SOURCE,'preview_mesh':mesh.get_path_name(),
        'duration_seconds':animation.get_play_length(),'final_hold_seconds':clip['timing']['final_hold_seconds'],
        'morph_curves':list(curves),'skipped_verified_zero_delta_curves':skipped_empty,'compressed_pose_checks':checks,
        'maximum_bone_position_error_cm':max(c['maximum_bone_position_error_cm'] for c in checks),
        'scope':'Candidate asset only. No Blueprint, level, CDO, runtime transition or original asset was modified.'}
(OUT/'RestrainedDeathImported.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if abs(animation.get_play_length()-float(clip['duration']))>.001:raise RuntimeError('Unexpected imported animation length')
if report['maximum_bone_position_error_cm']>.25:raise RuntimeError('Compressed candidate diverged from authored contact pose')
unreal.log('RESTRAINED_DEATH_CANDIDATE_SAVED '+DEST)
