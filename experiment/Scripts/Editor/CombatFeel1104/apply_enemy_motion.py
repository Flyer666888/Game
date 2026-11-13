"""Import independent v06 enemy clips and apply to four sword archetypes.
Run in an idle Unreal editor after bake_enemy_motion.py. Original clips stay intact.
"""
import hashlib, json, shutil
from pathlib import Path
import unreal

P = Path(unreal.Paths.project_dir()).resolve()
OUT = P/'Docs/Gameplay/CombatFeel1104'
DATA = json.loads((OUT/'EnemyMotionPoses.json').read_text(encoding='utf-8'))
A = unreal.EditorAssetLibrary
L = unreal.AnimationLibrary
ROOT = '/Game/ReversedScale/Characters/WuxiaMale/'
SOURCES = {'attack':ROOT+'Animations/Wuxia_Attack_Sword_Quick_v05',
           'chase':ROOT+'Animations/Wuxia_Walk_Sword_Upright_v01'}
DESTS = {'attack':ROOT+'Animations/Wuxia_Attack_Sword_Flow_v06',
         'chase':ROOT+'Animations/Wuxia_Chase_Sword_v06'}
MESH = A.load_asset(ROOT+'SK_WuxiaMale_Hands_v04')
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None, 'Stop PIE before asset authoring'
assert MESH

def file_for(path): return P/'Content'/(path.removeprefix('/Game/')+'.uasset')
def backup(path):
    src=file_for(path);dest=OUT/'Backups'/'Content'/src.relative_to(P/'Content')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if src.exists() and not dest.exists():shutil.copy2(src,dest)
def hash_asset(path):return hashlib.sha256(file_for(path).read_bytes()).hexdigest()
hashes={k:hash_asset(p) for k,p in SOURCES.items()}
assets={};reports={}
for kind in ('attack','chase'):
    clip=DATA[kind];src=A.load_asset(SOURCES[kind]);assert src
    assert MESH.get_editor_property('skeleton')==src.get_editor_property('skeleton')
    if A.does_asset_exist(DESTS[kind]):backup(DESTS[kind])
    dest=A.load_asset(DESTS[kind]) if A.does_asset_exist(DESTS[kind]) else A.duplicate_asset(SOURCES[kind],DESTS[kind])
    opts=unreal.AnimPoseEvaluationOptions()
    opts.evaluation_type=unreal.AnimDataEvalType.COMPRESSED
    opts.optional_skeletal_mesh=MESH;opts.should_retarget=False;opts.extract_root_motion=False
    times=[s['time'] for s in clip['samples']]
    original_poses=[unreal.AnimPoseExtensions.get_anim_pose_at_time(src,t,opts) for t in times]
    controller=dest.controller;model=src.controller.get_model_interface()
    curve_names=L.get_animation_curve_names(src,unreal.RawCurveTrackTypes.RCT_FLOAT)
    assert not L.get_animation_curve_names(src,unreal.RawCurveTrackTypes.RCT_TRANSFORM)
    controller.open_bracket('Body-led sword cut and faster planted pursuit',False)
    try:
        controller.set_frame_rate(unreal.FrameRate(numerator=clip['fps'],denominator=1),False)
        controller.set_number_of_frames(unreal.FrameNumber(value=len(times)-1),False)
        for bone in model.get_bone_track_names():
            name=str(bone)
            if name in clip['samples'][0]['local']:
                keys=[s['local'][name] for s in clip['samples']]
                p=[unreal.Vector(*k['p']) for k in keys]
                q=[unreal.Quat(*k['q']) for k in keys]
                scale=[unreal.Vector(*k['s']) for k in keys]
            else:
                keys=[unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.LOCAL) for pose in original_poses]
                p=[k.translation for k in keys];q=[k.rotation for k in keys];scale=[k.scale3d for k in keys]
            assert controller.set_bone_track_keys(bone,p,q,scale,False),name
        for name in curve_names:
            identifier=unreal.AnimationCurveIdentifier()
            identifier.set_curve_identifier(name,unreal.RawCurveTrackTypes.RCT_FLOAT)
            keys=[unreal.RichCurveKey(time=t,value=unreal.AnimPoseExtensions.get_curve_weight(pose,name),
                interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR) for t,pose in zip(times,original_poses)]
            assert controller.set_curve_keys(identifier,keys,False)
    finally:controller.close_bracket(False)
    if kind=='attack':
        tracks=L.get_animation_notify_track_names(dest)
        assert tracks
        for track in tracks:L.remove_animation_notify_events_by_track(dest,track)
        start,end=clip['notify']
        assert L.add_animation_notify_state_event(dest,tracks[0],start,end-start,unreal.NLEnemyAttackWindowNotifyState)
    dest.set_preview_skeletal_mesh(MESH)
    assert abs(dest.get_play_length()-clip['duration'])<.001
    assert A.save_loaded_asset(dest,False)
    max_error=0
    for sample in clip['samples']:
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(dest,sample['time'],opts)
        assert unreal.AnimPoseExtensions.is_valid(pose)
        for bone in ('pelvis','head','hand_l','hand_r','foot_l','foot_r'):
            actual=unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD).translation
            expected=unreal.Vector(*sample['world'][bone]['p'])
            max_error=max(max_error,(actual-expected).length())
    assert max_error<.5, (kind,'Compressed pose import error',max_error)
    assets[kind]=dest
    reports[kind]={'asset':dest.get_path_name(),'duration':dest.get_play_length(),
        'maximum_import_error_cm':max_error,'frames':len(times)}

rows=[]
for key,speed,factor in (('sword',310.,1.),('GM01',285.,1.2),('GM04',285.,1.2),('boss',290.,1.2)):
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    backup(path)
    bp=A.load_asset(path);default=unreal.get_default_object(A.load_blueprint_class(path))
    brain=default.get_enemy_brain();movement=default.get_component_by_class(unreal.CharacterMovementComponent)
    before={'speed':movement.get_editor_property('max_walk_speed'),
        'attack':default.get_editor_property('attack_animation').get_path_name(),
        'walk':default.get_editor_property('walk_animation').get_path_name()}
    default.set_editor_property('attack_animation',assets['attack'])
    default.set_editor_property('walk_animation',assets['chase'])
    default.set_editor_property('walk_animation_speed',122.815*DATA['chase']['stride_scale'])
    movement.set_editor_property('max_walk_speed',speed)
    movement.set_editor_property('max_acceleration',1500.)
    movement.set_editor_property('braking_deceleration_walking',1800.)
    movement.set_editor_property('rotation_rate',unreal.Rotator(yaw=420.))
    movement.set_editor_property('avoidance_consideration_radius',220.)
    start,end=DATA['attack']['notify']
    for prop,value in zip(('telegraph_seconds','attack_seconds','recover_seconds'),
                          (start*factor,(end-start)*factor,(1.5-end)*factor)):
        brain.set_editor_property(prop,value)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    check=unreal.get_default_object(A.load_blueprint_class(path))
    assert check.get_editor_property('attack_animation')==assets['attack']
    assert check.get_editor_property('walk_animation')==assets['chase']
    assert abs(check.get_component_by_class(unreal.CharacterMovementComponent).get_editor_property('max_walk_speed')-speed)<.01
    assert A.save_loaded_asset(bp,False)
    rows.append({'enemy':key,'before':before,'chase_speed_cm_s':speed,'full_attack_seconds':1.5*factor})
assert hashes=={k:hash_asset(p) for k,p in SOURCES.items()},'Source clips changed'
(OUT/'EnemyAssetsApplied.json').write_text(json.dumps({'state':'passed','clips':reports,'enemies':rows,
    'offline_metrics':DATA['metrics'],'note':'Compressed poses verified; gameplay contacts require runtime probe.'},indent=2),encoding='utf-8')
unreal.log('ENEMY_MOTION_V06_APPLIED')
