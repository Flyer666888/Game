"""Final presentation: legible greybox exposure and overview-right summit."""
import unreal,json,os,copy
ROOT=r'D:\game design\experiment'
OUT=os.path.join(ROOT,'Docs','LevelDesign','Blockout_v01')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV06'
assert editor.get_editor_world().get_path_name().startswith(MAP+'.')
path=os.path.join(OUT,'LayoutSpec.json');data=json.load(open(path,encoding='utf-8'))
allactors=actors.get_all_level_actors()
if not data.get('world_mirrored_x'):
    mirror=unreal.Transform(scale=unreal.Vector(-1,1,1))
    cameras={c['label']:c for c in data['cameras']}
    for a in allactors:
        if not a.actor_has_tag('NLBlockoutV06'):continue
        p=a.get_actor_location();p.x=-p.x
        if isinstance(a,unreal.CameraActor):
            c=cameras[a.get_actor_label()];t=c['target'];dest=unreal.Vector(-t[0]*100,t[1]*100,t[2]*100)
            a.set_actor_location(p,False,True);a.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(p,dest),True)
        elif isinstance(a,(unreal.TargetPoint,unreal.PlayerStart,unreal.TextRenderActor)):
            r=a.get_actor_rotation();r.yaw=180-r.yaw if not isinstance(a,unreal.TextRenderActor) else -90
            a.set_actor_location(p,False,True);a.set_actor_rotation(r,True)
        elif isinstance(a,unreal.StaticMeshActor):
            transform=unreal.MathLibrary.compose_transforms(a.get_actor_transform(),mirror)
            actors.set_actor_transform(a,transform)
    coordinate_keys={'center','ground','a','b','position','target','friend','furnace','boss','triangle_eye','breaker','combat_stand_A','workshop_right_center'}
    def convert(value,key=''):
        if isinstance(value,dict):
            for k in list(value):value[k]=convert(value[k],k)
            if 'yaw' in value:value['yaw']=180-value['yaw']
        elif isinstance(value,list):
            if key in coordinate_keys and value and all(isinstance(t,(int,float)) for t in value):value[0]=-value[0]
            elif key in ('route','points','victory_route'):
                for p in value:p[0]=-p[0]
            else:
                for i in range(len(value)):value[i]=convert(value[i])
        return value
    convert(data)
    data['world_mirrored_x']=True
    data['world_axes']='UE coordinates: -X is overview-right, +Y ascends, +Z altitude. Facades face -Y.'
    json.dump(data,open(path,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
for a in allactors:
    if isinstance(a,unreal.DirectionalLight):a.get_component_by_class(unreal.DirectionalLightComponent).set_intensity(8)
    if isinstance(a,unreal.PostProcessVolume):
        pp=a.get_editor_property('settings')
        pp.set_editor_property('auto_exposure_min_brightness',0.0);pp.set_editor_property('auto_exposure_max_brightness',0.0)
        a.set_editor_property('settings',pp)
    if isinstance(a,unreal.CameraActor):
        c=a.get_component_by_class(unreal.CameraComponent);pp=c.get_editor_property('post_process_settings')
        pp.set_editor_property('auto_exposure_min_brightness',0.0);pp.set_editor_property('auto_exposure_max_brightness',0.0)
        c.set_editor_property('post_process_settings',pp)
sky_path='/Game/ReversedScale/Blockout/V06/Materials/M_WhiteboxSky'
mat=unreal.EditorAssetLibrary.load_asset(sky_path) if unreal.EditorAssetLibrary.does_asset_exist(sky_path) else None
if not mat:
    mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_WhiteboxSky','/Game/ReversedScale/Blockout/V06/Materials',unreal.Material,unreal.MaterialFactoryNew())
    mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property('two_sided',True)
    mat.set_editor_property('is_sky',True)
    n=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector)
    n.set_editor_property('constant',unreal.LinearColor(.18,.3,.45,1))
    unreal.MaterialEditingLibrary.connect_material_property(n,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(mat);unreal.EditorAssetLibrary.save_loaded_asset(mat,False)
if not any(a.actor_has_tag('NLBlockout.WhiteboxSky') for a in allactors):
    a=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(0,30000,0))
    a.set_actor_label('NB_WhiteboxSky');a.set_editor_property('tags',[unreal.Name('NLBlockoutV06'),unreal.Name('NLBlockout.WhiteboxSky')]);a.set_folder_path('Nilin_V06/00_Environment')
    c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Sphere'));c.set_material(0,mat);c.set_collision_profile_name('NoCollision');c.set_editor_property('cast_shadow',False)
    a.set_actor_scale3d(unreal.Vector(10000,10000,10000))
overview=next(a for a in actors.get_all_level_actors() if a.get_actor_label().startswith('NB_CAM_00'))
editor.set_level_viewport_camera_info(overview.get_actor_location(),overview.get_actor_rotation())
assert level.save_current_level()
unreal.log('NILIN_PRESENTATION_OK')
