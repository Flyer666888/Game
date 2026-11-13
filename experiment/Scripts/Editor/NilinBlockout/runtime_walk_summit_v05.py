"""Targeted final-approach regression with actual PIE CharacterMovement.
One initial placement at original waypoint 479, then walk targets 480..532.
No map modifications, skipped collision, or teleports during the section walk.
"""
import unreal, json, os, time, math, traceback
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v05'
MAP='/Game/ReversedScale/Maps/L_NilinBlockoutV10'
START_INDEX=480
EXPECTED_ORIGINAL_COUNT=533
os.makedirs(OUT,exist_ok=True)
spec_path=os.path.join(OUT,'LayoutSpec.json')
with open(spec_path,encoding='utf-8') as _source:data=json.load(_source)
if data.get('map')!=MAP:raise RuntimeError('Runtime walk requires the saved V10 layout')
if not unreal.EditorAssetLibrary.does_asset_exist(MAP):raise RuntimeError('V10 map is not saved')
side=-1 if data.get('world_mirrored_x') else 1
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
phase=0;busy=False;handle=None;began=time.monotonic();last=0;index=0;pawn=None;movement=None;node_index=0;progress=time.monotonic();best=1e9
last_tick=began
report={'kind':'Actual PIE CharacterMovement targeted summit regression','state':'starting','nodes':[],'waypoints_reached':0,'failures':[],
        'initial_teleport_count':0,'teleports_during_walk':0,
        'limitations':['Covers the final section only; this is not a new full-route pass.',
                       'The earlier full route report records eight node landings and 513/533 targets before the rail repair.',
                       'No combat AI, VR input or headset performance is tested.']}
def save():
    with open(os.path.join(OUT,'RuntimeWalkSummit.json'),'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
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
perch_stations=data.get('ranged_encounters',{}).get('stations',[])
visited_perches=[]
lower_stairs=[s for s in data['stairs'] if not s['name'].startswith('Yufeng_')]
for flight in lower_stairs:
    name=flight['name']
    append_point(flight['a'])
    count=flight['steps']+flight['landings']
    pts=flight.get('route_samples',route[cursor:cursor+count]);cursor+=count
    perch_indices={}
    for station in perch_stations:
        if station['id'] in visited_perches:continue
        nearest=min(range(len(pts)),key=lambda i:math.dist(pts[i],station['route_rest']))
        if math.dist(pts[nearest],station['route_rest'])<.10:
            perch_indices.setdefault(nearest,[]).append(station)
    for i,p in enumerate(pts):
        if i%4==0 or i in perch_indices:append_point(p)
        for station in perch_indices.get(i,[]):
            append_point(station['route_rest'])
            for q in station['access_route']:append_point(q)
            for q in reversed(station['access_route'][:-1]):append_point(q)
            append_point(station['route_rest'])
            visited_perches.append(station['id'])
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
segments=data.get('upper_route_segments',[])
if not segments:raise RuntimeError('V10 upper route segments are missing')
arena_by_id={a['id']:a for a in data['grandmaster_arenas']}
visited_arenas=[]
def arena_circuit(arena_id):
    if not arena_id or arena_id=='BOSS' or arena_id in visited_arenas:return
    arena=arena_by_id[arena_id];x,y,z=arena['center'];width,depth=arena['clear_size']
    # Stay inside the declared clear fighting space, leaving 1 m at each edge.
    hx=width*.5-1;hy=depth*.5-1;yaw=math.radians(arena.get('rotation_yaw',0))
    append_point((x,y,z))
    for ox,oy in ((-hx,-hy),(hx,-hy),(hx,hy),(-hx,hy),(-hx,-hy),(0,0)):
        append_point((x+ox*math.cos(yaw)-oy*math.sin(yaw),y+ox*math.sin(yaw)+oy*math.cos(yaw),z))
    visited_arenas.append(arena_id)
append_point(nodes_by_id[5]['ground'])
exit_side=-1 if segments[0]['a'][0]<cx else 1
append_point((cx+exit_side*8,nodes_by_id[5]['ground'][1],cz))
append_point((cx+exit_side*12,cy-9,cz))
append_point((cx+exit_side*(cw*.5-8),cy,cz))
if 'C_EastExit' in rests_by_name:append_point(rests_by_name['C_EastExit']['center'])
upper_stairs={s['name']:s for s in data['stairs'] if s['name'].startswith('Yufeng_')}
for segment in segments:
    arena_circuit(segment.get('source_arena'))
    append_point(segment['a'])
    if segment['name'] in upper_stairs:
        flight=upper_stairs[segment['name']]
        if 'route_samples' not in flight:raise RuntimeError('Upper stair requires explicit route_samples: '+flight['name'])
        for p in flight['route_samples'][::4]:append_point(p)
    append_point(segment['b'])
    arena_circuit(segment.get('target_arena'))
if len(visited_arenas)!=4:raise RuntimeError('Continuous walk does not visit all four grandmaster spaces')
if len(visited_perches)!=len(perch_stations):raise RuntimeError('A ranged access route does not connect to a lower stair landing')
# Same summit victory exit: bypass the colliding circular seal, not through it.
append_point((px,py-radius*.56,pz))
append_point(nodes_by_id[7]['ground'])
# An actual walking loop around the enlarged boss floor tests lateral movement,
# not merely a single centerline from its entrance to the victory marker.
boss_clear=data['boss_arena']['clear_radius']
for k in range(13):
    angle=-math.pi/2+k*2*math.pi/12
    append_point((px+boss_clear*.7*math.cos(angle),py+boss_clear*.7*math.sin(angle),pz))
append_point(nodes_by_id[7]['ground'])
seal=next((p for p in data.get('footprints',[]) if p['name']=='SealWall'),None)
seal_y=seal['center'][1] if seal else py+radius*2/3
append_point((px+side*radius*.4,py+radius*.2,pz))
append_point((px+side*radius*.47,seal_y-1,pz))
append_point((px+side*radius*.33,nodes_by_id[8]['ground'][1],pz))
append_point(nodes_by_id[8]['ground'])
original_waypoints=waypoints
if len(original_waypoints)!=EXPECTED_ORIGINAL_COUNT:raise RuntimeError('Waypoint sequence changed; targeted regression range must be reviewed')
baseline_path=os.path.join(OUT,'RuntimeWalk_before_summit_rail_fix.json')
with open(baseline_path,encoding='utf-8') as handle:baseline=json.load(handle)
if baseline.get('map')!=MAP or baseline.get('total_waypoints')!=EXPECTED_ORIGINAL_COUNT:
    raise RuntimeError('The prior full-route evidence does not match this V10 target sequence')
if len(baseline.get('waypoints_m',[]))!=len(original_waypoints) or any(math.dist(a,b)>.001 for a,b in zip(baseline['waypoints_m'],original_waypoints)):
    raise RuntimeError('Current targets differ from the prior full-route report; cannot combine coverage')
start_ground=original_waypoints[START_INDEX-1]
waypoints=original_waypoints[START_INDEX:]
report['map']=MAP;report['source_layout']=spec_path
report['baseline_report']=baseline_path
report['original_waypoint_count']=len(original_waypoints)
report['start_index']=START_INDEX
report['planned_range']={'start_inclusive':START_INDEX,'end_exclusive':len(original_waypoints)}
report['covered_range']={'start_inclusive':START_INDEX,'end_exclusive':START_INDEX}
report['initial_position_original_index']=START_INDEX-1
report['initial_ground_m']=start_ground
report['original_waypoint_indices_reached']=[]
report['total_waypoints']=len(waypoints)
report['waypoints_m']=waypoints
report['grandmaster_arena_circuits']=['GM04']
report['ranged_perch_access_circuits']=[]
report['boss_clear_floor_circuit_radius_m']=boss_clear*.7
def finish(error=None):
    global handle,pawn,movement
    if error:report['failures'].append(error)
    report['state']='failed' if report['failures'] else 'passed'
    report['success']=not report['failures'] and index==len(waypoints)
    report['completed_target_count']=index
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
        if now-began>180:finish({'error':'Summit regression timeout'});return
        if phase==0:
            # No same-map reload, and no UWorld reference is retained across a load.
            if not editor.get_game_world():
                if not editor.get_editor_world().get_path_name().startswith(MAP+'.'):
                    if not level.load_level(MAP):finish({'error':'Cannot load V10'});return
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
            p=start_ground
            pawn.set_actor_location(vec((p[0],p[1],p[2]+.94)),False,True)
            report['initial_teleport_count']+=1
            movement.stop_movement_immediately();movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)
            last=now;phase=3;return
        if phase==3 and now-last>.8:
            p=start_ground;loc=pawn.get_actor_location()
            record={'original_waypoint':START_INDEX-1,'location_m':[loc.x/100,loc.y/100,loc.z/100],'grounded':movement.is_moving_on_ground(),'height_error_cm':loc.z-p[2]*100-90}
            report['section_start_smoke']=record
            save()
            if not record['grounded'] or abs(record['height_error_cm'])>8:report['failures'].append(record)
            if report['failures']:finish();return
            movement.stop_movement_immediately();phase=4;last=now;return
        if phase==4 and now-last>1:
            phase=5;progress=now;best=1e9;report['state']='walking';save()
        if phase==5:
            if index>=len(waypoints):finish();return
            target=waypoints[index];loc=pawn.get_actor_location()
            dx=target[0]*100-loc.x;dy=target[1]*100-loc.y;dist=math.hypot(dx,dy)
            if dist<55 and abs(loc.z/100-.90-target[2])<.5:
                report['original_waypoint_indices_reached'].append(START_INDEX+index)
                index+=1;report['waypoints_reached']=index;progress=now;best=1e9
                report['covered_range']['end_exclusive']=START_INDEX+index
                if index%5==0:save()
                return
            if dist<best-10:best=dist;progress=now
            if now-progress>6:
                finish({'error':'Character movement stalled','waypoint':index,'original_waypoint':START_INDEX+index,'target':target,'position':[loc.x/100,loc.y/100,loc.z/100],'distance_cm':dist,'movement_mode':str(movement.get_editor_property('movement_mode'))});return
            if loc.z<target[2]*100-250:
                finish({'error':'Character fell below route','waypoint':index,'target':target,'position':[loc.x/100,loc.y/100,loc.z/100]});return
            pawn.add_movement_input(unreal.Vector(dx/dist,dy/dist,0),1.0,True)
    except Exception:finish({'error':traceback.format_exc()})
    finally:busy=False
handle=unreal.register_slate_post_tick_callback(tick)
save()

