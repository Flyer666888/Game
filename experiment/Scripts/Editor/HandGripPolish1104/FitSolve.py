import bpy,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/HandGripPolish1104'
d=json.loads((O/'FitCrossSection.json').read_text())
bvh=BVHTree.FromPolygons([Vector(v) for v in d['vertices']],d['faces'],all_triangles=False)
def gap(p):
 co,n,idx,dist=bvh.find_nearest(Vector(p));return float(dist)*(1 if (Vector(p)-co).dot(n)>=0 else -1)
xs=[-.035,-.025,-.015,-.005,.005,.015,.025,.035]
rows=[]
for yi in range(48,78):
 for zi in range(20,51):
  y,z=yi*.001,zi*.001;g=[gap((x,y,z)) for x in xs];rows.append({'y':y,'z':z,'min':min(g),'gaps':g})
rows.sort(key=lambda r:-r['min'])
result={'original':{'y':.065,'z':.035,'gaps':[gap((x,.065,.035)) for x in xs]},'best':rows[:15],'shaft_samples':xs,'sword_bounds':[[min(v[i] for v in d['sword_vertices']),max(v[i] for v in d['sword_vertices'])] for i in range(3)],'basis':d['basis']}
(O/'FitSolveReport.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
