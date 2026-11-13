from pathlib import Path
import json
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/HandGripPolish1104'
candidate=json.loads((O/'FitCandidateB.json').read_text())
src=(P/'Scripts/Editor/HandGripPolish1104/GeometryInspect.py').read_text()
src=src.replace("for label,kind,index in [('D','attack',15),('Idle','idle',0)]:", "for label,kind,index in [('Final','idle',0)]:")
src=src.replace(" bpy.context.view_layer.update()", "\n for n,a in zip(['RightHandIndex1','RightHandIndex2','RightHandIndex3'],[60,100,75]):\n  b=next(b for b in arm.pose.bones if key(b.name)==n);b.rotation_mode='QUATERNION';b.rotation_quaternion=Quaternion((1,0,0),math.radians(a))\n bpy.context.view_layer.update()")
src=src.replace('ArtSource/Weapons/Yueyao/SlenderBladeRevision/YueyaoPlayerSlender.fbx','ArtSource/Weapons/Yueyao/EnemyGripPolish1104/YueyaoEnemyGrip.fbx')
src=src.replace("g=samples['grip'];G=mat(g)","g=candidate['grip'];G=mat(g)")
src=src.replace("[('Palm',(.35,.07,.03)),('Side',(0,.07,.35)),('Oblique',(.3,.3,.25))]","[('Side',(0,.07,.35)),('Oblique',(.3,.3,.25))]")
src=src.replace("GeometryReport.json","HiltFinalGeometryReport.json").replace("f'Geometry_{label}_{view}.png'","f'Hilt{label}_{view}.png'")
exec(compile(src,__file__,'exec'))
