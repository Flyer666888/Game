"""Compare source and destination base actors; allow only documented B changes."""
import unreal,os,json,math
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v03'
V07='/Game/ReversedScale/Maps/L_NilinBlockoutV07'
V08='/Game/ReversedScale/Maps/L_NilinBlockoutV08'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
def xyz(v):return [round(v.x,3),round(v.y,3),round(v.z,3)]
def transform(t):
    q=t.get_editor_property('rotation')
    return {'p':xyz(t.get_editor_property('translation')),'s':xyz(t.get_editor_property('scale3d')),'q':[round(x,5) for x in (q.x,q.y,q.z,q.w)]}
def inventory():
    result={}
    for a in sub.get_all_level_actors():
        if a.actor_has_tag('NLPressureV03'):continue
        entry={'class':a.get_class().get_path_name(),'transform':transform(a.get_actor_transform()),'tags':sorted(str(t) for t in a.get_editor_property('tags'))}
        c=a.get_component_by_class(unreal.StaticMeshComponent)
        if c:
            m=c.get_editor_property('static_mesh');entry['mesh']=m.get_path_name() if m else None
            entry['materials']=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())]
            entry['collision']=str(c.get_collision_profile_name())
        c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
        if c:entry['instances']=[transform(c.get_instance_transform(i,world_space=True)) for i in range(c.get_instance_count())]
        result[a.get_actor_label()]=entry
    return result
def main():
    if editor.get_game_world():raise RuntimeError('End PIE first')
    if not editor.get_editor_world().get_path_name().startswith(V08+'.'):raise RuntimeError('Start comparison in V08')
    dest=inventory()
    for record in json.load(open(os.path.join(OUT,'BuildPressure.json'),encoding='utf-8'))['relocated_racks']:
        dest[record['cluster']]['instances'][record['index']]['p']=[round(x,3) for x in record['old_cm']]
    if not level.load_level(V07):raise RuntimeError('Cannot inspect preserved source')
    source=inventory()
    removed=[key for key in source if key.startswith(('NB_B_EnemyL_','NB_B_EnemyR_','NB_B_CloseMelee_'))]
    expected={key:value for key,value in source.items() if key not in removed}
    missing=sorted(set(expected)-set(dest));extra=sorted(set(dest)-set(expected))
    differences=[{'label':key,'source':expected[key],'destination':dest[key]} for key in expected.keys()&dest.keys() if expected[key]!=dest[key]]
    report={'source':V07,'destination':V08,'source_actor_count':len(source),'unchanged_base_actors':len(dest),'expected_old_enemy_parts_removed':removed,'documented_rack_moves':3,'missing':missing,'extra':extra,'differences':differences,'success':len(source)==657 and len(removed)==12 and not missing and not extra and not differences}
    json.dump(report,open(os.path.join(OUT,'SourceComparison.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    if not level.load_level(V08):raise RuntimeError('Cannot return to V08')
    unreal.log('NILIN_SOURCE_COMPARE '+str(report['success']))
main()
