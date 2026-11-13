"""Export hand sources after editor and rendering services are ready."""
import json
import runpy
import time
import traceback
from pathlib import Path
import unreal

_hand_root = Path(unreal.Paths.project_dir())
_hand_start = time.monotonic()
_hand_done = None
_hand_running = False
_hand_handle = None

def _hand_tick(delta):
    global _hand_done, _hand_running
    if _hand_running or time.monotonic() - _hand_start < 5.0:
        return
    if _hand_done is not None:
        if time.monotonic() - _hand_done >= 2.0:
            unreal.unregister_slate_post_tick_callback(_hand_handle)
            unreal.SystemLibrary.quit_editor()
        return
    result = {'success': False, 'scope': 'Source mesh and pose export only.'}
    _hand_running = True
    try:
        runpy.run_path(str(_hand_root / 'Saved/Scripts/export_player_hand_sources.py'))
        result['success'] = True
    except Exception:
        result['error'] = traceback.format_exc()
        unreal.log_error(result['error'])
    finally:
        (_hand_root / 'Docs/AI/PlayerHandExport-2026-10-15.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        _hand_done = time.monotonic()
        _hand_running = False

_hand_handle = unreal.register_slate_post_tick_callback(_hand_tick)
