"""Delayed full-editor navigation/input authoring; never enters PIE/gameplay."""
import json
import runpy
import time
import traceback
from pathlib import Path
import unreal


_vr_nav_root = Path(unreal.Paths.project_dir())
_vr_nav_docs = _vr_nav_root / 'Docs/AI'
_vr_nav_started = time.monotonic()
_vr_nav_repaired_at = None
_vr_nav_rebuild_at = None
_vr_nav_done_at = None
_vr_nav_running = False
_vr_nav_handle = None
_vr_nav_api = None
_vr_nav_before = None
_vr_nav_reset = None
_vr_nav_result = {'date': '2026-10-16', 'success': False, 'navigation_saved': False,
                  'reset_action_saved': False,
                  'scope': 'VR navigation asset build/save and pause-enabled reset action authoring only; no gameplay, enemies, or tests.'}


def _vr_nav_write_result():
    _vr_nav_docs.mkdir(parents=True, exist_ok=True)
    (_vr_nav_docs / 'VRNavigationEditorRepair-2026-10-16.json').write_text(
        json.dumps(_vr_nav_result, ensure_ascii=False, indent=2), encoding='utf-8')


def _vr_nav_tick(delta):
    global _vr_nav_running, _vr_nav_done_at, _vr_nav_repaired_at, _vr_nav_rebuild_at
    global _vr_nav_api, _vr_nav_before, _vr_nav_reset
    now = time.monotonic()
    # Loading assets, rebuilding and saving can pump nested Slate callbacks.
    if _vr_nav_running or now - _vr_nav_started < 6.0:
        return
    if _vr_nav_done_at is not None:
        if now - _vr_nav_done_at >= 2.0:
            unreal.unregister_slate_post_tick_callback(_vr_nav_handle)
            unreal.SystemLibrary.quit_editor()
        return
    _vr_nav_running = True
    try:
        if _vr_nav_repaired_at is None:
            level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
            if not level.load_level('/Game/ReversedScale/Maps/L_CombatLabVR'):
                raise RuntimeError('Could not load the independent VR map.')
            _vr_nav_api = runpy.run_path(str(_vr_nav_root / 'Saved/Scripts/repair_vr_navigation.py'))
            _vr_nav_before = _vr_nav_api['inspect_navigation'](
                _vr_nav_docs / 'VRNavigationBeforeRepair-2026-10-16.json')
            _vr_nav_result['before_report'] = 'Docs/AI/VRNavigationBeforeRepair-2026-10-16.json'
            unreal.log('VR_NAVIGATION_BEFORE_REPAIR_SAVED')
            _vr_nav_result['authoring'] = _vr_nav_api['repair_navigation']()
            _vr_nav_reset = unreal.load_asset('/Game/ReversedScale/Player/VR/Input/IA_VRReset')
            if not _vr_nav_reset or not isinstance(_vr_nav_reset, unreal.InputAction):
                raise RuntimeError('The existing IA_VRReset action is missing or has the wrong class.')
            _vr_nav_result['reset_trigger_when_paused_before'] = _vr_nav_reset.get_editor_property('trigger_when_paused')
            _vr_nav_reset.set_editor_property('trigger_when_paused', True)
            _vr_nav_repaired_at = time.monotonic()
            _vr_nav_result['phase'] = 'waiting_for_recast_registration'
            _vr_nav_write_result()
            return

        if now - _vr_nav_repaired_at > 240.0:
            raise RuntimeError('Navigation authoring did not finish within 240 seconds.')
        if _vr_nav_rebuild_at is None:
            if now - _vr_nav_repaired_at < 2.0:
                return
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
            # FNavigationSystemExec handles this only after NavDataSet contains
            # a registered actor. Kismet falls back to GEngine->Exec in editor
            # worlds without a PlayerController (confirmed in local UE source).
            unreal.SystemLibrary.execute_console_command(world, 'RebuildNavigation')
            _vr_nav_rebuild_at = time.monotonic()
            _vr_nav_result['phase'] = 'building_navigation'
            _vr_nav_write_result()
            return
        if now - _vr_nav_rebuild_at < 5.0:
            return
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        if unreal.NavigationSystemV1.is_navigation_being_built_or_locked(world):
            return
        saved = _vr_nav_api['save_navigation'](_vr_nav_before,
                                             _vr_nav_docs / 'VRNavigationSaved-2026-10-16.json',
                                             date='2026-10-16')
        _vr_nav_result['navigation_saved'] = bool(saved['saved'])
        _vr_nav_result['after'] = saved['after']
        if not _vr_nav_reset.get_editor_property('trigger_when_paused'):
            raise RuntimeError('IA_VRReset lost its pause-enabled setting before save.')
        if not unreal.EditorAssetLibrary.save_loaded_asset(_vr_nav_reset, False):
            raise RuntimeError('Could not save the pause-enabled IA_VRReset action.')
        _vr_nav_result['reset_action_saved'] = True
        _vr_nav_result['reset_trigger_when_paused_after'] = _vr_nav_reset.get_editor_property('trigger_when_paused')
        _vr_nav_result['success'] = True
        _vr_nav_result['phase'] = 'complete'
        unreal.log('VR_NAVIGATION_EDITOR_REPAIR_SUCCESS')
        _vr_nav_done_at = time.monotonic()
        _vr_nav_write_result()
    except Exception:
        _vr_nav_result['phase'] = 'failed'
        _vr_nav_result['error'] = traceback.format_exc()
        unreal.log_error(_vr_nav_result['error'])
        _vr_nav_done_at = time.monotonic()
        _vr_nav_write_result()
    finally:
        _vr_nav_running = False


_vr_nav_handle = unreal.register_slate_post_tick_callback(_vr_nav_tick)
unreal.log('VR_NAVIGATION_EDITOR_REPAIR_REGISTERED')
