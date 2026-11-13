import json,math
from pathlib import Path
P=Path(r'D:/game design/experiment/Docs/Gameplay/PackSlashReview1104')
data=json.loads((P/'CandidateMotion.json').read_text())
def add(a,b):return [x+y for x,y in zip(a,b)]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def mul(a,s):return [x*s for x in a]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def unit(a):return mul(a,1/norm(a)) if norm(a)>1e-9 else [0,0,0]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def rot(q,v):
    t=mul(cross(q[:3],v),2)
    return add(add(v,mul(t,q[3])),cross(q[:3],t))
variants={'current':([1,0,0],[0,-1,0]),'reverse_blade_and_edge':([-1,0,0],[0,1,0]),'reverse_blade_same_edge':([-1,0,0],[0,-1,0]),'same_blade_reverse_edge':([1,0,0],[0,1,0]),
 'tip_negZ_edge_posX':([0,0,-1],[1,0,0]),'tip_negZ_edge_negX':([0,0,-1],[-1,0,0]),
 'tip_negZ_edge_posY':([0,0,-1],[0,1,0]),'tip_negZ_edge_negY':([0,0,-1],[0,-1,0]),
 'tip_posZ_edge_posX':([0,0,1],[1,0,0]),'tip_posZ_edge_negX':([0,0,1],[-1,0,0]),
 'tip_posZ_edge_posY':([0,0,1],[0,1,0]),'tip_posZ_edge_negY':([0,0,1],[0,-1,0])}
mapping=json.loads((P/'SourceToNativeHandMapping.json').read_text())[0]['source_axis_in_target']
variants['source_shaft_negY_edge_negX']=(mapping['blade_negativeY'],mul(mapping['X'],-1))
variants['source_shaft_negY_edge_posX']=(mapping['blade_negativeY'],mapping['X'])
variants['source_shaft_negY_edge_posZ']=(mapping['blade_negativeY'],mapping['Z'])
variants['source_shaft_negY_edge_negZ']=(mapping['blade_negativeY'],mul(mapping['Z'],-1))
output={'source':data['mesh'],'candidates':[]}
for clip in data['clips']:
    frames=clip['frames']
    row={'clip':clip['name'],'variants':{}}
    for name,(axis,edge) in variants.items():
        f=[]
        for frame in frames:
            hand=frame['bones']['RightHand'];hips=frame['bones']['Hips']['p']
            h=sub(hand['p'],hips)
            q=hand['q'];blade=rot(q,axis);cut=rot(q,edge)
            tip=add(h,mul(blade,71));mid=add(h,mul(blade,40))
            f.append({'t':frame['t'],'h':h,'tip':tip,'mid':mid,'blade':blade,'edge':cut})
        samples=[]
        for i in range(1,len(f)-1):
            dt=f[i+1]['t']-f[i-1]['t']
            tv=mul(sub(f[i+1]['tip'],f[i-1]['tip']),1/dt)
            mv=mul(sub(f[i+1]['mid'],f[i-1]['mid']),1/dt)
            hv=mul(sub(f[i+1]['h'],f[i-1]['h']),1/dt)
            av=mul(sub(f[i+1]['blade'],f[i-1]['blade']),1/dt)
            samples.append({'t':f[i]['t'],'tip_speed':norm(tv),'tip_edge_cos':dot(unit(tv),f[i]['edge']),
                'mid_edge_cos':dot(unit(mv),f[i]['edge']),'shaft_ang_speed':norm(av),'hand_vz':hv[2],
                'blade':f[i]['blade'],'edge':f[i]['edge'],'tip':f[i]['tip'],'hand':f[i]['h']})
        fastest=sorted(samples,key=lambda s:s['shaft_ang_speed'],reverse=True)[:10]
        fastdown=sorted([s for s in samples if s['hand_vz']<0],key=lambda s:s['shaft_ang_speed'],reverse=True)[:10]
        attack=[s for s in samples if .3<s['t']<clip['duration']*.65 and s['hand_vz']<0]
        attack=sorted(attack,key=lambda s:s['shaft_ang_speed'],reverse=True)[:10]
        row['variants'][name]={'fastest':sorted(fastest,key=lambda s:s['t']),
            'main_fastdown_cos':sum(s['tip_edge_cos'] for s in attack)/len(attack),
            'avg_fast_edge_cos':sum(s['tip_edge_cos'] for s in fastest)/len(fastest),
            'avg_fastdown_edge_cos':sum(s['tip_edge_cos'] for s in fastdown)/len(fastdown),
            'fastdown_t':[round(s['t'],3) for s in sorted(fastdown,key=lambda s:s['t'])],
            'keypose':[{k:f[round(len(f)*frac)][k] for k in ['t','h','blade','edge','tip']} for frac in [0,.3,.45,.6]]}
    output['candidates'].append(row)
(P/'GripDirectionAudit.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
for row in output['candidates']:
    print(row['clip'])
    for n,r in row['variants'].items():print(n,'fast',round(r['avg_fast_edge_cos'],3),'down',round(r['avg_fastdown_edge_cos'],3),'mainDown',round(r['main_fastdown_cos'],3))
    print('CURRENT KEY',row['variants']['current']['keypose'])

print('TWO_HAND_AXES')
for source_file,hand_r,hand_l in [('SourceMotion.json','hand_r','hand_l'),('CandidateMotion.json','RightHand','LeftHand')]:
    sd=json.loads((P/source_file).read_text())
    for clip in sd['clips']:
        if 'heavy' not in clip['name']:continue
        rows=[]
        for frame in clip['frames']:
            if .8<=frame['t']<=1.6:
                r=frame['bones'][hand_r];l=frame['bones'][hand_l]
                axis=sub(r['p'],l['p']);q=r['q'];qi=[-q[0],-q[1],-q[2],q[3]]
                rows.append({'t':round(frame['t'],2),'gap':round(norm(axis),2),'local':rot(qi,unit(axis))})
        avg=unit([sum(r['local'][i] for r in rows) for i in range(3)])
        print(source_file,clip['name'],'avg',avg,'minmaxgap',min(r['gap'] for r in rows),max(r['gap'] for r in rows),'rows',rows[::5])
