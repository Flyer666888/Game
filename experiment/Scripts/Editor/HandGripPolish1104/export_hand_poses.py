import unreal,json,hashlib,math
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/HandGripPolish1104';A=unreal.EditorAssetLibrary
obj=unreal.get_default_object(A.load_blueprint_class('/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_sword'))
mesh=obj.enemy_skeletal_mesh;sk=mesh.skeleton
ref=unreal.AnimPoseExtensions.get_reference_pose(sk);names=list(unreal.AnimPoseExtensions.get_bone_names(ref))
W=unreal.AnimPoseSpaces.WORLD;L=unreal.AnimPoseSpaces.LOCAL
def rec(t):return {'p':[t.translation.x,t.translation.y,t.translation.z], 'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w], 's':[t.scale3d.x,t.scale3d.y,t.scale3d.z]}
options=unreal.AnimPoseEvaluationOptions();options.evaluation_type=unreal.AnimDataEvalType.RAW
options.optional_skeletal_mesh=mesh;options.should_retarget=False;options.extract_root_motion=False
report={'mesh':mesh.get_path_name(),'skeleton':sk.get_path_name(),'grip':rec(obj.sword_grip_transform),
    'reference':{'local':{str(b):rec(unreal.AnimPoseExtensions.get_bone_pose(ref,b,L)) for b in names},
        'world':{str(b):rec(unreal.AnimPoseExtensions.get_bone_pose(ref,b,W)) for b in names}},'clips':{}}
protected=[mesh,sk,obj.attack_animation,obj.idle_animation,obj.walk_animation,obj.hit_reaction_animation,obj.death_animation,obj.cast_animation]
report['protected_sha256']={x.get_path_name():hashlib.sha256((P/'Content'/(x.get_path_name().split('.')[0].removeprefix('/Game/')+'.uasset')).read_bytes()).hexdigest() for x in protected if x}
for key,anim in [('attack',obj.attack_animation),('idle',obj.idle_animation),('walk',obj.walk_animation),('hit',obj.hit_reaction_animation),('death',obj.death_animation),('cast',obj.cast_animation)]:
    if not anim:continue
    duration=anim.get_play_length();frames=[]
    for i in range(round(duration*30)+1):
        t=min(i/30,duration);pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,t,options)
        frames.append({'t':t,'local':{str(b):rec(unreal.AnimPoseExtensions.get_bone_pose(pose,b,L)) for b in names},
            'world':{str(b):rec(unreal.AnimPoseExtensions.get_bone_pose(pose,b,W)) for b in names}})
    report['clips'][key]={'asset':anim.get_path_name(),'duration':duration,'fps':30,'frames':frames}
(O/'PoseSamples.json').write_text(json.dumps(report,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
