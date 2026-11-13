"""Read-only bind-grip closeup used to separate morph defects from pose defects."""
from pathlib import Path
P=Path(r'D:\game design\experiment')
exec(compile((P/'Scripts/Editor/RigPolishV04/audit_hands_blender.py').read_text(encoding='utf-8').split('rows=[]')[0], 'audit_hand_setup','exec'))
localref={b:record(context['mat'](reference[par]).inverted()@context['mat'](reference[b])) if par else reference[b] for b,par in context['PARENTS'].items()}
print('VERTEX_DETAIL',json.dumps([{'i':i,'basis':list(basis[i,:3]),'grip':list(coords[i,:3]),'weights':weights[i]} for i in (968,971,910,913,116,117,903,904)]),flush=True)
for obj in bpy.context.scene.objects:obj.hide_render=True
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1100;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.render.use_compositing=False;scene.render.use_sequencer=False
scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0.;scene.view_settings.gamma=1.
scene.world=bpy.data.worlds.new('HandNeutralWorld');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');output=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(bg.outputs[0],output.inputs['Surface']);bg.inputs['Color'].default_value=(.055,.055,.055,1);bg.inputs['Strength'].default_value=.65
md=mesh.data.copy();obj=bpy.data.objects.new('HandNeutralBody',md);scene.collection.objects.link(obj);obj.shape_key_clear()
pd=weapon.data.copy();pd.transform(weapon.matrix_world);prop_obj=bpy.data.objects.new('HandNeutralSword',pd);scene.collection.objects.link(prop_obj)
bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=.37
for loc,power in [((-3,-3,5),900),((4,-1,4),650),((0,4,5),900)]:
    bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=5
for label,points in [('NeutralGrip',coords[:,:3]),('NeutralOpen',basis[:,:3])]:
    md.vertices.foreach_set('co',(points*.01).ravel());md.update()
    prop_obj.matrix_world=Matrix.Scale(.01,4)@reflect@context['mat'](reference['hand_r'])@attach@reflect
    focus=Vector(coords[side_data['r']['ids'],:3].mean(axis=0)*.01)
    for view,offset in [('Front',Vector((-1.,-3.,.8))),('Side',Vector((3.,0.,.25))),('Palm',Vector((-.2,3.,.1)))]:
        camera.location=focus+offset;camera.rotation_euler=(-offset).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/(label+'_'+view+'.png'));bpy.ops.render.render(write_still=True)
print('NEUTRAL_GRIP_RENDER_DONE',flush=True)
