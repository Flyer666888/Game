"""Read-only geometric and pose audit, no Unreal or source-asset writes."""
import json,math
from pathlib import Path
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/HandGripPolish1104'
d=json.loads((O/'PoseSamples.json').read_text(encoding='utf-8-sig'))
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
def angle(a,b):return math.degrees(2*math.acos(min(1,abs(dot(unit(a),unit(b))))))
def aa(q):
    q=unit(q)
    if q[3]<0:q=mul(q,-1)
    a=2*math.acos(min(1,q[3]));s=math.sin(a/2)
    return mul(q[:3],math.degrees(a)/s) if abs(s)>1e-8 else [0,0,0]
grip_q=[.647854955,-.73402617,-.14345028,.144608286]
grip_p=[0,-6.5,3.5];axis=rot(grip_q,[0,0,1])
ref=d['reference'];names=[n for n in ref['local'] if n.startswith('RightHand') and n!='RightHand']
out={'current_grip':{'center_hand_space_cm':grip_p,'shaft_axis_hand_space':axis},
     'old_physical_grip':{'q_xyzw':[.5,.5,.5,.5],'shaft_axis':[1,0,0]},
     'constant_hand_rotation_to_keep_current_sword_with_old_grip':qm(grip_q,qi([.5,.5,.5,.5])),
     'wrist_correction_angle_degrees':angle(grip_q,[.5,.5,.5,.5]),'clips':{},'reference_finger_positions_hand_cm':{}}
for n in names:
    out['reference_finger_positions_hand_cm'][n]=rot(qi(ref['world']['RightHand']['q']),sub(ref['world'][n]['p'],ref['world']['RightHand']['p']))
for kind,clip in d['clips'].items():
    rows=[]
    for f in clip['frames']:
        H=f['world']['RightHand'];bones={}
        for n in names:
            p=rot(qi(H['q']),sub(f['world'][n]['p'],H['p']))
            delta=sub(p,grip_p);along=dot(delta,axis);radial=norm(sub(delta,mul(axis,along)))
            bones[n]={'p_hand_cm':p,'shaft_axial_cm':along,'shaft_radial_cm':radial,
                      'bind_delta_axisangle_deg':aa(qm(qi(ref['local'][n]['q']),f['local'][n]['q']))}
        rows.append({'t':f['t'],'bones':bones})
    variation={n:max(angle(clip['frames'][0]['local'][n]['q'],f['local'][n]['q']) for f in clip['frames']) for n in names}
    out['clips'][kind]={'asset':clip['asset'],'duration':clip['duration'], 'finger_rotation_max_from_first_deg':variation,
       'max_finger_rotation_change_deg':max(variation.values()),'frames':rows}
(O/'AuditFingerPose.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
summary={'grip':out['current_grip'],'wrist_correction_angle':out['wrist_correction_angle_degrees'],
 'hand_correction_q':out['constant_hand_rotation_to_keep_current_sword_with_old_grip'],
 'clips':{k:{'finger_change_deg':v['max_finger_rotation_change_deg'],
  'first_fingers':{n:v['frames'][0]['bones'][n] for n in ['RightHandIndex1','RightHandIndex2','RightHandIndex3','RightHandIndex4','RightHandThumb1','RightHandThumb2','RightHandThumb3','RightHandThumb4']}} for k,v in out['clips'].items()}}
(O/'AuditSummary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({'grip':out['current_grip'],'wrist_correction_degrees':out['wrist_correction_angle_degrees'],
 'finger_change_deg':{k:v['max_finger_rotation_change_deg'] for k,v in out['clips'].items()},
 'D_finger_deltas':{n:out['clips']['attack']['frames'][0]['bones'][n]['bind_delta_axisangle_deg'] for n in names}},indent=2))
