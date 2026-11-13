import sys,json
sys.path.insert(0,r'D:/game design/experiment/Scripts/Editor/SlashRevision1104')
import new_rig_common as c
from mathutils import Matrix,Vector
arm,mesh,walk,meta=c.load_rig()
g=json.loads((c.DOC/'NativeGuard.json').read_text())
world={b:Matrix(m) for b,m in g['world'].items()}
for label,w in [('guard',world),('walk0',walk[0]['world']),('walk16',walk[16]['world']),('walk31',walk[31]['world'])]:
 print(label,'hips',list(w['mixamorig:Hips'].translation),'shoulders',list(w['mixamorig:LeftArm'].translation-w['mixamorig:RightArm'].translation))
 for side in ['Left','Right']:
  print(side,'foot',list(w['mixamorig:'+side+'Foot'].translation),'toe',list(w['mixamorig:'+side+'ToeBase'].translation))
