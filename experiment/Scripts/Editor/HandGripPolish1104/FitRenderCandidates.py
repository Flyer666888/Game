from pathlib import Path
import json
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/HandGripPolish1104'
variants={'FitB':{'angles':[60,100,75],'y':.048,'z':.046,'sy':.2,'sz':-.25},'FitC':{'angles':[45,120,75],'y':.060,'z':.058,'sy':0,'sz':-.65}}
src=(P/'Scripts/Editor/HandGripPolish1104/GeometryInspect.py').read_text()
src=src.replace("for label,kind,index in [('D','attack',15),('Idle','idle',0)]:", "for label,kind,index in [('FitB','idle',0),('FitC','idle',0)]:")
src=src.replace(" bpy.context.view_layer.update()", "\n for n,a in zip(['RightHandIndex1','RightHandIndex2','RightHandIndex3'],variants[label]['angles']):\n  b=next(b for b in arm.pose.bones if key(b.name)==n);b.rotation_mode='QUATERNION';b.rotation_quaternion=Quaternion((1,0,0),math.radians(a))\n bpy.context.view_layer.update()")
src=src.replace("g=samples['grip'];G=mat(g)","v=variants[label];d=Vector((1,v['sy'],v['sz'])).normalized();dq=Vector((1,0,0)).rotation_difference(d);rq=(H.to_3x3()@dq.to_matrix()@H.to_3x3()@Quaternion((.5,.5,.5,.5)).to_matrix()).to_quaternion();g={'p':[0,-v['y'],v['z']],'q':[rq.x,rq.y,rq.z,rq.w],'s':[.01,.01,.01]};G=mat(g)")
src=src.replace("out['frames'].append(row)","out['frames'].append(row)\n ue_world={key(b.name):(M@H).inverted()@(arm.matrix_world@b.matrix)@rest[key(b.name)].inverted()@(M@H)@ue_ref[key(b.name)] for b in arm.pose.bones}\n bones={}\n for b in arm.pose.bones:\n  n=key(b.name)\n  if n.startswith('RightHand') and n!='RightHand':\n   l=ue_world[key(b.parent.name)].inverted()@ue_world[n];q=l.to_quaternion();bones[n]={'q':[q.x,q.y,q.z,q.w]}\n (O/(label.replace('Fit','FitCandidate')+'.json')).write_text(json.dumps({'grip':g,'bones':bones,'wrist_delta':None,'fit_parameters':v,'status':'offline fitted; pending UE review'},indent=2))")
src=src.replace("GeometryReport.json","FitBCReport.json")
exec(compile(src,__file__,'exec'))
