import unreal,json
from pathlib import Path
O=Path(unreal.Paths.project_dir()).resolve()/'Docs/Gameplay/PackSlashReview1104'
mesh=unreal.load_asset('/Game/Character/Mesh/SK_Mannequin')
sk=mesh.skeleton
out={'mesh_api':{n:str(getattr(mesh,n).__doc__) for n in dir(mesh) if 'socket' in n},'skeleton_api':{n:str(getattr(sk,n).__doc__) for n in dir(sk) if 'socket' in n},'properties':{}}
out['sockets']=[]
for i in range(mesh.num_sockets()):
    v=mesh.get_socket_by_index(i)
    out['sockets'].append({k:str(v.get_editor_property(k)) for k in ['socket_name','bone_name','relative_location','relative_rotation','relative_scale']})
for objname,obj in [('mesh',mesh),('skeleton',sk)]:
    for p in ['sockets','mesh_only_sockets']:
        try:
            values=obj.get_editor_property(p)
            out['properties'][objname+'.'+p]=str(values)
            for v in values:
                out['properties'][objname+'.'+v.get_name()]={k:str(v.get_editor_property(k)) for k in ['socket_name','bone_name','relative_location','relative_rotation','relative_scale']}
        except Exception as e:out['properties'][objname+'.'+p]=str(e)
options=unreal.AnimPoseEvaluationOptions();options.optional_skeletal_mesh=mesh;options.evaluation_type=unreal.AnimDataEvalType.RAW
clip=unreal.load_asset('/Game/Animations/Sword/Anim_CSAT_heavy_01')
out['frames']=[]
def rec(t):return {'p':[t.translation.x,t.translation.y,t.translation.z],'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]}
for t in [0.0,0.5,1.0,1.2,1.4,1.6,2.0]:
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(clip,t,options)
    out['frames'].append({'t':t,'bones':{b:rec(unreal.AnimPoseExtensions.get_bone_pose(pose,b,unreal.AnimPoseSpaces.WORLD)) for b in ['hand_r','hand_l','ik_hand_r','ik_hand_l','ik_hand_gun','index_01_r','index_02_r','index_03_r','thumb_01_r','thumb_02_r','thumb_03_r']}})
(O/'SourceGripProbe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
