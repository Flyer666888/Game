import unreal,json,os
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v02'
def main():
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world():raise RuntimeError('End PIE before final camera placement')
    spec=json.load(open(os.path.join(OUT,'LayoutSpec.json'),encoding='utf-8'));allactors=sub.get_all_level_actors()
    vec=lambda p:unreal.Vector(*[v*100 for v in p])
    for c in spec['cameras']:
        if '_00_' in c['name']:c.update(position=[-65,-560,450],target=[-65,200,70],fov=58)
        elif '_06_' in c['name']:c.update(position=[-65,255,1050],target=[-65,255,0],fov=60)
    if not any('_09_' in c['name'] for c in spec['cameras']):
        label='NB_CAM_09_AlternateOverview_0000'
        a=sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector());a.set_actor_label(label);a.set_folder_path('Nilin_V07/07_ReviewCameras')
        a.set_editor_property('tags',[unreal.Name('NLBlockoutV06')])
        ref=next(a for a in allactors if isinstance(a,unreal.CameraActor) and '_00_' in a.get_actor_label())
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('post_process_settings',ref.get_component_by_class(unreal.CameraComponent).get_editor_property('post_process_settings'))
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('constrain_aspect_ratio',False)
        spec['cameras'].append({'name':'CAM_09_AlternateOverview','label':label,'position':[-230,-520,430],'target':[-65,200,65],'fov':58})
    allactors=sub.get_all_level_actors()
    for c in spec['cameras']:
        a=next(a for a in allactors if a.get_actor_label()==c['label'])
        a.set_actor_location(vec(c['position']),False,True);a.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(vec(c['position']),vec(c['target'])),True)
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',c['fov'])
    spec['actor_count']=len(allactors)
    json.dump(spec,open(os.path.join(OUT,'LayoutSpec.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():raise RuntimeError('Final camera save failed')
main()
