"""Wait for full editor initialization, author shader assets, then exit."""
import json
import runpy
import time
import traceback
from pathlib import Path
import unreal

_surface_author_root = Path(unreal.Paths.project_dir())
_surface_author_start = time.monotonic()
_surface_author_done = None
_surface_author_handle = None
_surface_author_running = False


def _surface_author_tick(delta):
    global _surface_author_done, _surface_author_running
    if _surface_author_running:
        return
    if time.monotonic() - _surface_author_start < 5.0:
        return
    if _surface_author_done is not None:
        if time.monotonic() - _surface_author_done >= 2.0:
            unreal.unregister_slate_post_tick_callback(_surface_author_handle)
            unreal.SystemLibrary.quit_editor()
        return
    result = {'date': '2026-10-14', 'success': False,
              'scope': 'Shield surface assets only; no gameplay or tests.'}
    # Asset saving can pump Slate ticks. Prevent nested author invocations.
    _surface_author_running = True
    try:
        runpy.run_path(str(_surface_author_root / 'Saved/Scripts/author_shield_realistic_materials.py'))
        result['success'] = True
        unreal.log('SHIELD_SURFACE_EDITOR_AUTHOR_SUCCESS')
    except Exception:
        result['error'] = traceback.format_exc()
        unreal.log_error(result['error'])
    finally:
        (_surface_author_root / 'Docs/AI/ShieldSurfaceEditorAuthor-2026-10-14.json').write_text(
            json.dumps(result, indent=2), encoding='utf-8')
        _surface_author_done = time.monotonic()
        _surface_author_running = False


_surface_author_handle = unreal.register_slate_post_tick_callback(_surface_author_tick)
unreal.log('SHIELD_SURFACE_EDITOR_AUTHOR_REGISTERED')
