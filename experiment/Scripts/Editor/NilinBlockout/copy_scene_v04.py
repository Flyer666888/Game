import unreal,json,os
SOURCE='/Game/ReversedScale/Maps/L_NilinBlockoutV08'
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV09'
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v04'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not unreal.EditorAssetLibrary.does_asset_exist(MAP):
    if not ed.get_editor_world().get_path_name().startswith(SOURCE+'.'):raise RuntimeError('Expected V08 source')
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(),MAP):raise RuntimeError('Copy failed')
if not ed.get_editor_world().get_path_name().startswith(MAP+'.'):
    if not level.load_level(MAP):raise RuntimeError('Cannot open independent V09')
if not ed.get_editor_world().get_path_name().startswith(MAP+'.'):raise RuntimeError('Refusing incorrect world')
json.dump({'map':MAP,'state':'independent_copy_loaded'},open(os.path.join(OUT,'Copy.json'),'w'),indent=2)
