import unreal,json,os
SOURCE='/Game/ReversedScale/Maps/L_NilinBlockoutV09'
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV10'
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v05'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not unreal.EditorAssetLibrary.does_asset_exist(MAP):
    if not ed.get_editor_world().get_path_name().startswith(SOURCE+'.'):raise RuntimeError('Expected V09 source')
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(),MAP):raise RuntimeError('Copy failed')
if not ed.get_editor_world().get_path_name().startswith(MAP+'.'):
    if not level.load_level(MAP):raise RuntimeError('Cannot open independent V10')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
records=[]
for a in actors.get_all_level_actors():
    p=a.get_actor_location();b,e=a.get_actor_bounds(False)
    c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
    rec={'label':a.get_actor_label(),'folder':str(a.get_folder_path()),'class':a.get_class().get_name(),'position':[p.x/100,p.y/100,p.z/100],'bounds_center':[b.x/100,b.y/100,b.z/100],'bounds_extent':[e.x/100,e.y/100,e.z/100],'tags':[str(t) for t in a.get_editor_property('tags')]}
    if c:
        rec['instances']=[]
        for i in range(c.get_instance_count()):
            tr=c.get_instance_transform(i,world_space=True);p=tr.get_editor_property('translation');s=tr.get_editor_property('scale3d')
            rec['instances'].append({'index':i,'position':[p.x/100,p.y/100,p.z/100],'scale':[s.x,s.y,s.z]})
    records.append(rec)
json.dump({'map':MAP,'state':'independent_copy_loaded','actors':records},open(os.path.join(OUT,'SourceActors.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
