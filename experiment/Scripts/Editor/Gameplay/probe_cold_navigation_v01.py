import unreal,json
from pathlib import Path
out=Path(r'D:\game design\experiment\Docs\Gameplay\EncounterRecovery_v01')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
cfg=json.loads((out/'EncounterConfig.json').read_text(encoding='utf-8'))
report={'world':world.get_path_name(),'busy':unreal.NavigationSystemV1.is_navigation_being_built_or_locked(world),'navs':[],'volumes':[],'points':[]}
v=lambda p:[p.x,p.y,p.z]
for actor in actors:
    if isinstance(actor,unreal.NavMeshBoundsVolume):
        origin,extent=actor.get_actor_bounds(False)
        report['volumes'].append({'actor':actor.get_path_name(),'bounds':[v(origin),v(extent)],'scale':v(actor.get_actor_scale3d())})
    if isinstance(actor,unreal.RecastNavMesh):
        item={'actor':actor.get_path_name()}
        for prop in ('runtime_generation','force_rebuild_on_load','fixed_tile_pool_size','tile_pool_size','tile_size_uu','agent_radius','agent_height','min_region_area'):
            item[prop]=str(actor.get_editor_property(prop))
        item['resolutions']=[{p:r.get_editor_property(p) for p in ('cell_size','cell_height','agent_max_step_height')} for r in actor.get_editor_property('nav_mesh_resolution_params')]
        report['navs'].append(item)
for stage in cfg['stages']:
    point=stage['spawn_points'][0]
    ground=unreal.Vector(*[x*100 for x in point['ground_m']])
    proj=unreal.NavigationSystemV1.project_point_to_navigation(world,ground,None,None,unreal.Vector(100,100,250))
    report['points'].append({'stage':stage['id'],'ground':v(ground),'projection':v(proj) if proj is not None else None})
(out/'ColdNavigationProbe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
