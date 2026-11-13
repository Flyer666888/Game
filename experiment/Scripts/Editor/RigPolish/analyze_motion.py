"""Summarize observational before/after telemetry, not a deterministic benchmark."""
import json,math,statistics
from pathlib import Path
OUT=Path(__file__).resolve().parents[3]/'Docs/Gameplay/RigPolish_v01'
result={'scope':'Two real-AI observations with a fixed target and health protection. Animation-change frame displacement is diagnostic; frame time and AI scheduling differ between runs.','runs':{}}
for label in ('Before','After'):
    data=json.loads((OUT/(label+'Motion.json')).read_text(encoding='utf-8'))
    frames=data['frames'];changes=[]
    for old,new in zip(frames,frames[1:]):
        if old['asset']==new['asset']:continue
        shifts={bone:math.dist(old['positions'][bone],new['positions'][bone]) for bone in new['positions']}
        changes.append({'time':new['t'],'from':old['asset'],'to':new['asset'],'dt':new['t']-old['t'],
                        'max_bone_displacement_cm':max(shifts.values()),'right_hand_displacement_cm':shifts['hand_r']})
    health_losses=[old['player_health']-new['player_health'] for old,new in zip(frames,frames[1:]) if old['player_health']>new['player_health']]
    result['runs'][label]={'state':data['state'],'frames':len(frames),'states':sorted(set(row['state'] for row in frames)),
        'instances':sorted(set(row['instance'] for row in frames)),'transitions':changes,
        'transition_max_cm':max((c['max_bone_displacement_cm'] for c in changes),default=0),
        'transition_median_cm':statistics.median([c['max_bone_displacement_cm'] for c in changes]) if changes else 0,
        'observed_player_damage_events':len(health_losses),'observed_damage':sum(health_losses),
        'brain_attack_frames':sum(row['attack_window'] for row in frames),
        'blade_active_frames':sum('SWING_ACTIVE' in row.get('blade_state','') for row in frames) if 'blade_state' in frames[0] else None}
(OUT/'MotionComparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{p:v for p,v in row.items() if p not in ('transitions','states')} for k,row in result['runs'].items()},indent=2))
