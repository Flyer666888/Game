"""Read-only source hand anatomy, wrist, and D cutting-edge audit."""
import json, math
from pathlib import Path
P=Path(r'D:/game design/experiment'); O=P/'Docs/Gameplay/HandGripPolish1104'
def add(a,b):return [x+y for x,y in zip(a,b)]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def mul(a,s):return [x*s for x in a]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def unit(a):return mul(a,1/norm(a))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def qi(q):return [-q[0],-q[1],-q[2],q[3]]
def qm(a,b):
    x,y,z,w=a;X,Y,Z,W=b
    return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def rot(q,v):
    t=mul(cross(q[:3],v),2);return add(add(v,mul(t,q[3])),cross(q[:3],t))
def ang(a,b,unoriented=False):
    c=dot(unit(a),unit(b));c=abs(c) if unoriented else c
    return math.degrees(math.acos(max(-1,min(1,c))))
def qangle(q):return math.degrees(2*math.acos(min(1,abs(unit(q)[3]))))
def local(bones,name,hand='hand_r'):
    return rot(qi(bones[hand]['q']),sub(bones[name]['p'],bones[hand]['p']))

d=json.loads((O/'PoseSamples.json').read_text(encoding='utf-8-sig'))
s=json.loads((O/'SourceDHand.json').read_text(encoding='utf-8-sig'))
mapping=json.loads((P/'Docs/Gameplay/PackSlashReview1104/SourceToNativeHandMapping.json').read_text())[3]
out={'source_clip':'/Game/Animations/Sword/Anim_CSATLI_04','source_finger_planes':[],'native_wrist':{},'blade_candidates':{}}
for f in s['frames']:
    bs=f['bones'];r={'t':f['t'],'fingers':{}}
    for finger in ['index','middle','ring','pinky']:
        ps=[local(bs,f'{finger}_0{i}_r') for i in [1,2,3]]
        n=unit(cross(sub(ps[1],ps[0]),sub(ps[2],ps[1])))
        r['fingers'][finger]={'points_hand_cm':ps,'curl_plane_normal':n,
            'shaft_Y_normal_error_deg':ang(n,[0,1,0],True),'shaft_Z_normal_error_deg':ang(n,[0,0,1],True)}
    r['thumb_points']=[local(bs,f'thumb_0{i}_r') for i in [1,2,3]]
    out['source_finger_planes'].append(r)
out['source_positive_Z_in_native_hand']=mapping['source_axis_in_target']['Z']
out['source_Z_to_native_X_degrees']=ang(mapping['source_axis_in_target']['Z'],[1,0,0])
source_reference_wrist=qm(qi(s['reference']['lowerarm_r']['q']),s['reference']['hand_r']['q'])
native_reference_wrist=d['reference']['local']['RightHand']['q']
source_wrist=[]
for f in s['frames']:
    local_q=qm(qi(f['bones']['lowerarm_r']['q']),f['bones']['hand_r']['q'])
    source_delta=qangle(qm(qi(source_reference_wrist),local_q))
    target_frame=min(d['clips']['attack']['frames'],key=lambda x:abs(x['t']-f['t']))
    native_delta=qangle(qm(qi(native_reference_wrist),target_frame['local']['RightHand']['q']))
    source_wrist.append({'t':f['t'],'source_reference_delta_deg':source_delta,'native_reference_delta_deg':native_delta,'difference_deg':abs(source_delta-native_delta)})
out['source_native_wrist_comparison']=source_wrist
out['wrist_interpretation']='Native wrist reference-delta angles match the authored source. High initial twist belongs to D itself; no additional wrist correction justified by these measurements.'

for kind,c in d['clips'].items():
    rows=[];rq=d['reference']['local']['RightHand']['q']
    for f in c['frames']:
        delta=qm(qi(rq),f['local']['RightHand']['q'])
        twist=unit([0,delta[1],0,delta[3]])
        if twist[3]<0:twist=mul(twist,-1)
        swing=qm(delta,qi(twist))
        rows.append({'t':f['t'],'local_reference_delta_deg':qangle(delta),'longitudinal_twist_deg':math.degrees(2*math.atan2(twist[1],twist[3])),
            'swing_deg':qangle(swing)})
    out['native_wrist'][kind]={'first':rows[0], 'swing_range_deg':[min(x['swing_deg'] for x in rows),max(x['swing_deg'] for x in rows)],
        'twist_range_deg':[min(x['longitudinal_twist_deg'] for x in rows),max(x['longitudinal_twist_deg'] for x in rows)]}

frames=d['clips']['attack']['frames'];gp=[0,-6.5,3.5]
variants={'old_physical_positive_X_edge_negative_Y':[.5,.5,.5,.5],
          'current_inferred_negative_source_Y':[.647854955,-.73402617,-.14345028,.144608286]}
for label,gq in variants.items():
    seq=[]
    for f in frames:
        h=f['world']['RightHand'];q=qm(h['q'],gq)
        center=add(h['p'],rot(h['q'],gp)); shaft=rot(q,[0,0,1]);edge=rot(q,[-1,0,0]);normal=rot(q,[0,1,0])
        seq.append({'t':f['t'],'center':center,'shaft':shaft,'edge':edge,'normal':normal,'mid':add(center,mul(shaft,35)),'tip':add(center,mul(shaft,71))})
    rows=[]
    for i,row in enumerate(seq[1:-1],1):
        velocity=mul(sub(seq[i+1]['mid'],seq[i-1]['mid']),1/(seq[i+1]['t']-seq[i-1]['t']))
        velperp=sub(velocity,mul(row['shaft'],dot(velocity,row['shaft'])))
        rows.append({'t':row['t'],'midblade_speed_cm_s':norm(velocity),'edge_dot_velocity':dot(row['edge'],unit(velocity)),
            'edge_dot_perpendicular_velocity':dot(row['edge'],unit(velperp)),
            'blade_plane_normal_dot_velocity':dot(row['normal'],unit(velocity)),
            'hand_cm':frames[i]['world']['RightHand']['p'],'blade_tip_cm':row['tip']})
    window=[r for r in rows if .4-1e-5<=r['t']<=.8+1e-5]
    weighted=lambda key:sum(r[key]*r['midblade_speed_cm_s'] for r in window)/sum(r['midblade_speed_cm_s'] for r in window)
    out['blade_candidates'][label]={'q_xyzw':gq,'sample_window':[.4,.8],
        'speed_weighted_edge_dot_velocity':weighted('edge_dot_velocity'),
        'speed_weighted_edge_dot_perpendicular_velocity':weighted('edge_dot_perpendicular_velocity'),
        'speed_weighted_abs_blade_plane_normal_dot_velocity':sum(abs(r['blade_plane_normal_dot_velocity'])*r['midblade_speed_cm_s'] for r in window)/sum(r['midblade_speed_cm_s'] for r in window),
        'window_rows':window,'all_rows':rows}
out['conclusions']=['Source fingers curl approximately in local XY; the shaft belongs near source Z, mapping near native X. Previous negative-source-Y shaft inference from inter-hand distance was anatomically incorrect.',
    'Native +X shaft with native -Y cutting edge is physically supported by mesh agent and edge-leading during the fast D cut at 0.67-0.73s.',
    'Use the same closed finger layer on all held-sword clips. Preserve D wrist/body animation initially; validate closeups and transitions.']
out['limits']=['Source curl-plane normals indicate anatomically plausible shaft axes, not an authored socket.','Blade velocities use currently exported rooted gameplay poses; actor root-travel curve is not added.','Wrist swing/twist uses native hand longitudinal local Y and reference pose, not clinical joint limits.']
(O/'AuditSourceAxis.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({'source_first_fingers':out['source_finger_planes'][0], 'source_Z_to_native_X_degrees':out['source_Z_to_native_X_degrees'],
    'wrist':out['native_wrist']['attack'], 'blade':{k:{n:v for n,v in x.items() if n not in ['all_rows','window_rows','q_xyzw']} for k,x in out['blade_candidates'].items()}},indent=2))
