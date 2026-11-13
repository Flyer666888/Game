import unreal,os,json
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v01'
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
camera=None
for a in sub.get_all_level_actors():
    if isinstance(a,unreal.TextRenderActor):a.get_component_by_class(unreal.TextRenderComponent).set_world_size(30)
    if a.get_actor_label().startswith('NB_CAM_00'):
        camera=a;a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',65)
assert camera
editor.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
assert level.save_current_level()
p=os.path.join(OUT,'LayoutSpec.json');data=json.load(open(p,encoding='utf-8'));data['cameras'][0]['fov']=65
json.dump(data,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
unreal.AutomationLibrary.take_high_res_screenshot(2400,1350,os.path.join(OUT,'Screenshots','UE_00_Overview.png'),camera=camera,delay=3)
