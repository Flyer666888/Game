import unreal,json,os,datetime,collections
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v05'
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV10'
def main():
    ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);world=ed.get_editor_world()
    if not world.get_path_name().startswith(MAP+'.'):raise RuntimeError('Unexpected final map')
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    spec=json.load(open(os.path.join(OUT,'LayoutSpec.json'),encoding='utf-8'));nodes=[];clusters=[]
    if spec.get('map')!=MAP or not unreal.EditorAssetLibrary.does_asset_exist(MAP):raise RuntimeError('V10 source/asset is not saved')
    dirty=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if MAP in dirty:raise RuntimeError('V10 map has unsaved changes; save it before readback')
    for n in spec['nodes']:
        matches=[a for a in actors if isinstance(a,unreal.TargetPoint) and a.actor_has_tag('NLBlockout.Node.%02d'%n['index'])]
        if len(matches)!=1:raise RuntimeError('Non-unique node '+str(n['index']))
        p=matches[0].get_actor_location();actual=[p.x/100,p.y/100,p.z/100]
        error=max(abs(actual[i]-n['ground'][i]) for i in range(3))
        if error>.001:raise RuntimeError('Node placement differs from spec')
        nodes.append({'index':n['index'],'actual_ground':actual,'error_m':error})
    for a in actors:
        if a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent):
            c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            clusters.append({'label':a.get_actor_label(),'instances':c.get_instance_count()})
    report={'map':MAP,'world':world.get_path_name(),'checked_at':datetime.datetime.now().isoformat(),'actor_count':len(actors),'classes':dict(collections.Counter(a.get_class().get_name() for a in actors)),'nodes':nodes,'clusters':clusters,'cluster_count':len(clusters),'instance_count':sum(c['instances'] for c in clusters),'gamemode':world.get_world_settings().get_editor_property('default_game_mode').get_path_name()}
    report['save_confirmed']=True
    report['saved_asset_exists']=True
    report['loaded_map_dirty']=False
    report['read_only_audit']=True
    report['success']=True
    report['new_encounter_geometry']={'grandmaster_arenas':spec.get('grandmaster_arenas',[]),'boss_arena':spec.get('boss_arena'),'ranged_stations':len(spec.get('ranged_encounters',{}).get('stations',[]))}
    json.dump(report,open(os.path.join(OUT,'Readback.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.SystemLibrary.execute_console_command(world,'MAP CHECK')
    unreal.log('NILIN_FINAL_READBACK_OK '+str(len(actors)))
main()

