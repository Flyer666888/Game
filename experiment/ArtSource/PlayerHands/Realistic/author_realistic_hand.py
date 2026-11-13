"""Author a continuous human skin derivative; source FBX and reference bones remain unchanged."""
import bpy, bmesh, json, math, hashlib
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
from mathutils import noise
import numpy as np

OUT=Path(__file__).resolve().parent
SOURCE=OUT.parent/'Source'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=str(SOURCE/'SKM_MannyXR_right.fbx'),use_anim=False,automatic_bone_orientation=False)
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
src=next(o for o in bpy.context.scene.objects if o.type=='MESH')
source_stats={'vertices':len(src.data.vertices),'triangles':sum(len(p.vertices)-2 for p in src.data.polygons)}
rest={b.name:b.matrix_local.copy() for b in rig.data.bones}
parents={b.name:b.parent.name if b.parent else 'root' for b in rig.data.bones}
original_rig_matrix=rig.matrix_world.copy()
src.name='Manny_SourceReference';src.hide_render=True
src.hide_set(True)
skin=src.copy();skin.data=src.data.copy();bpy.context.scene.collection.objects.link(skin)
skin.name='PlayerHandRealistic_R'
skin.hide_render=False;skin.hide_set(False)
for mod in list(skin.modifiers):skin.modifiers.remove(mod)
skin.data.materials.clear()
bpy.context.view_layer.objects.active=skin;skin.select_set(True);src.select_set(False);rig.select_set(False)

# Blend the raised mechanical plates into a rounded palm and a plain wrist.
for v in skin.data.vertices:
    x,y,z=v.co
    if y>-9.3:
        dorsal=1.20+0.42*math.exp(-((y+5.0)/3.5)**2)
        if z>dorsal-0.3:
            blend=min(1.0,max(0.0,(y+9.3)/1.7))
            v.co.z=z*(1.0-blend*.92)+min(z,dorsal)*blend*.92
        if y>-1.5:
            # An anatomical oval wrist removes the original rigid cuff edge.
            r=math.sqrt((x/3.28)**2+((z+0.10)/2.13)**2)
            blend=min(1.0,max(0.0,(y+1.5)/1.5))*.82
            if r>0.05:
                v.co.x=x*(1.0-blend)+x/r*blend
                v.co.z=z*(1.0-blend)+((z+0.10)/r-0.10)*blend

parts=[skin]
def volume(name,center,radii):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20)
    obj=bpy.context.object;obj.name=name
    # Mesh local positions are centimeters; preserve the source .01 world scale.
    obj.matrix_world=skin.matrix_world.copy()
    for v in obj.data.vertices:v.co=Vector(center)+Vector((v.co.x*radii[0],v.co.y*radii[1],v.co.z*radii[2]))
    parts.append(obj)

volume('PalmContinuity',(0,-4.4,-.42),(3.48,5.50,1.88))
volume('ThenarPad',(3.0,-4.6,-1.55),(1.74,3.45,1.23))
volume('HypothenarPad',(-2.70,-4.7,-1.35),(1.20,3.25,1.12))
for finger,radius in [('index',.94),('middle',.99),('ring',.93),('pinky',.79)]:
    head=rig.data.bones[finger+'_01_r'].head_local
    volume(finger+'_Knuckle',head+Vector((0,.22,.20)),(radius,radius*1.18,radius*.89))

bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=skin;bpy.ops.object.join()
# Voxel union gives the palm, fingers and pads a continuous skin surface.
mod=skin.modifiers.new('ContinuousSkinUnion','REMESH');mod.mode='VOXEL';mod.voxel_size=.105;mod.use_smooth_shade=True
bpy.ops.object.modifier_apply(modifier=mod.name)
mod=skin.modifiers.new('RemovePlateRidges','SMOOTH');mod.factor=1.30;mod.iterations=9
bpy.ops.object.modifier_apply(modifier=mod.name)

# Remove disconnected chips left behind by the source's overlapping mechanical parts.
bm=bmesh.new();bm.from_mesh(skin.data)
visited=set();components=[]
for v in bm.verts:
    if v in visited:continue
    stack=[v];visited.add(v);component=[]
    while stack:
        q=stack.pop();component.append(q)
        for e in q.link_edges:
            n=e.other_vert(q)
            if n not in visited:visited.add(n);stack.append(n)
    components.append(component)
if len(components)>1:
    largest=max(components,key=len)
    bmesh.ops.delete(bm,geom=[v for c in components if c is not largest for v in c],context='VERTS')
bm.to_mesh(skin.data);bm.free()
# Finish the sleeve transition as a smooth oval wrist with a clean flat end.
# This removes the original glove's V-shaped raised cuff and sawtooth opening.
for v in skin.data.vertices:
    x,y,z=v.co
    if y>-2.1:
        r=math.sqrt((x/3.12)**2+((z+.15)/1.87)**2)
        t=min(1.,max(0.,(y+2.1)/2.2));t=t*t*(3-2*t)
        if r>.62:
            v.co.x=x*(1-t)+(x/r)*t
            v.co.z=z*(1-t)+((z+.15)/r-.15)*t
bm=bmesh.new();bm.from_mesh(skin.data)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
    plane_co=Vector((0,.72,0)),plane_no=Vector((0,1,0)),dist=.0001,clear_outer=True,clear_inner=False)
boundary=[e for e in bm.edges if e.is_boundary and all(abs(v.co.y-.72)<.002 for v in e.verts)]
if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
bm.to_mesh(skin.data);bm.free()
mod=skin.modifiers.new('SkinSurfaceBudget','DECIMATE');mod.ratio=min(1.0,14500/max(1,len(skin.data.polygons)))
bpy.ops.object.modifier_apply(modifier=mod.name)
for p in skin.data.polygons:p.use_smooth=True
skin.data.update()

# Low relief creases are actual geometry, rather than painted dark glove seams.
crease_count=0
for v in skin.data.vertices:
    x,y,z=v.co
    if -8.4<y<-.5 and v.normal.z>.50:
        tendon=0.
        for finger in ('index','middle','ring','pinky'):
            h=rig.data.bones[finger+'_01_r'].head_local
            t=max(0.,min(1.,(-y-.5)/max(1.,-h.y-.5)))
            ridge_x=h.x*(.18+.82*t)
            tendon+=.070*math.exp(-((x-ridge_x)/.30)**2)*math.sin(math.pi*t)
        v.co.z+=tendon
    if -8.8<y<-.4 and v.normal.z<-.25:
        palm_mask=min(1.,max(0.,(-v.normal.z-.25)/.45))
        line1=-6.75+.11*x+.035*x*x
        line2=-4.45-.16*x+.018*x*x
        life=1.15+.095*(y+5.5)**2
        depth=.050*math.exp(-((y-line1)/.115)**2)+.035*math.exp(-((y-line2)/.115)**2)
        if -7.4<y<-1.4:depth+=.045*math.exp(-((x-life)/.12)**2)
        v.co.z+=depth*palm_mask
        if depth>.008:crease_count+=1
    for finger in ('index','middle','ring','pinky','thumb'):
        for joint in ('02','03'):
            b=rig.data.bones[finger+'_'+joint+'_r']
            prev=rig.data.bones[finger+'_'+('01' if joint=='02' else '02')+'_r']
            axis=(b.head_local-prev.head_local).normalized()
            dorsal=(Vector((0,0,1))-axis*axis.z).normalized()
            rel=v.co-b.head_local
            along=rel.dot(axis)
            radial=rel-axis*along
            if radial.length<1.5 and abs(along)<.48 and rel.dot(dorsal)>.30:
                d=.034*math.exp(-(along/.10)**2)+.016*math.exp(-((along-.25)/.07)**2)
                v.co-=d*dorsal

skin.data.update()
# Transfer smoothly interpolated bone weights from the unchanged Manny reference.
for group in src.vertex_groups:
    if group.name not in skin.vertex_groups:skin.vertex_groups.new(name=group.name)
transfer=skin.modifiers.new('OriginalXRBoneWeights','DATA_TRANSFER')
transfer.object=src;transfer.use_vert_data=True;transfer.data_types_verts={'VGROUP_WEIGHTS'}
transfer.vert_mapping='POLYINTERP_NEAREST';transfer.layers_vgroup_select_src='ALL';transfer.layers_vgroup_select_dst='NAME'
bpy.ops.object.modifier_apply(modifier=transfer.name)
# Keep every point normalized and at most four influences, as required by the VR mesh.
bpy.ops.object.vertex_group_limit_total(limit=4)
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
arm=skin.modifiers.new('XR47BoneDeformation','ARMATURE');arm.object=rig

def skin_color(position,normal):
    x,y,z=position
    palm=min(1.,max(0.,(-normal.z+.10)/1.0))
    base=Vector((.43,.255,.177)).lerp(Vector((.52,.326,.232)),palm*.73)
    n=noise.noise_vector(position*.82).x*.018+noise.noise_vector(position*3.7).z*.007
    base+=Vector((n,n*.63,n*.45))
    for finger in ('index','middle','ring','pinky','thumb'):
        for j in ('01','02','03'):
            h=rig.data.bones[finger+'_'+j+'_r'].head_local
            amount=math.exp(-((position-h).length/1.25)**2)*.04
            base+=Vector((amount,-amount*.27,-amount*.37))
    return (*[max(.03,min(.8,c)) for c in base],1.)
color=skin.data.color_attributes.new(name='SkinTint',type='BYTE_COLOR',domain='CORNER')
for loop in skin.data.loops:
    v=skin.data.vertices[loop.vertex_index]
    color.data[loop.index].color=skin_color(v.co,v.normal)
skin.data.color_attributes.active_color=color

skinmat=bpy.data.materials.new('M_Skin');skinmat.use_nodes=True
nodes=skinmat.node_tree.nodes;links=skinmat.node_tree.links;bsdf=nodes.get('Principled BSDF')
vc=nodes.new('ShaderNodeVertexColor');vc.layer_name='SkinTint';links.new(vc.outputs['Color'],bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value=.52;bsdf.inputs['Specular IOR Level'].default_value=.28
bsdf.inputs['Subsurface Weight'].default_value=.025
bsdf.inputs['Subsurface Radius'].default_value=(1.0,.45,.25)
tex=nodes.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=320;tex.inputs['Detail'].default_value=2
bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.14;bump.inputs['Distance'].default_value=.00013
links.new(tex.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
skin.data.materials.append(skinmat)

# Nails are conforming curved shells on the dorsal distal finger surface.
bvh=BVHTree.FromPolygons([v.co.copy() for v in skin.data.vertices],[tuple(p.vertices) for p in skin.data.polygons])
nailmat=bpy.data.materials.new('M_Nails');nailmat.use_nodes=True
nbs=nailmat.node_tree.nodes.get('Principled BSDF');nbs.inputs['Base Color'].default_value=(.56,.37,.29,1)
nbs.inputs['Roughness'].default_value=.36;nbs.inputs['Specular IOR Level'].default_value=.27
nvc=nailmat.node_tree.nodes.new('ShaderNodeVertexColor');nvc.layer_name='SkinTint'
nailmat.node_tree.links.new(nvc.outputs['Color'],nbs.inputs['Base Color'])
nails=[];nail_records=[]
for finger,width in [('index',.60),('middle',.65),('ring',.60),('pinky',.48),('thumb',.54)]:
    b=rig.data.bones[finger+'_03_r'];prev=rig.data.bones[finger+'_02_r']
    axis=(b.head_local-prev.head_local).normalized();normal=(Vector((0,0,1))-axis*axis.z).normalized()
    side=axis.cross(normal).normalized()
    group=src.vertex_groups.get(finger+'_03_r')
    points=[v.co for v in src.data.vertices if any(g.group==group.index and g.weight>.25 for g in v.groups)]
    far=max((p-b.head_local).dot(axis) for p in points)
    length=min(1.35,max(.84,far*.56));center=b.head_local+axis*(far*.44)
    if finger=='thumb':length*=.86
    verts=[];faces=[];rows=13;cols=15
    for i in range(rows):
        t=i/(rows-1);along=(t-.5)*length
        taper=.84+.16*math.sin(math.pi*t)
        p=center+axis*along
        hit,hitnormal,_,_=bvh.ray_cast(p+normal*4,-normal,8)
        if hit is None:raise RuntimeError('Missing center of nail bed: '+finger)
        # Fit one continuous curvature to each row; independent per-column ray
        # projections can jump across the far side of a curled thumb.
        row_center=hit
        for j in range(cols):
            u=(j/(cols-1)*2-1)
            rounding=.14*(1-u*u)*(t**5)+.13*u*u*((1-t)**5)
            q=row_center+axis*rounding+side*u*width*taper+normal*(.020-.20*u*u)
            surface,surface_normal,_,_=bvh.find_nearest(q)
            if surface is None:raise RuntimeError('Missing conforming nail surface: '+finger)
            # Keep the full shell against the real skin. Embed its perimeter;
            # a nail crown rises at most 0.13 mm, preventing floating edge cards.
            offset=-.012+.025*(1-u*u)*max(0.,math.sin(math.pi*t))**.35
            q=surface+surface_normal*offset
            verts.append(q)
    for i in range(rows-1):
        for j in range(cols-1):
            a=i*cols+j;faces.append((a,a+1,a+cols+1,a+cols))
    mesh=bpy.data.meshes.new(finger+'_NailSurface');mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(finger+'_NaturalNail',mesh);bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world=skin.matrix_world.copy();obj.parent=rig;obj.matrix_world=skin.matrix_world.copy()
    vg=obj.vertex_groups.new(name=finger+'_03_r');vg.add(list(range(len(verts))),1.,'REPLACE')
    for p in mesh.polygons:p.use_smooth=True
    obj.data.materials.append(nailmat)
    col=obj.data.color_attributes.new(name='SkinTint',type='BYTE_COLOR',domain='CORNER')
    for loop in mesh.loops:
        t=(loop.vertex_index//cols)/(rows-1)
        edge=max(0.,min(1.,(t-.955)/.045))
        c=Vector((.43,.258,.205)).lerp(Vector((.59,.45,.37)),edge)
        c=(*c,1.)
        col.data[loop.index].color=c
    nails.append(obj);nail_records.append({'finger':finger,'bone':b.name,'center':list(center),'length_cm':length,'width_cm':width*2})

bpy.ops.object.select_all(action='DESELECT');skin.select_set(True)
for o in nails:o.select_set(True)
bpy.context.view_layer.objects.active=skin;bpy.ops.object.join()
skin.data.name='HumanHand_ContinuousSkinAndNails'
skin.data.color_attributes.active_color=skin.data.color_attributes.get('SkinTint')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.015)
bpy.ops.object.mode_set(mode='OBJECT')

# Cheap tileable micro normal and roughness for the UE material; no baked lighting.
res=1024;rng=np.random.default_rng(20261015)
height=np.zeros((res,res),dtype=np.float32)
for cells,weight in ((64,.70),(128,.32),(256,.13),(512,.06)):
    a=rng.normal(size=(cells,cells)).astype(np.float32)
    factor=res//cells
    a=np.repeat(np.repeat(a,factor,axis=0),factor,axis=1)
    for _ in range(max(1,factor//2)):
        a=(a+np.roll(a,1,0)+np.roll(a,-1,0)+np.roll(a,1,1)+np.roll(a,-1,1))/5
    height+=a*weight
dx=(np.roll(height,-1,1)-np.roll(height,1,1))*.27
dy=(np.roll(height,-1,0)-np.roll(height,1,0))*.27
n=np.stack((-dx,dy,np.ones_like(dx)),axis=-1) # DirectX: flipped green relative to OpenGL.
n/=np.linalg.norm(n,axis=-1,keepdims=True)
def save_image(name,pixels,colorspace):
    image=bpy.data.images.new(name,width=res,height=res,alpha=True,float_buffer=False)
    image.colorspace_settings.name=colorspace;image.pixels.foreach_set(pixels.astype(np.float32).ravel())
    image.filepath_raw=str(OUT/(name+'.png'));image.file_format='PNG';image.save()
save_image('T_PlayerHand_Micro_N',np.dstack((n*.5+.5,np.ones((res,res)))), 'Non-Color')
rough=np.clip(.53+height*.055,.39,.67)
save_image('T_PlayerHand_Micro_R',np.dstack((rough,rough,rough,np.ones((res,res)))), 'Non-Color')

scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0
rig.data.pose_position='REST'
src.hide_set(True);src.hide_render=True
for name,matrix in rest.items():
    if max(abs(a-b) for ra,rb in zip(matrix,rig.data.bones[name].matrix_local) for a,b in zip(ra,rb))>1.e-6:
        raise RuntimeError('Reference bone changed: '+name)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'PlayerHandRealistic_R.blend'))
bpy.ops.object.select_all(action='DESELECT');skin.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.fbx(filepath=str(OUT/'PlayerHandRealistic_R.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},
    add_leaf_bones=False,use_armature_deform_only=False,bake_anim=False,apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',path_mode='STRIP',
    mesh_smooth_type='FACE',use_mesh_modifiers=False,colors_type='LINEAR')
manifest={'source':'../Source/SKM_MannyXR_right.fbx','fbx':'PlayerHandRealistic_R.fbx','blend':'PlayerHandRealistic_R.blend',
    'source_mesh_stats':source_stats,'mesh_stats':{'vertices':len(skin.data.vertices),'triangles':sum(len(p.vertices)-2 for p in skin.data.polygons)},
    'materials':['M_Skin','M_Nails'],'vertex_color':{'name':'SkinTint','meaning':'Actual warm neutral skin RGB, scene linear; alpha 1','fbx_colors_type':'LINEAR'},
    'textures':{'skin':{'normal':'T_PlayerHand_Micro_N.png','roughness':'T_PlayerHand_Micro_R.png','normal_convention':'DirectX','normal_strength':.28,'uv_tiling':6.0}},
    'anatomy_changes':['Continuous skin voxel union','Removed rigid dorsal plate and wrist cuff contour','Thenar and hypothenar palm volume','Rounded metacarpal knuckles','Low relief palmar and joint creases','Five conforming dorsal nails'],
    'nails':nail_records,'palm_crease_vertices':crease_count,'blender_bone_count':len(rig.data.bones),'fbx_root_object_name':rig.name,
    'ue_bone_count_including_root_object':len(rig.data.bones)+1,'bone_hierarchy':parents,'rest_bone_matrices_unchanged':True,
    'armature_matrix':[list(r) for r in rig.matrix_world],'mesh_matrix':[list(r) for r in skin.matrix_world],
    'source_assets_changed':False,'weapon_attachment_changed':False,'preview_only_pose':False}
(OUT/'HandsAuthoring.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('HUMAN_HAND_AUTHORED',manifest['mesh_stats'],len(rig.data.bones),rig.name)

# Preview only: pose with UE world-space deltas relative to the original Idle reference.
poses=json.loads((SOURCE/'PlayerHandSourceExport.json').read_text(encoding='utf-8'))['poses']
def ue_matrix(data):
    return Matrix.LocRotScale(Vector(data['p']),Quaternion((data['q'][3],*data['q'][:3])),Vector(data['s']))
reflection=Matrix.Diagonal((1,-1,1,1))
def set_pose(label):
    rig.data.pose_position='POSE'
    for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
    for pb in rig.pose.bones:
        if pb.name in poses[label]:
            delta=reflection@ue_matrix(poses[label][pb.name]['world'])@ue_matrix(poses['Idle'][pb.name]['world']).inverted()@reflection
            pb.matrix=delta@rest[pb.name]
            bpy.context.view_layer.update()

scene.render.engine='CYCLES';scene.cycles.samples=40
scene.render.resolution_x=1400;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.055,.065,.080,1)
scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.45
scene.view_settings.view_transform='AgX'
def bounds():
    dg=bpy.context.evaluated_depsgraph_get();evaluated=skin.evaluated_get(dg)
    points=[skin.matrix_world@v.co for v in evaluated.data.vertices]
    low=Vector([min(v[i] for v in points) for i in range(3)]);high=Vector([max(v[i] for v in points) for i in range(3)])
    return (low+high)*.5,max(high-low)
center,span=bounds()
preview_lights=[]
for name,loc,power,size in [('Key',Vector((.4,-.1,.6)),8,.45),('Fill',Vector((-.4,-.2,.25)),4,.4),('Rim',Vector((.1,.4,.3)),6,.3)]:
    light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='DISK';light.size=size
    obj=bpy.data.objects.new(name,light);scene.collection.objects.link(obj);obj.location=center+loc
    obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
    preview_lights.append(obj)
camdata=bpy.data.cameras.new('HumanHandCamera');cam=bpy.data.objects.new('HumanHandCamera',camdata);scene.collection.objects.link(cam)
camdata.type='ORTHO';scene.camera=cam
for label,direction,file in [('Idle',Vector((.4,-.7,1.1)),'HumanHand_Dorsal.png'),('Idle',Vector((.2,-.3,-1)),'HumanHand_Palm.png'),('Grip',Vector((1,-.5,1)),'HumanHand_Grip.png')]:
    set_pose(label);center,span=bounds()
    cam.location=center+direction.normalized()*span*2.3
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();camdata.ortho_scale=span*1.30
    orientation=direction.normalized().to_track_quat('Z','Y')
    for light,offset in zip(preview_lights,(Vector((.22,.08,.40)),Vector((-.22,-.05,.30)),Vector((.05,.22,-.20)))):
        light.location=center+orientation@offset
        light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/file);bpy.ops.render.render(write_still=True)
set_pose('Grip')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'PlayerHandRealistic_GripPreview.blend'))
print('HUMAN_HAND_PREVIEWS_SAVED')
