import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
P=Path(r'D:/game design/experiment');OUT=P/'Docs/Gameplay/SlashRevision1104/OfflineFrames';OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(P/'ArtSource/WuxiaMale/NativeRigV07/Wuxia_Attack_Native_v07.blend'))
scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE');mesh=next(o for o in scene.objects if o.type=='MESH')
texture=P/'ArtSource/WuxiaMale/ProvidedRigV07/ProvidedWalk_Source.fbm/Color_f05e5449-02a3-4819-9cc0-0c1e8c93d000.jpg'
for mat in mesh.data.materials:
    mat.use_nodes=True
    for n in mat.node_tree.nodes:
        if n.type=='TEX_IMAGE' and n.image and n.image.name.startswith('Color'):n.image=bpy.data.images.load(str(texture),check_existing=True)
manifest=json.loads((OUT.parent/'NativeSlashManifest.json').read_text())
old=set(scene.objects);bpy.ops.import_scene.fbx(filepath=str(P/'ArtSource/Weapons/Yueyao/SlenderBladeRevision/YueyaoPlayerSlender.fbx'))
weapon=next(o for o in scene.objects if o not in old and o.type=='MESH');weapon.parent=None
weapon.data.transform(weapon.matrix_world);weapon.matrix_world=Matrix.Identity(4)
points=[v.co for v in weapon.data.vertices];length=max(p.z for p in points)-min(p.z for p in points)
weapon.data.transform(Matrix.Scale(.86/length,4))
material=bpy.data.materials.new('blade');material.diffuse_color=(.12,.55,.65,1);weapon.data.materials.clear();weapon.data.materials.append(material)
scene.render.engine='CYCLES';scene.cycles.samples=8;scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG';scene.render.use_compositing=False;scene.render.use_sequencer=False
scene.world=bpy.data.worlds.new('Review');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.4
bpy.ops.mesh.primitive_plane_add(size=20);floor=bpy.context.object
m=bpy.data.materials.new('ground');m.diffuse_color=(.08,.1,.12,1);floor.data.materials.append(m)
bpy.ops.object.camera_add(location=(4,-5,2.5));cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=2.9
focus=Vector((.1,0,1.1));cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler()
for loc,power in [((3,-4,5),900),((-3,-1,4),500),((0,4,5),800)]:
    bpy.ops.object.light_add(type='AREA',location=loc);l=bpy.context.object;l.data.energy=power;l.data.size=4;l.rotation_euler=(focus-l.location).to_track_quat('-Z','Y').to_euler()
grip=Matrix.LocRotScale(Vector(manifest['grip_translation_m']),Quaternion(manifest['grip_quaternion_wxyz']),Vector((1,1,1)))
for i in (0,29,43,50,60):
    scene.frame_set(i+1);weapon.matrix_world=arm.matrix_world@arm.pose.bones['mixamorig:RightHand'].matrix@grip
    scene.render.filepath=str(OUT/f'Native_{i:03d}.png');bpy.ops.render.render(write_still=True)
print('NATIVE_FRAMES_RENDERED')
