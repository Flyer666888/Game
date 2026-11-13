"""Bake fixed blockout navigation locally; avoid Recast's global ini editor side effect."""
import unreal,json,time,hashlib,traceback
from pathlib import Path
root=Path(r'D:\game design\experiment')
out=root/'Docs/Gameplay/EncounterRecovery_v01'
ini=root/'Config/DefaultEngine.ini'
before=hashlib.sha256(ini.read_bytes()).hexdigest()
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=editor.get_editor_world()
assert not editor.get_game_world() and 'L_NilinGameplayV01' in world.get_path_name()
navs=[a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.RecastNavMesh)]
assert len(navs)==1
nav=navs[0]
nav.set_editor_property('runtime_generation',unreal.RuntimeGenerationType.STATIC,unreal.PropertyAccessChangeNotifyMode.NEVER)
nav.set_editor_property('force_rebuild_on_load',False)
report={'state':'building','default_engine_sha256_before':before,'map':world.get_path_name(),'generation':'Static','force_rebuild_on_load':False}
def save():
    (out/'StaticNavigationBake.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
save()
unreal.SystemLibrary.execute_console_command(world,'BUILDPATHS')
started=time.monotonic();stable=0;handle=None;busy=False;finished=False
def tick(delta):
    global stable,handle,busy,finished
    if busy or finished:return
    try:
        assert time.monotonic()-started<120,'Static navigation did not settle'
        stable=0 if unreal.NavigationSystemV1.is_navigation_being_built_or_locked(world) else stable+1
        if stable<3:return
        busy=True
        after=hashlib.sha256(ini.read_bytes()).hexdigest()
        assert before==after,'Map-only navigation must not change global project ini'
        source=root/'Scripts/Editor/Gameplay/verify_gameplay_v01.py'
        exec(compile(source.read_text(encoding='utf-8-sig'),str(source),'exec'),{'__file__':str(source),'__name__':'__main__'})
        report.update({'state':'passed','saved':True,'default_engine_sha256_after':after,'global_ini_unchanged':True,'elapsed_seconds':time.monotonic()-started})
    except Exception:
        report.update({'state':'failed','error':traceback.format_exc()})
    save()
    finished=True
    busy=False
    unreal.unregister_slate_post_tick_callback(handle)
handle=unreal.register_slate_post_tick_callback(tick)
