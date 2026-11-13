"""Frame all four bridge terraces in one evidence view; geometry is unchanged."""
import unreal,json,os
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v05'
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV10'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert not ed.get_game_world(),'Finish the character walk before framing'
assert ed.get_editor_world().get_path_name().startswith(MAP+'.')
camera=next(a for a in actors.get_all_level_actors() if isinstance(a,unreal.CameraActor) and 'CAM_16_Yufeng' in a.get_actor_label())
p=[-365,300,280];target=[-125,470,112]
v=lambda q:unreal.Vector(*[t*100 for t in q])
camera.set_actor_location(v(p),False,True)
camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(v(p),v(target)),False)
camera.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',68.)
assert level.save_current_level()
path=os.path.join(OUT,'LayoutSpec.json');spec=json.load(open(path,encoding='utf-8'))
for c in spec['cameras']:
    if c['name']=='CAM_16_Yufeng':c.update(position=p,target=target,fov=68)
json.dump(spec,open(path,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
ed.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
unreal.AutomationLibrary.take_high_res_screenshot(1920,1080,os.path.join(OUT,'Screenshots','UE_16_Yufeng.png'),camera=camera,delay=2.0,force_game_view=True)
