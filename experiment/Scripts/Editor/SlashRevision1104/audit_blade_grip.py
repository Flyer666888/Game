"""Read-only source inspection; no mesh, rig or game assets are modified."""
import bpy,json,math
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
P=Path(r'D:/game design/experiment');OUT=P/'Docs/Gameplay/SlashRevision1104';OUT.mkdir(parents=True,exist_ok=True)
def vec(v):return [round(float(x),6) for x in v]
def mat(v):return Matrix.LocRotScale(Vector(v['p']),Quaternion((v['q'][3],*v['q'][:3])),Vector(v['s']))
data=json.loads((P/'Docs/Gameplay/CombatFeel1104/EnemyMotionPoses.json').read_text())
grip=json.loads((P/'Docs/Gameplay/RigPolish_v04/CandidateGrip.json').read_text())
attach=Matrix.LocRotScale(Vector(grip['translation']),Quaternion((grip['quaternion'][3],*grip['quaternion'][:3])),Vector(grip['scale']))
rows=[]
samples=data['attack']['samples']
for i,s in enumerate(samples[1:-1],1):
    t=s['time'];pose=mat(s['world']['hand_r'])@attach
    before=mat(samples[i-1]['world']['hand_r'])@attach;after=mat(samples[i+1]['world']['hand_r'])@attach
    mid=Vector((0.7,0,39));v=(after@mid-before@mid)/(samples[i+1]['time']-samples[i-1]['time'])
    axis=(pose.to_3x3()@Vector((0,0,1))).normalized();edge=(pose.to_3x3()@Vector((-1,0,0))).normalized()
    cutting=v-axis*v.dot(axis)
    rows.append({'time':t,'blade_middle_speed_cm_s':v.length,'edge_dot_crossblade_velocity':edge.dot(cutting.normalized()),'edge':vec(edge),'crossblade_velocity':vec(cutting),'tip':vec(pose@Vector((4.3,0,70.972)))})
contact=[r for r in rows if .6<=r['time']<=.83334]
report={'v06':{'contact':contact,'edge_dot_range':[min(r['edge_dot_crossblade_velocity'] for r in contact),max(r['edge_dot_crossblade_velocity'] for r in contact)]}}
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r'C:/Users/21475/Desktop/Game model/古代男青年走路动画.fbx',automatic_bone_orientation=False,use_anim=False)
arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
world_points=[mesh.matrix_world@v.co for v in mesh.data.vertices];zmin=min(v.z for v in world_points);zmax=max(v.z for v in world_points);scale_cm=180/(zmax-zmin)
hand=arm.data.bones['mixamorig:RightHand'];hworld=arm.matrix_world@hand.matrix_local
hand_points={b.name:vec((hworld.inverted()@arm.matrix_world@b.head_local)*scale_cm) for b in arm.data.bones if 'RightHand' in b.name or 'RightForeArm' in b.name}
groups={g.index:g.name for g in mesh.vertex_groups}
weighted=[]
for v in mesh.data.vertices:
    w=sum(g.weight for g in v.groups if 'RightHand' in groups[g.group])
    if w>.5:weighted.append(vec((hworld.inverted()@mesh.matrix_world@v.co)*scale_cm))
report['native']={'standing_height_source_units':zmax-zmin,'normalized_scale_to_cm':scale_cm,'hand_local_points_cm':hand_points,'hand_local_bounds_cm':[[min(p[a] for p in weighted),max(p[a] for p in weighted)] for a in range(3)],'hand_world_matrix':[list(row) for row in hworld]}
(OUT/'BladeGripAudit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
