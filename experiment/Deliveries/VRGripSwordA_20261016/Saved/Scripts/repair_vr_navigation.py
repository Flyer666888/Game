"""Inspect/author the VR map's navigation assets. Does not start gameplay.

Full-editor caller example:
    api = runpy.run_path(str(root / 'Saved/Scripts/repair_vr_navigation.py'))
    before = api['inspect_navigation']()
    api['repair_navigation']()
    # Wait for Slate/editor navigation generation, then:
    api['save_navigation'](before)
"""
import json
from pathlib import Path
import unreal

MAP = '/Game/ReversedScale/Maps/L_CombatLabVR'
ROOT = Path(unreal.Paths.project_dir())


def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _value(obj, name):
    try:
        value = obj.get_editor_property(name)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, unreal.Object):
            return value.get_path_name()
        return str(value)
    except Exception as error:
        return {'unavailable': str(error)}


def _vector(value):
    return [value.x, value.y, value.z]


def _config(config):
    if not config:
        return None
    result = {'object': config.get_path_name(), 'class': config.get_class().get_path_name()}
    for name in ('navigation_system_class', 'default_agent_name', 'supported_agents_mask',
                 'bStrictlyStatic', 'bAutoSpawnMissingNavData', 'bCreateOnClient',
                 'bSpawnNavDataInNavBoundsLevel'):
        result[name] = _value(config, name)
    return result


def _override_config(settings):
    # This transient, non-Edit UPROPERTY has no generated snake_case alias.
    # get_editor_property falls back to native FProperty names in UE's wrapper.
    try:
        return _config(settings.get_editor_property('NavigationSystemConfigOverride'))
    except Exception as error:
        return {'unavailable': str(error), 'native_property': 'NavigationSystemConfigOverride'}


def inspect_navigation(report_path=None):
    world = _world()
    settings = world.get_world_settings()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    report = {'map': world.get_path_name(), 'config': _config(settings.get_editor_property('navigation_system_config')),
              'override': _override_config(settings),
              'navigation_system': None, 'nav_data': [], 'bounds': [], 'player_starts': [], 'floors': [],
              'scope': 'Read authored navigation settings and component bounds only; no gameplay or path queries.'}
    navigation = unreal.NavigationSystemV1.get_navigation_system(world)
    report['navigation_system'] = navigation.get_path_name() if navigation else None
    if navigation:
        report['navigation_building_or_locked'] = unreal.NavigationSystemV1.is_navigation_being_built_or_locked(world)
        report['system_settings'] = {name: _value(navigation, name) for name in
                                     ('bAutoCreateNavigationData', 'bInitialBuildingLocked', 'bWholeWorldNavigable',
                                      'bGenerateNavigationOnlyAroundNavigationInvokers', 'supported_agents')}
    for actor in actors:
        if isinstance(actor, unreal.RecastNavMesh):
            report['nav_data'].append({'actor': actor.get_path_name(), **{name: _value(actor, name) for name in
                                      ('AgentRadius', 'AgentHeight', 'bForceRebuildOnLoad', 'runtime_generation')}})
        elif isinstance(actor, unreal.NavMeshBoundsVolume):
            origin, extent = actor.get_actor_bounds(False)
            report['bounds'].append({'actor': actor.get_path_name(), 'origin': _vector(origin), 'extent': _vector(extent),
                                     'supported_agents': _value(actor, 'supported_agents')})
        elif isinstance(actor, unreal.PlayerStart):
            report['player_starts'].append({'actor': actor.get_path_name(), 'location': _vector(actor.get_actor_location()),
                                            'yaw': actor.get_actor_rotation().yaw})
        elif isinstance(actor, unreal.StaticMeshActor) and any(word in actor.get_actor_label().lower()
                                                               for word in ('floor', 'ground', 'platform')):
            mesh = actor.get_component_by_class(unreal.StaticMeshComponent)
            origin, extent = actor.get_actor_bounds(False)
            report['floors'].append({'label': actor.get_actor_label(), 'origin': _vector(origin), 'extent': _vector(extent),
                                    'collision_profile': str(mesh.get_collision_profile_name()),
                                    'affects_navigation': _value(mesh, 'bCanEverAffectNavigation')})
    if report_path is not None:
        Path(report_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def _is_dynamic(value):
    label = str(value).lower()
    if 'dynamic' in label and 'modifiers' not in label:
        return True
    try:
        return int(value) == 2
    except (TypeError, ValueError):
        return False


def _dynamic_generation():
    # UE exports may omit a named Python enum wrapper, but the reflected CDO
    # value remains usable for round-tripping this config-backed enum property.
    cdo = unreal.get_default_object(unreal.RecastNavMesh)
    value = cdo.get_editor_property('RuntimeGeneration')
    if not _is_dynamic(value):
        raise RuntimeError('Recast CDO is not Dynamic; inspect DefaultEngine.ini before saving navigation: ' + str(value))
    return value


def repair_navigation():
    world = _world()
    if MAP not in world.get_path_name():
        raise RuntimeError('Load the dedicated VR map before repairing navigation.')
    settings = world.get_world_settings()
    module_class = unreal.load_class(None, '/Script/NavigationSystem.NavigationSystemModuleConfig')
    config = settings.get_editor_property('navigation_system_config')
    # A copied NullNavSysConfig must be replaced with a real module config.
    if not config or config.get_class() != module_class:
        config = unreal.new_object(module_class, outer=settings, name='VRNavigationConfig')
    config.set_editor_property('navigation_system_class', unreal.SoftClassPath('/Script/NavigationSystem.NavigationSystemV1'))
    config.set_editor_property('default_agent_name', unreal.Name('SwordDisciple'))
    config.set_editor_property('bStrictlyStatic', False)
    config.set_editor_property('bAutoSpawnMissingNavData', True)
    config.set_editor_property('bCreateOnClient', True)
    mask = config.get_editor_property('supported_agents_mask')
    mask.set_editor_property('bSupportsAgent0', True)
    config.set_editor_property('supported_agents_mask', mask)
    override_action = 'none'
    try:
        override = settings.get_editor_property('NavigationSystemConfigOverride')
        if override:
            settings.set_editor_property('NavigationSystemConfigOverride', None)
            override_action = 'cleared_transient_override'
    except Exception as error:
        # An unavailable transient override must not block repair of the map's
        # real editable configuration. Report it for the editor authoring log.
        override_action = {'unavailable': str(error)}
    # The config property change recreates the editor world's navigation system.
    settings.set_editor_property('navigation_system_config', config)
    actors_api = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actors_api.get_all_level_actors()
    volumes = [actor for actor in actors if isinstance(actor, unreal.NavMeshBoundsVolume)]
    if not volumes:
        raise RuntimeError('Expected the inherited real navigation brush; none found. Do not save an empty replacement volume.')
    for volume in volumes:
        origin, extent = volume.get_actor_bounds(False)
        if extent.x < 1400 or extent.y < 1100 or extent.z < 200:
            raise RuntimeError('The navigation brush no longer covers the authored arena: ' + str(extent))
        mask = volume.get_editor_property('supported_agents')
        mask.set_editor_property('bSupportsAgent0', True)
        volume.set_editor_property('supported_agents', mask)
    nav_data = [actor for actor in actors if isinstance(actor, unreal.RecastNavMesh)]
    if not nav_data:
        nav = actors_api.spawn_actor_from_class(unreal.RecastNavMesh, unreal.Vector(300.0, 0.0, 0.0))
        if not nav:
            raise RuntimeError('Could not author the missing Recast navigation data actor.')
        nav.set_actor_label('RecastNavMesh-SwordDisciple')
        nav_data = [nav]
    for nav in nav_data:
        nav.set_editor_property('AgentRadius', 28.0)
        nav.set_editor_property('AgentHeight', 176.0)
        nav.set_editor_property('bForceRebuildOnLoad', True)
        nav.set_editor_property('RuntimeGeneration', _dynamic_generation())
        if not _is_dynamic(nav.get_editor_property('RuntimeGeneration')):
            raise RuntimeError('Recast did not retain Dynamic runtime generation.')
    unreal.SystemLibrary.execute_console_command(world, 'RebuildNavigation')
    return {'authoring_started': True, 'map': MAP, 'transient_override': override_action,
            'note': 'Allow editor ticks to finish generation before saving.'}


def save_navigation(before, report_path=None, date='2026-10-16'):
    after = inspect_navigation()
    if not after['navigation_system'] or not after['nav_data']:
        raise RuntimeError('Navigation system or Recast data is still missing; do not deliver as repaired.')
    if after.get('navigation_building_or_locked'):
        raise RuntimeError('Navigation is still building/locked. Continue editor ticks before saving.')
    for nav in after['nav_data']:
        if not _is_dynamic(nav['runtime_generation']):
            raise RuntimeError('Recast runtime generation is not Dynamic: ' + str(nav))
    if not any(row['extent'][0] >= 1400 and row['extent'][1] >= 1100 and row['extent'][2] >= 200
               for row in after['bounds']):
        raise RuntimeError('No real navigation brush covers the arena.')
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError('Failed to save the repaired VR navigation map.')
    report = {'date': date, 'before': before, 'after': after, 'saved': True,
              'scope': 'Navigation asset authoring/build/save only. No enemies spawned and no gameplay/path test.'}
    if report_path is not None:
        Path(report_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
