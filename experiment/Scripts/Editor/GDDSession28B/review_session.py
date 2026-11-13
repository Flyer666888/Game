"""Sequential editor worker for the authorized VR grip and sword detail revision."""
import json, time, traceback
from pathlib import Path
import unreal
P = Path(unreal.Paths.project_dir()).resolve()
BASE = P / 'Scripts/Editor'
OUT = P / 'Docs/Gameplay/GDDSession28B'
OUT.mkdir(parents=True, exist_ok=True)
last_revision = None
busy = False
contexts = []
started = time.monotonic()

def status(data):
    data['utc_timestamp'] = time.time()
    (OUT / 'Status.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def tick(delta):
    global last_revision, busy
    if busy or time.monotonic() - started < 5:
        return
    busy = True
    try:
        path = OUT / 'Command.json'
        if not path.exists():
            return
        job = json.loads(path.read_text(encoding='utf-8-sig'))
        if job['revision'] == last_revision:
            return
        last_revision = job['revision']
        status({'revision': last_revision, 'state': 'running', 'job': job})
        if job['action'] == 'quit':
            assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
            status({'revision': last_revision, 'state': 'closed'})
            unreal.unregister_slate_post_tick_callback(handle)
            unreal.SystemLibrary.quit_editor()
            return
        source = (BASE / job['script']).resolve()
        assert source.is_relative_to(BASE) and source.suffix == '.py'
        context = {'__name__': '__main__', '__file__': str(source)}
        contexts.append(context)
        exec(compile(source.read_text(encoding='utf-8-sig'), str(source), 'exec'), context)
        status({'revision': last_revision, 'state': 'dispatched', 'job': job,
                'note': 'Inspect the asynchronous job final report before dependent work.'})
    except Exception:
        error = traceback.format_exc()
        status({'revision': last_revision, 'state': 'error', 'error': error})
        unreal.log_error(error)
    finally:
        busy = False

handle = unreal.register_slate_post_tick_callback(tick)
unreal.SystemLibrary.execute_console_command(None, 't.IdleWhenNotForeground 0')
status({'state': 'ready', 'scope': 'GDD continuation editor work; sequential commands.'})
