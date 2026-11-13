"""Actual V07 Editor/PIE collision read-back; never reload the current map."""
import unreal, os, json, math, traceback, datetime, collections

ROOT=r'D:\game design\experiment'
OUT=os.path.join(ROOT,'Docs','LevelDesign','Blockout_v02')
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV07'
os.makedirs(OUT,exist_ok=True)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
query_world=None
ignore=[]
report={'map':MAP,'checked_at':datetime.datetime.now().isoformat(),'checks':{},'warnings':[]}

def vec(p):return unreal.Vector(*[c*100 for c in p])
def trace(a,b):
    hit=unreal.SystemLibrary.line_trace_single(query_world,vec(a),vec(b),unreal.TraceTypeQuery.ECC_VISIBILITY,False,ignore,unreal.DrawDebugTrace.NONE)
    if hit is None:return None
    values=hit.to_tuple();actor=values[9];point=values[5]
    return {'actor':actor.get_actor_label() if actor else '',
            'folder':str(actor.get_folder_path()) if actor else '',
            'point':[point.x/100,point.y/100,point.z/100],'distance':values[3]/100}

def capsule(p):
    c=(p[0],p[1],p[2]+.93)
    return unreal.SystemLibrary.capsule_trace_single(query_world,vec(c),vec((c[0],c[1],c[2]+.01)),30,90,unreal.TraceTypeQuery.ECC_VISIBILITY,False,ignore,unreal.DrawDebugTrace.NONE)

def in_polygon(x,y,poly):
    inside=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>y)!=(b[1]>y) and x<a[0]+(b[0]-a[0])*(y-a[1])/(b[1]-a[1]):inside=not inside
    return inside

def main():
    global query_world,ignore
    query_world=editor.get_game_world()
    if query_world:
        if MAP.rsplit('/',1)[-1] not in query_world.get_path_name():raise RuntimeError('PIE is using a different map')
        pawn=unreal.GameplayStatics.get_player_pawn(query_world,0)
        if pawn:ignore=[pawn]
        report['world_type']='PIE'
    else:
        # Keep no UWorld reference across load: loading the same map can GC a
        # world still referenced by the persistent Python worker context.
        if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):
            if not level.load_level(MAP):raise RuntimeError('Cannot load V07 map')
        query_world=editor.get_editor_world();report['world_type']='Editor'
    path=os.path.join(OUT,'LayoutSpec.json')
    if not os.path.exists(path):path=os.path.join(OUT,'LayoutSpec_working.json')
    with open(path,encoding='utf-8') as f:data=json.load(f)
    report['source_layout']=path
    nodes_by_id={n['index']:n for n in data['nodes']}
    actors=unreal.GameplayStatics.get_all_actors_of_class(query_world,unreal.Actor)
    report['checks']['read_back_actor_count']=len(actors)
    gm=query_world.get_world_settings().get_editor_property('default_game_mode')
    report['checks']['gamemode']=gm.get_path_name() if gm else None
    report['checks']['no_combat_controllers']=not any('EncounterController' in a.get_class().get_name() for a in actors)
    report['checks']['node_tags']={str(n['index']):sum(a.actor_has_tag(unreal.Name('NLBlockout.Node.%02d'%n['index'])) for a in actors) for n in data['nodes']}
    report['checks']['stairs']=[{'name':s['name'],'riser_cm':round(s['riser']*100,3),'tread_cm':round(s['tread']*100,3),'width_m':s['width'],'passes':s['riser']<=.161 and s['tread']>=.30} for s in data['stairs']]
    report['checks']['furnace_behind_friend_m']=data['furnace'][1]-data['friend'][1]
    report['checks']['player_to_friend_m']=math.dist(nodes_by_id[5]['ground'],data['friend'])
    report['checks']['boss_distance_m']=math.dist(nodes_by_id[7]['ground'],data['boss'])
    floor_fail=[]
    for i,p in enumerate(data['route']):
        hit=trace((p[0],p[1],p[2]+1),(p[0],p[1],p[2]-2))
        if not hit or abs(hit['point'][2]-p[2])>.20:floor_fail.append({'sample':i,'position':p,'hit':hit})
    report['checks']['route_floor_samples']=len(data['route'])
    report['checks']['route_floor_failures']=floor_fail
    landings=[]
    for n in data['nodes']:
        p=n['ground'];hit=trace((p[0],p[1],p[2]+.5),(p[0],p[1],p[2]-1))
        landings.append({'index':n['index'],'floor':hit,'capsule_clear':capsule(p) is None})
    report['checks']['node_landings']=landings
    peak=next(p for p in data['platforms'] if p['name'].startswith('D_'))
    px,py,pz=peak['center'];radius=peak.get('radius',30)
    offsets=[radius*t for t in (-.8,-.6,-.4,-.2,0,.2,.4,.6,.8)]
    targets=[(px+x,py-math.sqrt(radius*radius-x*x),pz+.2) for x in offsets]
    seal=next((p for p in data.get('footprints',[]) if p['name']=='SealWall'),None)
    crown=(px,seal['center'][1] if seal else py+radius*2/3,pz+26)
    report['sightlines']={'targets_m':targets,'crown_target_m':crown,'nodes':[],'court_grid':{},'route':{}}
    def visible(p,t):
        hit=trace(p,t)
        return (hit is None or '05_SummitSeal' in hit['folder']),hit
    def peak_check(p):
        hits=[visible(p,t) for t in targets]
        cv,ch=visible(p,crown)
        return hits,cv,ch
    for n in data['nodes']:
        if n['index']>=7:continue
        for eye in (1.1,1.7):
            p=list(n['ground']);p[2]+=eye
            hits,cv,ch=peak_check(p)
            report['sightlines']['nodes'].append({'node':n['index'],'eye':eye,'physical_peak':any(h[0] for h in hits),'rim_segment':any(a[0] and b[0] for a,b in zip(hits,hits[1:])),'crown':cv,'blockers':[h[1] for h in hits if not h[0]],'crown_blocker':None if cv else ch})
    for floor in data['platforms']:
        if floor['name'].startswith('D_'):continue
        cx,cy,z=floor['center']
        if floor.get('shape')=='polygon':
            poly=floor['points'];xmin,xmax=min(p[0] for p in poly),max(p[0] for p in poly);ymin,ymax=min(p[1] for p in poly),max(p[1] for p in poly)
        else:
            w,d=floor['size'];xmin,xmax=cx-w/2,cx+w/2;ymin,ymax=cy-d/2,cy+d/2;poly=None
        good=total=0;blocks=collections.Counter();fail=[]
        for xi in range(int(math.floor(xmin))+2,int(math.ceil(xmax))-1,3):
            for yi in range(int(math.floor(ymin))+2,int(math.ceil(ymax))-1,3):
                if poly and not in_polygon(xi,yi,poly):continue
                foot=(xi,yi,z)
                fh=trace((xi,yi,z+.5),(xi,yi,z-1))
                if not fh or abs(fh['point'][2]-z)>.2 or capsule(foot) is not None:continue
                eye=(xi,yi,z+1.1);hits,cv,ch=peak_check(eye);total+=1
                if any(h[0] for h in hits):good+=1
                else:
                    for hit in hits:blocks[hit[1]['actor'] if hit[1] else 'unknown']+=1
                    if len(fail)<15:fail.append({'eye':eye,'hits':[h[1] for h in hits]})
        report['sightlines']['court_grid'][floor['name']]={'clear':good,'total':total,'fraction':good/total if total else 0,'blockers':dict(blocks.most_common(12)),'examples':fail}
    good=total=crown_good=any_good=0;blocks=collections.Counter();fail=[];any_fail=[]
    for p in data['route'][::5]:
        if p[2]>=pz-.5:continue
        hits,cv,ch=peak_check((p[0],p[1],p[2]+1.1));total+=1
        physical=any(h[0] for h in hits)
        crown_good+=int(cv);any_good+=int(physical or cv)
        if physical:good+=1
        else:
            for hit in hits:blocks[hit[1]['actor'] if hit[1] else 'unknown']+=1
            if len(fail)<20:fail.append({'position':p,'hits':[h[1] for h in hits]})
        if not physical and not cv and len(any_fail)<20:
            any_fail.append({'position':p,'rim_hits':[h[1] for h in hits],'crown_hit':ch})
    report['sightlines']['route']={'clear':good,'total':total,'fraction':good/total if total else 0,
        'crown_clear':crown_good,'crown_total':total,'crown_fraction':crown_good/total if total else 0,
        'any_target_clear':any_good,'any_target_total':total,'any_target_fraction':any_good/total if total else 0,
        'any_target_fail_examples':any_fail,'blockers':dict(blocks.most_common(15)),'examples':fail}
    cp=nodes_by_id[1]['ground']
    control=trace((cp[0],cp[1],cp[2]+2),(cp[0],cp[1],cp[2]-2))
    report['checks']['physics_control_hit']=control
    report['sightlines']['trustworthy']=control is not None
    report['checks']['node_sightlines_pass']=all(n['physical_peak'] and n['crown'] for n in report['sightlines']['nodes'])
    report['success']=bool(control and not floor_fail and all(n['capsule_clear'] and n['floor'] for n in landings) and all(s['passes'] for s in report['checks']['stairs']) and report['checks']['node_sightlines_pass'])
    with open(os.path.join(OUT,'Validation.json'),'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    unreal.log('NILIN_V02_VALIDATION_DONE '+str(report['success']))

try:main()
except Exception:
    with open(os.path.join(OUT,'ValidationError.txt'),'w',encoding='utf-8') as f:f.write(traceback.format_exc())
    raise
finally:
    # Persistent live workers must not retain an Editor/PIE UWorld or Pawn.
    query_world=None
    ignore=[]
