"""Author player hand assets after the full editor has initialized, then exit."""
import json
import runpy
import time
import traceback
from pathlib import Path

import unreal


_player_hands_root = Path(unreal.Paths.project_dir())
_player_hands_start = time.monotonic()
_player_hands_done = None
_player_hands_running = False
_player_hands_handle = None


def _player_hands_tick(delta):
    global _player_hands_done, _player_hands_running
    # Import, shader compilation and saving can pump nested Slate callbacks.
    if _player_hands_running or time.monotonic() - _player_hands_start < 5.0:
        return
    if _player_hands_done is not None:
        if time.monotonic() - _player_hands_done >= 2.0:
            unreal.unregister_slate_post_tick_callback(_player_hands_handle)
            unreal.SystemLibrary.quit_editor()
        return
    result = {'date': '2026-10-15', 'success': False,
              'scope': 'Player hand asset authoring only; no gameplay or tests.'}
    _player_hands_running = True
    try:
        runpy.run_path(str(_player_hands_root / 'Saved/Scripts/import_realistic_player_hands.py'))
        result['success'] = True
        unreal.log('PLAYER_HANDS_EDITOR_AUTHOR_SUCCESS')
    except Exception:
        result['error'] = traceback.format_exc()
        unreal.log_error(result['error'])
    finally:
        report = _player_hands_root / 'Docs/AI/PlayerHandsEditorAuthor-2026-10-15.json'
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        _player_hands_done = time.monotonic()
        _player_hands_running = False


_player_hands_handle = unreal.register_slate_post_tick_callback(_player_hands_tick)
unreal.log('PLAYER_HANDS_EDITOR_AUTHOR_REGISTERED')
