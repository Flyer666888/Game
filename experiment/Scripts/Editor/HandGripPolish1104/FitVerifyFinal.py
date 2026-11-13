from pathlib import Path
P=Path(r'D:/game design/experiment')
script=(P/'Scripts/Editor/HandGripPolish1104/FitClearance.py').read_text().split('axis=Vector((1,.2,-.25))')[0]
needle="exec(compile(src,__file__,'exec'))"
at=script.rfind(needle)
script=script[:at]+"src=src.replace('ArtSource/Weapons/Yueyao/SlenderBladeRevision/YueyaoPlayerSlender.fbx','ArtSource/Weapons/Yueyao/EnemyGripPolish1104/YueyaoEnemyGrip.fbx')\n"+script[at:]
script=script.replace("('FitClearance'+label+'Report.json')","('FitClearance'+label+'FinalReport.json')")
exec(compile(script,__file__,'exec'))
me=bpy.data.meshes.new('FinalHandMesh');me.from_pydata(coords,[],[[mapping[i] for i in f] for f in faces]);me.update();hand=bpy.data.objects.new('FinalHand',me);bpy.context.collection.objects.link(hand);hand.data.materials.append(skin)
for p in me.polygons:p.use_smooth=True
for view,location in [('Side',(0,.07,.35)),('Oblique',(.3,.3,.25))]:
 cam.location=location;cam.rotation_euler=(Vector((0,.07,.025))-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(O/f'Geometry_Final_{view}.png');bpy.ops.render.render(write_still=True)
