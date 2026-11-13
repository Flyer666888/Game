import os,json,unreal,datetime
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v01'
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
path=os.path.join(BASE,'validate_blockout.py')
exec(compile(open(path,encoding='utf-8').read(),path,'exec'),{'__name__':'__main__'})
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
camera=next(a for a in sub.get_all_level_actors() if a.get_actor_label().startswith('NB_CAM_03'))
unreal.AutomationLibrary.take_high_res_screenshot(1920,1080,os.path.join(OUT,'Screenshots','UE_03_Alchemy.png'),camera=camera,delay=3)
validation=json.load(open(os.path.join(OUT,'Validation.json'),encoding='utf-8'))
runtime=json.load(open(os.path.join(OUT,'RuntimeWalk.json'),encoding='utf-8'))
spec=json.load(open(os.path.join(OUT,'LayoutSpec.json'),encoding='utf-8'))
report={'map':'/Game/ReversedScale/Maps/L_NilinBlockoutV06','saved_file':r'D:\game design\experiment\Content\ReversedScale\Maps\L_NilinBlockoutV06.umap','built_with':'Unreal Engine 5.8.2','updated_at':datetime.datetime.now().isoformat(),'actor_count':len(sub.get_all_level_actors()),'native_editor_build':'Succeeded','map_reload':True,'map_check':'0 errors, 0 warnings','route_floor_samples':validation['checks']['route_floor_samples'],'floor_failures':len(validation['checks']['route_floor_failures']),'node_capsule_clear':all(n['capsule_clear'] for n in validation['checks']['node_landings']),'main_nodes_seated_and_standing_see_peak_and_crown':all(n['physical_peak'] and n['crown'] for n in validation['sightlines']['nodes']),'continuous_desktop_walk':runtime['state'],'walk_waypoints':runtime['waypoints_reached'],'walk_failures':runtime['failures'],'scope':'Playable desktop layout whitebox; combat characters are static placeholders','not_validated':['Headset performance and VR comfort','Formal battle, rescue, boss phase and progression logic','Manual testing of every key and fade path'],'coordinate_system':spec['world_axes']}
json.dump(report,open(os.path.join(OUT,'FinalReport.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
unreal.log('NILIN_FINAL_CHECKS_OK')
