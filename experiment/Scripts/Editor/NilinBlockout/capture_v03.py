"""Capture the saved map with the real UE renderer; never generates concept art."""
import unreal, os, json, time, traceback
ROOT=r'D:\game design\experiment'
OUT=os.path.join(ROOT,'Docs','LevelDesign','Blockout_v03','Screenshots')
os.makedirs(OUT,exist_ok=True)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
started=time.monotonic();stage=0;busy=False;handle=None;task=None;pending=None;last=0;cameras=[];results=[]

def finish(error=None):
    json.dump({'source':'Actual Unreal Engine 5.8.2 renderer','captures':results,'error':error},open(os.path.join(OUT,'CaptureReport.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.unregister_slate_post_tick_callback(handle)
    unreal.log('NILIN_CAPTURE_DONE '+str(error))

def tick(delta):
    global stage,busy,last,cameras,task,pending
    if busy or time.monotonic()-started<5:return
    busy=True
    try:
        if stage==0:
            if not editor.get_editor_world().get_path_name().startswith('/Game/ReversedScale/Maps/L_NilinBlockoutV08.') and not level.load_level('/Game/ReversedScale/Maps/L_NilinBlockoutV08'):raise RuntimeError('Saved blockout cannot load')
            cameras=sorted([a for a in sub.get_all_level_actors() if isinstance(a,unreal.CameraActor) and a.get_actor_label().startswith('NB_CAM_') and ('Pressure' in a.get_actor_label() or 'AlternateOverview' in a.get_actor_label())],key=lambda a:a.get_actor_label())
            unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'r.ScreenPercentage 100')
            unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'r.MotionBlurQuality 0')
            last=time.monotonic();stage=1
        elif stage==1 and time.monotonic()-last>20:
            if not cameras:finish();return
            cam=cameras.pop(0)
            editor.set_level_viewport_camera_info(cam.get_actor_location(),cam.get_actor_rotation())
            name=cam.get_actor_label().rsplit('_',1)[0].replace('NB_CAM_','UE_')+'.png'
            pending=os.path.join(OUT,name)
            if os.path.exists(pending):
                archive=os.path.join(OUT,'EarlierLighting');os.makedirs(archive,exist_ok=True)
                os.replace(pending,os.path.join(archive,name))
            task=unreal.AutomationLibrary.take_high_res_screenshot(1920,1080,pending,camera=cam,delay=2.0,force_game_view=True)
            last=time.monotonic();stage=2
        elif stage==2 and time.monotonic()-last>7:
            if os.path.exists(pending) and os.path.getsize(pending)>10000:
                results.append({'file':pending,'bytes':os.path.getsize(pending)})
                stage=1;last=time.monotonic()-16
            elif time.monotonic()-last>60:raise RuntimeError('Screenshot timed out: '+str(pending))
        if time.monotonic()-started>600:raise RuntimeError('Capture session timeout')
    except Exception:finish(traceback.format_exc())
    finally:busy=False
handle=unreal.register_slate_post_tick_callback(tick)


