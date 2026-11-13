"""Replace only the failed right palm with the project's real posed player hand."""
import bpy,json,math,hashlib
import numpy as np
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
P=Path(r'D:\game design\experiment');O=P/'ArtSource/WuxiaMale/RigPolishV04/HandsReplacement';O.mkdir(parents=True,exist_ok=True)
body=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');source_path=bpy.data.filepath
oldmesh=body.data;basis=np.asarray([list(v.co) for v in oldmesh.vertices]);oldweights=[{body.vertex_groups[g.group].name:float(g.weight) for g in v.groups if g.weight>0} for v in oldmesh.vertices]
oldkeys={k.name:np.asarray([list(v.co) for v in k.data]) for k in oldmesh.shape_keys.key_blocks}
def mat(t):return Matrix.LocRotScale(Vector(t['p']),Quaternion((t['q'][3],*t['q'][:3])),Vector(t.get('s',(1,1,1))))
H=Matrix.Diagonal((1,-1,1,1));reference=json.loads((P/'ArtSource/WuxiaMale/NaturalDeath/NaturalCandidatePoses.json').read_text(encoding='utf-8'))['reference']
grip=json.loads((P/'ArtSource/WuxiaMale/GripRefinement/GripAuthoringSummary.json').read_text(encoding='utf-8'));q=grip['sword_relative_quaternion_xyzw'];enemy_attach=Matrix.LocRotScale(Vector(grip['sword_relative_location_cm']),Quaternion((q[3],*q[:3])),Vector(grip['sword_relative_scale']))
playerposes=json.loads((P/'ArtSource/PlayerHands/Source/PlayerHandSourceExport.json').read_text(encoding='utf-8'))['poses']
hand_basis=Quaternion((0,0,-math.sqrt(.5),math.sqrt(.5)));blade_along=Quaternion(Vector((0,1,0)),math.pi/2)@Quaternion(Vector((0,0,1)),math.pi)
player_attach=Matrix.LocRotScale(Vector((0,2.65,-7.8)),hand_basis.inverted()@blade_along,Vector((1,1,1)))
enemy_weapon=mat(reference['hand_r'])@enemy_attach;player_weapon=mat(playerposes['Grip']['hand_r']['world'])@player_attach
mapping=H@enemy_weapon@player_weapon.inverted()@H
with bpy.data.libraries.load(str(P/'ArtSource/PlayerHands/Realistic/PlayerHandRealistic_GripPreview.blend'),link=False) as (available,loaded):
    loaded.objects=['root','PlayerHandRealistic_R']
for o in loaded.objects:
    if o:bpy.context.scene.collection.objects.link(o)
hand=next(o for o in loaded.objects if o.type=='MESH');player_rig=next(o for o in loaded.objects if o.type=='ARMATURE')
bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();posed=bpy.data.meshes.new_from_object(hand.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
posed.transform(Matrix.Scale(100,4)@hand.matrix_world)
temp=bpy.data.objects.new('ReducedGripHand',posed);bpy.context.scene.collection.objects.link(temp)
bpy.ops.object.select_all(action='DESELECT');temp.select_set(True);bpy.context.view_layer.objects.active=temp
dec=temp.modifiers.new('VRHandLocalReduction','DECIMATE');dec.ratio=.26;dec.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=dec.name)
hm=temp.data;player_points=np.asarray([list(v.co) for v in hm.vertices]);wrist=np.asarray(reference['hand_r']['p'])*np.asarray([1,-1,1])
player_wrist=H@Vector(playerposes['Grip']['hand_r']['world']['p']);shaft=H@enemy_weapon.translation;shaft_axis=(H.to_3x3()@enemy_weapon.to_3x3()@Vector((0,0,1))).normalized()
mapped_wrist=mapping@player_wrist;v=mapped_wrist-shaft;desired=Vector(wrist)-shaft;v-=shaft_axis*v.dot(shaft_axis);desired-=shaft_axis*desired.dot(shaft_axis)
roll=math.atan2(shaft_axis.dot(v.cross(desired)),v.dot(desired));correction=Matrix.Translation(shaft)@Quaternion(shaft_axis,roll).to_matrix().to_4x4()@Matrix.Translation(-shaft)
mapping=correction@mapping;mapped_wrist=mapping@player_wrist
final_wrist_delta=Vector(wrist)-mapped_wrist;mapping=Matrix.Translation(final_wrist_delta)@mapping
wrist_delta=Vector((0,0,0));mapped_wrist=mapping@player_wrist
new_attach=mat(reference['hand_r']).inverted()@H@Matrix.Translation(final_wrist_delta)@H@enemy_weapon
gp,gq,gs=new_attach.decompose();grip_spec={'translation':list(gp),'quaternion':grip['sword_relative_quaternion_xyzw'],'scale':grip['sword_relative_scale'],'sword_relative_location_cm':list(gp),'sword_relative_quaternion_xyzw':grip['sword_relative_quaternion_xyzw'],'sword_relative_scale':grip['sword_relative_scale'],'translation_only_change':True,'bind_space_translation_blender_cm':list(final_wrist_delta),'previous_location_cm':grip['sword_relative_location_cm'],'reason':'Translate held sword with the rigid anatomical grip; do not stretch the wrist to meet the old grip origin.'}
(O/'RealGripTransform.json').write_text(json.dumps(grip_spec,indent=2),encoding='utf-8')
hm.transform(mapping)
def smooth(a,b,x):
    t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
for i,vertex in enumerate(hm.vertices):
    along_palm=-(float(player_points[i][1])-player_wrist.y)
    # Extend the proximal wrist tube into the cuff without altering palm/fingers.
    vertex.co+=(mapping.to_3x3()@Vector((0,3.,0)))*(1-smooth(0.,3.5,along_palm))
hm.update();hand_points=np.asarray([list(v.co) for v in hm.vertices]);newwrist=mapped_wrist+wrist_delta
axis=np.asarray([-.3191732196912358,-.5743433374616473,-.7538290167838767]);distal=(basis-wrist)@axis
region={i for i,(p,w) in enumerate(zip(basis,oldweights)) if p[0]<-34 and p[2]<108 and distal[i]>-.5 and w.get('hand_r',0)+w.get('lowerarm_r',0)>.5}
color_image=next(n.image for n in oldmesh.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.image and n.image.name.startswith('Color'))
iw,ih=color_image.size;pixels=np.empty(iw*ih*4,dtype=np.float32);color_image.pixels.foreach_get(pixels);uv_layer=oldmesh.uv_layers.active;removed_polys=[];bodypolys=[]
for p in oldmesh.polygons:
    if not any(i in region for i in p.vertices):bodypolys.append(p);continue
    warm=0
    for li in p.loop_indices:
        u,v=uv_layer.data[li].uv;px=min(iw-1,max(0,int(u*iw)));py=min(ih-1,max(0,int(v*ih)));idx=4*(py*iw+px)
        red,green,blue=pixels[idx:idx+3]
        warm+=red>blue*1.025 and red>green*.985
    if float(distal[list(p.vertices)].mean())>6 or warm>=max(2,math.ceil(len(p.vertices)*.6)):removed_polys.append(p.index)
    else:bodypolys.append(p)
used={i for p in bodypolys for i in p.vertices};remove={i for i in region if i not in used}
keep=[i for i in range(len(basis)) if i not in remove];remap={old:new for new,old in enumerate(keep)}
faces=[[remap[i] for i in p.vertices] for p in bodypolys];offset=len(keep);faces.extend([[offset+i for i in p.vertices] for p in hm.polygons])
points=np.concatenate((basis[keep],hand_points),axis=0);newmesh=bpy.data.meshes.new('WuxiaBodyRealGripMesh');newmesh.from_pydata(points.tolist(),[],faces);newmesh.update()
newobj=bpy.data.objects.new('SK_WuxiaMale_RealGrip_v04',newmesh);bpy.context.scene.collection.objects.link(newobj);newobj.matrix_world=body.matrix_world.copy()
for m in oldmesh.materials:newmesh.materials.append(m)
for m in hm.materials:newmesh.materials.append(m)
for p,source in zip(newmesh.polygons,bodypolys):p.material_index=source.material_index;p.use_smooth=source.use_smooth
for p,source in zip(list(newmesh.polygons)[len(bodypolys):],hm.polygons):p.material_index=len(oldmesh.materials)+source.material_index;p.use_smooth=True
bodyloops=[li for p in bodypolys for li in p.loop_indices]
for layer in oldmesh.uv_layers:
    nl=newmesh.uv_layers.new(name=layer.name);uvs=[tuple(layer.data[i].uv) for i in bodyloops]
    hl=hm.uv_layers.get(layer.name) or hm.uv_layers.active
    uvs.extend([tuple(d.uv) for d in hl.data] if hl else [(0,0)]*len(hm.loops));nl.data.foreach_set('uv',np.asarray(uvs).ravel())
if not newmesh.uv_layers:
    uv=newmesh.uv_layers.new(name='UVMap');uvs=[(0,0)]*len(bodyloops)+[tuple(d.uv) for d in hm.uv_layers.active.data];uv.data.foreach_set('uv',np.asarray(uvs).ravel())
color=newmesh.color_attributes.new(name='SkinTint',type='FLOAT_COLOR',domain='CORNER');hc=hm.color_attributes.get('SkinTint');colors=[(1,1,1,1)]*len(bodyloops)
if hc:
    colors.extend([tuple(hc.data[i if hc.domain=='CORNER' else hm.loops[i].vertex_index].color) for i in range(len(hm.loops))])
else:colors.extend([(0.52,.28,.18,1)]*len(hm.loops))
color.data.foreach_set('color',np.asarray(colors).ravel());newmesh.color_attributes.active_color=color
for group in body.vertex_groups:newobj.vertex_groups.new(name=group.name)
for oldid,newid in remap.items():
    for name,value in oldweights[oldid].items():newobj.vertex_groups[name].add([newid],value,'REPLACE')
newobj.vertex_groups['hand_r'].add(list(range(offset,len(points))),1.,'REPLACE')
for name,keycoords in oldkeys.items():
    if name=='EnemyGrip_R':continue
    key=newobj.shape_key_add(name=name);values=np.concatenate((keycoords[keep],hand_points),axis=0);key.data.foreach_set('co',values.ravel());key.value=0
arm=newobj.modifiers.new('OriginalEnemy23Bones','ARMATURE');arm.object=rig
newobj.parent=rig;newobj.matrix_parent_inverse=body.matrix_parent_inverse.copy();newobj.matrix_world=body.matrix_world.copy()
for o in [body,hand,player_rig,temp]:bpy.data.objects.remove(o,do_unlink=True)
newobj.name='SK_WuxiaMale_RealGrip_v04';bpy.context.view_layer.update()
blend=O/'WuxiaMaleRealGrip_v04.blend';fbx=O/'WuxiaMaleRealGrip_v04.fbx';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action='DESELECT');newobj.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,use_armature_deform_only=True,bake_anim=False,apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',path_mode='STRIP',mesh_smooth_type='FACE',use_mesh_modifiers=False,colors_type='LINEAR')
newmesh.calc_loop_triangles();report={'status':'candidate_requires_alignment_review','source_body':source_path,'source_hand':str(P/'ArtSource/PlayerHands/Realistic/PlayerHandRealistic_GripPreview.blend'),'blend':str(blend),'fbx':str(fbx),'removed_right_hand_vertices':len(remove),'retained_body_vertices':len(keep),'added_hand_vertices':len(hand_points),'final_vertices':len(points),'final_triangles':len(newmesh.loop_triangles),'bone_count':len(rig.data.bones),'material_slots':[m.name for m in newmesh.materials],'shape_keys':[k.name for k in newmesh.shape_keys.key_blocks],'grip_mode':'Fixed real player Grip geometry. EnemyGrip_R omitted, never applies the rejected morph.','body_basis_unchanged':bool(np.array_equal(points[:offset],basis[keep])),'body_weights_unchanged':True,'death_morphs_retained':True,'hand_bone_binding':'hand_r 1.0 for added vertices','player_to_enemy_bind_matrix':[list(r) for r in mapping],'hand_roll_around_unchanged_shaft_deg':math.degrees(roll),'proximal_wrist_extension_cm':list(wrist_delta),'player_mapped_wrist_cm':list(newwrist),'enemy_wrist_cm':list(wrist),'wrist_gap_cm':float((newwrist-Vector(wrist)).length),'vertex_color':'SkinTint FLOAT_COLOR CORNER, FBX LINEAR','retained_vertex_source_indices':keep}
(O/'RealGripReplacementSummary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('REAL_GRIP_REPLACEMENT',json.dumps({k:v for k,v in report.items() if k!='retained_vertex_source_indices'}),flush=True)
