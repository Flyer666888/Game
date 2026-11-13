import unreal, json
from pathlib import Path
OUT=Path(unreal.Paths.project_dir()).resolve()/'Docs/Gameplay/PackSlashReview1104'
def tr(t):
    return {'p':[t.translation.x,t.translation.y,t.translation.z], 'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w], 's':[t.scale3d.x,t.scale3d.y,t.scale3d.z]}
report={'api':{},'assets':{}}
for name in ['IKRigController','IKRetargeterController','IKRetargetBatchOperationInputs','IKRigDefinitionFactory','IKRetargetFactory']:
    cls=getattr(unreal,name,None)
    if cls:
        methods={n:str(getattr(cls,n).__doc__) for n in dir(cls) if any(s in n for s in ['retarget','chain','preview','rotation','pose','skeleton','solver','op','mesh']) and not n.startswith('_')}
        report['api'][name]=methods
for path in ['/Game/Character/Mesh/SK_Mannequin','/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/SK_WuxiaMale_Native_v07']:
    mesh=unreal.load_asset(path)
    pose=unreal.AnimPoseExtensions.get_reference_pose(mesh.skeleton)
    bones=unreal.AnimPoseExtensions.get_bone_names(pose)
    report['assets'][path]={'skeleton':mesh.skeleton.get_path_name(),'reference':{str(b):tr(unreal.AnimPoseExtensions.get_bone_pose(pose,b,unreal.AnimPoseSpaces.WORLD)) for b in bones},'local_reference':{str(b):tr(unreal.AnimPoseExtensions.get_bone_pose(pose,b,unreal.AnimPoseSpaces.LOCAL)) for b in bones}}
for name in ['Anim_CSATLI_01','Anim_CSATLI_02','Anim_CSATLI_03','Anim_CSATLI_04','Anim_CSAT_heavy_01','Anim_CSAT_heavy_02']:
    path='/Game/Animations/Sword/'+name
    clip=unreal.load_asset(path)
    report['assets'][path]={'duration':clip.get_play_length(),'skeleton':clip.get_editor_property('skeleton').get_path_name()}
old=unreal.load_asset('/Game/ReversedScale/Characters/WuxiaMale/RTG_Mannequin_WuxiaMale_SwordCombat')
rc=unreal.IKRetargeterController.get_controller(old)
report['old_retargeter']={}
for side in [unreal.RetargetSourceOrTarget.SOURCE,unreal.RetargetSourceOrTarget.TARGET]:
    rig=rc.get_ik_rig(side)
    r=unreal.IKRigController.get_controller(rig)
    report['old_retargeter'][str(side)]={'rig':rig.get_path_name(),'pose_names':str(rc.get_retarget_poses(side)),'current_pose':str(rc.get_current_retarget_pose_name(side)),'chains':str(r.get_retarget_chains()),'root':str(r.get_retarget_root())}
(OUT/'Probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
