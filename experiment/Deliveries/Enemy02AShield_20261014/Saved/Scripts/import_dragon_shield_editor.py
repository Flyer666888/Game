"""Full-editor asset authoring entry point; never enters gameplay."""
import json
import runpy
import time
import traceback
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir())
_author_start = time.monotonic()
_author_handle = None
_author_complete_time = None


def _author_tick(delta):
    global _author_complete_time
    # Startup ExecCmds may execute before editor mode tools finish initializing.
    # Wait for actual editor ticks before asset authoring and defer shutdown.
    if time.monotonic() - _author_start < 5.0:
        return
    if _author_complete_time is not None:
        if time.monotonic() - _author_complete_time >= 2.0:
            unreal.unregister_slate_post_tick_callback(_author_handle)
            unreal.SystemLibrary.quit_editor()
        return
    result = {'date': '2026-10-14', 'asset': 'DragonShield', 'success': False,
              'scope': 'Asset import and LOD authoring only; no gameplay or tests.'}
    try:
        runpy.run_path(str(root / 'Saved/Scripts/import_dragon_shield.py'))
        result['success'] = True
        unreal.log('DRAGON_SHIELD_EDITOR_AUTHOR_SUCCESS')
    except Exception:
        result['error'] = traceback.format_exc()
        unreal.log_error(result['error'])
    finally:
        (root / 'ArtSource/DragonShield/DragonShieldEditorAuthor.json').write_text(
            json.dumps(result, indent=2), encoding='utf-8')
        _author_complete_time = time.monotonic()


_author_handle = unreal.register_slate_post_tick_callback(_author_tick)
