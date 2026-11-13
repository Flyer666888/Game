import json
from pathlib import Path
import unreal
q=unreal.Quat(.8239123225,-.525321424,-.167013094,.131577238)
t=unreal.Transform()
result={'quat_methods':[n for n in dir(q) if 'rotat' in n.lower()]}
try:
    t.rotation=q
    t.translation=unreal.Vector(.504277,-8.22116,.144474)
    result['field_assignment']=True
except Exception as exc:result['field_assignment']=str(exc)
try:
    result['rotator']=str(q.rotator())
except Exception as exc:result['rotator']=str(exc)
Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v04\TransformProbe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
