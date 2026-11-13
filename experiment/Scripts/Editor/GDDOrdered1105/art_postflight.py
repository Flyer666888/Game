"""Read saved art, material usage, authored births and baked navigation."""
import hashlib,json,math
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/GDDOrdered1105'
E=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
L=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert E.get_game_world() is None
if not E.get_editor_world().get_path_name().startswith('/Game/ReversedScale/Maps/L_NilinGameplayV01.'):
    assert L.load_level('/Game/ReversedScale/Maps/L_NilinGameplayV01')
world=E.get_editor_world();actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
report=json.loads((O/'ArtApplied.json').read_text(encoding='utf-8-sig'));assert report['state']=='passed'
usage=unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES
materials=[]
for path in report['materials'].values():
    m=unreal.load_asset(path);assert m
    materials.append({'asset':path,'instanced_usage':unreal.MaterialEditingLibrary.has_material_usage(m,usage)})
decor=[]
for actor in actors:
    if not actor.actor_has_tag('NL.GDD1105.Art'):continue
    for c in actor.get_components_by_class(unreal.StaticMeshComponent):
        if isinstance(actor,unreal.CameraActor):continue
        decor.append({'actor':actor.get_actor_label(),'collision':str(c.get_collision_enabled()),
            'navigation':c.get_editor_property('can_ever_affect_navigation'),
            'materials_support_instancing':all(unreal.MaterialEditingLibrary.has_material_usage(c.get_material(i),usage)
                for i in range(c.get_num_materials()) if c.get_material(i))})
director=next(a for a in actors if isinstance(a,unreal.NLLevelEncounterDirector))
navs=[a for a in actors if isinstance(a,unreal.RecastNavMesh)]
assert len(navs)==1,[(a.get_name(),a.get_class().get_name()) for a in actors if 'Nav' in a.get_class().get_name()]
assert not unreal.NavigationSystemV1.is_navigation_being_built_or_locked(world),'Navigation has not settled after map load'
points=[]
for stage in director.stages:
    entry=stage.entry_transform.translation-unreal.Vector(0,0,88)
    for point in stage.spawn_points:
        ground=point.spawn_transform.translation-unreal.Vector(0,0,88)
        projected=unreal.NavigationSystemV1.project_point_to_navigation(world,ground,navs[0],None,unreal.Vector(60,60,180))
        valid=projected is not None and (projected-ground).length()<180
        path=unreal.NavigationSystemV1.find_path_to_location_synchronously(world,entry,projected) if valid else None
        points.append({'stage':str(stage.stage_id),'point':str(point.spawn_point_id),'projection':valid,
            'path':path is not None and path.is_valid() and not path.is_partial()})
file=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
checks={'all_new_materials_support_instancing':all(m['instanced_usage'] for m in materials),
    'cosmetic_meshes_have_no_collision':all('NO_COLLISION' in d['collision'] for d in decor),
    'cosmetic_meshes_do_not_affect_navigation':all(not d['navigation'] for d in decor),
    'all_decor_materials_support_instancing':all(d['materials_support_instancing'] for d in decor),
    'all_16_stages_present':len(director.stages)==16,'spawn_projection_and_path':all(p['projection'] and p['path'] for p in points),
    'baked_static_nav_retained':navs[0].get_editor_property('runtime_generation')==unreal.RuntimeGenerationType.STATIC and not navs[0].get_editor_property('force_rebuild_on_load'),
    'saved_art_map_hash_matches':hashlib.sha256(file.read_bytes()).hexdigest()==report['map_sha256_after']}
(O/'ArtPostflight.json').write_text(json.dumps({'state':'passed' if all(checks.values()) else 'failed','checks':checks,
    'materials':materials,'cosmetic_components':decor,'spawn_checks':points,'spawn_reference_count':len(points)},ensure_ascii=False,indent=2),encoding='utf-8')
assert all(checks.values()),checks
