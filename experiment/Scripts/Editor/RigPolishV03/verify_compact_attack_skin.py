"""Read-only actual skin and held sword clearance check, offline or UE poses."""
import copy,json,math,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Quaternion,Vector,kdtree
PROJECT=Path(r'D:\game design\experiment');OUT=PROJECT/'ArtSource/WuxiaMale/RigPolishV03/Attack'
SETUP=PROJECT/'Saved/Scripts/bake_selected_death.py';context={'__name__':'compact_attack_verify','__file__':str(SETUP)}
exec(compile(SETUP.read_text(encoding='utf-8').split('raw=[];locals=[];support=[]')[0],str(SETUP),'exec'),context)
skin=context['skin'];world=context['world'];prop_world=context['prop_world'];weights=context['weights'];mesh=context['mesh']
runtime='--runtime' in sys.argv;name='CompactAttackRuntimePoses.json' if runtime else 'CompactAttackPoses.json'
data=json.loads((OUT/name).read_text(encoding='utf-8'));clip=data['clips'][0]
source_data=json.loads((PROJECT/'Docs/Gameplay/RigPolish_v01/UprightCandidatePoses.json').read_text(encoding='utf-8'))
source=next(c for c in source_data['clips'] if c['name']=='Wuxia_Attack_Sword_Upright_v01')
idle_q=Quaternion((source['samples'][0]['local']['hand_r']['q'][3],*source['samples'][0]['local']['hand_r']['q'][:3]))
body_ids=[i for i,w in enumerate(weights) if sum(w.get(b,0.) for b in ('spine_01','spine_02','spine_03','neck_01','head','clavicle_l','upperarm_l','lowerarm_l','hand_l'))>.5]
idle_hand=np.asarray(world(source['samples'][0]['local'])['hand_r'].translation)*np.array([1,-1,1]);prop=prop_world(source['samples'][0]['local']);tip_id=int(np.linalg.norm(prop-idle_hand,axis=1).argmax())
rows=[]
for s in clip['samples']:
    points,w=skin(s['local']);prop=prop_world(s['local']);tip=prop[tip_id];hand=np.asarray(w['hand_r'].translation)*np.array([1,-1,1])
    tree=kdtree.KDTree(len(body_ids))
    for n,i in enumerate(body_ids):tree.insert(points[i],i)
    tree.balance();nearest=[]
    for u in np.linspace(.25,1.,35):
        p=hand+(tip-hand)*u;co,vertex,distance=tree.find(p);nearest.append((distance,int(vertex),float(u)))
    closest=min(nearest)
    q=Quaternion((s['local']['hand_r']['q'][3],*s['local']['hand_r']['q'][:3]))
    rows.append({'time':s['time'],'skin_min_z_cm':float(points[:,2].min()),'sword_min_z_cm':float(prop[:,2].min()),
        'blade_to_torso_head_left_arm_vertex_clearance_cm':closest[0],'closest_body_vertex':closest[1],'closest_body_weights':weights[closest[1]],'blade_fraction':closest[2],
        'wrist_rotation_from_idle_deg':math.degrees(2.*math.acos(min(1.,abs(idle_q.normalized().dot(q.normalized())))))})
report={'state':'passed' if min(r['blade_to_torso_head_left_arm_vertex_clearance_cm'] for r in rows)>.8 else 'review',
    'source':name,'actual_mesh_vertices':len(mesh.data.vertices),'frames':len(rows),
    'minimum_blade_body_vertex_clearance_cm':min(r['blade_to_torso_head_left_arm_vertex_clearance_cm'] for r in rows),
    'minimum_skin_height_cm':min(r['skin_min_z_cm'] for r in rows),'minimum_sword_height_cm':min(r['sword_min_z_cm'] for r in rows),
    'maximum_wrist_deviation_from_idle_deg':max(r['wrist_rotation_from_idle_deg'] for r in rows),
    'method':'Actual held blade-axis samples beyond inner 25 percent, nearest skinned torso/head/left-arm vertices. A coarse self-clearance diagnostic, not continuous triangle collision proof.',
    'frames_data':rows}
output='CompactAttackRuntimeSkin.json' if runtime else 'CompactAttackSkin.json'
(OUT/output).write_text(json.dumps(report,indent=2),encoding='utf-8');print('COMPACT_ATTACK_SKIN',json.dumps({k:v for k,v in report.items() if k!='frames_data'}),flush=True)
