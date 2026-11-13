from pathlib import Path
import json
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/HandGripPolish1104'
src=(P/'Scripts/Editor/HandGripPolish1104/GeometryInspect.py').read_text()
src=src.replace("for label,kind,index in [('D','attack',15),('Idle','idle',0)]:", "for label,kind,index in [('FitA','idle',0)]:")
src=src.replace("g=samples['grip'];G=mat(g)","g={'p':[0,-.065,.035],'q':[.5,.5,.5,.5],'s':[.01,.01,.01]};G=mat(g)")
src=src.replace("GeometryReport.json","FitAReport.json")
exec(compile(src,__file__,'exec'))
candidate={'grip':{'p':[0,-.065,.035],'q':[.5,.5,.5,.5],'s':[.01,.01,.01]},'bones':{k:{'q':v['q']} for k,v in samples['clips']['idle']['frames'][0]['local'].items() if k.startswith('RightHand') and k!='RightHand'},'wrist_delta':None,'status':'first physical candidate; pending geometry review'}
(O/'FitCandidateA.json').write_text(json.dumps(candidate,indent=2))
