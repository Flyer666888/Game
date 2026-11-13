"""Actual Combat-skin + still-held sword authoring comparison. No gameplay."""
from pathlib import Path
import json
import bpy
from mathutils import Matrix,Vector
PROJECT=Path(__file__).resolve().parents[2]
# Reuse the exact contact measurement pipeline, stopping before any authoring.
setup=(PROJECT/'Saved/Scripts/bake_selected_death.py').read_text(encoding='utf-8').split('raw=[];locals=[];support=[]')[0]
exec(compile(setup,'selected_death_preview_setup','exec'),globals())
after=json.loads((OUT/'OptimizedDeathPoses.json').read_text(encoding='utf-8'))
for obj in bpy.context.scene.objects:obj.hide_render=True
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1000;scene.render.resolution_y=850
scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
scene.render.film_transparent=False;scene.render.use_compositing=False;scene.render.use_sequencer=False
scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
scene.world=bpy.data.worlds.new('SelectedDeathPreviewWorld');scene.world.use_nodes=True
background=scene.world.node_tree.nodes.get('Background') or scene.world.node_tree.nodes.new('ShaderNodeBackground')
out_world=next((node for node in scene.world.node_tree.nodes if node.type=='OUTPUT_WORLD'),None) or scene.world.node_tree.nodes.new('ShaderNodeOutputWorld')
scene.world.node_tree.links.new(background.outputs['Background'],out_world.inputs['Surface'])
background.inputs['Color'].default_value=(.22,.22,.22,1.);background.inputs['Strength'].default_value=.6
pose_data=mesh.data.copy();pose_obj=bpy.data.objects.new('SelectedDeathPreviewBody',pose_data);scene.collection.objects.link(pose_obj)
if pose_obj.data.shape_keys:pose_obj.shape_key_clear()
prop_data=weapon.data.copy();prop_data.transform(weapon.matrix_world)
prop_obj=bpy.data.objects.new('SelectedDeathPreviewHeldSword',prop_data);scene.collection.objects.link(prop_obj)
bpy.ops.mesh.primitive_plane_add(size=20.,location=(0,0,-.015));floor=bpy.context.object
floor_mat=bpy.data.materials.new('SelectedDeathFloor');floor_mat.use_nodes=True
shader=floor_mat.node_tree.nodes.get('Principled BSDF') or floor_mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
mat_output=next((node for node in floor_mat.node_tree.nodes if node.type=='OUTPUT_MATERIAL'),None) or floor_mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
floor_mat.node_tree.links.new(shader.outputs['BSDF'],mat_output.inputs['Surface'])
shader.inputs['Base Color'].default_value=(.22,.22,.22,1.);shader.inputs['Roughness'].default_value=.9;floor.data.materials.append(floor_mat)
bpy.ops.object.camera_add(location=(2.2,-5.,2.3));camera=bpy.context.object;scene.camera=camera
focus=Vector((.05,-.60,.78));camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=3.8
for loc,power in [((-3,-3,5),1100),((4,-1,4),900),((0,4,5),1100)]:
 bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=5
 light.rotation_euler=(focus-light.location).to_track_quat('-Z','Y').to_euler()
for label,data in [('Before',before),('After',after)]:
 folder=OUT/(label+'Frames');folder.mkdir(parents=True,exist_ok=True)
 for frame,sample in enumerate(data['clips'][0]['samples'][::3]):
  posed,w=skin(sample['local'],sample.get('morph_weights',{}))
  pose_data.vertices.foreach_set('co',(posed*.01).ravel());pose_data.update()
  prop_obj.matrix_world=Matrix.Scale(.01,4)@reflect@w['hand_r']@attach@reflect
  scene.render.filepath=str(folder/('frame_%03d.png'%frame));bpy.ops.render.render(write_still=True)
 print('SELECTED_DEATH_COMPARISON_RENDERED',label,frame+1,str(folder),flush=True)
