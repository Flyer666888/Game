"""PIE smoke/continuous walking check with the real CharacterMovement component.
No map modifications, no combat systems, no simulated success assertions.
"""
import unreal, json, os, time, math, traceback
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v03'
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV08'
os.makedirs(OUT,exist_ok=True)
spec_path=os.path.join(OUT,'LayoutSpec.json')
if not os.path.exists(spec_path):spec_path=os.path.join(OUT,'LayoutSpec_working.json')
with open(spec_path,encoding='utf-8') as _source:data=json.load(_source)
side=-1 if data.get('world_mirrored_x') else 1
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
phase=0;busy=False;handle=None;began=time.monotonic();last=0;index=0;pawn=None;movement=None;node_index=0;progress=time.monotonic();best=1e9
last_tick=began
report={'kind':'Actual PIE CharacterMovement smoke and continuous walk','state':'starting','nodes':[],'waypoints_reached':0,'failures':[]}
def save():
    with open(os.path.join(OUT,'RuntimeWalk.json'),'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
def vec(p):return unreal.Vector(*[x*100 for x in p])
# All upper landmarks come from the current source, never old V06 XY literals.
nodes_by_id={n['index']:n for n in data['nodes']}
rests_by_name={r['name']:r for r in data.get('rests',[])}
peak=next(p for p in data['platforms'] if p['name'].startswith('D_'))
px,py,pz=peak['center'];radius=peak.get('radius',30)
alchemy=next(p for p in data['platforms'] if p['name'].startswith('C_'))
cx,cy,cz=alchemy['center'];cw=alchemy.get('size',[64,60])[0]
side=-1 if px<cx else 1
waypoints=[]
def append_point(p):
    p=tuple(p)
    if not waypoints or math.dist(waypoints[-1],p)>.05:waypoints.append(p)
first=data['stairs'][0]['a']
gate=next((p for p in data.get('footprints',[]) if p['name']=='Shanmen'),None)
gate_y=gate['center'][1] if gate else (nodes_by_id[1]['ground'][1]+first[1])*.5
append_point((first[0],gate_y,first[2]))
append_point((first[0],(gate_y+first[1])*.5,first[2]))
route=data['route'];cursor=0
for flight in data['stairs']:
    name=flight['name']
    if name=='C_to_Ridge':
        append_point(nodes_by_id[5]['ground'])
        exit_side=-1 if flight['a'][0]<cx else 1
        append_point((cx+exit_side*8,nodes_by_id[5]['ground'][1],cz))
        append_point((cx+exit_side*12,cy-9,cz))
        append_point((cx+exit_side*(cw*.5-8),cy,cz))
        if 'C_EastExit' in rests_by_name:append_point(rests_by_name['C_EastExit']['center'])
    append_point(flight['a'])
    count=flight['steps']+flight['landings']
    pts=route[cursor:cursor+count];cursor+=count
    for p in pts[::4]:append_point(p)
    append_point(flight['b'])
    if name=='Threshold_to_C':
        bridge=next((b for b in data.get('bridgeheads',[]) if b['name']=='AlchemyEntryBridgehead'),None)
        if bridge:
            start=bridge['start'];inward=bridge['inward'];length=bridge['size'][0]
            append_point((start[0]+inward[0]*length,start[1]+inward[1]*length,start[2]))
    if name=='A_to_Rest':append_point(nodes_by_id[2]['ground'])
    elif name=='Rest_to_B':
        append_point(nodes_by_id[3]['ground'])
        court=next(p for p in data['platforms'] if p['name'].startswith('B_'))
        append_point(court['center'])
        for detour in data.get('pressure',{}).get('walk_detours',[]):
            for p in detour:append_point(p)
    elif name=='B_to_Threshold':append_point(nodes_by_id[4]['ground'])
    else:
        rest_name={'C_to_Ridge':'RidgeLanding','Ridge_to_Node06':'Node06_BridgeLanding',
                   'Node06_to_Upper':'UpperLanding'}.get(name)
        if rest_name in rests_by_name:append_point(rests_by_name[rest_name]['center'])
        if name=='Ridge_to_Node06':
            append_point(nodes_by_id[6]['ground'])
            next_flight=next(s for s in data['stairs'] if s['name']=='Node06_to_Upper')
            a,b=next_flight['a'],next_flight['b'];run=math.hypot(b[0]-a[0],b[1]-a[1])
            append_point(data.get('route_approaches',{}).get('6',(a[0]-4*(b[0]-a[0])/run,a[1]-4*(b[1]-a[1])/run,a[2])))
# Same summit victory exit: bypass the colliding circular seal, not through it.
append_point((px,py-radius*.56,pz))
append_point(nodes_by_id[7]['ground'])
seal=next((p for p in data.get('footprints',[]) if p['name']=='SealWall'),None)
seal_y=seal['center'][1] if seal else py+radius*2/3
append_point((px+side*radius*.4,py+radius*.2,pz))
append_point((px+side*radius*.47,seal_y-1,pz))
append_point((px+side*radius*.33,nodes_by_id[8]['ground'][1],pz))
append_point(nodes_by_id[8]['ground'])
report['map']=MAP;report['source_layout']=spec_path
report['total_waypoints']=len(waypoints)
report['waypoints_m']=waypoints
def finish(error=None):
    global handle,pawn,movement
    if error:report['failures'].append(error)
    report['state']='failed' if report['failures'] else 'passed'
    report['elapsed_seconds']=time.monotonic()-began
    save()
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        handle=None
    # Do not leave a PIE Pawn/Movement/UWorld in the persistent worker context.
    pawn=None;movement=None
    level.editor_request_end_play()
def tick(delta):
    global phase,busy,last,index,pawn,movement,node_index,progress,best,began,last_tick
    if busy:return
    busy=True
    try:
        now=time.monotonic()
        gap=now-last_tick;last_tick=now
        if gap>2:
            report.setdefault('render_stalls_seconds',[]).append(round(gap,2))
            began+=gap;last+=gap;progress+=gap
        if now-began>480:finish({'error':'Runtime audit timeout'});return
        if phase==0:
            # No same-map reload, and no UWorld reference is retained across a load.
            if not editor.get_game_world():
                if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):
                    if not level.load_level(MAP):finish({'error':'Cannot load V07'});return
                level.editor_request_begin_play()
            elif MAP.rsplit('/',1)[-1] not in editor.get_game_world().get_path_name():
                finish({'error':'Existing PIE uses another map'});return
            phase=1;last=now;return
        if phase==1:
            world=editor.get_game_world()
            if not world or now-last<2:return
            pawn=unreal.GameplayStatics.get_player_pawn(world,0)
            if not pawn:
                if now-last>30:finish({'error':'No possessed PIE pawn'})
                return
            report['pawn_class']=pawn.get_class().get_path_name()
            if 'NLBlockoutCharacter' not in report['pawn_class']:finish({'error':'Unexpected game pawn'});return
            movement=pawn.get_component_by_class(unreal.CharacterMovementComponent)
            unreal.SystemLibrary.execute_console_command(world,'t.IdleWhenNotForeground 0')
            unreal.SystemLibrary.execute_console_command(world,'Slate.bAllowThrottling 0')
            unreal.GameplayStatics.set_game_paused(world,False)
            phase=2
        if phase==2:
            n=data['nodes'][node_index];p=n['ground']
            pawn.set_actor_location(vec((p[0],p[1],p[2]+.94)),False,True)
            movement.stop_movement_immediately();movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)
            last=now;phase=3;return
        if phase==3 and now-last>.8:
            n=data['nodes'][node_index];p=n['ground'];loc=pawn.get_actor_location()
            record={'node':n['index'],'location_m':[loc.x/100,loc.y/100,loc.z/100],'grounded':movement.is_moving_on_ground(),'height_error_cm':loc.z-p[2]*100-90}
            report['nodes'].append(record)
            save()
            if not record['grounded'] or abs(record['height_error_cm'])>8:report['failures'].append(record)
            node_index+=1
            if node_index<len(data['nodes']):phase=2;return
            if report['failures']:finish();return
            p=data['nodes'][0]['ground'];pawn.set_actor_location(vec((p[0],p[1],p[2]+.94)),False,True)
            movement.stop_movement_immediately();phase=4;last=now;return
        if phase==4 and now-last>1:
            phase=5;progress=now;best=1e9;report['state']='walking';save()
        if phase==5:
            if index>=len(waypoints):finish();return
            target=waypoints[index];loc=pawn.get_actor_location()
            dx=target[0]*100-loc.x;dy=target[1]*100-loc.y;dist=math.hypot(dx,dy)
            if dist<55 and abs(loc.z/100-.90-target[2])<.5:
                index+=1;report['waypoints_reached']=index;progress=now;best=1e9
                if index%20==0:save()
                return
            if dist<best-10:best=dist;progress=now
            if now-progress>6:
                finish({'error':'Character movement stalled','waypoint':index,'target':target,'position':[loc.x/100,loc.y/100,loc.z/100],'distance_cm':dist,'movement_mode':str(movement.get_editor_property('movement_mode'))});return
            if loc.z<target[2]*100-250:
                finish({'error':'Character fell below route','waypoint':index,'target':target,'position':[loc.x/100,loc.y/100,loc.z/100]});return
            pawn.add_movement_input(unreal.Vector(dx/dist,dy/dist,0),1.0,True)
    except Exception:finish({'error':traceback.format_exc()})
    finally:busy=False
handle=unreal.register_slate_post_tick_callback(tick)
save()

