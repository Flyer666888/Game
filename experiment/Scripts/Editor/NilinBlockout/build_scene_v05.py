"""Persist V10 scene enrichment in a separate level, using real collision."""
import unreal,sys,os,json,math,hashlib,importlib,datetime
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
ROOT=r'D:\game design\experiment'
OUT=os.path.join(ROOT,'Docs','LevelDesign','Blockout_v05')
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV10'
ASSET='/Game/ReversedScale/Blockout/V10'
TAG='NLEncounterV05'
sys.path.insert(0,BASE)
import ue_mesh_v02,terrain_v02,mesh_shapes_v02,junctions_v02,encounter_layout_v05,ranged_positions_v05
importlib.reload(encounter_layout_v05);importlib.reload(ranged_positions_v05)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assets=unreal.EditorAssetLibrary

def vec(p):return unreal.Vector(*[float(x)*100 for x in p])
class Scene:
    def __init__(self):self.materials={};self.clusters={};self.records=[];self.group='Architecture'
    def tag(self,a,name):
        a.set_actor_label('NB4_'+name)
        a.set_folder_path('Nilin_V10/'+self.group)
        a.set_editor_property('tags',[unreal.Name(TAG)])
        return a
    def mat(self,key):
        if key not in self.materials:
            path=ASSET+'/Materials/M_'+key
            m=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset('/Game/ReversedScale/Blockout/V06/Materials/M_'+key,path)
            if not m:raise RuntimeError('Unknown material '+key)
            unreal.MaterialEditingLibrary.set_base_material_usage(m,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES,True)
            unreal.MaterialEditingLibrary.recompile_material(m)
            if not assets.save_loaded_asset(m,False):raise RuntimeError('Material not saved')
            self.materials[key]=m
        return self.materials[key]
    def instance(self,name,p,size,mat,collision,rotation):
        key=(mat,collision,self.group)
        if key not in self.clusters:
            a=self.tag(actors.spawn_actor_from_class(unreal.load_class(None,'/Script/experiment.NLBlockoutMeshCluster'),unreal.Vector()),'Cluster_'+self.group+'_'+mat+('_Solid' if collision else '_Trim'))
            c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            c.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
            c.set_material(0,self.mat(mat));c.set_mobility(unreal.ComponentMobility.STATIC)
            c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
            c.set_editor_property('can_ever_affect_navigation',collision)
            self.clusters[key]=(a,c)
        c=self.clusters[key][1]
        idx=c.add_instance(unreal.Transform(location=vec(p),rotation=rotation,scale=unreal.Vector(*size)),world_space=True)
        self.records.append({'name':name,'type':'box','center':p,'size':size,'rotation':[rotation.pitch,rotation.yaw,rotation.roll],'material':mat,'collision':collision,'cluster':self.clusters[key][0].get_actor_label(),'index':idx})
        return idx
    def box(self,name,p,size,mat='Stone',collision=True,yaw=0):
        return self.instance(name,p,size,mat,collision,unreal.Rotator(yaw=yaw))
    def beam(self,name,a,b,width=.3,depth=None,mat='Wood',collision=True):
        return self.instance(name,tuple((x+y)*.5 for x,y in zip(a,b)),(math.dist(a,b),width,depth or width),mat,collision,unreal.MathLibrary.find_look_at_rotation(vec(a),vec(b)))
    def part(self,name,vertices,triangles,mat='Roof',collision=True):
        digest=hashlib.sha1(json.dumps([vertices,triangles,collision]).encode()).hexdigest()[:9]
        # Separate rock render vertices retain the intended plane changes.
        if mat.startswith('Cliff'):
            vertices=[vertices[i] for t in triangles for i in t]
            triangles=[(i,i+1,i+2) for i in range(0,len(vertices),3)]
        mesh=ue_mesh_v02.make_asset(ASSET+'/Meshes/SM_'+name+'_'+digest,vertices,triangles,collision)
        a=self.tag(actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector()),name)
        c=a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_static_mesh(mesh);c.set_material(0,self.mat(mat))
        c.set_mobility(unreal.ComponentMobility.STATIC)
        c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
        self.records.append({'name':name,'type':'mesh','asset':mesh.get_path_name(),'triangles':len(triangles),'material':mat,'collision':collision,'bounds':[[min(p[k] for p in vertices) for k in range(3)],[max(p[k] for p in vertices) for k in range(3)]]})
        return a

def cylinder(scene,name,p,r,h,mat='Stone',collision=True):
    a=scene.tag(actors.spawn_actor_from_class(unreal.StaticMeshActor,vec(p)),name)
    c=a.get_component_by_class(unreal.StaticMeshComponent)
    c.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cylinder'));c.set_material(0,scene.mat(mat))
    c.set_collision_profile_name('BlockAll' if collision else 'NoCollision');c.set_mobility(unreal.ComponentMobility.STATIC)
    a.set_actor_scale3d(unreal.Vector(2*r,2*r,h))
    scene.records.append({'name':name,'type':'cylinder','center':p,'radius':r,'height':h,'collision':collision})
    return a

def rail(scene,a,b,name='Rail'):
    if math.dist(a,b)<.35:return
    scene.beam(name+'_Base',(a[0],a[1],a[2]+.2),(b[0],b[1],b[2]+.2),.20,.25,'Stone')
    scene.beam(name+'_Handrail',(a[0],a[1],a[2]+1.15),(b[0],b[1],b[2]+1.15),.24,.18,'Trim')
    n=max(1,math.ceil(math.dist(a,b)/4))
    for i in range(n+1):
        p=[a[j]+(b[j]-a[j])*i/n for j in range(3)]
        scene.box(name+'_Post',(p[0],p[1],p[2]+.65),(.32,.32,1.3),'Stone')
        scene.box(name+'_Cap',(p[0],p[1],p[2]+1.35),(.46,.46,.14),'Trim')

def ring(scene,name,p,r,width,mat='Accent',vertical=False,collision=False):
    for i in range(64):
        a=2*math.pi*i/64;b=2*math.pi*(i+1)/64
        if vertical:
            q=(p[0]+r*math.cos(a),p[1],p[2]+r*math.sin(a));t=(p[0]+r*math.cos(b),p[1],p[2]+r*math.sin(b))
        else:
            q=(p[0]+r*math.cos(a),p[1]+r*math.sin(a),p[2]);t=(p[0]+r*math.cos(b),p[1]+r*math.sin(b),p[2])
        scene.beam(name,q,t,width,width,mat,collision)

def silhouette(scene,name,p,height=2.1,mat='Dummy',style=0):
    x,y,z=p;k=height/1.9
    def box(n,q,s,m=mat):scene.box(name+'_'+n,(x+q[0]*k,y+q[1]*k,z+q[2]*k),tuple(v*k for v in s),m,False)
    for side in (-1,1):box('Leg',(side*.16,0,.35),(.20,.28,.70))
    box('Robe',(0,0,.91),(.74,.42,.74));box('Shoulder',(0,0,1.38),(.86,.44,.30))
    box('Head',(0,0,1.69),(.32,.32,.38));box('Topknot',(0,.01,1.94),(.15,.15,.12),'Wood')
    box('Sash',(0,-.24,1.14),(.10,.06,.70),'Trim')
    for side in (-1,1):box('Arm',(side*.49,0,1.2),(.20,.3,.48))
    if style==0:box('Sword',(.63,-.15,.95),(.07,.07,1.65),'Accent')
    elif style==1:box('Talisman',(.61,-.20,1.43),(.27,.08,.52),'Accent')
    elif style==2:box('Censer',(.62,-.17,1.32),(.45,.38,.35),'Warm')
    else:box('WindStaff',(.65,-.12,1.08),(.11,.11,2.15),'Trim')
    cylinder(scene,name+'_Footprint',(x,y,z+.024),.65*k,.035,'Accent',False)

def target(scene,name,p,tag):
    a=scene.tag(actors.spawn_actor_from_class(unreal.TargetPoint,vec(p)),name)
    a.set_editor_property('tags',[unreal.Name(TAG),unreal.Name(tag)])
    return a

def clear_original():
    removed=[];instances=0
    for a in list(actors.get_all_level_actors()):
        name=a.get_actor_label();folder=str(a.get_folder_path());p=a.get_actor_location()
        destroy=a.actor_has_tag(TAG) or '05_SummitSeal' in folder or 'TerrainV02_Ridge' in name or any(t in name for t in ('V09_Terrain_Upper_','V09_Terrain_Summit_'))
        if not destroy and '04_ContinuousAscent' in folder:
            c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            if c:
                for i in reversed(range(c.get_instance_count())):
                    q=c.get_instance_transform(i,world_space=True).get_editor_property('translation')
                    if q.x<-3000 and q.y>=30400:
                        # The short C exit shelf is the connection to the unchanged courtyard.
                        if abs(q.x+3400)<5 and abs(q.y-31000)<5 and abs(q.z-7150)<5:continue
                        c.remove_instance(i);instances+=1
                if c.get_instance_count()==0:destroy=True
            elif p.x<-3000 and p.y>=30400:destroy=True
        if not destroy and 'Nilin_V09/Architecture' in folder:
            c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            if c:
                for i in reversed(range(c.get_instance_count())):
                    q=c.get_instance_transform(i,world_space=True).get_editor_property('translation')
                    if q.y>45000:c.remove_instance(i);instances+=1
            else:
                b,e=a.get_actor_bounds(False)
                if b.y>45000:destroy=True
        if destroy:removed.append(name);actors.destroy_actor(a)
    return {'actors':removed,'instances':instances}

def stair(scene,s):
    a,b=s['a'],s['b'];dx,dy=b[0]-a[0],b[1]-a[1];run=math.hypot(dx,dy);u=(dx/run,dy/run);n=(-u[1],u[0]);yaw=math.degrees(math.atan2(dy,dx));travel=0
    spans=[];previous=a
    for i in range(s['steps']):
        z=a[2]+s['riser']*(i+1);t=s['tread']
        scene.box(s['name']+'_Tread',(a[0]+u[0]*(travel+t/2),a[1]+u[1]*(travel+t/2),z-.35),(t+.025,s['width'],.7),'Floor',True,yaw)
        travel+=t
        if (i+1)%20==0 and i<s['steps']-1:
            end=(a[0]+u[0]*travel,a[1]+u[1]*travel,z);spans.append((previous,end))
            scene.box(s['name']+'_Rest',(a[0]+u[0]*(travel+.625),a[1]+u[1]*(travel+.625),z-.35),(1.275,s['width'],.7),'Landing',True,yaw)
            travel+=1.25;previous=(a[0]+u[0]*travel,a[1]+u[1]*travel,z);spans.append((end,previous))
    spans.append((previous,b))
    for v,w in spans:
        for side in (-1,1):rail(scene,(v[0]+n[0]*side*s['width']/2,v[1]+n[1]*side*s['width']/2,v[2]),(w[0]+n[0]*side*s['width']/2,w[1]+n[1]*side*s['width']/2,w[2]),s['name']+'_Rail')
    scene.beam(s['name']+'_StoneSpine',(a[0],a[1],a[2]-2.5),(b[0],b[1],b[2]-2.5),s['width']*.8,3,'Cliff')

def new_bridge(scene,spec):
    scene.group='04_YufengBridge'
    upper=[s for s in spec['stairs'] if s['a'][2]>=72]
    for s in upper:stair(scene,s)
    for link in spec.get('flat_links',[]):
        a,b=link['a'],link['b'];run=math.dist(a,b);yaw=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))
        scene.box(link['name'],[(a[i]+b[i])*.5-(.4 if i==2 else 0) for i in range(3)],(run,link['width'],.8),'Floor',True,yaw)
        n=(-(b[1]-a[1])/run,(b[0]-a[0])/run)
        for side in (-1,1):
            q=(a[0]+n[0]*side*link['width']/2,a[1]+n[1]*side*link['width']/2)
            t=(b[0]+n[0]*side*link['width']/2,b[1]+n[1]*side*link['width']/2)
            for v,w in junctions_v02.open_segments(q,t,[junctions_v02.rectangle(r['center'],r['size']) for r in spec['rests'] if abs(r['center'][2]-a[2])<.01]):rail(scene,(*v,a[2]),(*w,b[2]))
    for r in spec['rests']:
        if r['center'][2]<72 or r['name']=='C_EastExit':continue
        p=r['center'];scene.box(r['name'],(p[0],p[1],p[2]-.5),(*r['size'],1),'Landing')
    for b in spec['bridgeheads']:
        p=b['center'];scene.box(b['name'],(p[0],p[1],p[2]-.5),(*b['size'],1),'Floor',True,b['rotation_yaw'])
    exclusions=[junctions_v02.strip(s['a'],s['b'],s['width']+.7) for s in upper+spec.get('flat_links',[])]
    surfaces=[r for r in spec['rests'] if r['center'][2]>=72 and r['name']!='C_EastExit']+spec['bridgeheads']
    for r in surfaces:
        poly=r.get('points',junctions_v02.rectangle(r['center'],r['size']));z=r['center'][2]
        others=[q.get('points',junctions_v02.rectangle(q['center'],q['size'])) for q in surfaces if q is not r and abs(q['center'][2]-z)<.01]
        if abs(z-spec['boss_arena']['center'][2])<.01:
            px,py,_=spec['boss_arena']['center'];radius=spec['boss_arena']['radius']
            others.append([(px+radius*math.cos(i*2*math.pi/96),py+radius*math.sin(i*2*math.pi/96)) for i in range(96)])
        # Explicit level bridgeheads overlap sloping flights only at their ends.
        for a,b in zip(poly,poly[1:]+poly[:1]):
            for v,w in junctions_v02.open_segments(a,b,exclusions+others):rail(scene,(*v,z),(*w,z))
    for i,arena in enumerate(spec['grandmaster_arenas']):
        x,y,z=arena['center'];w,d=arena['size']
        scene.box(arena['id']+'_Cornice',(x,y,z-1.35),(w+.8,d+.8,.5),'Stone')
        ring(scene,arena['id']+'_DuelRing',(x,y,z+.025),7.2,.08,'Accent')
        # Monuments sit in the outer band, beyond the 18 x 16 metre clear rectangle.
        for side in (-1,1):
            p=(x+side*(w/2-1.2),y,z)
            scene.box(arena['id']+'_StelePlinth',(p[0],p[1],z+.25),(1.3,1.2,.5),'Stone')
            scene.box(arena['id']+'_Stele',(p[0],p[1],z+2.5),(.8,.7,4),'CliffLight')
            scene.box(arena['id']+'_SteleCap',(p[0],p[1],z+4.55),(1.45,1.25,.3),'Trim')
        foot=arena['enemy_spawn'];silhouette(scene,arena['id'],foot,2.35,'Dummy',i)
        target(scene,'Enemy_'+arena['id'],foot,'NLBlockout.EncounterEnemy.'+arena['id'])
        spec['new_enemies'].append({'id':arena['id'],'foot':foot,'role':'grandmaster','stage':i+1,'drop':arena['drop'],'static_preview':True})

def summit(scene,spec):
    scene.group='05_SummitSeal';p=spec['boss_arena']['center'];x,y,z=p;r=spec['boss_arena']['radius']
    cylinder(scene,'D_SummitFloor',(x,y,z-.6),r,1.2,'Floor')
    cylinder(scene,'D_SummitCornice',(x,y,z-1.45),r+.7,.5,'Stone')
    ring(scene,'D_ClearCombat',(x,y,z+.025),30,.10,'Accent')
    ring(scene,'D_StoneCourt',(x,y,z+.025),40,.08,'Joint')
    for deg in range(0,360,30):
        a=math.radians(deg)
        scene.beam('D_StoneSpoke',(x+32*math.cos(a),y+32*math.sin(a),z+.012),(x+43.7*math.cos(a),y+43.7*math.sin(a),z+.012),.08,.02,'Joint',False)
    # Keep a full-width opening at the radial bridge approach.
    b=next(q for q in spec['bridgeheads'] if q['name']=='SummitEntryBridgehead');entry=b['start']
    angle=math.atan2(entry[1]-y,entry[0]-x);gap=math.asin(5/(r-.7))
    for i in range(64):
        a=angle+gap+(2*math.pi-2*gap)*i/64;c=angle+gap+(2*math.pi-2*gap)*(i+1)/64
        rail(scene,(x+(r-.7)*math.cos(a),y+(r-.7)*math.sin(a),z),(x+(r-.7)*math.cos(c),y+(r-.7)*math.sin(c),z))
    for side in (-1,1):
        qx=x+side*30;qy=y+27
        for i,(w,d,h) in enumerate(((8,7,1.2),(6.8,5.8,.8))):scene.box('Que_SteppedPlinth',(qx,qy,z+.6+i), (w,d,h),'Stone')
        scene.box('Que_StoneShaft',(qx,qy,z+12),(4.8,4.3,20),'CliffLight')
        # Tapered traditional que capitals and corbel courses, without an obstructing roof.
        for i in range(4):scene.box('Que_Corbel',(qx,qy,z+22+i*.42),(5.2+i*.8,4.7+i*.65,.40),'Stone')
        scene.box('Que_Upper',(qx,qy,z+25),(3.6,3.2,3.4),'CliffLight')
        scene.box('Que_Crown',(qx,qy,z+27),(6.6,5.9,.6),'Stone')
        scene.box('Que_Ridge',(qx,qy,z+27.6),(4.8,.7,.65),'Trim')
        for j in (-1,1):scene.box('Que_UpturnedEave',(qx+j*3,qy,z+27.6),(.65,5.7,.45),'Trim')
        scene.box('Que_SealRelief',(qx,qy-2.18,z+16),(.75,.08,6),'Trim',False)
    ring(scene,'VerticalSealOuter',(x,y+30,z+17),13,.8,'Stone',True,True)
    ring(scene,'VerticalSealInner',(x,y+29.5,z+17),11.4,.18,'Accent',True)
    ring(scene,'VerticalSealCore',(x,y+29.4,z+17),4.3,.14,'Accent',True)
    for i in range(8):
        a=2*math.pi*i/8
        scene.beam('SealRadial',(x+5.5*math.cos(a),y+29.4,z+17+5.5*math.sin(a)),(x+10*math.cos(a),y+29.4,z+17+10*math.sin(a)),.18,.18,'Trim',False)
    for dx,h in ((-17,31),(-9,35),(0,38),(9,35),(17,31)):
        scene.box('SuspendedSword',(x+dx,y+29,z+h-4),(.75,.30,8),'Trim',False)
        scene.box('SuspendedSwordGuard',(x+dx,y+29,z+h),(2.8,.55,.4),'Accent',False)
        scene.box('SuspendedSwordHilt',(x+dx,y+29,z+h+1),(.4,.4,1.7),'Wood',False)
    silhouette(scene,'D_Boss',spec['boss'],4.8,'Dummy',0)
    target(scene,'Boss',spec['boss'],'NLBlockout.EncounterEnemy.Boss')

def terrain(scene,spec):
    scene.group='Terrain'
    mesh=terrain_v02.ridge(spec);scene.part('TerrainV10_Ridge',mesh['vertices'],mesh['triangles'],'Cliff')
    for i,r in enumerate(spec['grandmaster_arenas']):
        x,y,z=r['center'];w,d=r['size'];outline=[(-w*.54,-d*.48),(-w*.32,-d*.60),(w*.46,-d*.55),(w*.56,-d*.25),(w*.53,d*.48),(w*.22,d*.59),(-w*.50,d*.54),(-w*.59,d*.12)]
        m=terrain_v02.mountain('MasterFoundation'+str(i),(x,y),outline,z-1.65,-78,i+4)
        scene.part(m['name'],m['vertices'],m['triangles'],'CliffLight' if i%2 else 'Cliff')
    x,y,z=spec['boss_arena']['center'];r=spec['boss_arena']['radius']
    outline=[(r*.985*math.cos(i*2*math.pi/20),r*.985*math.sin(i*2*math.pi/20)) for i in range(20)]
    m=terrain_v02.mountain('SummitV10',(x,y),outline,z-1.8,-91,9)
    scene.group='05_SummitSeal';scene.part(m['name'],m['vertices'],m['triangles'],'Cliff')

def cameras_nodes(scene,spec):
    scene.group='07_ReviewCameras'
    for n in spec['nodes']:
        if n['index']<6:continue
        tag='NLBlockout.Node.%02d'%n['index']
        for a in list(actors.get_all_level_actors()):
            if a.actor_has_tag(tag):actors.destroy_actor(a)
        a=target(scene,'Node_%02d'%n['index'],n['ground'],tag);a.set_actor_rotation(unreal.Rotator(yaw=n['yaw']),False)
        p=n['ground'];cylinder(scene,'Node_%02d_Floor'%n['index'],(p[0],p[1],p[2]+.018),.8,.025,'Accent',False)
    # Update all inherited objective shots to look at the new, enlarged peak.
    for c in spec['cameras']:
        if any(s in c['name'] for s in ('_00_','_04_','_05_','_06_','_07_','_08_','_09_')):
            cam=next((a for a in actors.get_all_level_actors() if isinstance(a,unreal.CameraActor) and c['name'] in a.get_actor_label()),None)
            if cam:
                cam.set_actor_location(vec(c['position']),False,True);cam.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(vec(c['position']),vec(c['target'])),False)
                cam.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',c['fov'])
    shots=[('CAM_15_Ranged',[-20,211,66],[0,236,58],65),('CAM_16_Yufeng',[-365,300,280],[-125,470,112],68),('CAM_17_Summit',[-208,581,134],[-208,650,149],85),('CAM_18_Grandmaster',[-76,379,94],[-82,400,91],78)]
    template=next(a for a in actors.get_all_level_actors() if isinstance(a,unreal.CameraActor) and 'CAM_03_Alchemy' in a.get_actor_label())
    for name,p,t,fov in shots:
        a=scene.tag(actors.spawn_actor_from_class(unreal.CameraActor,vec(p),unreal.MathLibrary.find_look_at_rotation(vec(p),vec(t))),name);a.set_actor_label('NB_'+name+'_V10')
        c=a.get_component_by_class(unreal.CameraComponent);c.set_editor_property('field_of_view',fov);c.set_editor_property('constrain_aspect_ratio',False)
        c.set_editor_property('post_process_settings',template.get_component_by_class(unreal.CameraComponent).get_editor_property('post_process_settings'));c.set_editor_property('post_process_blend_weight',1.)
        spec['cameras'].append({'name':name,'position':p,'target':t,'fov':fov,'label':a.get_actor_label()})

def add_ranged_metadata_and_openings(scene,spec,ranged):
    cuts=[]
    for station in ranged['stations']:
        box=station['rail_clearance'];center=box['center'];half=[s/2 for s in box['size']]
        for a in list(actors.get_all_level_actors()):
            if a.actor_has_tag(TAG) or '04_ContinuousAscent' not in str(a.get_folder_path()):continue
            c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            if c:
                for i in reversed(range(c.get_instance_count())):
                    q=c.get_instance_transform(i,world_space=True).get_editor_property('translation');p=[q.x/100,q.y/100,q.z/100]
                    if all(abs(p[j]-center[j])<=half[j] for j in range(3)):
                        cuts.append({'actor':a.get_actor_label(),'index':i,'position':p});c.remove_instance(i)
            elif any(token in a.get_actor_label() for token in ('Rail','PostCap','Balustrade')):
                q=a.get_actor_location();p=[q.x/100,q.y/100,q.z/100]
                if all(abs(p[j]-center[j])<=half[j] for j in range(3)):
                    cuts.append({'actor':a.get_actor_label(),'position':p});actors.destroy_actor(a)
        for e in station['enemies']:target(scene,'Enemy_'+e['id'],e['foot'],e['tag'])
    spec['ranged_rail_openings']=cuts

def main():
    if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):raise RuntimeError('Open independent V10 before editing')
    removed=clear_original();spec=encounter_layout_v05.make_layout();spec['new_enemies']=[]
    x,y,z=spec['boss_arena']['center']
    spec['objective_targets']=[{'id':'central_sword','position':[x,y+29,z+38]},
        {'id':'left_que','position':[x-30,y+27,z+27]},
        {'id':'right_que','position':[x+30,y+27,z+27]},
        {'id':'seal_top','position':[x,y+30,z+30]}]
    scene=Scene();new_bridge(scene,spec);summit(scene,spec);terrain(scene,spec)
    scene.group='RangedWalkways';ranged=ranged_positions_v05.build(scene)
    spec['ranged_encounters']=ranged
    # Ranged module supplies the exact local railing openings and marker records.
    add_ranged_metadata_and_openings(scene,spec,ranged)
    cameras_nodes(scene,spec)
    if not level.save_current_level():raise RuntimeError('V10 save failed')
    json.dump(spec,open(os.path.join(OUT,'LayoutSpec.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    report={'map':MAP,'saved':True,'time':datetime.datetime.now().isoformat(),'actor_count':len(actors.get_all_level_actors()),'new_clusters':len(scene.clusters),'new_instances':sum(c.get_instance_count() for _,c in scene.clusters.values()),'removed':removed,'records':scene.records}
    json.dump(report,open(os.path.join(OUT,'SceneBuild.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    unreal.log('NILIN_V10_BUILD_SAVED')

main()
