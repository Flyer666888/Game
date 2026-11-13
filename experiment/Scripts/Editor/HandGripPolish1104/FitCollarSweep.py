from pathlib import Path
P=Path(r'D:/game design/experiment')
script=(P/'Scripts/Editor/HandGripPolish1104/FitClearance.py').read_text().split('axis=Vector((1,.2,-.25))')[0]
exec(compile(script,__file__,'exec'))
from mathutils.bvhtree import BVHTree
tree=BVHTree.FromPolygons(coords,[[mapping[i] for i in f] for f in faces],all_triangles=False)
components=json.loads((O/'HiltComponents.json').read_text());collar=next(c for c in components if c['name'].startswith('22 '))
def check(p):
 co,n,i,d=tree.find_nearest(p)
 if (p-co).dot(n)>=0 or d<.0005:return 0
 votes=0
 for dr in [(0,1,0),(.13,1,.17),(-.19,1,.12),(.11,1,-.23),(-.21,1,-.18)]:
  direction=Vector(dr).normalized();origin=p.copy();count=0
  for rep in range(40):
   co,n,i,dist=tree.ray_cast(origin,direction,.5)
   if co is None:break
   count+=1;origin=co+direction*.000001
  votes+=count%2
 return float(d) if votes>=4 else 0
rows=[]
for scale in [1,.8]:
 for shift in [0,.005,.01,.015,.02,.025,.03]:
  depths=[]
  for xyz in collar['vertices']:
   v=Vector((xyz[0]*scale*100,xyz[1]*scale*100,(xyz[2]+shift)*100));depths.append(check(weapon.matrix_world@v))
  rows.append({'scale_xy':scale,'shift_z_m':shift,'inside_vertices':sum(d>0 for d in depths),'max_depth_m':max(depths)})
(O/'FitCollarSweepReport.json').write_text(json.dumps({'component':collar['name'],'vertices':len(collar['vertices']),'variants':rows},indent=2));print('COLLAR_SWEEP',json.dumps(rows))
