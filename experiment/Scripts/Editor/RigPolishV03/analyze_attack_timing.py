"""Read-only numerical audit of the saved v02 baseline's real sword timeline."""
import json,math
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[3];OUT=PROJECT/'Docs/Gameplay/RigPolish_v03'
motion=json.loads((OUT/'BeforeMotion.json').read_text(encoding='utf-8'))
assets=json.loads((PROJECT/'Docs/Gameplay/RigPolish_v02/AssetAudit.json').read_text(encoding='utf-8'))
names=('blade_root_local','blade_mid_local','blade_tip_local')
def lerp(a,b,t):return [x+(y-x)*t for x,y in zip(a,b)]
def distance(a,b):return math.dist(a,b)
def capsule_axis_distance(point,player):
    low,high=player[2]-60.,player[2]+60.
    return math.dist(point,[player[0],player[1],max(low,min(high,point[2]))])
def segment_distance(a,b,player):
    lo,hi=0.,1.
    for _ in range(36):
        u=lo+(hi-lo)/3.;v=hi-(hi-lo)/3.
        if capsule_axis_distance(lerp(a,b,u),player)<capsule_axis_distance(lerp(a,b,v),player):hi=v
        else:lo=u
    return capsule_axis_distance(lerp(a,b,(lo+hi)/2.),player)
frames=motion['frames'];segments=[];current=None;closest={'distance_to_player_capsule_axis_cm':1e9};maxstep=0.;maxspeed=0.;maxnormalstep=0.;longgaps=[];prior=None
for frame in frames:
    label=(frame['state'],frame['asset'])
    if not current or current['label']!=list(label):
        current={'label':list(label),'start':frame['t'],'end':frame['t'],'frames':0};segments.append(current)
    current['end']=frame['t'];current['frames']+=1
    if 'Attack_Sword' in str(frame['asset']) and prior and prior['asset']==frame['asset'] and frame['animation_time']>=prior['animation_time']:
        dt=frame['t']-prior['t']
        for name in names:
            step=distance(frame['blade_points_world'][name],prior['blade_points_world'][name]);maxstep=max(maxstep,step)
            if dt<=.1:maxnormalstep=max(maxnormalstep,step)
            if dt>0:maxspeed=max(maxspeed,step/dt)
        if dt>.1:longgaps.append({'t':frame['t'],'gap_seconds':dt,'clip_time':frame['animation_time']})
    if 'SWING_ACTIVE' in frame['blade_state']:
        points=[frame['blade_points_world'][name] for name in names];p=frame['player_location']
        d=min(segment_distance(a,b,p) for a,b in zip(points,points[1:]))
        if prior and 'SWING_ACTIVE' in prior['blade_state']:
            # Sample the entire curved blade at <=3 cm, then follow each sample's
            # exact between-frame segment, as the native swept-sphere method does.
            old=[prior['blade_points_world'][name] for name in names]
            for i in (0,1):
                n=math.ceil(distance(points[i],points[i+1])/3)
                d=min(d,*[segment_distance(lerp(old[i],old[i+1],j/n),lerp(points[i],points[i+1],j/n),p) for j in range(n+1)])
        if d<closest['distance_to_player_capsule_axis_cm']:
            closest={'distance_to_player_capsule_axis_cm':d,'clearance_from_capsule_plus_sweep_cm':d-32.,
                't':frame['t'],'clip_time':frame['animation_time'],'target_distance_cm':frame['target_distance_cm'],
                'blade_points_world':frame['blade_points_world'],'player_location':p}
    prior=frame
timings=[]
for enemy in assets['enemies']:
    total=sum(enemy['timing'].values());is_sword='Attack_Sword' in enemy['animations']['attack_animation']
    timings.append({'enemy':enemy['key'],'timing':enemy['timing'],'uses_sword_clip':is_sword,
        'play_rate':(2.3333332538604736 if is_sword else 2.)/total,
        'notify_animation_seconds':[.8,1.03] if is_sword else None})
report={'state':'audited','source':'BeforeMotion.json','timings':timings,'timeline_segments':segments,
    'actual_attack_rates':sorted({f['play_rate'] for f in frames if 'Attack_Sword' in str(f['asset'])}),
    'minimum_player_health':min(f['player_health'] for f in frames),
    'closest_active_blade_to_target':closest,'max_attack_blade_sample_step_cm':maxstep,
    'max_attack_blade_step_within_100ms_cm':maxnormalstep,'capture_induced_long_frame_gaps':longgaps,
    'max_attack_blade_sample_speed_cm_s':maxspeed,
    'direction':'Mesh yaw -90: skeletal component +Y is actor forward; Blender -Y.',
    'conclusions':['No runtime speedup: ordinary sword plays at 1x, captains at 2/3x.',
        'Only Telegraph starts the attack clip; Attack and Recover do not restart it.',
        'Native blade requires both the brain window and notify window, aligned at clip 0.8–1.03 seconds.',
        'The original 130cm stopping range is larger than the original blade trajectory reaches in the tested encounter.',
        'Compact swing should cover forward component Y 100–130cm, near centre X and torso Z during the original active window; keep authored range and damage unchanged.'],
    'limits':'Capsule/sweep geometry audit uses native defaults radius28,halfheight88,sweep4. Sampled blade coverage is numerical evidence, not a replacement for real UE collision validation.'}
(OUT/'AttackTimingAudit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ('actual_attack_rates','minimum_player_health','closest_active_blade_to_target','max_attack_blade_sample_step_cm','max_attack_blade_sample_speed_cm_s')},indent=2))
