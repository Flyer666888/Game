"""Persist dedicated V07 material usage for HISM without editing V06 assets."""
import unreal,os,json,datetime
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v02'
def main():
    ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world():raise RuntimeError('End PIE before material asset edits')
    world=ed.get_editor_world()
    if not world.get_path_name().startswith('/Game/ReversedScale/Maps/L_NilinBlockoutV07.'):raise RuntimeError('Expected V07')
    lib=unreal.EditorAssetLibrary;mapping={};components=[]
    usage=unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if not a.actor_has_tag('NLBlockout.ClusterV02'):continue
        c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent);components.append(c)
        for i in range(c.get_num_materials()):
            m=c.get_material(i);source=m.get_path_name();dest='/Game/ReversedScale/Blockout/V07/Materials/Instanced/'+m.get_name()
            if source.startswith('/Game/ReversedScale/Blockout/V07/Materials/Instanced/'):mapping[source]=m;continue
            if source not in mapping:
                copy=lib.load_asset(dest) if lib.does_asset_exist(dest) else lib.duplicate_asset(source,dest)
                if not copy:raise RuntimeError('Cannot duplicate HISM material')
                unreal.MaterialEditingLibrary.set_base_material_usage(copy,usage,True)
                unreal.MaterialEditingLibrary.recompile_material(copy)
                if not lib.save_loaded_asset(copy,False):raise RuntimeError('Material save failed')
                if not unreal.MaterialEditingLibrary.has_material_usage(copy,usage):raise RuntimeError('HISM usage did not persist')
                mapping[source]=copy
            c.set_material(i,mapping[source])
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():raise RuntimeError('Cannot save material reassignment')
    report={'updated_at':datetime.datetime.now().isoformat(),'clusters':len(components),'material_remaps':{k:v.get_path_name() for k,v in mapping.items()},'usage':'InstancedStaticMeshes','V06_material_files_modified_by_script':False}
    json.dump(report,open(os.path.join(OUT,'MaterialFix.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.SystemLibrary.execute_console_command(world,'MAP CHECK')
    unreal.log('NILIN_INSTANCE_MATERIALS_SAVED '+str(len(mapping)))
main()
