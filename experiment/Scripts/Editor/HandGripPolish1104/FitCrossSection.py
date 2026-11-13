from pathlib import Path
P=Path(r'D:/game design/experiment')
src=(P/'Scripts/Editor/HandGripPolish1104/GeometryInspect.py').read_text()
src=src.replace("for label,kind,index in [('D','attack',15),('Idle','idle',0)]:", "for label,kind,index in [('FitA','idle',0)]:")
src=src.replace("g=samples['grip'];G=mat(g)","g={'p':[0,-.065,.035],'q':[.5,.5,.5,.5],'s':[.01,.01,.01]};G=mat(g)")
src=src.replace("scene.render.filepath=str(O/f'Geometry_{label}_{view}.png');bpy.ops.render.render(write_still=True)","pass")
src=src.replace("out['frames'].append(row)","out['frames'].append(row)\n (O/'FitCrossSection.json').write_text(json.dumps({'vertices':[list(v) for v in coords],'faces':[[mapping[i] for i in f] for f in faces],'sword_vertices':[list(v.co) for v in weapon.data.vertices],'sword_faces':[list(p.vertices) for p in weapon.data.polygons],'basis':{key(b.name):list(b.rotation_quaternion) for b in arm.pose.bones if 'RightHand' in b.name}}))")
src=src.replace("GeometryReport.json","FitCrossSectionReport.json")
exec(compile(src,__file__,'exec'))
