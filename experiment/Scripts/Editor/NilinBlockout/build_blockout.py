"""Rebuild only the owned V06 whitebox map. Units in this source are metres.

Run with UE PythonScriptPlugin commandlet. No existing combat map/config is changed.
"""
import unreal, math, json, os, traceback, datetime, shutil

ROOT = r'D:\game design\experiment'
OUT = os.path.join(ROOT, 'Docs', 'LevelDesign', 'Blockout_v01')
MAP = '/Game/ReversedScale/Maps/L_NilinBlockoutV06'
FOLDER = '/Game/ReversedScale/Blockout/V06'
TAG = 'NLBlockoutV06'
os.makedirs(OUT, exist_ok=True)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assets = unreal.EditorAssetLibrary
spec = {'map': MAP, 'units': 'metres', 'nodes': [], 'route': [], 'platforms': [], 'stairs': [], 'cameras': [], 'meshes': 0}
materials = {}
meshes = {}
group = '00_Environment'
serial = 0
rail_posts=set()

def v(p): return unreal.Vector(*[float(t)*100.0 for t in p])
def add(a,b): return tuple(x+y for x,y in zip(a,b))
def mul(a,k): return tuple(x*k for x in a)
def label(actor,name):
    global serial
    serial += 1
    actor.set_actor_label('NB_%s_%04d' % (name,serial))
    actor.set_folder_path(unreal.Name('Nilin_V06/'+group))
    actor.set_editor_property('tags',[unreal.Name(TAG)])
    return actor

def material(name,color,emissive=0):
    path=FOLDER+'/Materials/M_'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else None
    if not mat:
        assets.make_directory(FOLDER+'/Materials')
        mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_'+name,FOLDER+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
        node=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector)
        node.set_editor_property('constant',unreal.LinearColor(*color,1.0))
        unreal.MaterialEditingLibrary.connect_material_property(node,'',unreal.MaterialProperty.MP_BASE_COLOR)
        rough=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant)
        rough.set_editor_property('r',0.87)
        unreal.MaterialEditingLibrary.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
        if emissive:
            light=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector)
            light.set_editor_property('constant',unreal.LinearColor(*[c*emissive for c in color],1.0))
            unreal.MaterialEditingLibrary.connect_material_property(light,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        unreal.MaterialEditingLibrary.recompile_material(mat)
        assets.save_loaded_asset(mat,False)
    materials[name]=mat

def shape(name,p,size,mat='Stone',kind='Cube',rot=None,collision=True):
    a=label(actors.spawn_actor_from_class(unreal.StaticMeshActor,v(p),rot or unreal.Rotator()),name)
    c=a.get_component_by_class(unreal.StaticMeshComponent)
    c.set_static_mesh(meshes[kind])
    c.set_material(0,materials[mat])
    c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
    c.set_mobility(unreal.ComponentMobility.STATIC)
    a.set_actor_scale3d(unreal.Vector(*size))
    spec['meshes']+=1
    return a

def cube(name,p,size,mat='Stone',yaw=0,collision=True,rot=None):
    return shape(name,p,size,mat,rot=rot or unreal.Rotator(yaw=yaw),collision=collision)
def cyl(name,p,r,h,mat='Stone',collision=True,rot=None):
    return shape(name,p,(r*2,r*2,h),mat,'Cylinder',rot,collision)
def sphere(name,p,size,mat='Stone',collision=True):
    return shape(name,p,size,mat,'Sphere',collision=collision)

def beam(name,a,b,width,depth=None,mat='Wood',collision=True):
    d=tuple(y-x for x,y in zip(a,b)); length=math.sqrt(sum(t*t for t in d))
    mid=mul(add(a,b),0.5)
    return cube(name,mid,(length,width,depth or width),mat,rot=unreal.MathLibrary.find_look_at_rotation(v(a),v(b)),collision=collision)

def ring(name,center,r,width,mat='Accent',vertical=False,segments=48,collision=False):
    for i in range(segments):
        t0=2*math.pi*i/segments; t1=2*math.pi*(i+1)/segments
        a=add(center,(r*math.cos(t0),0,r*math.sin(t0)) if vertical else (r*math.cos(t0),r*math.sin(t0),0))
        b=add(center,(r*math.cos(t1),0,r*math.sin(t1)) if vertical else (r*math.cos(t1),r*math.sin(t1),0))
        beam(name,a,b,width,width,mat,collision)

def rail(a,b,mat='Stone',posts=True):
    beam('Balustrade',add(a,(0,0,.22)),add(b,(0,0,.22)),.18,.16,mat)
    beam('Handrail',add(a,(0,0,1.12)),add(b,(0,0,1.12)),.28,.18,mat)
    if posts:
        n=max(1,int(math.dist(a,b)/4.0))
        for i in range(n+1):
            p=tuple(a[j]+(b[j]-a[j])*i/n for j in range(3))
            key=tuple(round(c,3) for c in p)
            if key in rail_posts:continue
            rail_posts.add(key)
            cube('RailPost',add(p,(0,0,.64)),(.4,.4,1.28),mat)
            cube('PostCap',add(p,(0,0,1.35)),(.55,.55,.14),mat)

def platform(name,center,size):
    x,y,z=center; w,d=size
    cube(name+'_Floor',(x,y,z-.6),(w,d,1.2),'Floor')
    cube(name+'_Cornice',(x,y,z-1.45),(w+1,d+1,.5),'Stone')
    spec['platforms'].append({'name':name,'center':center,'size':size})
    # Visual stone pavement joints are deliberately nonblocking.
    for u in range(int(-w/2)+4,int(w/2),4):
        cube('PavingJoint',(x+u,y,z+.005),(.025,d-.2,.012),'Joint',collision=False)
    for u in range(int(-d/2)+4,int(d/2),4):
        cube('PavingJoint',(x,y+u,z+.006),(w-.2,.025,.012),'Joint',collision=False)

def crag(name,p,top_r,height,bottom_r=None):
    x,y,z=p
    # Stacked irregular buttresses taper below a continuous inhabitable summit.
    for j,(frac,scale) in enumerate(((.0,1),(.27,.94),(.54,.82),(.8,.64))):
        h=height*.30
        cyl(name+'_Rock',(x+math.sin(j*2)*top_r*.08,y+math.cos(j*2)*top_r*.05,z-height*frac-h*.5-1.5),top_r*scale,h,'Cliff')
    for j in range(9):
        a=2*math.pi*j/9; rr=top_r*.78
        h=height*(.62+.2*math.sin(j*2.5))
        cube(name+'_RockRib',(x+rr*math.cos(a),y+rr*math.sin(a),z-2-h*.5),(top_r*.32,top_r*.35,h),'CliffLight',yaw=j*40)

def stairs(name,a,b,width=6,landing_every=20):
    """16 cm or smaller risers, >=30 cm treads, level rest platforms."""
    dx,dy,dz=[b[i]-a[i] for i in range(3)]
    run=math.hypot(dx,dy); ux,uy=dx/run,dy/run; nx,ny=-uy,ux
    count=int(math.ceil(dz/.16)); rise=dz/count
    landing_count=(count-1)//landing_every
    landing=1.25
    tread=(run-landing_count*landing)/count
    if tread<.30: raise RuntimeError('%s has too short treads: %.3f'%(name,tread))
    yaw=math.degrees(math.atan2(dy,dx))
    s=0; points=[];rail_spans=[];flight_start=a
    for i in range(count):
        z=a[2]+(i+1)*rise
        c=(a[0]+ux*(s+tread*.5),a[1]+uy*(s+tread*.5),z-.35)
        cube(name+'_Tread',c,(tread+.015,width,.7),'Floor',yaw=yaw)
        points.append((a[0]+ux*(s+tread*.5),a[1]+uy*(s+tread*.5),z))
        s+=tread
        if (i+1)%landing_every==0 and i<count-1:
            flight_end=(a[0]+ux*s,a[1]+uy*s,z)
            rail_spans.append((flight_start,flight_end))
            c=(a[0]+ux*(s+landing*.5),a[1]+uy*(s+landing*.5),z-.35)
            cube(name+'_Rest',c,(landing+.015,width,.7),'Landing',yaw=yaw)
            points.append((c[0],c[1],z))
            s+=landing
            flight_start=(a[0]+ux*s,a[1]+uy*s,z)
            rail_spans.append((flight_end,flight_start))
    # Structural spine supports the visible stairs and connects cliff shoulders.
    beam(name+'_Spine',add(a,(0,0,-2.8)),add(b,(0,0,-2.8)),width*.82,3.5,'Cliff')
    for j in range(max(1,int(run/15))):
        t=(j+.5)/max(1,int(run/15))
        top=a[2]+dz*t-7
        height=top+63
        cyl(name+'_MountainBackbone',(a[0]+dx*t,a[1]+dy*t,top-height*.5),9,height,'Cliff')
    rail_spans.append((flight_start,b))
    for r0,r1 in rail_spans:
        rail(add(r0,(nx*width/2,ny*width/2,0)),add(r1,(nx*width/2,ny*width/2,0)))
        rail(add(r0,(-nx*width/2,-ny*width/2,0)),add(r1,(-nx*width/2,-ny*width/2,0)))
    spec['stairs'].append({'name':name,'a':a,'b':b,'width':width,'riser':rise,'tread':tread,'steps':count,'landings':landing_count})
    spec['route']+=points

def rest(name,p,width=8,depth=6):
    cube(name,add(p,(0,0,-.5)),(width,depth,1),'Landing')
    spec.setdefault('rests',[]).append({'name':name,'center':p,'size':[width,depth]})

def roof(name,p,width,depth,mat='Roof'):
    x,y,z=p
    # Three shallow ascending slopes and separate lifted eaves give a legible
    # Chinese sweeping roof silhouette while keeping the asset a true blockout.
    for side in (-1,1):
        cube(name+'_Slope',(x,y+side*depth*.22,z+.85),(width,depth*.54,.30),mat,rot=unreal.Rotator(roll=side*17))
        cube(name+'_Eave',(x,y+side*depth*.49,z+.05),(width+1,depth*.16,.24),mat,rot=unreal.Rotator(roll=-side*12))
        for end in (-1,1):
            beam(name+'_LiftedCorner',(x+end*(width*.5-2),y+side*depth*.5,z+.1),(x+end*(width*.5+.5),y+side*(depth*.5+.6),z+1.2),.35,.35,'Trim')
    cube(name+'_Ridge',(x,y,z+1.9),(width*.86,.5,.45),'Trim')
    for end in (-1,1):
        cube(name+'_RidgeFinial',(x+end*width*.44,y,z+2.25),(.55,.65,1.0),'Trim')

def pavilion(name,p,width,depth,height,open_center=True):
    x,y,z=p
    for xx in (-width*.42,width*.42):
        for yy in (-depth*.32,depth*.32):
            cyl(name+'_Column',(x+xx,y+yy,z+height*.5),.55,height,'Wood')
            cube(name+'_Plinth',(x+xx,y+yy,z+.22),(1.6,1.6,.44),'Stone')
            cube(name+'_Bracket',(x+xx,y+yy,z+height-.4),(2.1,2.1,.7),'Trim')
    for yy in (-depth*.32,depth*.32):
        cube(name+'_Beam',(x,y+yy,z+height-.25),(width,.65,.85),'Wood')
    roof(name,p=(x,y,z+height),width=width+3,depth=depth+3)

def flag(p):
    x,y,z=p
    cyl('BannerPole',(x,y,z+5.5),.12,11,'Trim')
    cube('BannerCrossbar',(x,y,z+10.2),(2.4,.18,.18),'Trim')
    cube('Banner',(x,y,z+7.3),(1.8,.09,5.3),'Banner')
    cube('BannerStripe',(x,y-.055,z+7.3),(.15,.025,4.3),'Accent',collision=False)

def lantern(p):
    x,y,z=p
    cube('LanternBase',(x,y,z+.18),(.8,.8,.36),'Stone')
    cyl('LanternStem',(x,y,z+1.1),.18,1.5,'Wood')
    cube('LanternBody',(x,y,z+2.15),(.7,.7,.8),'Warm',collision=False)
    cube('LanternCap',(x,y,z+2.65),(1,1,.2),'Roof')

def dummy(name,p,mat='Dummy'):
    cyl(name+'_Body',add(p,(0,0,.85)),.23,1.15,mat,False)
    sphere(name+'_Head',add(p,(0,0,1.6)),(.36,.36,.36),mat,False)
    cyl(name+'_FootMarker',add(p,(0,0,.02)),.55,.035,mat,False)

def node(n,p,yaw=90):
    a=label(actors.spawn_actor_from_class(unreal.TargetPoint,v(p),unreal.Rotator(yaw=yaw)),'Node_%02d'%n)
    a.set_editor_property('tags',[unreal.Name(TAG),unreal.Name('NLBlockout.Node.%02d'%n)])
    cyl('Node_%02d_Floor'%n,add(p,(0,0,.018)),.8,.025,'Accent',False)
    text=label(actors.spawn_actor_from_class(unreal.TextRenderActor,v(add(p,(-5,0,1.8))),unreal.Rotator(yaw=-90)),'Node_%02d_Sign'%n)
    tc=text.get_component_by_class(unreal.TextRenderComponent)
    tc.set_text('%02d | +%dm'%(n,p[2]))
    tc.set_world_size(30.0)
    tc.set_text_render_color(unreal.Color(180,207,202,255))
    spec['nodes'].append({'index':n,'ground':p,'yaw':yaw})

def camera(name,p,target,fov=65):
    a=label(actors.spawn_actor_from_class(unreal.CameraActor,v(p),unreal.MathLibrary.find_look_at_rotation(v(p),v(target))),name)
    c=a.get_component_by_class(unreal.CameraComponent)
    c.set_editor_property('field_of_view',fov)
    c.set_editor_property('constrain_aspect_ratio',False)
    pp=c.get_editor_property('post_process_settings')
    for key,val in [('override_auto_exposure_method',True),('auto_exposure_method',unreal.AutoExposureMethod.AEM_HISTOGRAM),('override_auto_exposure_min_brightness',True),('override_auto_exposure_max_brightness',True),('auto_exposure_min_brightness',5.0),('auto_exposure_max_brightness',5.0),('override_auto_exposure_bias',True),('auto_exposure_bias',0.0),('override_vignette_intensity',True),('vignette_intensity',0.0),('override_motion_blur_amount',True),('motion_blur_amount',0.0)]:
        pp.set_editor_property(key,val)
    c.set_editor_property('post_process_settings',pp)
    c.set_editor_property('post_process_blend_weight',1.0)
    spec['cameras'].append({'name':name,'position':p,'target':target,'fov':fov,'label':a.get_actor_label()})
    return a

def main():
    global group
    disk=os.path.join(ROOT,'Content','ReversedScale','Maps','L_NilinBlockoutV06.umap')
    if os.path.exists(disk):
        backup=os.path.join(OUT,'Backups');os.makedirs(backup,exist_ok=True)
        shutil.copy2(disk,os.path.join(backup,datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.umap'))
        if not levels.load_level(MAP):raise RuntimeError('Refusing to build: target map did not load')
        if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):raise RuntimeError('Unexpected world; refusing mutations')
        for a in actors.get_all_level_actors():
            if a.actor_has_tag(unreal.Name(TAG)): actors.destroy_actor(a)
    else:
        if not levels.new_level(MAP):raise RuntimeError('Refusing to build: target map was not created')
        if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):raise RuntimeError('Unexpected new world; refusing mutations')
    for key in ('Cube','Cylinder','Sphere','Cone'):
        meshes[key]=unreal.load_asset('/Engine/BasicShapes/'+key)
    for args in [('Floor',(.64,.66,.65)),('Stone',(.45,.48,.48)),('Landing',(.68,.63,.52)),('Cliff',(.22,.26,.28)),('CliffLight',(.30,.34,.35)),('Wood',(.28,.24,.20)),('Roof',(.23,.29,.33)),('Trim',(.52,.43,.28)),('Accent',(.15,.53,.51),.4),('Warm',(.85,.49,.18),1),('Banner',(.14,.24,.31)),('Joint',(.39,.42,.42)),('Dummy',(.62,.27,.20)),('Pine',(.27,.34,.30))]:
        material(*args)
    world=editor.get_editor_world()
    gm=unreal.load_class(None,'/Script/experiment.NLBlockoutGameMode')
    if not gm: raise RuntimeError('Compile NLBlockoutGameMode before running this builder')
    world.get_world_settings().set_editor_property('default_game_mode',gm)
    world.get_world_settings().set_editor_property('kill_z',-15000.0)
    group='00_Environment'
    sun=label(actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,50000),unreal.Rotator(pitch=-38,yaw=-35)),'Sun')
    sun_component=sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sun_component.set_intensity(5.0)
    sun_component.set_editor_property('atmosphere_sun_light',True)
    sky=label(actors.spawn_actor_from_class(unreal.SkyLight,unreal.Vector(0,0,20000)),'SkyFill')
    sc=sky.get_component_by_class(unreal.SkyLightComponent)
    sc.set_mobility(unreal.ComponentMobility.MOVABLE)
    sc.set_editor_property('source_type',unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    sc.set_editor_property('cubemap',unreal.load_asset('/Engine/MapTemplates/Sky/DaylightAmbientCubemap'))
    sc.set_intensity(1.4)
    label(actors.spawn_actor_from_class(unreal.SkyAtmosphere,unreal.Vector()),'SkyAtmosphere')
    fog=label(actors.spawn_actor_from_class(unreal.ExponentialHeightFog,v((0,0,-42))),'LowCloudSea')
    fc=fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property('fog_density',.012)
    fc.set_editor_property('fog_height_falloff',.14)
    ppv=label(actors.spawn_actor_from_class(unreal.PostProcessVolume,unreal.Vector()),'GlobalExposure')
    ppv.set_editor_property('unbound',True)
    settings=ppv.get_editor_property('settings')
    for key,val in [('override_auto_exposure_min_brightness',True),('override_auto_exposure_max_brightness',True),('auto_exposure_min_brightness',5.0),('auto_exposure_max_brightness',5.0),('override_motion_blur_amount',True),('motion_blur_amount',0.0)]:settings.set_editor_property(key,val)
    ppv.set_editor_property('settings',settings)
    # A low cloud sheet gives depth below the path without hiding the objective.
    for i in range(12):
        sphere('CloudSea',(180*math.sin(i*1.7),i*65-60,-58+5*math.sin(i)),(260,135,16),'Floor',False)

    group='01_Shanmen'
    platform('A_Shanmen',(0,0,0),(60,56))
    crag('A',(0,1,0),28,65)
    # Central opening is 16m wide; the gate remains physically traversable.
    for x in (-12,12):
        for y in (-6,1):
            cube('GatePier',(x,y,5.7),(1.6,1.6,11.4),'Wood')
            cube('GatePierFoot',(x,y,.45),(2.7,2.7,.9),'Stone')
        cube('GateBracket',(x,-2.5,10.8),(3.6,10,1.0),'Trim')
    cube('GateLintel',(0,-2.5,11.2),(29,1.4,1.8),'Wood')
    cube('GateNameTablet',(0,-3.4,11.0),(8,.3,1.25),'Trim')
    roof('ShanmenRoof',(0,-2.5,12.2),34,12)
    for x in (-25,25):
        pavilion('GateSide',(x,3,0),7,12,4.1)
        flag((x,-13,0));lantern((x,-23,0))
        cube('LionBase',(x/1.5,-12,.45),(2.3,2.3,.9),'Stone')
        sphere('LionMassing',(x/1.5,-12,1.7),(1.6,2.2,2.1),'Stone')
    for x in (-29,29): rail((x,-27,0),(x,27,0))
    rail((-29,-27,0),(-5,-27,0));rail((5,-27,0),(29,-27,0))
    rail((-29,27,0),(-4,27,0));rail((4,27,0),(29,27,0))
    ring('A_CombatBoundary',(0,14,.025),10,.09,'Accent')
    dummy('A_Guard_L',(-8,18,0));dummy('A_Guard_R',(8,18,0))
    node(1,(0,-21,0));node(2,(6,64,12))
    ps=label(actors.spawn_actor_from_class(unreal.PlayerStart,v((0,-21,.94)),unreal.Rotator(yaw=90)),'PlayerStart')

    group='02_MartialCourt'
    # A real cut in the south-east shoulder keeps the summit visible at node 02.
    platform('B_SouthWing',(-7.5,127,28),(45,22))
    platform('B_RearCourt',(0,151,28),(60,26))
    spec['platforms']=[p for p in spec['platforms'] if not p['name'].startswith('B_')]
    spec['platforms'].append({'name':'B_MartialCourt','shape':'polygon','center':[0,140,28],'points':[[-30,116],[15,116],[15,138],[30,138],[30,164],[-30,164]]})
    crag('B',(0,140,22),29,85)
    cube('B_CutShoulderSouth',(-7,129,23),(42,22,8),'CliffLight')
    cube('B_CutShoulderRear',(0,150,23),(56,24,8),'CliffLight')
    for x in (-25,25):
        pavilion('LowMartialGallery',(x,145,28),7,22,4.3)
        for y in (127,154):
            flag((x,y,28));lantern((x*.8,y,28))
        for y in (135,139,143):
            beam('WeaponRack',(x*.75,y,28.3),(x*.75,y,31),.15,.15,'Wood')
    ring('B_CombatBoundary',(0,140,28.025),14,.09,'Accent')
    rail((-29,117,28),(-29,163,28))
    rail((14,117,28),(14,139,28));rail((14,139,28),(29,139,28));rail((29,139,28),(29,163,28))
    rail((-29,117,28),(-4,117,28));rail((4,117,28),(14,117,28))
    rail((-29,163,28),(-4,163,28));rail((4,163,28),(29,163,28))
    dummy('B_EnemyL',(-10,151,28));dummy('B_EnemyR',(10,151,28))
    node(3,(0,126,28));node(4,(6,201,44))

    group='03_AlchemyCourt'
    platform('C_AlchemyCourt',(0,300,72),(64,60))
    crag('C',(0,300,72),31,136)
    ring('C_ClearCombat',(0,291,72.025),14,.12,'Accent')
    ring('C_RescueFormation',(0,283,72.04),3,.13,'Accent')
    ring('C_RescueFormationInner',(0,283,72.04),2.2,.07,'Accent')
    dummy('C_Friend',(0,283,72),'Accent')
    pavilion('OpenAlchemyPavilion',(0,315,72),41,17,13.2)
    # Furnace behind the friend and outside the 28m combat disk.
    for x,y in ((-2.5,308),(2.5,308),(0,312.5)):
        cyl('FurnaceLeg',(x,y,73.7),.55,3.4,'Trim')
    sphere('GiantFurnaceBody',(0,310,77.0),(8.2,8.2,8.5),'Trim')
    cyl('FurnaceBelt',(0,310,77.1),4.25,.65,'Wood')
    cyl('FurnaceNeck',(0,310,81.0),2.3,1.3,'Trim')
    shape('FurnaceLid',(0,310,82.3),(6.6,6.6,1.6),'Trim','Cone')
    cyl('FurnaceFinial',(0,310,83.4),.4,1.4,'Trim')
    for x in (-4.3,4.3):
        ring('FurnaceHandle',(x,310,78.3),1.15,.3,'Trim',True,16,True)
    sphere('FurnaceFire',(0,306.01,76.8),(1.3,.10,1.3),'Warm',False)
    for x in (-27,27):
        pavilion('AlchemyWorkshop',(x,323 if x>0 else 316,72),6,14,4.0)
        flag((x,275,72));lantern((x,298,72))
    for x in (-31,31):
        if x<0:rail((x,271,72),(x,329,72))
        else:
            rail((x,271,72),(x,305,72));rail((x,315,72),(x,329,72))
    rail((-31,271,72),(-4,271,72));rail((4,271,72),(31,271,72))
    rail((-31,329,72),(31,329,72))
    dummy('C_CasterLeft',(-12,300,72));dummy('C_CasterRight',(12,300,72))
    node(5,(0,279,72))

    group='04_ContinuousAscent'
    stairs('A_to_Rest',(0,27,0),(0,61.5,12),8)
    rest('Node02_Landing',(0,64,12),8,5)
    rest('Node02_Overlook',(6,64,12),6,5)
    rail((9,61.5,12),(9,66.5,12));rail((4,61.5,12),(9,61.5,12));rail((4,66.5,12),(9,66.5,12))
    stairs('Rest_to_B',(0,66.5,12),(0,116,28),8)
    stairs('B_to_Threshold',(0,163,28),(0,198.5,44),8)
    rest('Node04_Landing',(0,201,44),8,5)
    rest('Node04_Overlook',(6,201,44),6,5)
    rail((9,198.5,44),(9,203.5,44));rail((4,198.5,44),(9,198.5,44));rail((4,203.5,44),(9,203.5,44))
    stairs('Threshold_to_C',(0,203.5,44),(0,270,72),8)
    cube('C_EastExit',(34,310,71.5),(8,10,1),'Floor')
    spec.setdefault('rests',[]).append({'name':'C_EastExit','center':[34,310,72],'size':[8,10]})
    stairs('C_to_Ridge',(36,310,72),(77,356,88),7)
    rest('RidgeLanding',(80,360,88),9,8)
    stairs('Ridge_to_Node06',(80,364,88),(127.5,436,104),7)
    rest('Node06_BridgeLanding',(130,440,104),9,8)
    rest('Node06_Overlook',(138,439,104),8,8)
    rail((142,435,104),(142,443,104));rail((134.5,435,104),(142,435,104));rail((134.5,443,104),(142,443,104))
    stairs('Node06_to_Upper',(130,444,104),(187,516,122),7)
    rest('UpperLanding',(190,520,122),9,8)
    stairs('Upper_to_Summit',(190,524,122),(220,550.5,132),7)
    node(6,(138,439,104),50)
    # Rock supports keep the ascent part of one continuous mountain formation.
    for p,r,h in [((80,360,88),12,150),((130,440,104),13,165),((190,520,122),13,180)]:crag('RidgePillar',p,r,h)

    group='05_SummitSeal'
    cyl('D_SummitFloor',(220,580,131.4),30,1.2,'Floor')
    spec['platforms'].append({'name':'D_SummitFloor','shape':'circle','center':[220,580,132],'radius':30})
    cyl('D_SummitCornice',(220,580,130.6),30.6,.5,'Stone')
    crag('D',(220,580,132),29.5,195)
    ring('D_ClearCombat',(220,576,132.03),14,.12,'Accent')
    ring('D_StoneCourt',(220,580,132.025),25,.08,'Joint')
    for i in range(40):
        t0=2*math.pi*i/40;t1=2*math.pi*(i+1)/40
        # Entry in the south and exit onto same summit behind the encounter.
        if abs(math.cos((t0+t1)/2))<.15 and math.sin((t0+t1)/2)<0:continue
        rail((220+29.3*math.cos(t0),580+29.3*math.sin(t0),132),(220+29.3*math.cos(t1),580+29.3*math.sin(t1),132),posts=i%2==0)
    for x in (201,239):
        cube('StoneQuePlinth',(x,598,133),(5.5,5,2),'Stone')
        cube('StoneQueTower',(x,598,140),(3.7,3.7,12),'CliffLight')
        cube('StoneQueCapital',(x,598,146.5),(6,5,1.1),'Stone')
        cube('StoneQueUpper',(x,598,148.2),(3,3,2.3),'CliffLight')
        cube('StoneQueCrown',(x,598,149.7),(4.7,4,.7),'Stone')
        flag((x,589,132))
    ring('VerticalSealOuter',(220,600,142),9,.65,'Stone',True,48,True)
    ring('VerticalSealInner',(220,599.6,142),7.5,.16,'Accent',True,48,False)
    ring('VerticalSealCore',(220,599.5,142),3.3,.12,'Accent',True,32,False)
    for i in range(8):
        t=2*math.pi*i/8
        beam('SealRadial',(220+4.3*math.cos(t),599.5,142+4.3*math.sin(t)),(220+6.6*math.cos(t),599.5,142+6.6*math.sin(t)),.12,.12,'Trim',False)
    for x,z in ((207,155),(214,158),(220,160),(226,158),(233,155)):
        cube('SuspendedSwordBlade',(x,599,z-3),(.55,.22,6),'Trim',collision=False)
        cube('SuspendedSwordGuard',(x,599,z+.1),(2,.4,.25),'Accent',collision=False)
        cube('SuspendedSwordHilt',(x,599,z+.8),(.3,.3,1.3),'Wood',collision=False)
    dummy('D_Boss',(220,583,132),'Dummy')
    node(7,(220,573,132));node(8,(220,605,132),270)
    for x,y in ((199,566),(241,566),(197,589),(243,589)):lantern((x,y,132))

    group='06_GiantPine'
    # Sole giant pine sits west of the playable spine, never through a route.
    beam('PineTrunk',(-46,175,10),(-45,180,76),5.5,5,'Wood')
    for a,b in [((-45,180,55),(-64,178,78)),((-45,180,62),(-28,182,86)),((-45,180,72),(-50,190,96))]:
        beam('PineBranch',a,b,2.2,2.2,'Wood')
        sphere('PineCanopy',add(b,(0,0,2)),(29,22,9),'Pine')
    for i in range(5):
        beam('PineRoot',(-46,175,13),(-65+i*5,165-i*2,0),1.8,1.8,'Wood')

    group='07_ReviewCameras'
    overview=camera('CAM_00_Overview',(210,-430,400),(75,280,65),65)
    camera('CAM_01_Gate',(0,-42,7),(0,1,7),75)
    camera('CAM_02_Martial',(0,119,29.7),(0,148,31),78)
    camera('CAM_03_Alchemy',(0,275,73.7),(0,311,78),80)
    camera('CAM_04_Ridge',(100,405,108),(220,580,139),70)
    camera('CAM_05_Boss',(220,555,133.7),(220,598,141),80)
    camera('CAM_06_Top',(85,290,920),(85,290,0),50)
    camera('CAM_07_LowObjective',(18,15,1.7),(220,580,142),68)
    camera('CAM_08_AlchemyObjective',(15,290,73.7),(220,580,142),68)
    editor.set_level_viewport_camera_info(overview.get_actor_location(),overview.get_actor_rotation())
    if not levels.save_current_level():raise RuntimeError('Map save failed')
    spec['generated_at']=datetime.datetime.now().isoformat()
    spec['actor_count']=len(actors.get_all_level_actors())
    spec['friend']=[0,283,72];spec['furnace']=[0,310,72];spec['boss']=[220,583,132]
    spec['footprints']=[{'name':'Shanmen','center':[0,-2.5,0],'size':[34,12],'height':15.5},{'name':'OpenAlchemyPavilion','center':[0,315,72],'size':[44,20],'height':16.5},{'name':'Furnace','center':[0,310,72],'shape':'circle','radius':4.25,'height':12.1},{'name':'SealWall','center':[220,600,132],'size':[46,5],'height':18.1}]
    with open(os.path.join(OUT,'LayoutSpec.json'),'w',encoding='utf-8') as f:json.dump(spec,f,ensure_ascii=False,indent=2)
    unreal.log('NILIN_BLOCKOUT_BUILD_OK '+str(spec['actor_count']))

try:
    main()
except Exception:
    with open(os.path.join(OUT,'BuildError.txt'),'w',encoding='utf-8') as f:f.write(traceback.format_exc())
    unreal.log_error(traceback.format_exc())
    raise
