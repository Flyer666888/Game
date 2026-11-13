import bpy,json,math,sys
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/HandGripPolish1104'
samples=json.loads((O/'PoseSamples.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(P/'ArtSource/WuxiaMale/NativeRigV07/NativeMesh.fbx'),automatic_bone_orientation=False,use_anim=False,ignore_leaf_bones=False)
arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
body=next(o for o in bpy.context.scene.objects if o.type=='MESH')
arm.animation_data_clear()
def key(b):return b.split(':')[-1]
def mat(t):return Matrix.LocRotScale(Vector(t['p']),Quaternion((t['q'][3],*t['q'][:3])),Vector(t['s']))
H=Matrix.Diagonal((1,-1,1,1));CM=Matrix.Scale(100,4);M=Matrix.Scale(.01,4)
ref=samples['reference']
if 'world' in ref:ref=ref['world']
rest={key(b.name):arm.matrix_world@b.matrix_local for b in arm.data.bones}
ue_ref={n:mat(t) for n,t in ref.items()}
groups={g.index:g.name for g in body.vertex_groups}
keep={v.index for v in body.data.vertices if sum(g.weight for g in v.groups if 'RightHand' in groups[g.group])>.15}
faces=[list(p.vertices) for p in body.data.polygons if all(i in keep for i in p.vertices)]
ids=sorted(set(i for f in faces for i in f));mapping={i:n for n,i in enumerate(ids)}
existing=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(P/'ArtSource/Weapons/Yueyao/SlenderBladeRevision/YueyaoPlayerSlender.fbx'))
weapon=next(o for o in bpy.data.objects if o not in existing and o.type=='MESH')
weapon_original=weapon.matrix_world.copy()
weapon.name='DiagnosticActualSword'
body.hide_render=True;arm.hide_render=True
def material(name,color,rough=.7):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough
 return m
skin=material('DiagnosticSkin',(.54,.32,.19));metal=material('DiagnosticSword',(.12,.24,.27),.35)
weapon.data.materials.clear();weapon.data.materials.append(metal)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=20
scene.world=bpy.data.worlds.new('DiagnosticWorld');scene.world.color=(.25,.25,.25)
scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
for pos,power in [((.3,.3,.4),4),((-.3,.05,.25),3),((.05,-.3,.2),2)]:
 bpy.ops.object.light_add(type='AREA',location=pos);l=bpy.context.object;l.data.energy=power;l.data.size=.4
 l.rotation_euler=(Vector((0,.05,0))-l.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=.24;scene.camera=cam
out={'body_vertices':len(body.data.vertices),'hand_vertices':len(ids),'arm_matrix':list(map(list,arm.matrix_world)),'hand_rest_matrix':list(map(list,rest['RightHand'])),'frames':[]}
for label,kind,index in [('D','attack',15),('Idle','idle',0)]:
 frame=samples['clips'][kind]['frames'][index]
 world={n:M@H@mat(t)@ue_ref[n].inverted()@CM@H@rest[n] for n,t in frame['world'].items()}
 for b in arm.pose.bones:
  name=key(b.name);desired=arm.matrix_world.inverted()@world[name];bone_rest=b.bone.matrix_local
  if b.parent:
   bone_rest=b.parent.bone.matrix_local.inverted()@bone_rest
   desired=world[key(b.parent.name)].inverted()@world[name]
  b.matrix_basis=bone_rest.inverted()@desired
 bpy.context.view_layer.update()
 bh=arm.matrix_world@arm.pose.bones[next(b.name for b in arm.pose.bones if key(b.name)=='RightHand')].matrix
 # Use a unit-scale local hand frame so camera and garment dimensions are meters.
 p,q,s=bh.decompose();localizer=Matrix.LocRotScale(p,q,Vector((1,1,1))).inverted()
 dep=bpy.context.evaluated_depsgraph_get();ev=body.evaluated_get(dep);me_eval=ev.to_mesh()
 coords=[localizer@body.matrix_world@me_eval.vertices[i].co for i in ids]
 me=bpy.data.meshes.new('DiagnosticHandMesh');me.from_pydata(coords,[],[[mapping[i] for i in f] for f in faces]);me.update()
 ev.to_mesh_clear();hand=bpy.data.objects.new('DiagnosticHand',me);bpy.context.collection.objects.link(hand);hand.data.materials.append(skin)
 for polygon in me.polygons:polygon.use_smooth=True
 g=samples['grip'];G=mat(g)
 weapon.matrix_world=localizer@M@H@mat(frame['world']['RightHand'])@G@CM@H@weapon_original
 row={'kind':kind,'index':index,'t':frame['t'],'local_bounds':[[min(v[j] for v in coords),max(v[j] for v in coords)] for j in range(3)],'weapon_matrix':list(map(list,weapon.matrix_world)),
      'bones':{key(b.name):{'head':list(localizer@arm.matrix_world@b.head),'tail':list(localizer@arm.matrix_world@b.tail)} for b in arm.pose.bones if 'RightHand' in b.name}}
 for view,location in [('Palm',(.35,.07,.03)),('Side',(0,.07,.35)),('Oblique',(.3,.3,.25))]:
  cam.location=location;cam.rotation_euler=(Vector((0,.07,.025))-cam.location).to_track_quat('-Z','Y').to_euler()
  scene.render.filepath=str(O/f'Geometry_{label}_{view}.png');bpy.ops.render.render(write_still=True)
 out['frames'].append(row)
 bpy.data.objects.remove(hand,do_unlink=True)
(O/'GeometryReport.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
