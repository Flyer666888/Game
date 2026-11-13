import json,math
from pathlib import Path
P=Path(__file__).resolve().parents[3];O=P/'Docs/Gameplay/PlayerBackstepIntermittent1106'
j=json.loads((O/'Runtime.json').read_text(encoding='utf-8-sig'))
uid=j['fixture_isolation']['temporary_level_id'].split('.')[-1]
rows=[json.loads(line) for line in (O/'Frames.jsonl').read_text(encoding='utf-8').splitlines()]
rows=[r for r in rows if r.get('session')==uid]
episodes=[];current=None;relative_drift=0.0
for r in rows:
    relative_drift=max(relative_drift,math.hypot(r['camera_relative'][0],r['camera_relative'][1]))
    axes=r.get('values',{})
    moving_input=any(axes.get(k,0)>.5 for k in ['W','A','S','D'])
    yaw=math.radians(r['yaw'])
    backward_speed=-(r['velocity'][0]*math.cos(yaw)+r['velocity'][1]*math.sin(yaw))
    suspect=not moving_input and not r['paused'] and backward_speed>10 and 'WALKING' in r['move_mode']
    if suspect:
        if current is None:current={'start':r['wall_t'],'end':r['wall_t'],'peak_speed':backward_speed}
        current['end']=r['wall_t'];current['peak_speed']=max(current['peak_speed'],backward_speed)
    elif current is not None:
        episodes.append(current);current=None
if current:episodes.append(current)
suspects=[e for e in episodes if e['end']-e['start']>.5]
summary={'state':'analyzed','frame_count':len(rows),'events':j.get('events',[]),
    'sustained_no_directional_value_backward_episodes':suspects,
    'maximum_camera_relative_xy_offset_cm':relative_drift,
    'scope':'Supplemental visible-PIE observation. OS input is observed, not a scripted continuous manual playthrough. Native coalesced-event regression is the primary fix evidence.'}
(O/'TraceAnalysis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='events'}))
print(json.dumps({'events':summary['events'][-15:]}))
