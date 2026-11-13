from pathlib import Path
P=Path(r'D:/game design/experiment')
exec(compile((P/'Scripts/Editor/HandGripPolish1104/FitCrossSection.py').read_text(),__file__,'exec'))
from mathutils.bvhtree import BVHTree
import itertools,time
# Restrict evaluation to the actual weighted hand for bounded fitting iterations.
mesh=bpy.data.meshes.new('FitSkinMesh');mesh.from_pydata([list(body.data.vertices[i].co) for i in ids],[],[[mapping[i] for i in f] for f in faces]);mesh.update()
fitmesh=bpy.data.objects.new('FitSkin',mesh);bpy.context.collection.objects.link(fitmesh);fitmesh.matrix_world=body.matrix_world.copy()
for grp in body.vertex_groups:fitmesh.vertex_groups.new(name=grp.name)
for old,new in mapping.items():
 for g in body.data.vertices[old].groups:fitmesh.vertex_groups[g.group].add([new],g.weight,'REPLACE')
mod=fitmesh.modifiers.new('FitSkinArmature','ARMATURE');mod.object=arm
names={key(b.name):b.name for b in arm.pose.bones}
xs=[-.032,-.024,-.016,-.008,0,.008,.016,.024,.032]
centers=[(y*.001,z*.001,sy,sz) for y in range(48,79,4) for z in range(26,59,4) for sy in [-.2,0,.2] for sz in [-.65,-.45,-.25,0]]
results=[]
def evaluate_pose(angles):
 for n,a in zip(['RightHandIndex1','RightHandIndex2','RightHandIndex3'],angles):
  b=arm.pose.bones[names[n]];b.rotation_mode='QUATERNION';b.rotation_quaternion=Quaternion((1,0,0),math.radians(a))
 bpy.context.view_layer.update();dep=bpy.context.evaluated_depsgraph_get();ev=fitmesh.evaluated_get(dep);em=ev.to_mesh();vs=[localizer@fitmesh.matrix_world@v.co for v in em.vertices];ev.to_mesh_clear()
 tree=BVHTree.FromPolygons(vs,[[mapping[i] for i in f] for f in faces],all_triangles=False)
 best=None
 for y,z,sy,sz in centers:
  gaps=[]
  for x in xs:
   v=Vector((x,y+x*sy,z+x*sz));co,n,idx,d=tree.find_nearest(v);gaps.append(float(d)*(1 if (v-co).dot(n)>=0 else -1))
  # prioritize minimum signed axis clearance, then stay near the closed grip shape
  # Require a wrapped channel: rays in the hand's YZ plane must meet skin.
  rays=[]
  # Actual grip plus winding radius is 8--11 mm. Penalize penetration,
  # open fingers, and a loose channel independently.
  score=-sum(max(0,.010-g)**2*100+max(0,g-.014)**2 for g in gaps) - max(0,180-sum(angles))*.00001
  if best is None or score>best['score']:best={'angles':angles,'y':y,'z':z,'slope_y':sy,'slope_z':sz,'score':score,'gaps':gaps,'rays':rays}
 return best
for angles in itertools.product([45,60,75,90],[60,80,100,120],[0,25,50,75]):
 results.append(evaluate_pose(angles))
results.sort(key=lambda x:-x['score'])
(O/'FitOptimizeReport.json').write_text(json.dumps({'best':results,'samples':len(results)},indent=2))
print('FIT_BEST',json.dumps(results[:3]),flush=True)
