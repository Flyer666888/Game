"""Offline pose review on the actual v04 hand mesh; never saves the blend."""
import json, math
from pathlib import Path
import bpy, numpy as np
from mathutils import Vector, Matrix, Quaternion
P=Path(r'D:/game design/experiment');OUT=P/'Docs/Gameplay/CombatFeel1104/OfflineFrames'
OUT.mkdir(parents=True,exist_ok=True)
setup=P/'Saved/Scripts/bake_selected_death.py'
ctx={'__name__':'motion_review','__file__':str(setup)}
code=setup.read_text(encoding='utf-8').split('raw=[];locals=[];support=[]')[0]
code=code.replace("if grip is None:raise RuntimeError('Actual Combat EnemyGrip_R is required for this authoring preview.')","if grip is None:grip=mesh.data.shape_keys.key_blocks['Basis']")
exec(compile(code,str(setup),'exec'),ctx)
grip=json.loads((P/'Docs/Gameplay/RigPolish_v04/CandidateGrip.json').read_text())
q=grip['quaternion'];attach=Matrix.LocRotScale(Vector(grip['translation']),Quaternion((q[3],*q[:3])),Vector(grip['scale']))
ctx['attach']=attach
mesh=ctx['mesh'];weapon=ctx['weapon'];reflect=ctx['reflect'];skin=ctx['skin'];prop_world=ctx['prop_world']
data=json.loads((P/'Docs/Gameplay/CombatFeel1104/EnemyMotionPoses.json').read_text())
for o in bpy.context.scene.objects:o.hide_render=True
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12
scene.render.resolution_x=800;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.render.use_compositing=False;scene.render.use_sequencer=False
scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
scene.world=bpy.data.worlds.new('MotionReviewWorld');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');wo=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld')
scene.world.node_tree.links.new(bg.outputs[0],wo.inputs['Surface'])
bg.inputs['Color'].default_value=(.08,.10,.13,1);bg.inputs['Strength'].default_value=.6
md=mesh.data.copy();obj=bpy.data.objects.new('ActualEnemyBody',md);scene.collection.objects.link(obj);obj.shape_key_clear()
pd=weapon.data.copy();pd.transform(weapon.matrix_world);prop=bpy.data.objects.new('ActualEnemySword',pd);scene.collection.objects.link(prop)
bpy.ops.mesh.primitive_plane_add(size=10,location=(0,0,-.006));floor=bpy.context.object
material=bpy.data.materials.new('MotionFloor');material.diffuse_color=(.055,.07,.09,1);floor.data.materials.append(material)
bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=2.7
focus=Vector((0,-.25,.9));camera.location=(-2.8,-4,2.4);camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler()
for loc,power in [((-3,-3,5),1100),((4,-1,4),800),((0,4,5),1100)]:
    bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=5;light.rotation_euler=(focus-light.location).to_track_quat('-Z','Y').to_euler()
report=[]
for kind in ('attack','chase'):
    clip=data[kind]
    indices=range(0,len(clip['samples']),3) if kind=='attack' else range(0,len(clip['samples']),2)
    for i in indices:
        sample=clip['samples'][i];points,w=skin(sample['local']);md.vertices.foreach_set('co',(points*.01).ravel());md.update()
        prop.matrix_world=Matrix.Scale(.01,4)@reflect@w['hand_r']@attach@reflect
        scene.render.filepath=str(OUT/f'{kind}_{i:03d}.png');bpy.ops.render.render(write_still=True)
        sword=prop_world(sample['local']);report.append({'kind':kind,'time':sample['time'],'blade_forward_max_cm':float(-sword[:,1].min()),'skin_min_z_cm':float(points[:,2].min())})
(OUT.parent/'OfflineGeometry.json').write_text(json.dumps(report,indent=2))
print('OFFLINE_MOTION_RENDERED')
