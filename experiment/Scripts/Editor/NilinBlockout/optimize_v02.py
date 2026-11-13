"""Upgrade a copy of V06 to V07. Existing gameplay surfaces remain intact."""
import unreal,os,sys,json,math,hashlib,copy,datetime,re
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
ROOT=r'D:\game design\experiment'
OUT=os.path.join(ROOT,'Docs','LevelDesign','Blockout_v02')
os.makedirs(OUT,exist_ok=True)
sys.path.insert(0,BASE)
import mesh_shapes_v02 as shapes,ue_mesh_v02 as meshes,layout_v02,junctions_v02 as junctions,importlib
importlib.reload(shapes);importlib.reload(meshes)
importlib.reload(layout_v02)
importlib.reload(junctions)
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV07'
SOURCE='/Game/ReversedScale/Maps/L_NilinBlockoutV06'
TAG='NBOptV02'
ASSETS='/Game/ReversedScale/Blockout/V07'
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assets=unreal.EditorAssetLibrary
materials={}
group='00_Environment'
serial=0
log={'removed_terrain':0,'removed_roof_parts':0,'new_meshes':[],'architecture':[]}
def vec(p):return unreal.Vector(*[float(c)*100 for c in p])
def tag(a,name):
    global serial
    serial+=1;a.set_actor_label('NB2_'+name+'_%04d'%serial)
    a.set_folder_path('Nilin_V07/'+group)
    a.set_editor_property('tags',[unreal.Name(TAG),unreal.Name('NLBlockoutV06')])
    return a
def asset(name,vertices,triangles,collision=True):
    digest=hashlib.sha1(json.dumps([vertices,triangles,collision],separators=(',',':')).encode()).hexdigest()[:7]
    path=ASSETS+'/Meshes/SM_'+name+'_'+digest
    result=meshes.make_asset(path,vertices,triangles,collision)
    log['new_meshes'].append({'path':path,'triangles':len(triangles),'collision':collision})
    return result
def part(name,mesh,p=(0,0,0),mat='Stone',scale=(1,1,1),rot=None,collision=True):
    a=tag(actors.spawn_actor_from_class(unreal.StaticMeshActor,vec(p),rot or unreal.Rotator()),name)
    c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(mesh);c.set_material(0,materials[mat]);c.set_collision_profile_name('BlockAll' if collision else 'NoCollision');c.set_mobility(unreal.ComponentMobility.STATIC)
    a.set_actor_scale3d(unreal.Vector(*scale))
    return a
def box(name,p,size,mat='Stone',rot=None,collision=True):return part(name,unreal.load_asset('/Engine/BasicShapes/Cube'),p,mat,size,rot,collision)
def beam(name,a,b,width=.3,depth=None,mat='Trim',collision=True):
    return box(name,tuple((x+y)*.5 for x,y in zip(a,b)),(math.dist(a,b),width,depth or width),mat,unreal.MathLibrary.find_look_at_rotation(vec(a),vec(b)),collision)
def remove_if(predicate):
    found=[]
    for a in actors.get_all_level_actors():
        if (a.actor_has_tag('NLBlockoutV06') or a.actor_has_tag(TAG)) and predicate(a):found.append(a)
    for a in found:actors.destroy_actor(a)
    return len(found)
def roof(name,p,width,depth,height):
    along_y=depth>width
    vertices,triangles=shapes.roof(depth,width,height) if along_y else shapes.roof(width,depth,height)
    if along_y:vertices=[(-y,x,z) for x,y,z in vertices]
    mesh=asset(name,vertices,triangles)
    part(name,mesh,p,'Roof')
    ridge=(depth if along_y else width)*.67
    offset=lambda d:(p[0] if along_y else p[0]+d,p[1]+d if along_y else p[1],p[2]+height+.15)
    beam(name+'_Ridge',offset(-ridge/2),offset(ridge/2),.42,.5)
    for x in (-ridge/2,ridge/2):
        q=offset(x)
        box(name+'_RidgeEnd',(q[0],q[1],p[2]+height+.55),(.5,.6,.9),'Trim')
    log['architecture'].append({'name':name,'center':p,'size':[width,depth],'height':height})
def cloud_material():
    path=ASSETS+'/Materials/M_CloudMass'
    if assets.does_asset_exist(path):
        m=assets.load_asset(path)
        unreal.MaterialEditingLibrary.delete_all_material_expressions(m)
    else:m=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_CloudMass',ASSETS+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    color=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionConstant3Vector)
    color.set_editor_property('constant',unreal.LinearColor(.48,.56,.62,1))
    unreal.MaterialEditingLibrary.connect_material_property(color,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    fresnel=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionFresnel)
    fresnel.set_editor_property('exponent',2.0);fresnel.set_editor_property('base_reflect_fraction',0.0)
    inv=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionOneMinus)
    mul=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionMultiply)
    mul.set_editor_property('const_b',.35)
    if not unreal.MaterialEditingLibrary.connect_material_expressions(fresnel,'',inv,''):raise RuntimeError('Cloud opacity input could not connect')
    unreal.MaterialEditingLibrary.connect_material_expressions(inv,'',mul,'A')
    unreal.MaterialEditingLibrary.connect_material_property(mul,'',unreal.MaterialProperty.MP_OPACITY)
    unreal.MaterialEditingLibrary.recompile_material(m);assets.save_loaded_asset(m,False)
    return m
def main():
    global group
    if not assets.does_asset_exist(MAP):
        if not editor.get_editor_world().get_path_name().startswith(SOURCE+'.'):raise RuntimeError('Start from source map to create independent level')
        if not unreal.EditorLoadingAndSavingUtils.save_map(editor.get_editor_world(),MAP):raise RuntimeError('Cannot save independent source copy')
    if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):
        if not levels.load_level(MAP):raise RuntimeError('Cannot load independent optimization map')
    if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):raise RuntimeError('Unexpected map; refusing changes')
    # Repeatable own additions; established floors, stairs and markers survive.
    remove_if(lambda a:a.actor_has_tag(TAG))
    for name in ('Stone','Floor','Cliff','CliffLight','Roof','Wood','Trim','Accent','Warm','Pine'):
        materials[name]=assets.load_asset('/Game/ReversedScale/Blockout/V06/Materials/M_'+name)
    spec=layout_v02.make_layout()
    spec['map']=MAP;spec['version']='Optimized whitebox v02';spec['optimized_at']=datetime.datetime.now().isoformat()
    # Relocate the summit without shrinking its arena or the architecture on it.
    for a in actors.get_all_level_actors():
        name=a.get_actor_label();folder=str(a.get_folder_path());p=a.get_actor_location()
        if ('05_SummitSeal' in folder or name.startswith(('NB_D_TargetEye_','NB_VictoryAfterBossRoute_'))) and not a.actor_has_tag('NBOpt.SummitRelocated'):
            p.x+=4600;p.y-=6750;a.set_actor_location(p,False,True)
            a.set_editor_property('tags',list(a.get_editor_property('tags'))+[unreal.Name('NBOpt.SummitRelocated')])
        if name.startswith('NB_Node_06_') and not a.actor_has_tag('NBOpt.Node06Relocated'):
            p.x+=2550;p.y-=3225;a.set_actor_location(p,False,True)
            a.set_editor_property('tags',list(a.get_editor_property('tags'))+[unreal.Name('NBOpt.Node06Relocated')])
    # Place review nodes inside their existing safe decks at collision-verified
    # seated/standing view positions, clear of the outgoing stair rail silhouettes.
    for index in (4,6):
        point=next(a for a in actors.get_all_level_actors() if isinstance(a,unreal.TargetPoint) and a.actor_has_tag('NLBlockout.Node.%02d'%index))
        p=point.get_actor_location();goal=vec(next(n for n in spec['nodes'] if n['index']==index)['ground']);delta=goal-p
        for a in actors.get_all_level_actors():
            if a.get_actor_label().startswith('NB_Node_%02d_'%index):a.set_actor_location(a.get_actor_location()+delta,False,True)
    # Replace only the upper flights. Use the proven builder's tread/rail logic.
    remove_if(lambda a:isinstance(a,unreal.StaticMeshActor) and '04_ContinuousAscent' in str(a.get_folder_path()) and a.get_actor_location().y>30600 and not a.get_actor_label().startswith(('NB_C_EastExit_','NB_Node_06_')))
    rail_names=('NB_Balustrade_','NB_Handrail_','NB_RailPost_','NB_PostCap_')
    remove_if(lambda a:'04_ContinuousAscent' in str(a.get_folder_path()) and (a.get_actor_label().startswith('NB_Threshold_to_C_') or (a.get_actor_label().startswith(rail_names) and ((20349<=a.get_actor_location().y<=27010 and abs(a.get_actor_location().x)<650) or (19840<=a.get_actor_location().y<=20360 and -1000<=a.get_actor_location().x<=-300)))))
    remove_if(lambda a:'03_AlchemyCourt' in str(a.get_folder_path()) and a.get_actor_label().startswith(rail_names))
    source=open(os.path.join(BASE,'build_blockout.py'),encoding='utf-8').read().split('\ntry:\n    main()')[0]
    helper={'__name__':'v02_stair_helpers'};exec(compile(source,'<stair_helpers>','exec'),helper)
    helper['TAG']=TAG;helper['group']='04_ContinuousAscent'
    for k in ('Cube','Cylinder','Sphere','Cone'):helper['meshes'][k]=unreal.load_asset('/Engine/BasicShapes/'+k)
    for k in ('Stone','Floor','Landing','Cliff'):helper['materials'][k]=assets.load_asset('/Game/ReversedScale/Blockout/V06/Materials/M_'+k)
    for s in spec['stairs']:
        if s['name'] in layout_v02.REBUILT:helper['stairs'](s['name'],s['a'],s['b'],s['width'])
    for r in spec['rests']:
        if r['name'] in ('RidgeLanding','Node06_BridgeLanding','Node06_Overlook','UpperLanding'):helper['rest'](r['name'],r['center'],*r['size'])
    group='04_ContinuousAscent'
    for bridge in spec['bridgeheads']:
        if not bridge.get('associated_rest'):continue
        group='03_AlchemyCourt' if bridge['associated_rest']=='C_AlchemyCourt' else '04_ContinuousAscent'
        p=bridge['center'];length,width=bridge['size']
        box(bridge['name'],(p[0],p[1],p[2]-.5),(length,width,1),'Floor',rot=unreal.Rotator(yaw=bridge['rotation_yaw']))
    helper['group']='04_ContinuousAscent'
    for a,b in junctions.guarded_landings(spec,{'Node04_Landing','Node04_Overlook','RidgeLanding','Node06_BridgeLanding','Node06_Overlook','UpperLanding'}):helper['rail'](a,b)
    helper['group']='03_AlchemyCourt'
    for a,b in junctions.guarded_landings(spec,{'C_AlchemyCourt','C_EastExit'}):helper['rail'](a,b)
    remove_if(lambda a:a.actor_has_tag(TAG) and 'MountainBackbone' in a.get_actor_label())
    # Approach the summit radially. The top plate begins at the last riser,
    # extending only into the circle, so it never forms a high ceiling over steps.
    group='05_SummitSeal';helper['group']=group
    remove_if(lambda a:'05_SummitSeal' in str(a.get_folder_path()) and a.get_actor_label().startswith(('NB_Balustrade_','NB_Handrail_','NB_RailPost_','NB_PostCap_')))
    bridge=next(b for b in spec['bridgeheads'] if b['name']=='SummitEntryBridgehead');p=bridge['center'];u=bridge['inward'];n=(-u[1],u[0]);start=bridge['start']
    box('SummitEntryBridgehead',(p[0],p[1],p[2]-.5),(3,8,1),'Floor',rot=unreal.Rotator(yaw=bridge['rotation_yaw']))
    peak=next(p for p in spec['platforms'] if p['name'].startswith('D_'));px,py,pz=peak['center']
    theta=math.atan2(start[1]-py,start[0]-px);radius=29.3;gap=math.asin(4/radius)
    for i in range(40):
        t0=theta+gap+(2*math.pi-2*gap)*i/40;t1=theta+gap+(2*math.pi-2*gap)*(i+1)/40
        helper['rail']((px+radius*math.cos(t0),py+radius*math.sin(t0),pz),(px+radius*math.cos(t1),py+radius*math.sin(t1),pz),posts=i%2==0)
    inset=30-math.sqrt(radius*radius-16)
    for side in (-1,1):
        a=(start[0]+n[0]*side*4,start[1]+n[1]*side*4,pz)
        b=(a[0]+u[0]*inset,a[1]+u[1]*inset,pz)
        helper['rail'](a,b)
        helper['rail']((start[0]+n[0]*side*3.25,start[1]+n[1]*side*3.25,pz),a,posts=False)
    log['bridgehead']=bridge
    group='02_MartialCourt'
    # The east gallery and rack used to overhang the clipped south-east floor.
    for a in actors.get_all_level_actors():
        name=a.get_actor_label();p=a.get_actor_location()
        if p.x<0 and 'NB_LowMartialGallery_' in name and not a.actor_has_tag('NBOpt.GalleryMoved'):
            p.y+=600;a.set_actor_location(p,False,True);a.set_editor_property('tags',list(a.get_editor_property('tags'))+[unreal.Name('NBOpt.GalleryMoved')])
        if p.x<0 and 'NB_WeaponRack_' in name and not a.actor_has_tag('NBOpt.RackMoved'):
            p.y+=1000;a.set_actor_location(p,False,True);a.set_editor_property('tags',list(a.get_editor_property('tags'))+[unreal.Name('NBOpt.RackMoved')])
    roof_tokens=('_Slope_','_Eave_','_LiftedCorner_','_Ridge_','_RidgeFinial_')
    roof_names=('NB_ShanmenRoof_','NB_GateSide_','NB_LowMartialGallery_','NB_OpenAlchemyPavilion_','NB_AlchemyWorkshop_')
    log['removed_roof_parts']=remove_if(lambda a:any(a.get_actor_label().startswith(n) for n in roof_names) and any(t in a.get_actor_label() for t in roof_tokens))
    group='01_Shanmen';roof('ShanmenHipRoof',(0,-2.5,12.2),34,12,3.2)
    for x in (-25,25):roof('GateSideHipRoof',(x,3,4.1),10,15,1.7)
    # Layered bracket arms under the main gate roof, clear of the central opening.
    for x in (-12,12):
        for y in (-6,1):
            for i in range(3):box('GateDougong',(x,y,10.0+i*.34),(2.0+i*.75,.55, .22),'Trim')
    group='02_MartialCourt'
    roof('WestMartialHipRoof',(25,145,32.3),10,25,1.9)
    roof('EastMartialHipRoof',(-25,151,32.3),10,25,1.9)
    group='03_AlchemyCourt';roof('AlchemyHipRoof',(0,315,85.2),44,20,3.8)
    roof('WestAlchemyWorkshop',(27,316,76),9,17,1.6)
    roof('EastAlchemyWorkshop',(-27,323,76),9,17,1.6)
    for x in (-17.22,17.22):
        for y in (309.56,320.44):
            for i in range(3):box('AlchemyDougong',(x,y,84.0+i*.3),(1.4+i*.6,.65,.2),'Trim')
    remove_if(lambda a:any(s in a.get_actor_label() for s in ('NB_GiantFurnaceBody_','NB_FurnaceBelt_','NB_FurnaceNeck_','NB_FurnaceLid_','NB_FurnaceFinial_','NB_FurnaceHandle_','NB_FurnaceFire_')))
    body=[(2.15,2.7),(2.65,3.45),(3.4,4.05),(4.8,4.2),(6.0,4.1),(7.0,3.5),(7.5,2.7),(8.35,2.65)]
    part('FurnaceShoulderBelly',asset('FurnaceShoulderBelly',*shapes.lathe(body)),(0,310,72),'Trim')
    part('FurnaceBroadRim',asset('FurnaceBroadRim',*shapes.lathe([(8.2,2.7),(8.2,3),(8.65,3),(8.65,2.7)])),(0,310,72),'Wood')
    part('FurnaceLid',asset('FurnaceLid',*shapes.lathe([(8.7,3.15),(9.1,3.3),(9.7,1.7),(10.0,.8),(10.55,.48),(11.2,.48),(11.35,.15)])),(0,310,72),'Trim')
    belt=asset('FurnaceBelt',*shapes.lathe([(4.1,4.24),(4.65,4.24)]))
    part('FurnaceBelt',belt,(0,310,72),'Wood')
    handle=asset('FurnaceEar',*shapes.torus(1.15,.23))
    for x in (-4.35,4.35):part('FurnaceEar',handle,(x,310,78.4),'Trim',rot=unreal.Rotator(roll=90))
    for x,y in ((-2.5,308),(2.5,308),(0,312.5)):box('FurnaceFoot',(x,y,72.18),(1.3,1.3,.36),'Stone')
    roundmesh=unreal.load_asset('/Engine/BasicShapes/Cylinder')
    part('FurnaceVentRim',roundmesh,(0,305.72,76.75),'Wood',(1.75,1.75,.18),unreal.Rotator(roll=90),False)
    part('FurnaceVentFire',roundmesh,(0,305.59,76.75),'Warm',(1.25,1.25,.08),unreal.Rotator(roll=90),False)
    group='04_ContinuousAscent'
    # True arch side profiles below the two major bridge sections.
    for name in ('Ridge_to_Node06','Node06_to_Upper'):
        s=next(s for s in spec['stairs'] if s['name']==name);a=s['a'];b=s['b'];dx=b[0]-a[0];dy=b[1]-a[1];length=math.hypot(dx,dy);dz=b[2]-a[2]
        vv,tt=shapes.arch_side(length,8,1.3,.8)
        vv=[(x,y,z+dz*x/length) for x,y,z in vv]
        mesh=asset('StoneArch_'+name,vv,tt)
        n=(-dy/length,dx/length)
        for side in (-1,1):
            p=(a[0]+n[0]*side*2.8,a[1]+n[1]*side*2.8,a[2]-11)
            part('StoneArch_'+name,mesh,p,'Stone',rot=unreal.Rotator(yaw=math.degrees(math.atan2(dy,dx))))
    group='06_GiantPine';remove_if(lambda a:a.get_actor_label().startswith(('NB_PineTrunk_','NB_PineBranch_','NB_PineCanopy_','NB_PineRoot_')))
    trunk=[(46,175,7),(47,176,22),(51,179,41),(47,182,59),(43,186,78),(45,190,88)]
    part('PineTwistedTrunk',asset('PineTwistedTrunk',*shapes.trunk(trunk,[3.5,3.2,2.8,2.2,1.5,.8])),mat='Wood')
    branches=[([(49,180,46),(62,178,57),(70,176,68)],[2,1.5,.6]), ([(47,182,56),(30,182,68),(25,183,73)],[1.8,1.3,.6]), ([(45,184,65),(58,191,75),(63,193,79)],[1.5,1,.5])]
    for i,(points,radii) in enumerate(branches):part('PineBentBranch',asset('PineBranch'+str(i),*shapes.trunk(points,radii)),mat='Wood')
    canopy=asset('PineCloudCrown',*shapes.canopy(2))
    for p,size in [((70,176,70),(27,20,8)),((60,177,65),(26,18,7)),((25,183,75),(26,19,8)),((35,181,70),(24,18,7)),((63,193,81),(25,18,8)),((48,188,85),(30,22,9)),((43,190,91),(22,17,7))]:part('PineCloudCrown',canopy,p,'Pine',size)
    for i in range(5):beam('PineRoot',(46,175,13),(62-i*5,164-i*2,0),1.4,1.6,'Wood')
    group='00_Environment';remove_if(lambda a:a.get_actor_label().startswith('NB_CloudSea_'))
    materials['Cloud']=cloud_material()
    cloud=asset('SoftCloudMass',*shapes.canopy(4),collision=False)
    for i in range(11):
        p=(30+82*math.sin(i*1.8),i*62-40,-38+6*math.sin(i*.7))
        part('LowCloudBank',cloud,p,'Cloud',(120,80,12),collision=False)
    for a in actors.get_all_level_actors():
        if isinstance(a,unreal.ExponentialHeightFog):
            p=a.get_actor_location();p.z=-2500;a.set_actor_location(p,False,True)
            c=a.get_component_by_class(unreal.ExponentialHeightFogComponent);c.set_fog_density(.028);c.set_fog_height_falloff(.6);c.set_fog_inscattering_color(unreal.LinearColor(.52,.61,.67,1))
        if isinstance(a,unreal.CameraActor) and a.get_actor_label().startswith('NB_CAM_00'):
            a.set_editor_property('tags',list(a.get_editor_property('tags'))+[unreal.Name('NLBlockout.Overview')])
    for camera in spec['cameras']:
        a=next(a for a in actors.get_all_level_actors() if a.get_actor_label()==camera['label'])
        a.set_actor_location(vec(camera['position']),False,True);a.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(vec(camera['position']),vec(camera['target'])),True)
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',camera['fov'])
    terrain_file=os.path.join(ROOT,'ArtSource','BlockoutV02','TerrainV02_spec.json')
    if os.path.exists(terrain_file):
        terrain=json.load(open(terrain_file,encoding='utf-8'))
        import_terrain(terrain,spec)
    else:log['terrain_pending']=True
    spec['footprints']=[{'name':r['name'],'center':r['center'],'size':r['size'],'height':r['height'],'kind':'roof','label':r['name']} for r in log['architecture']]
    spec['footprints'] += [{'name':'Furnace','center':[0,310,72],'shape':'circle','radius':4.25,'height':11.35,'kind':'obstacle'},{'name':'SealWall','center':[-174,532.5,132],'size':[46,5],'height':18.1,'kind':'stone' }]
    spec['actor_count']=len(actors.get_all_level_actors())
    if not levels.save_current_level():raise RuntimeError('V07 map save failed')
    json.dump(spec,open(os.path.join(OUT,'LayoutSpec.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    json.dump(log,open(os.path.join(OUT,'Optimization.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.log('NILIN_V02_OPTIMIZE_OK '+str(spec['actor_count']))

def import_terrain(terrain,spec):
    global group
    log['removed_terrain']=remove_if(lambda a:bool(re.match(r'^NB_[ABCD]_Rock',a.get_actor_label())) or a.get_actor_label().startswith(('NB_RidgePillar','NB_B_CutShoulder')) or 'MountainBackbone' in a.get_actor_label())
    for record in terrain['meshes']:
        data=json.load(open(record['json_path'],encoding='utf-8'))
        group=record['folder']
        # Duplicate render vertices at triangle boundaries to retain rock facets.
        # World-space collision triangle positions remain exactly source geometry.
        vv=[data['vertices'][i] for tri in data['triangles'] for i in tri]
        tt=[(i,i+1,i+2) for i in range(0,len(vv),3)]
        mesh=asset(record['name']+'_Faceted',vv,tt)
        part(record['name'],mesh,record.get('actor_location_m',[0,0,0]),'CliffLight' if record.get('group') in ('A','B','D') else 'Cliff')
    footprint_path=os.path.join(ROOT,'ArtSource','BlockoutV02','terrain_footprints.json')
    if os.path.exists(footprint_path):
        fp=json.load(open(footprint_path,encoding='utf-8'))
        spec['terrain_footprints']=fp.get('terrain_footprints',fp.get('footprints',fp.get('meshes',[]))) if isinstance(fp,dict) else fp
    spec['terrain_sources']=[{'name':r['name'],'triangles':r['validation']['triangles'],'sha256':r['content_sha256']} for r in terrain['meshes']]

if __name__=='__main__':main()
