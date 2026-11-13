"""Sequential local editor worker for the three-hour optimization session."""
import json,time,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve()
BASE=ROOT/'Scripts/Editor'
OUT=ROOT/'Docs/Gameplay/Optimization1111'
last_revision=None
contexts=[]
started=time.monotonic()
busy=False
def status(data):
    data['timestamp']=time.time()
    (OUT/'EditorStatus.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def tick(delta):
    global last_revision,busy
    if busy or time.monotonic()-started<4:return
    command=OUT/'EditorCommand.json'
    if not command.exists():return
    busy=True
    try:
        try:
            job=json.loads(command.read_text(encoding='utf-8-sig'))
        except json.JSONDecodeError:
            return # A writer may be replacing the command; retry on the next tick.
        if job['revision']==last_revision:return
        last_revision=job['revision']
        status({'state':'running','revision':last_revision,'job':job})
        if job['action']=='quit':
            assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
            unreal.unregister_slate_post_tick_callback(handle)
            status({'state':'closed','revision':last_revision})
            unreal.SystemLibrary.quit_editor();return
        script=(BASE/job['script']).resolve()
        assert script.is_relative_to(BASE) and script.suffix=='.py'
        context={'__name__':'__main__','__file__':str(script)}
        contexts.append(context)
        exec(compile(script.read_text(encoding='utf-8-sig'),str(script),'exec'),context)
        status({'state':'dispatched','revision':last_revision,'job':job})
    except Exception:
        error=traceback.format_exc();status({'state':'error','revision':last_revision,'error':error});unreal.log_error(error)
    finally:busy=False
handle=unreal.register_slate_post_tick_callback(tick)
unreal.SystemLibrary.execute_console_command(None,'t.IdleWhenNotForeground 0')
status({'state':'ready'})
