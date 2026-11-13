"""Recover only this session's completed probe after a stale-wrapper cleanup error."""
import gc
import json
from pathlib import Path
import unreal

out = Path(unreal.Paths.project_dir()).resolve() / 'Docs/Gameplay/Level01Polish_v01'
isolation = json.loads((out / 'FixtureIsolation.json').read_text(encoding='utf-8'))
uid = isolation['temporary_level_id'].removeprefix('Test.Level01.')
assert len(uid) == 32
probes = [obj for obj in gc.get_objects()
          if type(obj).__name__ == 'FirstLevelProbe' and getattr(obj, 'uid', None) == uid]
assert len(probes) == 1, 'Expected one exact pending probe'

def safe_valid(obj):
    try:
        return obj is not None and unreal.SystemLibrary.is_valid(obj)
    except (TypeError, RuntimeError):
        return False

probe = probes[0]
type(probe).valid = staticmethod(safe_valid)
probe.report['harness_recovery'] = 'Stale destroyed-encounter Python wrappers are now treated as invalid. Original failure history retained; a fresh run is required.'
probe.finish()
