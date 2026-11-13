import unreal,json,os
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v01'
ns={}
source=open(os.path.join(BASE,'build_blockout.py'),encoding='utf-8').read()
exec(compile(source.split('\ntry:\n    main()')[0],'<blockout_helpers>','exec'),ns)
world=ns['editor'].get_editor_world()
assert world.get_path_name().startswith(ns['MAP']+'.')
allactors=ns['actors'].get_all_level_actors()
right_workshop=[a for a in allactors if 'NB_AlchemyWorkshop_' in a.get_actor_label() and a.get_actor_location().x>0]
shift_workshop=bool(right_workshop) and sum(a.get_actor_location().y for a in right_workshop)/len(right_workshop)<32000
for a in right_workshop:
    if shift_workshop and not a.actor_has_tag('NLBlockout.WorkshopExitClear'):
        p=a.get_actor_location();p.y+=700;a.set_actor_location(p,False,True)
        a.set_editor_property('tags',list(a.get_editor_property('tags'))+[unreal.Name('NLBlockout.WorkshopExitClear')])
ns['group']='08_GameplayMarkers'
for key in ('Cube','Cylinder','Sphere','Cone'):ns['meshes'][key]=unreal.load_asset('/Engine/BasicShapes/'+key)
for key in ('Stone','Dummy','Accent','Warm'):ns['materials'][key]=unreal.load_asset(ns['FOLDER']+'/Materials/M_'+key)
if not any(a.actor_has_tag('NLBlockout.Refinement') for a in allactors):
    ns['dummy']('A_CloseMelee_L',(-4,12,0));ns['dummy']('A_CloseMelee_R',(4,12,0))
    ns['dummy']('B_CloseMelee_L',(-4,134,28));ns['dummy']('B_CloseMelee_R',(4,134,28))
    ns['dummy']('C_Breaker',(4,284,72),'Warm')
    a=ns['shape']('D_TargetEye',(226,579,133),(1.6,1.6,2),'Accent','Cone',collision=False)
    a.set_editor_property('tags',list(a.get_editor_property('tags'))+[unreal.Name('NLBlockout.Refinement')])
    ns['cyl']('A_CombatStand',(0,4,.025),.8,.035,'Accent',False)
    for a,b in [((232,592,132.03),(232,603,132.03)),((232,603,132.03),(220,605,132.03))]:ns['beam']('VictoryAfterBossRoute',a,b,.12,.025,'Accent',False)
assert ns['levels'].save_current_level()
p=os.path.join(OUT,'LayoutSpec.json');data=json.load(open(p,encoding='utf-8'))
data['gameplay_notes']={'transition_only_nodes':[2,4,6],'combat_stand_A':[0,4,0],'triangle_eye':[226,579,132],'breaker':[4,284,72],'victory_route':[[232,592,132],[232,603,132],[220,605,132]],'markers':'Layout placeholders only; combat AI is not connected','workshop_right_center':[27,323,72]}
data['actor_count']=len(ns['actors'].get_all_level_actors())
json.dump(data,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
unreal.log('NILIN_FINAL_REFINEMENT_OK')
