import unreal,json,os
out=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v02'
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
report={'actors':len(sub.get_all_level_actors()),'world':unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_path_name(),'cluster':bool(unreal.load_class(None,'/Script/experiment.NLBlockoutMeshCluster')),'duplicate_asset_doc':unreal.EditorAssetLibrary.duplicate_asset.__doc__}
json.dump(report,open(os.path.join(out,'LiveProbe.json'),'w',encoding='utf-8'),indent=2)
unreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(),'t.IdleWhenNotForeground 0')
