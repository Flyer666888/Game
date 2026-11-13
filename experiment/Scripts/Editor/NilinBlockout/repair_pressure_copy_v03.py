"""Restore the V07 source from the pristine copy, then edit only loaded V08."""
import unreal,os,json
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v03'
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
V07='/Game/ReversedScale/Maps/L_NilinBlockoutV07'
V08='/Game/ReversedScale/Maps/L_NilinBlockoutV08'
report={'initial_world':editor.get_editor_world().get_path_name()}
if editor.get_editor_world().get_path_name().startswith(V07+'.'):
    if not level.load_level(V08):raise RuntimeError('Cannot load pristine V08 copy')
    copied=list(actors.get_all_level_actors())
    report['pristine_actor_count']=len(copied)
    report['pristine_pressure_actors']=sum(a.actor_has_tag('NLPressureV03') for a in copied)
    if report['pristine_actor_count']!=657 or report['pristine_pressure_actors']!=0:raise RuntimeError('Pristine original copy verification failed')
    copied=[]
    if not unreal.EditorLoadingAndSavingUtils.save_map(editor.get_editor_world(),V07):raise RuntimeError('Cannot restore original source')
    # save_map does not change the loaded world. A real load is mandatory.
    if not level.load_level(V07):raise RuntimeError('Cannot read restored V07')
    report['restored_world']=editor.get_editor_world().get_path_name()
    restored=list(actors.get_all_level_actors())
    report['restored_actor_count']=len(restored)
    report['restored_pressure_actors']=sum(a.actor_has_tag('NLPressureV03') for a in restored)
    if report['restored_actor_count']!=657 or report['restored_pressure_actors']:raise RuntimeError('Restored source is not pristine')
    restored=[]
    if not level.load_level(V08):raise RuntimeError('Cannot select real destination')
if not editor.get_editor_world().get_path_name().startswith(V08+'.'):raise RuntimeError('Unexpected destination')
report['editing_world']=editor.get_editor_world().get_path_name()
json.dump(report,open(os.path.join(OUT,'SourcePreservation.json'),'w',encoding='utf-8'),indent=2)
path=os.path.join(BASE,'build_pressure_v03.py')
exec(compile(open(path,encoding='utf-8').read(),path,'exec'),{'__name__':'__main__'})
