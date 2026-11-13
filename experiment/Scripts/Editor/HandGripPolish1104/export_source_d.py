import unreal,json
from pathlib import Path
O=Path(unreal.Paths.project_dir()).resolve()/'Docs/Gameplay/HandGripPolish1104'
A=unreal.load_asset('/Game/Animations/Sword/Anim_CSATLI_04')
M=unreal.load_asset('/Game/Character/Mesh/SK_Mannequin')
E=unreal.AnimPoseExtensions;W=unreal.AnimPoseSpaces.WORLD
ref=E.get_reference_pose(A.get_editor_property('skeleton'))
names=[str(b) for b in E.get_bone_names(ref) if str(b)=='hand_r' or (str(b).endswith('_r') and any(x in str(b) for x in ['index','thumb','middle','ring','pinky','lowerarm']))]
def rec(pose):
    out={}
    for b in names:
        t=E.get_bone_pose(pose,b,W);out[b]={'p':list(t.translation.to_tuple()),'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]}
    return out
opt=unreal.AnimPoseEvaluationOptions();opt.evaluation_type=unreal.AnimDataEvalType.RAW;opt.should_retarget=False;opt.extract_root_motion=False;opt.optional_skeletal_mesh=M
data={'reference':rec(ref),'frames':[{'t':t,'bones':rec(E.get_anim_pose_at_time(A,t,opt))} for t in [0,.3,.6,.9,1.2,1.8,2.3]]}
(O/'SourceDHand.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
