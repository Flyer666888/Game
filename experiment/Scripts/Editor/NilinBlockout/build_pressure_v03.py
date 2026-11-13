"""Create an independent V08 enemy-height visual prototype from the saved V07."""
import os,sys,json,math,datetime,hashlib,unreal,importlib
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
ROOT=r'D:\game design\experiment'
OUT=os.path.join(ROOT,'Docs','LevelDesign','Blockout_v03')
SOURCE='/Game/ReversedScale/Maps/L_NilinBlockoutV07'
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV08'
ASSET='/Game/ReversedScale/Blockout/V08'
TAG='NLPressureV03'
sys.path.insert(0,BASE)
import pressure_layout_v03,ue_mesh_v02,mesh_shapes_v02
importlib.reload(pressure_layout_v03)
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assets=unreal.EditorAssetLibrary
clusters={};materials={};serial=0
relocated=[]
def v(p):return unreal.Vector(*[float(t)*100 for t in p])
def tags(a,name):
    a.set_actor_label('NB3_'+name)
    a.set_folder_path('Nilin_V08/EnemyPressure')
    a.set_editor_property('tags',[unreal.Name(TAG)])
    return a
def material(key,source):
    path=ASSET+'/Materials/M_'+key
    m=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset(source,path)
    if not m:raise RuntimeError('Cannot create owned material '+path)
    unreal.MaterialEditingLibrary.set_base_material_usage(m,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES,True)
    unreal.MaterialEditingLibrary.recompile_material(m)
    assets.save_loaded_asset(m,False);materials[key]=m
    return m
def inst(name,mesh,p,scale=(1,1,1),mat='Stone',collision=True,yaw=0):
    key=(mesh.get_path_name(),mat,collision)
    if key not in clusters:
        cls=unreal.load_class(None,'/Script/experiment.NLBlockoutMeshCluster')
        a=tags(sub.spawn_actor_from_class(cls,unreal.Vector()),'Pressure_'+mat+'_'+str(len(clusters)))
        c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
        c.set_static_mesh(mesh);c.set_material(0,materials[mat]);c.set_mobility(unreal.ComponentMobility.STATIC)
        c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
        c.set_editor_property('can_ever_affect_navigation',collision)
        if not collision:a.set_editor_property('tags',list(a.get_editor_property('tags'))+[unreal.Name('NLPressure.DisplayOnly')])
        clusters[key]=(a,c)
    transform=unreal.Transform(location=v(p),rotation=unreal.Rotator(yaw=yaw),scale=unreal.Vector(*scale))
    return clusters[key][1].add_instance(transform,world_space=True)
def box(name,p,size,mat='Stone',collision=True):return inst(name,unreal.load_asset('/Engine/BasicShapes/Cube'),p,size,mat,collision)
def guard_mesh():
    vertices=[];triangles=[]
    def append(vs,ts):
        offset=len(vertices);vertices.extend(vs);triangles.extend([tuple(q+offset for q in t) for t in ts])
    def cube(center,size):
        x,y,z=center;w,d,h=size
        vs=[(x+a*w/2,y+b*d/2,z+c*h/2) for c in (-1,1) for b in (-1,1) for a in (-1,1)]
        ts=[(0,2,3),(0,3,1),(4,5,7),(4,7,6),(0,1,5),(0,5,4),(2,6,7),(2,7,3),(0,4,6),(0,6,2),(1,3,7),(1,7,5)]
        append(vs,ts)
    for x in (-.16,.16):cube((x,0,.30),(.18,.24,.60))
    robe,rt=mesh_shapes_v02.lathe([(.42,.36),(.55,.35),(1.03,.22),(1.31,.30),(1.40,.25)],12)
    append([(x,y*.65,z) for x,y,z in robe],rt)
    for x in (-.36,.36):cube((x,0,1.17),(.20,.30,.48))
    head,ht=mesh_shapes_v02.lathe([(1.43,.10),(1.48,.17),(1.65,.18),(1.77,.12),(1.79,.04)],12)
    append(head,ht);cube((0,.015,1.84),(.12,.12,.10))
    # Vertical sword and crossguard retain the whitebox silhouette at distance.
    cube((.46,-.08,.69),(.055,.075,1.14));cube((.46,-.08,1.10),(.25,.08,.045))
    digest=hashlib.sha1(json.dumps([vertices,triangles]).encode()).hexdigest()[:8]
    return ue_mesh_v02.make_asset(ASSET+'/Meshes/SM_GuardSilhouette_'+digest,vertices,triangles,False)
def main():
    os.makedirs(OUT,exist_ok=True)
    if not assets.does_asset_exist(MAP):
        if not editor.get_editor_world().get_path_name().startswith(SOURCE+'.'):raise RuntimeError('Create V08 from V07 only')
        if not unreal.EditorLoadingAndSavingUtils.save_map(editor.get_editor_world(),MAP):raise RuntimeError('Independent copy failed')
        if not level.load_level(MAP):raise RuntimeError('Cannot switch to independent copy')
    elif not editor.get_editor_world().get_path_name().startswith(MAP+'.'):
        raise RuntimeError('Open V08 before updating existing prototype')
    if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):raise RuntimeError('Destination world must be loaded before edits')
    previous_path=os.path.join(OUT,'BuildPressure.json')
    if os.path.exists(previous_path):
        relocated.extend(json.load(open(previous_path,encoding='utf-8')).get('relocated_racks',[]))
    for a in list(sub.get_all_level_actors()):
        if a.actor_has_tag(TAG) or a.get_actor_label().startswith(('NB_B_EnemyL_','NB_B_EnemyR_','NB_B_CloseMelee_')):sub.destroy_actor(a)
    # V07's screen-right weapon poles occupy the new access stairs. Move only
    # those three existing instances under the adjacent gallery, in this copy.
    for a in sub.get_all_level_actors():
        if not a.actor_has_tag('NLBlockout.ClusterV02'):continue
        c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
        if not c:continue
        for i in range(c.get_instance_count()):
            tr=c.get_instance_transform(i,world_space=True);p=tr.get_editor_property('translation')
            if abs(p.x+1875)<1 and min(abs(p.y-y) for y in (14500,14900,15300))<1 and abs(p.z-2965)<1:
                old=[p.x,p.y,p.z];p.x=-2130;tr.set_editor_property('translation',p)
                c.update_instance_transform(i,tr,world_space=True,mark_render_state_dirty=True,teleport=True)
                relocated.append({'cluster':a.get_actor_label(),'index':i,'old_cm':old,'new_cm':[p.x,p.y,p.z]})
    pressure=pressure_layout_v03.make_pressure()
    for key,source in [('Stone','Stone'),('Floor','Floor'),('Trim','Trim'),('Enemy','Dummy')]:
        material(key,'/Game/ReversedScale/Blockout/V06/Materials/M_'+source)
    guard=guard_mesh()
    for t in pressure['terraces']:
        x,y,z=t['center'];w,d=t['size'];h=t['height']
        box(t['name']+'_Masonry',(x,y,28+(h-.18)/2),(w,d,h-.18))
        box(t['name']+'_Cap',(x,y,z-.09),(w,d,.18),'Floor')
        # Recessed frame and plinth bands echo Chinese stone inspection terraces.
        box(t['name']+'_FrontBelt',(x,y-d/2-.012,z-.26),(w,.06,.14),'Trim',False)
        for xx in (x-w/2+.22,x+w/2-.22):
            box(t['name']+'_Corner',(xx,y-d/2+.20,28+h/2),(.36,.40,h),'Stone')
        if t['rank']==3:
            # Rear parapet, never between the viewer and enemy silhouettes.
            box(t['name']+'_BackParapet',(x,163.65,z+.43),(w,.24,.86),'Stone')
            box(t['name']+'_BackCap',(x,163.65,z+.91),(w+.10,.36,.12),'Trim')
        for i in range(1,5):
            box(t['name']+'_StoneSeam',(x-w/2+i*2,y-d/2-.032,28+h/2),(.025,.012,max(.12,h-.4)),'Trim',False)
    for s in pressure['stairs']:
        for p in s['steps']:
            # Solid steps terminate at their real tread, leaving the next stage
            # landing coplanar; all 60 risers are 16 cm.
            box(s['name']+'_Step',(p[0],p[1],(28+p[2])/2-.01),(s['width'],s['tread']+.012,p[2]-28+.02),'Floor')
        y0=s['end_y'];y1=s['landing_end_y'];z=s['top']
        box(s['name']+'_Landing',(s['x'],(y0+y1)/2,z-.20),(s['width'],y1-y0+.012,.4),'Floor')
        # Outer safety parapet follows the stair without crossing the access.
        sx=1 if s['x']>0 else -1
        for j,p in enumerate(s['steps']):
            box(s['name']+'_OuterKerb',(s['x']+sx*1.20,p[1],p[2]+.25),(.16,s['tread']+.012,.50),'Stone')
    for e in pressure['enemies']:
        inst(e['id'],guard,e['foot'],mat='Enemy',collision=False)
        a=tags(sub.spawn_actor_from_class(unreal.TargetPoint,v(e['foot'])),'Enemy_'+e['id'])
        a.set_editor_property('tags',list(a.get_editor_property('tags'))+[unreal.Name('NLPressure.Enemy.'+e['id']),unreal.Name('NLPressure.DisplayOnly')])
    spec=json.load(open(os.path.join(ROOT,'Docs','LevelDesign','Blockout_v02','LayoutSpec.json'),encoding='utf-8'))
    spec['map']=MAP;spec['version']='V08 elevation pressure prototype';spec['pressure']=pressure
    template=next(a for a in sub.get_all_level_actors() if isinstance(a,unreal.CameraActor) and 'CAM_02_Martial' in a.get_actor_label())
    for camera in pressure['views']:
        p=camera['position'];target=camera['target']
        a=tags(sub.spawn_actor_from_class(unreal.CameraActor,v(p),unreal.MathLibrary.find_look_at_rotation(v(p),v(target))),camera['name'])
        # Capture scripts share the NB_CAM prefix with older maps.
        a.set_actor_label('NB_'+camera['name']+'_V08')
        comp=a.get_component_by_class(unreal.CameraComponent)
        comp.set_editor_property('field_of_view',camera['fov']);comp.set_editor_property('constrain_aspect_ratio',False)
        src=template.get_component_by_class(unreal.CameraComponent)
        comp.set_editor_property('post_process_settings',src.get_editor_property('post_process_settings'))
        comp.set_editor_property('post_process_blend_weight',1.0)
        spec['cameras'].append(dict(camera,label=a.get_actor_label()))
    if not level.save_current_level():raise RuntimeError('V08 save failed')
    spec['actor_count']=len(sub.get_all_level_actors())
    json.dump(spec,open(os.path.join(OUT,'LayoutSpec.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    report={'map':MAP,'source':SOURCE,'checked_at':datetime.datetime.now().isoformat(),'enemy_count':len(pressure['enemies']),'tier_heights_m':[1.6,3.2,4.8],'actor_count':spec['actor_count'],'relocated_racks':relocated,'new_clusters':[{'label':a.get_actor_label(),'count':c.get_instance_count()} for a,c in clusters.values()],'saved':True,'scope':'Static editable visual staging in B court; no AI or wave logic implemented. Other acts copied from V07.'}
    json.dump(report,open(os.path.join(OUT,'BuildPressure.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'MAP CHECK')
    unreal.log('NILIN_PRESSURE_BUILD_OK '+str(len(pressure['enemies'])))
main()
