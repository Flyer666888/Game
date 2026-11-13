from pathlib import Path
import json
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/HandGripPolish1104'
candidate=json.loads((O/'FitCandidateB.json').read_text())
src=(P/'Scripts/Editor/HandGripPolish1104/GeometryInspect.py').read_text()
src=src.replace("for label,kind,index in [('D','attack',15),('Idle','idle',0)]:", "for label,kind,index in [('HiltB','idle',0)]:")
src=src.replace(" bpy.context.view_layer.update()", "\n for n,a in zip(['RightHandIndex1','RightHandIndex2','RightHandIndex3'],[60,100,75]):\n  b=next(b for b in arm.pose.bones if key(b.name)==n);b.rotation_mode='QUATERNION';b.rotation_quaternion=Quaternion((1,0,0),math.radians(a))\n bpy.context.view_layer.update()")
src=src.replace("g=samples['grip'];G=mat(g)","g=candidate['grip'];G=mat(g)")
src=src.replace("scene.render.filepath=str(O/f'Geometry_{label}_{view}.png');bpy.ops.render.render(write_still=True)","pass")
src=src.replace("GeometryReport.json","HiltHandReport.json")
exec(compile(src,__file__,'exec'))
from mathutils.bvhtree import BVHTree
tree=BVHTree.FromPolygons(coords,[[mapping[i] for i in f] for f in faces],all_triangles=False)
comps=json.loads((O/'HiltComponents.json').read_text());wire=next(c for c in comps if c['name'].startswith('29 '))
verts=[Vector(v) for v in wire['vertices']]
def weight(z):
 t=max(0.,min(1.,(.083-z)/.045));return t*t*(3-2*t)
shaft=weapon.matrix_world.to_3x3()@Vector((0,0,1));shaft.normalize()
def distance(v,slide):
 p=weapon.matrix_world@(v*100)+shaft*slide;co,n,idx,d=tree.find_nearest(p);return float(d)*(1 if (p-co).dot(n)>=0 else -1)
trials=[]
for step in range(41):
 amount=step*.001
 ds=[distance(v-Vector((amount*weight(v.z),0,0)),slide) for v in verts for slide in [0,.01]]
 trials.append({'outward_cm':amount*100,'min_clearance_mm':min(ds)*1000,'inside_vertex_count':sum(d<0 for d in ds),'vertex_count':len(ds)})
chosen=next(t for t in trials if t['min_clearance_mm']>=10.)
report={'candidate':'FitB plus 1cm axial slide toward blade tip','component':wire['name'],'original':trials[0],'chosen':chosen,'trials':trials,
 'formula':'weapon_local_x -= amount*smoothstep(clamp((0.083-weapon_local_z)/0.045,0,1)); meters; z>=8.3cm anchor unchanged',
 'hand_mesh':{'vertices':[list(v) for v in coords],'faces':[[mapping[i] for i in f] for f in faces]},'weapon_matrix':list(map(list,weapon.matrix_world))}
(O/'HiltSweepFit.json').write_text(json.dumps(report),encoding='utf-8')
print('HILT_FIT',json.dumps({k:v for k,v in report.items() if k not in ['hand_mesh','trials']}))
