"""Replace only the three V10 ranged galleries with natural rock outcrops."""
import ast, json, os, datetime, hashlib, math, unreal
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v05'
REVIEW=os.path.join(OUT,'RockRefinement')
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV10'
FOLDER='Nilin_V10/RangedWalkways'
os.makedirs(REVIEW,exist_ok=True)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(),'End PIE before modifying the saved map'
assert editor.get_editor_world().get_path_name().startswith(MAP+'.'),'Expected V10'

# Reuse the existing tested scene adapter without calling its full-map build.
path=os.path.join(BASE,'build_scene_v05.py')
source=ast.parse(open(path,encoding='utf-8').read(),filename=path)
last=source.body[-1]
assert isinstance(last,ast.Expr) and isinstance(last.value,ast.Call) and isinstance(last.value.func,ast.Name) and last.value.func.id=='main'
source.body.pop()
helpers={'__name__':'__rock_refinement_helpers__','__file__':path}
exec(compile(source,path,'exec'),helpers)

def transform_values(transform):
    p=transform.get_editor_property('translation')
    q=transform.get_editor_property('rotation')
    s=transform.get_editor_property('scale3d')
    return [round(float(v),6) for v in (p.x,p.y,p.z,q.x,q.y,q.z,q.w,s.x,s.y,s.z)]

def outside_signature():
    result=[]
    for a in actors.get_all_level_actors():
        if str(a.get_folder_path())==FOLDER:continue
        item={'name':a.get_actor_label(),'folder':str(a.get_folder_path()),'class':a.get_class().get_path_name(),
              'transform':transform_values(a.get_actor_transform()),'tags':[str(t) for t in a.tags],'meshes':[]}
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            mesh=c.get_editor_property('static_mesh')
            part={'mesh':mesh.get_path_name() if mesh else None,'collision':str(c.get_collision_enabled()),
                  'materials':[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())]}
            if isinstance(c,unreal.InstancedStaticMeshComponent):
                part['instances']=[transform_values(c.get_instance_transform(i,world_space=True)) for i in range(c.get_instance_count())]
            item['meshes'].append(part)
        result.append(item)
    return hashlib.sha256(json.dumps(sorted(result,key=lambda r:r['name']),sort_keys=True).encode()).hexdigest(),len(result)

before_hash,unchanged_actor_count=outside_signature()
spec_path=os.path.join(OUT,'LayoutSpec.json')
spec=json.load(open(spec_path,encoding='utf-8'))
previous=spec['ranged_encounters']
old_actors=[a for a in actors.get_all_level_actors() if str(a.get_folder_path())==FOLDER]
assert old_actors,'No ranged-gallery actors found to replace'
removed=[a.get_actor_label() for a in old_actors]
for a in old_actors:actors.destroy_actor(a)
scene=helpers['Scene']();scene.group='RangedWalkways'
ranged=helpers['ranged_positions_v05'].build(scene)
assert ranged.get('visual_theme')=='natural_rock_outcrops','Rock module is not ready'
assert len(ranged['stations'])==3 and ranged['total_enemies']==6
for old,new in zip(previous['stations'],ranged['stations']):
    assert old['id']==new['id'] and old['access_route']==[list(p) for p in new['access_route']],'Preserve the checked access route'
    for before,after in zip(old['enemies'],new['enemies']):
        assert before['id']==after['id']
        for key in ('foot','projectile_origin','aim_target'):
            assert math.dist(before[key],after[key])<.00001,'Do not move an established enemy firing point'
        helpers['target'](scene,'Enemy_'+after['id'],after['foot'],after['tag'])
spec['ranged_encounters']=ranged
after_hash,after_count=outside_signature()
assert (before_hash,unchanged_actor_count)==(after_hash,after_count),'An actor outside the three ranged sites changed'
assert level.save_current_level(),'Map save failed'
json.dump(spec,open(spec_path,'w',encoding='utf-8'),ensure_ascii=False,indent=2)

scene_path=os.path.join(OUT,'SceneBuild.json')
build=json.load(open(scene_path,encoding='utf-8'))
old_records=build['records']
def ranged_collision_signature(records):
    cores=[{k:r.get(k) for k in ('name','type','center','size','rotation','material','collision')}
           for r in records if r.get('collision') and 'RangedWalkways' in r.get('cluster','')]
    return hashlib.sha256(json.dumps(sorted(cores,key=lambda r:r['name']),sort_keys=True).encode()).hexdigest()
old_collision_hash=ranged_collision_signature(old_records)
new_collision_hash=ranged_collision_signature(scene.records)
collision_preserved=old_collision_hash==new_collision_hash
if previous.get('visual_theme')=='natural_rock_outcrops':
    assert collision_preserved,'An exterior-only revision changed the tested rock collision'
build['records']=[r for r in old_records if 'RangedWalkways' not in r.get('cluster','') and not r['name'].startswith(('V10_Ranged_','V10_R01_','V10_R02_','V10_R03_'))]+scene.records
build.update(time=datetime.datetime.now().isoformat(),actor_count=len(actors.get_all_level_actors()),saved=True)
clusters=[a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent) for a in actors.get_all_level_actors() if a.actor_has_tag('NLEncounterV05')]
clusters=[c for c in clusters if c]
build.update(new_clusters=len(clusters),new_instances=sum(c.get_instance_count() for c in clusters))
change={'kind':'three ranged pavilion galleries replaced by natural rock outcrops','map':MAP,'saved_at':build['time'],
        'removed_actor_labels':removed,'new_records':scene.records,'outside_actor_count':unchanged_actor_count,
        'outside_geometry_signature_before':before_hash,'outside_geometry_signature_after':after_hash,
        'outside_geometry_unchanged':before_hash==after_hash,'access_routes_unchanged':True,'enemy_positions_and_shot_lanes_unchanged':True,
        'rock_collision_signature_before':old_collision_hash,'rock_collision_signature_after':new_collision_hash,
        'rock_collision_unchanged_from_preceding_revision':collision_preserved,
        'static_enemies':6,'implemented_ai':False}
build['rock_refinement']={k:v for k,v in change.items() if k!='new_records'}
json.dump(build,open(scene_path,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
json.dump(change,open(os.path.join(REVIEW,'ChangeReport.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
unreal.log('NILIN_ROCK_OUTCROPS_SAVED')
