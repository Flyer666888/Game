"""Read-only world inventory, update JSON metadata without resaving the level."""
import os,json,unreal
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v03'
def main():
    ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if not ed.get_editor_world().get_path_name().startswith('/Game/ReversedScale/Maps/L_NilinBlockoutV08.'):raise RuntimeError('Expected V08')
    clusters=[];cubes=enemies=0
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
        if not c:continue
        n=c.get_instance_count();mesh=c.get_editor_property('static_mesh').get_path_name()
        clusters.append({'label':a.get_actor_label(),'instances':n,'mesh':mesh})
        if mesh.startswith('/Engine/BasicShapes/Cube.'):cubes+=n
        elif 'GuardSilhouette' in mesh:enemies+=n
    assert len(clusters)==39 and enemies==36
    for name in ('LayoutSpec.json','Readback.json'):
        path=os.path.join(OUT,name);data=json.load(open(path,encoding='utf-8'))
        data['cluster_count']=len(clusters);data['instanced_cubes']=cubes;data['instanced_enemy_silhouettes']=enemies
        data['instance_count']=sum(c['instances'] for c in clusters)
        if name=='Readback.json':data['clusters']=clusters
        json.dump(data,open(path,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.log('NILIN_NATIVE_PRESSURE_COUNTS_OK '+str(cubes)+' cubes and '+str(enemies)+' guards')
main()
