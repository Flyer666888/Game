import unreal,json,hashlib
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/SlashRevision1104'
A=unreal.EditorAssetLibrary
data=json.loads((O/'NativeEnemiesApplied.json').read_text())
mesh=A.load_asset(data['mesh']);clips={k:A.load_asset(v['asset']) for k,v in data['clips'].items()}
rows=[]
for key in ('sword','GM01','GM04','boss'):
    default=unreal.get_default_object(A.load_blueprint_class('/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key))
    assert default.enemy_skeletal_mesh==mesh
    assert str(default.sword_attach_bone)=='RightHand'
    component=default.get_component_by_class(unreal.SkeletalMeshComponent)
    assert abs(component.get_editor_property('relative_rotation').yaw)<.01
    for prop,kind in (('attack_animation','attack'),('idle_animation','idle'),('walk_animation','walk'),
                      ('hit_reaction_animation','hit'),('death_animation','death'),('cast_animation','cast')):
        assert default.get_editor_property(prop)==clips[kind]
        assert clips[kind].get_editor_property('skeleton')==mesh.skeleton
    speed=default.get_component_by_class(unreal.CharacterMovementComponent).get_editor_property('max_walk_speed')
    assert speed>=280
    rows.append({'enemy':key,'chase_speed':speed,'walk_animation_speed':default.walk_animation_speed})
opts=unreal.AnimPoseEvaluationOptions();opts.evaluation_type=unreal.AnimDataEvalType.COMPRESSED
opts.optional_skeletal_mesh=mesh;opts.should_retarget=False;opts.extract_root_motion=False
def pose(kind,t):return unreal.AnimPoseExtensions.get_anim_pose_at_time(clips[kind],t,opts)
def distance(a,b,bone):
    return (unreal.AnimPoseExtensions.get_bone_pose(a,bone,unreal.AnimPoseSpaces.WORLD).translation-
      unreal.AnimPoseExtensions.get_bone_pose(b,bone,unreal.AnimPoseSpaces.WORLD).translation).length()
bones=('Hips','Head','RightHand','LeftHand','RightFoot','LeftFoot')
idle=pose('idle',0);entry=pose('attack',0);exit=pose('attack',clips['attack'].get_play_length())
entry_error=max(distance(idle,entry,b) for b in bones)
exit_error=max(distance(entry,exit,b) for b in bones)
assert entry_error<.1 and exit_error<.1,(entry_error,exit_error)
source=Path('C:/Users/21475/Desktop/Game model/古代男青年走路动画.fbx')
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
assert source_hash=='8dfe9c4f93b8af902d22645b9f731fd0d6957571b4d52d78060b9e19e49b293f'
report={'state':'passed','enemies':rows,'clips_share_native_skeleton':True,'source_fbx_unchanged':True,
 'guard_to_attack_max_position_error_cm':entry_error,'attack_loop_max_position_error_cm':exit_error}
(O/'SavedNativeVerification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
