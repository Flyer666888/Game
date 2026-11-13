"""Run the Guard Captain asset authoring after the editor has opened, then quit."""
import json
import runpy
import time
import traceback
from pathlib import Path
import unreal

_captain_author_root = Path(unreal.Paths.project_dir())
_captain_author_begin = time.monotonic()
_captain_author_state = 'wait'
_captain_author_handle = None
_captain_author_exit_at = None
_captain_author_rebuild_at = None
_captain_author_report = {'date': '2026-10-16', 'success': False, 'tests_added_or_run': False}


def _captain_author_finish(error=None):
    global _captain_author_state, _captain_author_exit_at
    _captain_author_report['success'] = error is None
    if error:
        _captain_author_report['error'] = error
        unreal.log_error(error)
    _captain_author_report['elapsed_seconds'] = round(time.monotonic()-_captain_author_begin, 3)
    (_captain_author_root / 'Docs/AI/GuardCaptainAuthoringSession-2026-10-16.json').write_text(
        json.dumps(_captain_author_report, ensure_ascii=False, indent=2), encoding='utf-8')
    _captain_author_state = 'exit'
    _captain_author_exit_at = time.monotonic() + 3.0


def _captain_author_tick(delta):
    global _captain_author_state, _captain_author_exit_at, _captain_author_rebuild_at
    if _captain_author_state == 'running':
        return
    if _captain_author_state == 'exit':
        if time.monotonic() >= _captain_author_exit_at:
            unreal.unregister_slate_post_tick_callback(_captain_author_handle)
            unreal.SystemLibrary.quit_editor()
        return
    if time.monotonic() - _captain_author_begin < 6.0:
        return
    previous_state = _captain_author_state
    _captain_author_state = 'running'
    try:
        if previous_state == 'wait':
            runpy.run_path(str(_captain_author_root / 'Saved/Scripts/create_guard_captain_lab.py'))
            _captain_author_report['assets_saved'] = True
            _captain_author_rebuild_at = time.monotonic()
            _captain_author_state = 'register_navigation'
            return
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        if previous_state == 'register_navigation':
            if time.monotonic()-_captain_author_rebuild_at < 3:
                _captain_author_state = previous_state
                return
            navs = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                    if isinstance(a, unreal.RecastNavMesh)]
            if not navs:
                raise RuntimeError('The new map has no Recast navigation actor.')
            for nav in navs:
                nav.set_editor_property('AgentRadius', 28.0)
                nav.set_editor_property('AgentHeight', 176.0)
                nav.set_editor_property('bForceRebuildOnLoad', True)
                nav.set_editor_property('RuntimeGeneration', unreal.RuntimeGenerationType.DYNAMIC)
            _captain_author_report['recast_count'] = len(navs)
            unreal.SystemLibrary.execute_console_command(world, 'RebuildNavigation')
            _captain_author_rebuild_at = time.monotonic()
            _captain_author_state = 'navigation'
            return
        if time.monotonic()-_captain_author_rebuild_at > 240:
            raise RuntimeError('Navigation authoring timed out.')
        if time.monotonic()-_captain_author_rebuild_at < 5 or unreal.NavigationSystemV1.is_navigation_being_built_or_locked(world):
            _captain_author_state = 'navigation'
            return
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            raise RuntimeError('Could not save the new map after navigation finished.')
        _captain_author_report['navigation_saved'] = True
        _captain_author_report['navigation_building_or_locked_at_save'] = False
        unreal.log('GUARD_CAPTAIN_AUTHORING_FINISHED')
        _captain_author_finish()
    except Exception:
        _captain_author_finish(traceback.format_exc())


_captain_author_handle = unreal.register_slate_post_tick_callback(_captain_author_tick)
