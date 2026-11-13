"""End only our active integration fixture after identifying its stair-entry setup error."""
import gc
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
matches = [obj for obj in gc.get_objects()
           if type(obj).__name__ == 'FullRulesProbe'
           and getattr(obj, 'world', None) == world
           and getattr(obj, 'phase', None) == 'stage_active']
assert world is not None and len(matches) == 1
probe = matches[0]
assert str(probe.stage_defs[probe.route_index].stage_id) == 'GM02'
probe.report['failures'].append('Fixture placement stopped at GM02 stair entry outside the authored arena trigger. Product state remained AVAILABLE; rerun uses a valid inside-trigger setup position.')
probe.finish()
