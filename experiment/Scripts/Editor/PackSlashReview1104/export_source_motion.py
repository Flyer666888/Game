import unreal,json,math
from pathlib import Path
O=Path(unreal.Paths.project_dir()).resolve()/'Docs/Gameplay/PackSlashReview1104'
mesh=unreal.load_asset('/Game/Character/Mesh/SK_Mannequin')
options=unreal.AnimPoseEvaluationOptions()
options.evaluation_type=unreal.AnimDataEvalType.RAW
options.optional_skeletal_mesh=mesh
bones=['root','pelvis','spine_03','head','clavicle_r','upperarm_r','lowerarm_r','hand_r','hand_l','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r']
def value(t):return {'p':[t.translation.x,t.translation.y,t.translation.z],'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w],'s':[t.scale3d.x,t.scale3d.y,t.scale3d.z]}
result={'fps':30,'mesh':mesh.get_path_name(),'clips':[]}
for name in ['Anim_CSATLI_01','Anim_CSATLI_02','Anim_CSATLI_03','Anim_CSATLI_04','Anim_CSAT_heavy_01','Anim_CSAT_heavy_02']:
    clip=unreal.load_asset('/Game/Animations/Sword/'+name)
    duration=clip.get_play_length()
    frames=[]
    for i in range(round(duration*30)+1):
        t=min(i/30,duration)
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(clip,t,options)
        frames.append({'t':t,'bones':{b:value(unreal.AnimPoseExtensions.get_bone_pose(pose,b,unreal.AnimPoseSpaces.WORLD)) for b in bones}})
    result['clips'].append({'name':name,'duration':duration,'frames':frames})
(O/'SourceMotion.json').write_text(json.dumps(result),encoding='utf-8')
