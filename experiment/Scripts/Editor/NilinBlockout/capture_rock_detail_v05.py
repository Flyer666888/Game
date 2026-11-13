"""One real UE detail render for the ranged-rock surface review."""
import unreal,os
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v05\RockRefinement'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert not editor.get_game_world(),'End PIE before taking the editor detail render'
assert 'L_NilinBlockoutV10' in editor.get_editor_world().get_path_name()
camera=next(a for a in actors.get_all_level_actors() if isinstance(a,unreal.CameraActor) and 'CAM_15_Ranged' in a.get_actor_label())
editor.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'r.ScreenPercentage 100')
unreal.AutomationLibrary.take_high_res_screenshot(1920,1080,os.path.join(OUT,'RangedRockPreview.png'),camera=camera,delay=2.0,force_game_view=True)
