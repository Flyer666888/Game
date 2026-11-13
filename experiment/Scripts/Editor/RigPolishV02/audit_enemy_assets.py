import unreal,json,math
from pathlib import Path
out=Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v02')
records=[];clips={};assets=unreal.EditorAssetLibrary
keys=('sword','talisman','rock_talisman','GM01','GM02','GM03','GM04','boss')
bones=('root','pelvis','spine_01','spine_02','spine_03','neck_01','head','clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')
for key in keys:
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    cls=assets.load_blueprint_class(path);default=unreal.get_default_object(cls)
    component=default.get_component_by_class(unreal.SkeletalMeshComponent)
    mesh=default.get_editor_property('enemy_skeletal_mesh') or component.get_editor_property('skeletal_mesh_asset')
    brain=default.get_enemy_brain();move=default.get_component_by_class(unreal.CharacterMovementComponent)
    row={'key':key,'blueprint':path,'mesh':mesh.get_path_name() if mesh else None,
         'walk_speed_cm_s':move.get_editor_property('max_walk_speed'),'animations':{},'role':str(brain.get_editor_property('role')),
         'timing':{p:brain.get_editor_property(p) for p in ('telegraph_seconds','attack_seconds','recover_seconds')},
         'mesh_relative':{p:str(component.get_editor_property(p)) for p in ('relative_location','relative_rotation','relative_scale3d')}}
    for prop in ('idle_animation','walk_animation','attack_animation','cast_animation','hit_reaction_animation','death_animation'):
        clip=default.get_editor_property(prop)
        row['animations'][prop]=clip.get_path_name() if clip else None
        if clip and clip.get_path_name() not in clips:
            options=unreal.AnimPoseEvaluationOptions()
            options.set_editor_property('evaluation_type',unreal.AnimDataEvalType.COMPRESSED)
            options.set_editor_property('optional_skeletal_mesh',mesh)
            data={'duration':clip.get_play_length(),'skeleton':clip.get_editor_property('skeleton').get_path_name(),
                  'compatible':clip.get_editor_property('skeleton')==mesh.get_editor_property('skeleton'),'samples':[]}
            for f in (0,.125,.25,.375,.5,.625,.75,.875,1):
                pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(clip,f*clip.get_play_length(),options)
                assert unreal.AnimPoseExtensions.is_valid(pose)
                sample={'time':f*clip.get_play_length(),'bones':{}}
                for bone in bones:
                    t=unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD)
                    sample['bones'][bone]={'position':[t.translation.x,t.translation.y,t.translation.z],
                        'rotation':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w],'scale':[t.scale3d.x,t.scale3d.y,t.scale3d.z]}
                data['samples'].append(sample)
            clips[clip.get_path_name()]=data
    records.append(row)
(out/'AssetAudit.json').write_text(json.dumps({'enemies':records,'clips':clips},ensure_ascii=False,indent=2),encoding='utf-8')
