"""Read-back validation using actual UE collision, without modifying the level."""
import unreal, os, json, math, traceback, datetime, collections
ROOT=r'D:\game design\experiment'
OUT=os.path.join(ROOT,'Docs','LevelDesign','Blockout_v01')
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV06'
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
report={'map':MAP,'checked_at':datetime.datetime.now().isoformat(),'checks':{},'warnings':[]}
query_world=None
ignore=[]
def vec(p):return unreal.Vector(*[c*100 for c in p])
def trace(a,b):
    h=unreal.SystemLibrary.line_trace_single(query_world,vec(a),vec(b),unreal.TraceTypeQuery.ECC_VISIBILITY,False,ignore,unreal.DrawDebugTrace.NONE)
    if h is None:return None
    values=h.to_tuple()
    actor=values[9]
    return {'actor':actor.get_actor_label() if actor else '', 'folder':str(actor.get_folder_path()) if actor else '', 'point':[v/100 for v in (values[5].x,values[5].y,values[5].z)],'distance':values[3]/100}

def main():
    global query_world,ignore
    query_world=editor.get_game_world()
    if not query_world:
        if not level.load_level(MAP):raise RuntimeError('Cannot reload saved map')
        query_world=editor.get_editor_world()
    else:
        player=unreal.GameplayStatics.get_player_pawn(query_world,0)
        if player:ignore=[player]
    report['world_type']='PIE' if editor.get_game_world() else 'Editor'
    data=json.load(open(os.path.join(OUT,'LayoutSpec.json'),encoding='utf-8'))
    allactors=unreal.GameplayStatics.get_all_actors_of_class(query_world,unreal.Actor)
    report['checks']['read_back_actor_count']=len(allactors)
    report['checks']['gamemode']=query_world.get_world_settings().get_editor_property('default_game_mode').get_path_name()
    report['checks']['no_combat_controllers']=not any('EncounterController' in a.get_class().get_name() for a in allactors)
    report['checks']['node_tags']={str(n['index']):sum(a.actor_has_tag(unreal.Name('NLBlockout.Node.%02d'%n['index'])) for a in allactors) for n in data['nodes']}
    report['checks']['stairs']=[{'name':s['name'],'riser_cm':round(s['riser']*100,2),'tread_cm':round(s['tread']*100,2),'width_m':s['width'],'passes':s['riser']<=.161 and s['tread']>=.30} for s in data['stairs']]
    report['checks']['furnace_behind_friend_m']=data['furnace'][1]-data['friend'][1]
    report['checks']['player_to_friend_m']=math.dist(data['nodes'][4]['ground'],data['friend'])
    report['checks']['boss_distance_m']=math.dist(data['nodes'][6]['ground'],data['boss'])
    floor_fail=[]
    for i,p in enumerate(data['route']):
        h=trace((p[0],p[1],p[2]+1),(p[0],p[1],p[2]-2))
        if not h or abs(h['point'][2]-p[2])>.20:
            floor_fail.append({'sample':i,'position':p,'hit':h})
    report['checks']['route_floor_samples']=len(data['route'])
    report['checks']['route_floor_failures']=floor_fail
    nodes=[]
    for n in data['nodes']:
        p=n['ground'];h=trace((p[0],p[1],p[2]+.5),(p[0],p[1],p[2]-1))
        c=(p[0],p[1],p[2]+.93)
        overlap=unreal.SystemLibrary.capsule_trace_single(query_world,vec(c),vec((c[0],c[1],c[2]+.01)),30,90,unreal.TraceTypeQuery.ECC_VISIBILITY,False,ignore,unreal.DrawDebugTrace.NONE)
        nodes.append({'index':n['index'],'floor':h,'capsule_clear':overlap is None})
    report['checks']['node_landings']=nodes
    # Eye positions are not magic markers: the first opaque hit must be the actual
    # summit formation, or the line must reach the target without any blocker.
    peak_x=data['boss'][0]
    targets=[(peak_x+offset,580-math.sqrt(30**2-offset**2),132.2) for offset in (-24,-18,-12,-6,0,6,12,18,24)]
    crown=(peak_x,599,158)
    def visible(p,t):
        h=trace(p,t)
        return (h is None or '05_SummitSeal' in h['folder']),h
    report['sightlines']={'nodes':[],'court_grid':{},'route':{}}
    for n in data['nodes'][:6]:
        for eye in (1.1,1.7):
            p=list(n['ground']);p[2]+=eye
            hits=[visible(p,t) for t in targets]
            cv,ch=visible(p,crown)
            report['sightlines']['nodes'].append({'node':n['index'],'eye':eye,'physical_peak':any(h[0] for h in hits),'crown':cv,'blockers':[h[1] for h in hits if not h[0]],'crown_blocker':None if cv else ch})
    for name,cx,cy,z,hw,hd in [('A',0,0,0,27,25),('B',0,140,28,27,21),('C',0,300,72,29,27)]:
        good=total=0;blocks=collections.Counter();fail=[]
        for x in range(-hw,hw+1,3):
            for y in range(-hd,hd+1,3):
                p=(cx+x,cy+y,z+1.1)
                # Ignore occupied architecture cells, not traversable floor.
                cap=unreal.SystemLibrary.capsule_trace_single(query_world,vec((p[0],p[1],z+.93)),vec((p[0],p[1],z+.94)),30,90,unreal.TraceTypeQuery.ECC_VISIBILITY,False,ignore,unreal.DrawDebugTrace.NONE)
                if cap is not None:continue
                hits=[visible(p,t) for t in targets];total+=1
                if any(h[0] for h in hits):good+=1
                else:
                    for h in hits:blocks[h[1]['actor'] if h[1] else 'unknown']+=1
                    if len(fail)<15:fail.append({'eye':p,'hits':[h[1] for h in hits]})
        report['sightlines']['court_grid'][name]={'clear':good,'total':total,'fraction':good/total if total else 0,'blockers':dict(blocks.most_common(12)),'examples':fail}
    good=total=0;blocks=collections.Counter();fail=[]
    for i,p in enumerate(data['route'][::5]):
        hits=[visible((p[0],p[1],p[2]+1.1),t) for t in targets];total+=1
        if any(h[0] for h in hits):good+=1
        else:
            for h in hits:blocks[h[1]['actor'] if h[1] else 'unknown']+=1
            if len(fail)<20:fail.append({'position':p,'hits':[h[1] for h in hits]})
    report['sightlines']['route']={'clear':good,'total':total,'fraction':good/total if total else 0,'blockers':dict(blocks.most_common(15)),'examples':fail}
    report['checks']['physics_control_hit']=trace((0,10,2),(0,10,-2))
    report['sightlines']['trustworthy']=report['checks']['physics_control_hit'] is not None
    report['success']=report['sightlines']['trustworthy'] and not floor_fail and all(n['capsule_clear'] and n['floor'] for n in nodes) and all(s['passes'] for s in report['checks']['stairs'])
    with open(os.path.join(OUT,'Validation.json'),'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    unreal.log('NILIN_BLOCKOUT_VALIDATION_DONE '+str(report['success']))
try:main()
except Exception:
    with open(os.path.join(OUT,'ValidationError.txt'),'w',encoding='utf-8') as f:f.write(traceback.format_exc())
    raise
