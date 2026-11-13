"""Offline diagnostic fit for the native hand and existing sword."""
import sys,math,json,bpy
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
P=Path(r'D:/game design/experiment');sys.path.insert(0,str(P/'Scripts/Editor/SlashRevision1104'))
from new_rig_common import load_rig
arm,body,_,meta=load_rig();out=P/'Docs/Gameplay/SlashRevision1104/Grip';out.mkdir(parents=True,exist_ok=True)
angles={'RightHandIndex1':75,'RightHandIndex2':142.5,'RightHandIndex3':-12.7,
        'RightHandThumb1':35,'RightHandThumb2':40,'RightHandThumb3':35}
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
if args:angles.update(json.loads(args[0]))
for name,angle in angles.items():
    b=arm.pose.bones['mixamorig:'+name];b.rotation_mode='QUATERNION';b.rotation_quaternion=Quaternion((1,0,0),math.radians(angle))
bpy.context.view_layer.update()
hand=arm.pose.bones['mixamorig:RightHand'];H=hand.matrix.copy();inv=H.inverted()
dep=bpy.context.evaluated_depsgraph_get();ev=body.evaluated_get(dep);evaluated=ev.to_mesh()
groups={g.index:g.name for g in body.vertex_groups}
keep={v.index for v in body.data.vertices if sum(g.weight for g in v.groups if 'RightHand' in groups[g.group])>.20}
faces=[list(p.vertices) for p in body.data.polygons if all(i in keep for i in p.vertices)]
ids=sorted(set(i for f in faces for i in f));mapping={i:n for n,i in enumerate(ids)}
me=bpy.data.meshes.new('DiagnosticHand');me.from_pydata([inv@body.matrix_world@evaluated.vertices[i].co for i in ids],[],[[mapping[i] for i in f] for f in faces]);me.update()
ev.to_mesh_clear();ob=bpy.data.objects.new('DiagnosticHand',me);bpy.context.collection.objects.link(ob);body.hide_render=True;arm.hide_render=True
m=bpy.data.materials.new('HandSkin');m.diffuse_color=(.55,.35,.21,1);m.use_nodes=True;m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.55,.35,.21,1);ob.data.materials.append(m)
for p in me.polygons:p.use_smooth=True
existing=set(bpy.data.objects);bpy.ops.import_scene.fbx(filepath=str(P/'ArtSource/Weapons/Yueyao/SlenderBladeRevision/YueyaoPlayerSlender.fbx'))
weapon=next(o for o in bpy.data.objects if o not in existing and o.type=='MESH')
R=Matrix(((0,0,1),( -1,0,0),(0,-1,0))).to_4x4();R.translation=Vector((0,.065,.035))
weapon.matrix_world=R@weapon.matrix_world
weapon.hide_render=True
bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.009,depth=.14,location=R.translation,rotation=(0,math.pi/2,0));handle=bpy.context.object
hm=bpy.data.materials.new('HandleFit');hm.diffuse_color=(.08,.15,.2,1);hm.use_nodes=True;hm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.08,.15,.2,1);handle.data.materials.append(hm)
# Mark exact handle axis (red) for silhouette review.
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.world=bpy.data.worlds.new('GripReviewWorld');scene.world.color=(.3,.3,.3)
scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
for location,power,size in [((.3,.3,.5),3,.5),((-.3,.1,.2),2,.3)]:
    bpy.ops.object.light_add(type='AREA',location=location);l=bpy.context.object;l.data.energy=power;l.data.shape='DISK';l.data.size=size;l.rotation_euler=(Vector((0,.07,.02))-l.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=.25;scene.camera=cam
for label,location in [('side',(0.4,.07,.03)),('top',(0,.07,.5)),('oblique',(.3,.3,.3))]:
    cam.location=Vector(location);cam.rotation_euler=(Vector((0,.07,.03))-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/(label+'.png'));bpy.ops.render.render(write_still=True)
pose={b.name: {'head_local_cm':list((inv@b.head)*100),'tail_local_cm':list((inv@b.tail)*100)} for b in arm.pose.bones if 'RightHand' in b.name}
(out/'Candidate.json').write_text(json.dumps({'angles':angles,'socket_cm':list(R.translation*100),'quaternion_xyzw':list(R.to_quaternion())[1:]+[R.to_quaternion().w],'pose':pose},indent=2))
print('GRIP_CANDIDATE',json.dumps({'angles':angles,'pose':pose}))
