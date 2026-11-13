"""Capture saved environment evidence from task-owned cameras in the UE renderer."""
import json
import ast
import hashlib
import time
import traceback
from pathlib import Path
import unreal

P=Path(unreal.Paths.project_dir()).resolve()
BASE=P/'Docs/Gameplay/GDDOrdered1105'
config_path=BASE/'ArtCaptureConfig.json'
config=json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else {}
BEFORE=bool(config.get('before',False))
O=BASE/('ArtBeforeScreenshots' if BEFORE else 'ArtScreenshots')
MAP='/Game/ReversedScale/Maps/L_NilinGameplayV01'
O.mkdir(parents=True,exist_ok=True)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
started=time.monotonic();phase=0;busy=False;last=0;pending=None;cameras=[];results=[];tasks=[];temporary=[]
MAPFILE=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
original_hash=hashlib.sha256(MAPFILE.read_bytes()).hexdigest()


def finish(error=None):
    for camera in temporary:
        if unreal.SystemLibrary.is_valid(camera):
            assert camera.actor_has_tag('NL.GDD1105.ArtCaptureTemp')
            actors.destroy_actor(camera)
    current_hash=hashlib.sha256(MAPFILE.read_bytes()).hexdigest()
    if current_hash!=original_hash:
        error=(error or '')+' Saved map changed during capture'
    (O/'CaptureReport.json').write_text(json.dumps({'state':'passed' if error is None and len(results)==6 else 'failed',
        'map':MAP,'before_mode':BEFORE,'source':'Actual saved-map Unreal Engine renderer','captures':results,
        'map_sha256_before':original_hash,'map_sha256_after':current_hash,'temporary_cameras_destroyed':len(temporary),
        'elapsed_seconds':time.monotonic()-started,'error':error},ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.unregister_slate_post_tick_callback(handle)


def tick(delta):
    global phase,busy,last,pending,cameras
    if busy:return
    busy=True
    try:
        if phase==0:
            assert editor.get_game_world() is None
            assert level.load_level(MAP)
            if BEFORE:
                # Read only the literal camera table, never execute the authoring module.
                source=P/'Scripts/Editor/GDDOrdered1105/art_apply.py'
                parsed=ast.parse(source.read_text(encoding='utf-8-sig'))
                table=next(n.value for n in parsed.body if isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='CAMERAS' for t in n.targets))
                specs=ast.literal_eval(table)
                for name,p,target,fov in specs:
                    camera=actors.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*p),
                        unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*p),unreal.Vector(*target)))
                    camera.set_actor_label('NL1105_Art_CAM_'+name)
                    camera.set_editor_property('tags',[unreal.Name('NL.GDD1105.ArtCaptureTemp')])
                    component=camera.get_component_by_class(unreal.CameraComponent)
                    component.set_editor_property('field_of_view',fov)
                    component.set_editor_property('constrain_aspect_ratio',False)
                    temporary.append(camera)
                cameras=sorted(temporary,key=lambda a:a.get_actor_label())
            else:
                cameras=sorted([a for a in actors.get_all_level_actors() if isinstance(a,unreal.CameraActor)
                    and a.actor_has_tag('NL.GDD1105.Art') and a.get_actor_label().startswith('NL1105_Art_CAM_')],key=lambda a:a.get_actor_label())
            assert len(cameras)==6, len(cameras)
            unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'r.ScreenPercentage 100')
            unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'r.MotionBlurQuality 0')
            last=time.monotonic();phase=1
        elif phase==1 and time.monotonic()-last>18:
            if not cameras:finish();return
            cam=cameras.pop(0)
            pending=O/(cam.get_actor_label().removeprefix('NL1105_Art_CAM_')+'.png')
            editor.set_level_viewport_camera_info(cam.get_actor_location(),cam.get_actor_rotation())
            tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1600,900,str(pending),camera=cam,delay=2.0,force_game_view=True))
            phase=2;last=time.monotonic()
        elif phase==2 and time.monotonic()-last>6:
            if pending.exists() and pending.stat().st_size>10000:
                results.append({'file':str(pending),'bytes':pending.stat().st_size})
                phase=1;last=time.monotonic()-14
            elif time.monotonic()-last>45:raise RuntimeError('Screenshot did not complete '+str(pending))
        assert time.monotonic()-started<300,'Environment capture deadline'
    except Exception:finish(traceback.format_exc())
    finally:busy=False


handle=unreal.register_slate_post_tick_callback(tick)
