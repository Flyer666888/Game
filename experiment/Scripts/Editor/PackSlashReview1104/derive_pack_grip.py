import json,math
from pathlib import Path
P=Path(r'D:/game design/experiment/Docs/Gameplay/PackSlashReview1104')
s=json.loads((P/'SourceMotion.json').read_text());t=json.loads((P/'CandidateMotion.json').read_text())
def add(a,b):return [x+y for x,y in zip(a,b)]
def mul(a,s):return [x*s for x in a]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def unit(a):return mul(a,1/norm(a))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def rot(q,v):
    tv=mul(cross(q[:3],v),2);return add(add(v,mul(tv,q[3])),cross(q[:3],tv))
def qm(a,b):
    x,y,z,w=a;X,Y,Z,W=b
    return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def qi(q):return [-q[0],-q[1],-q[2],q[3]]
yaw=[0,0,-math.sqrt(.5),math.sqrt(.5)]
rows=[]
for tc in t['clips']:
    sc=next(c for c in s['clips'] if c['name']==tc['name'][5:])
    offsets=[unit(qm(qi(tf['bones']['RightHand']['q']),qm(yaw,sf['bones']['hand_r']['q']))) for sf,tf in zip(sc['frames'],tc['frames'])]
    base=offsets[0];errors=[2*math.degrees(math.acos(min(1,abs(dot(base,q))))) for q in offsets]
    rows.append({'clip':tc['name'],'mapping':base,'max_offset_error_degrees':max(errors),'source_axis_in_target':{n:rot(base,v) for n,v in {'X':[1,0,0],'Y':[0,1,0],'Z':[0,0,1],'blade_negativeY':[0,-1,0]}.items()}})
print(json.dumps(rows,indent=2))
(P/'SourceToNativeHandMapping.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
C=rows[1]['mapping'];h=math.sqrt(.5)
variants={
  'shaft_source_negativeY_edge_source_positiveX':qm(C,[0,-h,h,0]),
  'shaft_source_negativeY_edge_source_negativeX':qm(C,[h,0,0,h]),
}
out={'note':'Read-only binding candidates from constant retarget hand mapping. Source shaft -Y inferred from two-handed grip line; edge +X supported for heavy01/02 descent, not all light slash clips. Visual QA required.',
     'source_to_target_hand_q_xyzw':C,'translation':[0,-.065,.035],'scale':[.01,.01,.01],'quaternions_xyzw':variants}
(P/'PackGripCandidates.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
