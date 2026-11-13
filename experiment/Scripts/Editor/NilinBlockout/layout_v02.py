"""Canonical V07 layout. Compact only the long upper ascent; keep combat courts."""
import json,os,math,copy,datetime
ROOT=r'D:\game design\experiment'
OUT=os.path.join(ROOT,'Docs','LevelDesign','Blockout_v02')
UPPER={'C_to_Ridge','Ridge_to_Node06','Node06_to_Upper','Upper_to_Summit'}
REBUILT=UPPER|{'Threshold_to_C'}
def compressed(p):return [-36+(p[0]+36)*.75,310+(p[1]-310)*.75,p[2]]
def summit(p):return [p[0]+46,p[1]-67.5,p[2]]
def stair_samples(a,b,width,name):
    dx,dy,dz=[b[i]-a[i] for i in range(3)];run=math.hypot(dx,dy)
    n=math.ceil(dz/.16);nl=(n-1)//20;rise=dz/n;tread=(run-nl*1.25)/n
    if tread<.30:raise ValueError('Too steep: '+name)
    points=[];s=0
    for i in range(n):
        z=a[2]+(i+1)*rise;mid=s+tread/2
        points.append([a[0]+dx/run*mid,a[1]+dy/run*mid,z]);s+=tread
        if (i+1)%20==0 and i<n-1:
            mid=s+.625;points.append([a[0]+dx/run*mid,a[1]+dy/run*mid,z]);s+=1.25
    return {'name':name,'a':a,'b':b,'width':width,'riser':rise,'tread':tread,'steps':n,'landings':nl},points
def make_layout():
    d=json.load(open(os.path.join(ROOT,'Docs','LevelDesign','Blockout_v01','LayoutSpec.json'),encoding='utf-8'))
    d['map']='/Game/ReversedScale/Maps/L_NilinBlockoutV07';d['optimized_at']=datetime.datetime.now().isoformat();d['version']='v02'
    d['nodes'][3]['ground']=[-8,199.4,44]
    d['nodes'][5]['ground']=[-114.4,404.5,104]
    for n in d['nodes'][6:]:n['ground']=summit(n['ground'])
    d['boss']=summit(d['boss'])
    for p in d['platforms']:
        if p['name'].startswith('D_'):p['center']=summit(p['center'])
    names={'RidgeLanding':[-69,347.5,88],'Node06_BridgeLanding':[-106.5,407.5,104],'Node06_Overlook':[-112.5,406.75,104],'UpperLanding':[-151.5,459.5,122]}
    for r in d['rests']:
        if r['name'] in names:r['center']=names[r['name']]
    last_a=[-151.5,460.7,122];peak=[-174,512.5,132]
    delta=[peak[i]-last_a[i] for i in range(2)];length=math.hypot(*delta);u=[v/length for v in delta]
    last_b=[peak[i]-30*u[i] for i in range(2)]+[132]
    def landing_entry(name,a,center):
        delta=[center[i]-a[i] for i in range(2)];length=math.hypot(*delta);u=[v/length for v in delta];n=[-u[1],u[0]]
        support=abs(u[0])*4.5+abs(u[1])*4
        b=[center[i]-u[i]*support for i in range(2)]+[center[2]]
        p=[b[0]+u[0]*support/2,b[1]+u[1]*support/2,center[2]]
        points=[[b[0]+u[0]*run+n[0]*side,b[1]+u[1]*run+n[1]*side] for run,side in ((0,4),(0,-4),(support,-4),(support,4))]
        return b,{'name':name+'_EntryBridgehead','associated_rest':name,'center':p,'size':[support,8],'rotation_yaw':math.degrees(math.atan2(u[1],u[0])),'points':points,'kind':'transition','start':b,'inward':u}
    endpoints={};bridges=[]
    for flight,a,rest in [('C_to_Ridge',[-34,310,72],'RidgeLanding'),('Ridge_to_Node06',[-69,348.7,88],'Node06_BridgeLanding'),('Node06_to_Upper',[-106.5,408.7,104],'UpperLanding')]:
        b,record=landing_entry(rest,a,names[rest]);endpoints[flight]=(a,b);bridges.append(record)
    endpoints['Upper_to_Summit']=(last_a,last_b)
    bridge_center=[last_b[0]+u[0]*1.5,last_b[1]+u[1]*1.5,132]
    n=[-u[1],u[0]]
    bridge_points=[[last_b[0]+u[0]*run+n[0]*side,last_b[1]+u[1]*run+n[1]*side] for run,side in ((0,4),(0,-4),(3,-4),(3,4))]
    d['bridgeheads']=bridges+[{'name':'SummitEntryBridgehead','center':bridge_center,'size':[3,8],'rotation_yaw':math.degrees(math.atan2(u[1],u[0])),'points':bridge_points,'kind':'transition','start':last_b,'inward':u}]
    d['route']=[];flights=[]
    for old in d['stairs']:
        a,b=endpoints.get(old['name'],(old['a'],old['b']))
        s,points=stair_samples(a,b,6.5 if old['name'] in UPPER else old['width'],old['name'])
        flights.append(s);d['route'].extend(points)
    d['stairs']=flights
    next_flight=next(s for s in flights if s['name']=='Node06_to_Upper')
    a,b=next_flight['a'],next_flight['b'];run=math.hypot(b[0]-a[0],b[1]-a[1])
    d['route_approaches']={'6':[a[0]-4*(b[0]-a[0])/run,a[1]-4*(b[1]-a[1])/run,a[2]]}
    for c in d['cameras']:
        name=c['name']
        if '_00_' in name:c.update(position=[-65,-560,450],target=[-65,200,70],fov=58)
        elif '_05_' in name:c.update(position=summit(c['position']),target=summit(c['target']))
        elif '_04_' in name:c.update(position=compressed(c['position']),target=summit(c['target']))
        elif '_06_' in name:c.update(position=[-65,255,1050],target=[-65,255,0],fov=60)
        elif '_07_' in name or '_08_' in name:c['target']=summit(c['target'])
    for f in d['footprints']:
        if f.get('name')=='SealWall':f['center']=summit(f['center'])
    g=d['gameplay_notes']
    g['triangle_eye']=summit(g['triangle_eye']);g['victory_route']=[summit(p) for p in g['victory_route']]
    d['upper_ascent_change']={'horizontal_scale':.75,'anchor':[-36,310],'original_summit':[-220,580,132],'summit':[-174,512.5,132],'combat_courts_resized':False}
    d['upper_ascent_change']['junction_refinement']='Stair end caps inset into unchanged rest plates; final flight approaches summit radially with a flush 8m bridgehead'
    return d
if __name__=='__main__':
    os.makedirs(OUT,exist_ok=True)
    json.dump(make_layout(),open(os.path.join(OUT,'LayoutSpec_working.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
