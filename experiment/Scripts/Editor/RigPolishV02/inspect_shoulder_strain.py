import bpy,json,sys
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
P=Path(r'D:\game design\experiment');O=P/'Docs/Gameplay/RigPolish_v02/ShoulderAudit'
source=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
coords=[v.co.copy() for v in source.data.vertices]
weights=[{source.vertex_groups[g.group].name:g.weight for g in v.groups if g.weight>0} for v in source.data.vertices]
data=json.loads((P/'Docs/Gameplay/RigPolish_v01/UprightCandidatePoses.json').read_text(encoding='utf-8'))
def mat(t):return Matrix.LocRotScale(Vector(t['p']),Quaternion((t['q'][3],*t['q'][:3])),Vector(t['s']))
reflection=Matrix.Diagonal((1.,-1.,1.,1.));inv={b:mat(t).inverted() for b,t in data['reference'].items()}
idle='--idle' in sys.argv
clip=next(c for c in data['clips'] if c['name']==('Wuxia_Idle_Planted_Upright_v01' if idle else 'Wuxia_Attack_Sword_Upright_v01'))
world=min(clip['samples'],key=lambda s:abs(s['time']-(0 if idle else 1.1)))['world']
deform={b:reflection@mat(t)@inv[b]@reflection for b,t in world.items()}
posed=[]
for p,w in zip(coords,weights):
    v=Vector((0,0,0))
    for b,a in w.items():v+=(deform[b]@p)*a
    posed.append(v)
rows=[]
for edge in source.data.edges:
    a,b=edge.vertices
    if not any(124<coords[i].z<154 and abs(coords[i].x)<32 for i in (a,b)):continue
    original=(coords[a]-coords[b]).length
    if original<.25:continue
    current=(posed[a]-posed[b]).length
    rows.append({'edge':[a,b],'ratio':current/original,'before_cm':original,'after_cm':current,
                 'vertices':[{'id':i,'co':list(coords[i]),'posed':list(posed[i]),'weights':weights[i]} for i in (a,b)]})
rows.sort(key=lambda r:r['ratio'],reverse=True)
(O/('ShoulderStrain_'+('Candidate_' if 'Shoulder_v02' in bpy.data.filepath else 'Original_')+('Idle' if idle else 'Attack')+'.json')).write_text(json.dumps(rows[:250],indent=2),encoding='utf-8')
print(json.dumps(rows[:6],indent=2))
