"""PIE smoke/continuous walking check with the real CharacterMovement component.
No map modifications, no combat systems, no simulated success assertions.
"""
import unreal, json, os, time, math, traceback
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v01'
data=json.load(open(os.path.join(OUT,'LayoutSpec.json'),encoding='utf-8'))
side=-1 if data.get('world_mirrored_x') else 1
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
phase=0;busy=False;handle=None;began=time.monotonic();last=0;index=0;pawn=None;movement=None;node_index=0;progress=time.monotonic();best=1e9
last_tick=began
report={'kind':'Actual PIE CharacterMovement smoke and continuous walk','state':'starting','nodes':[],'waypoints_reached':0,'failures':[]}
def save():
    with open(os.path.join(OUT,'RuntimeWalk.json'),'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
def vec(p):return unreal.Vector(*[x*100 for x in p])
waypoints=[(0,-5,0),(0,14,0),(0,26,0)]
route=data['route'];cursor=0
for flight in data['stairs']:
    if flight['name']=='C_to_Ridge':waypoints.extend([(0,279,72),(0,291,72),(side*24,300,72),(side*28,310,72),(side*36,310,72)])
    count=flight['steps']+flight['landings']
    pts=route[cursor:cursor+count];cursor+=count
    waypoints.extend(pts[::4]);waypoints.append(flight['b'])
    if flight['name']=='A_to_Rest':waypoints.append((0,64,12))
    elif flight['name']=='Rest_to_B':waypoints.extend([(0,126,28),(0,143,28),(0,162,28)])
    elif flight['name']=='B_to_Threshold':waypoints.append((0,201,44))
    elif flight['name']=='C_to_Ridge':waypoints.append((side*80,360,88))
    elif flight['name']=='Ridge_to_Node06':waypoints.append((side*130,440,104))
    elif flight['name']=='Node06_to_Upper':waypoints.append((side*190,520,122))
waypoints.extend([(side*220,563,132),(side*220,573,132),(side*231,586,132),(side*234,599,132),(side*230,605,132),(side*220,605,132)])
report['total_waypoints']=len(waypoints)
def finish(error=None):
    if error:report['failures'].append(error)
    report['state']='failed' if report['failures'] else 'passed'
    report['elapsed_seconds']=time.monotonic()-began
    save()
    unreal.unregister_slate_post_tick_callback(handle)
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
            level.editor_request_begin_play();phase=1;last=now;return
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
