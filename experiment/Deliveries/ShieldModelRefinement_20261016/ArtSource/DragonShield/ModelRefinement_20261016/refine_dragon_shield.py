import bpy, math, json, hashlib, re
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix
OUT=Path(__file__).resolve().parent
SOURCE=Path(bpy.data.filepath).resolve();SOURCE_SHA=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
scene=bpy.context.scene
bpy.context.preferences.filepaths.save_version=0
FACTOR=46.0/.82
original=[o for o in scene.objects if o.type in ('MESH','CURVE') and not o.hide_render]
original_names=[o.name for o in original]
source_hidden=[o.name for o in scene.objects if o.type in ('MESH','CURVE') and o.hide_render]

def triangles():
    d=bpy.context.evaluated_depsgraph_get();rows=[]
    for o in scene.objects:
        if o.type not in ('MESH','CURVE') or o.hide_render:continue
        e=o.evaluated_get(d);m=e.to_mesh();m.calc_loop_triangles();rows.append((o.name,len(m.loop_triangles)));e.to_mesh_clear()
    return sum(v for _,v in rows),rows
baseline_tris,_=triangles()
changes=[];hidden=[];added=[]
bronze=bpy.data.materials['01 | Aged chased bronze'];gold=bpy.data.materials['02 | Worn raised gold bronze'];dark=bpy.data.materials['03 | Recessed dark bronze'];leather=bpy.data.materials['06 | Dark oxblood shield leather'];brass=bpy.data.materials['07 | Rivet aged brass']

def hide(o,reason):
    if not o.hide_render:hidden.append({'name':o.name,'reason':reason})
    o.hide_render=True;o.hide_set(True)
def smooth(o):
    if o.type=='MESH':
        for p in o.data.polygons:p.use_smooth=True
    return o

def mesh_obj(name,verts,faces,mat):
    m=bpy.data.meshes.new(name+' mesh');m.from_pydata(verts,[],faces);m.materials.append(mat);m.update();o=bpy.data.objects.new(name,m);scene.collection.objects.link(o);smooth(o);added.append(name);return o

def tube(name,pts,r,mat,sides=6):
    # Low polygon real seam/stitch geometry; parallel transported local frames.
    verts=[];faces=[]
    points=[Vector(p) for p in pts]
    for i,p in enumerate(points):
        t=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized();ref=Vector((0,1,0))
        if abs(t.dot(ref))>.92:ref=Vector((1,0,0))
        a=t.cross(ref).normalized();b=t.cross(a).normalized()
        for j in range(sides):
            q=p+r*(math.cos(math.tau*j/sides)*a+math.sin(math.tau*j/sides)*b);verts.append(tuple(q))
    for i in range(len(points)-1):
        for j in range(sides):a=i*sides+j;b=i*sides+(j+1)%sides;faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(range(sides-1,-1,-1)));faces.append(tuple((len(points)-1)*sides+j for j in range(sides)))
    return mesh_obj(name,verts,faces,mat)

def torus(name,major,minor,y,mat,maj=144,minr=8):
    bpy.ops.mesh.primitive_torus_add(major_segments=maj,minor_segments=minr,major_radius=major,minor_radius=minor,location=(0,y,0),rotation=(math.pi*.5,0,0))
    o=bpy.context.object;o.name=name;o.data.materials.append(mat);smooth(o);added.append(name);return o

def box(name,loc,dims,mat,bevel=.002):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dims;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat)
    b=o.modifiers.new('Rounded machined edges','BEVEL');b.width=bevel;b.segments=3
    w=o.modifiers.new('Corner normals','WEIGHTED_NORMAL');w.keep_sharp=True
    added.append(name);return o

def cylinder_x(name,x,ry,rz,depth,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=40,radius=1,depth=1,location=(x,.092,-.01),rotation=(0,math.pi*.5,0));o=bpy.context.object;o.name=name;o.scale=(rz,ry,depth);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat);smooth(o)
    b=o.modifiers.new('Soft collar bevel','BEVEL');b.width=.0015;b.segments=3;added.append(name);return o

# Recover geometry budget from regular, tiny construction parts. Retain original hidden copies.
ring_prefixes=('Outer rolled rim','Outer rim shadow channel','Inner raised rim','Inner rim fine bead','Face inner pinstripe','Back outer rolled rim','Back inner rim','Engraved concentric hairline','Rear leather seat bezel','Rear boss bead')
for o in list(original):
    if o.name.startswith(ring_prefixes) and o.type=='MESH':
        coords=[v.co for v in o.data.vertices];minor=(max(p.z for p in coords)-min(p.z for p in coords))*.5;major=(max(p.x for p in coords)-min(p.x for p in coords))*.5-minor
        matrix=o.matrix_world.copy();mat=o.data.materials[0]
        hide(o,'Replace dense torus by matching round profile with useful near-view resolution')
        bpy.ops.mesh.primitive_torus_add(major_segments=192 if 'hairline' in o.name else 144,minor_segments=6 if minor<.003 else 10,major_radius=major,minor_radius=minor)
        n=bpy.context.object;n.name=o.name+' | detailed profile';n.matrix_world=matrix;n.data.materials.append(mat);smooth(n);added.append(n.name)
    elif o.type=='MESH' and any(tag in o.name.lower() for tag in ('rivet','stud','screw','rosette')):
        o.data.calc_loop_triangles()
        if len(o.data.loop_triangles)>250:
            d=o.modifiers.new('Reduce tiny round fastener redundancy','DECIMATE');d.ratio=.5
    elif o.type=='CURVE':
        o.data.bevel_resolution=min(o.data.bevel_resolution,2);o.data.resolution_u=min(o.data.resolution_u,12)
    for m in o.modifiers:
        if m.type=='BEVEL' and o.name.startswith('Rim index engraving'):m.segments=2
changes.append('Reduced cross-section density of circular hairlines and small round fasteners; silhouette and source material assignments retained.')

# Refine ONLY the existing projected face. SIMPLE subdivision linearly interpolates both original UV layers.
face=next(o for o in original if o.name.startswith('Front face | exact dragon reference'))
uv_names=[u.name for u in face.data.uv_layers]
face_original_vertices=len(face.data.vertices);face_original_polygons=len(face.data.polygons)
old_uv=[[(float(p.uv.x),float(p.uv.y)) for p in u.data] for u in face.data.uv_layers]
old_uv_hash=[hashlib.sha256(repr(u).encode()).hexdigest() for u in old_uv]
sub=face.modifiers.new('Reference aligned relief sampling','SUBSURF');sub.subdivision_type='SIMPLE';sub.levels=2;sub.render_levels=2
bpy.context.view_layer.objects.active=face
bpy.ops.object.modifier_apply(modifier=sub.name)
# Reference pixel positions remain fixed; height is authored from a hand-traced dragon body envelope
# and restrained bronze-color detail, so broad background highlights do not become raised bumps.
image=next(n.image for n in face.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.name=='Original shield reference crop')
w,h=image.size;pix=np.empty(w*h*4,dtype=np.float32);image.pixels.foreach_get(pix);pix=pix.reshape(h,w,4)

def sample(px,py):
    x=np.clip(px,0,w-1);y=np.clip(h-1-py,0,h-1);x0=np.floor(x).astype(int);y0=np.floor(y).astype(int);x1=np.minimum(x0+1,w-1);y1=np.minimum(y0+1,h-1);tx=x-x0;ty=y-y0
    return ((pix[y0,x0,:3]*(1-tx)[:,None]+pix[y0,x1,:3]*tx[:,None])*(1-ty)[:,None]+(pix[y1,x0,:3]*(1-tx)[:,None]+pix[y1,x1,:3]*tx[:,None])*ty[:,None])
co=np.array([v.co[:] for v in face.data.vertices]);px=640+362*co[:,0]/.331;py=640-362*co[:,2]/.331
rgb=sample(px,py);warm=np.clip(((rgb[:,0]-rgb[:,2])/(rgb.sum(axis=1)+1e-6)-.028)/.105,0,1)
# Broad volumes follow the exact reference's S-shaped spine, with locally adjusted radii.
body=[(632,427,30),(690,451,28),(714,488,29),(710,531,31),(674,556,33),(621,568,31),(566,565,33),(521,579,34),(484,614,35),(466,656,34),(483,700,34),(522,736,32),(578,758,31),(637,784,31),(676,817,29),(687,854,28),(674,893,27),(641,918,25),(603,926,23),(565,915,21),(532,892,18),(493,874,16),(463,883,13),(442,903,8)]
envelope=np.zeros(len(co))
for p0,p1 in zip(body,body[1:]):
    a=np.array(p0[:2]);b=np.array(p1[:2]);v=b-a;t=np.clip(((px-a[0])*v[0]+(py-a[1])*v[1])/np.dot(v,v),0,1);dx=px-(a[0]+v[0]*t);dy=py-(a[1]+v[1]*t);r=p0[2]+(p1[2]-p0[2])*t;dist2=(dx*dx+dy*dy)/(r*r)
    envelope=np.maximum(envelope,np.exp(-1.65*dist2)*np.clip((2.25-dist2)/.75,0,1))
# Head, muzzle and jaw are separately shaped; no added silhouette spikes.
head=np.zeros(len(co))
for x,z,rx,rz,amount in [(548,399,37,21,1.0),(576,438,31,29,.85),(489,415,36,14,.62),(479,460,24,13,.50),(605,471,33,18,.48)]:
    d=((px-x)/rx)**2+((py-z)/rz)**2;head=np.maximum(head,amount*np.exp(-1.6*d)*np.clip((2.0-d)/.6,0,1))
# A local bronze mask lifts the fine traced clouds and horns only about 1 mm in final size.
rad=np.sqrt(co[:,0]**2+co[:,2]**2)/.331;edge=np.clip((1.0-rad)/.055,0,1);edge=edge*edge*(3-2*edge)
height=(.0098*envelope*(.78+.22*warm)+.0105*head+.0017*warm**1.6)*edge
for v,dy in zip(face.data.vertices,height):v.co.y-=float(dy)
for p in face.data.polygons:p.use_smooth=True
# Quantify mapping preservation against the original analytic crop, without rewriting UVs.
uv_errors=[0.,0.]
for loop in face.data.loops:
    p=face.data.vertices[loop.vertex_index].co
    expect0=((640+362*p.x/.331)/w,1-(640-362*p.z/.331)/h)
    expect1=((p.x/.331+1)*.5,(p.z/.331+1)*.5)
    for index,expected in enumerate((expect0,expect1)):
        actual=face.data.uv_layers[index].data[loop.index].uv
        uv_errors[index]=max(uv_errors[index],abs(actual.x-expected[0]),abs(actual.y-expected[1]))
face['relief_depth_cm']=float(height.max()*FACTOR);face['reference_uv_policy']='Original two channels SIMPLE subdivided/interpolated; no unwrap or coordinate reprojection.'
changes.append('Raised image-aligned dragon spine/head relief and shallow bronze scroll detail on original dual-UV face; only depth coordinates displaced.')

# Replace faceted back grip and nonfunctional rear cross-bars by ergonomic rounded leather geometry.
for o in list(scene.objects):
    if o.name.startswith(('Rear hand grip | core','Grip cross wrap','Grip end ferrule','Grip pommel stud')):hide(o,'Replaced by rounded leather grip, real helical lap seam, and axial collars')
# Rounded elliptic barrel: overall original grip dimensions .235 x .052 x .062, fixed center.
verts=[];faces=[];rings=31;sides=40
for i in range(rings):
    u=i/(rings-1);x=-.1175+.235*u;cap=max(.0,1-((abs(x)-.094)/.0235)**2) if abs(x)>.094 else 1.;cap=math.sqrt(max(.0,cap));ry=.0252*cap;rz=.0302*cap
    for j in range(sides):a=math.tau*j/sides;verts.append((x,.092+ry*math.cos(a),-.01+rz*math.sin(a)))
for i in range(rings-1):
    for j in range(sides):a=i*sides+j;b=i*sides+(j+1)%sides;faces.append((a,a+sides,b+sides,b))
grip=mesh_obj('Detailed grip | rounded leather barrel',verts,faces,leather);grip['fixed_grip_center']=[0,.092,-.01]
# One thin overlapped leather strip, real thickness, laid diagonally along the barrel.
turns=10.0;n=360;verts=[];faces=[]
for i in range(n+1):
    t=i/n;a=math.tau*turns*t;x=-.103+.206*t
    for dx,th in [(-.007,0),(.007,0),(.007,.00065),(-.007,.00065)]:verts.append((x+dx,.092+(.02525+th)*math.cos(a),-.01+(.03025+th)*math.sin(a)))
for i in range(n):
    for j in range(4):a=4*i+j;b=4*i+(j+1)%4;faces.append((a,b,b+4,a+4))
faces.extend([(3,2,1,0),(4*n,4*n+1,4*n+2,4*n+3)])
mesh_obj('Detailed grip | continuous leather spiral wrap',verts,faces,leather)
# The seam sits shallowly in the lap edge; small diagonal stitches catch grazing light.
pts=[]
for i in range(361):t=i/360;a=math.tau*turns*t;pts.append((-.103+.206*t+.007,.092+.02615*math.cos(a),-.01+.03115*math.sin(a)))
tube('Detailed grip | spiral seam',pts,.00040,dark,5)
for k in range(35):
    t=.035+.93*k/34;a=math.tau*turns*t;x=-.103+.206*t+.0065
    pts=[(x-.0015,.092+.02635*math.cos(a-.045),-.01+.03135*math.sin(a-.045)),(x,.092+.02665*math.cos(a),-.01+.03165*math.sin(a)),(x+.0015,.092+.02635*math.cos(a+.045),-.01+.03135*math.sin(a+.045))]
    tube('Detailed grip stitch %02d'%k,pts,.00043,leather,5)
for sign in (-1,1):
    cylinder_x('Detailed grip | rounded bronze collar '+str(sign),sign*.1125,.0275,.0325,.010,bronze)
    box('Detailed grip | structural end anchor '+str(sign),(sign*.127,.078,-.01),(.024,.029,.047),bronze,.006)
    # Washer and slotted fixing sit on the rear of the anchor, with a genuine small inset slot.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=10,radius=1,location=(sign*.127,.096,-.01));o=bpy.context.object;o.name='Detailed grip | anchor domed screw '+str(sign);o.scale=(.008,.003,.008);o.data.materials.append(brass);smooth(o);added.append(o.name)
    box('Detailed grip | anchor screw slot '+str(sign),(sign*.127,.099,-.01),(.009,.00045,.0011),dark,.00025)
changes.append('Rounded fixed-center grip with actual spiral leather strip, lap seam, 35 stitches, rounded axial collars and two anchored slotted screws.')

# Keep the original forearm strap route and attachment coordinates; soften it and add sewn edging.
for o in original:
    if o.name.startswith('Rear forearm strap'):
        for p in o.data.polygons:p.use_smooth=True
        for m in o.modifiers:
            if m.type=='BEVEL':m.segments=5
for xcenter in (-.205,.205):
    for sign in (-1,1):
        pts=[]
        for i in range(55):z=-.179+.358*i/54;y=.088-.018*math.sqrt(max(0,1-(z/.408)**2))+.0062;pts.append((xcenter+sign*.022,y,z))
        tube('Detailed strap | rolled sewn edge %.3f %d'%(xcenter,sign),pts,.00095,leather,6)
        for i in range(29):
            z=-.16+.32*i/28;y=.088-.018*math.sqrt(max(0,1-(z/.408)**2))+.0068
            tube('Detailed strap stitch %.3f %d %02d'%(xcenter,sign,i),[(xcenter+sign*.021-.0012,y,z-.0014),(xcenter+sign*.021,y+.0004,z),(xcenter+sign*.021+.0012,y,z+.0014)],.00055,leather,5)
# Add shallow machined borders around the four retained leather anchor plates.
for x in (-.205,.205):
    for z in (-.17,.17):
        pts=[(x-.027,.078,z-.020),(x+.027,.078,z-.020),(x+.029,.078,z-.017),(x+.029,.078,z+.017),(x+.027,.078,z+.020),(x-.027,.078,z+.020),(x-.029,.078,z+.017),(x-.029,.078,z-.017),(x-.027,.078,z-.020)]
        tube('Detailed anchor | fine chased border %.3f %.3f'%(x,z),pts,.0008,brass,6)
        box('Detailed anchor | slot %.3f %.3f'%(x,z),(x,.090,z),(.007,.00045,.0011),dark,.0002)
changes.append('Soft strap faces with rolled edges, 116 real stitches and chased/slotted anchor details; original anchor positions retained.')
# Fine concentric machined channels on the existing rolled rim, no silhouette growth.
torus('Detailed rim | fine dark turning groove outer',.402,.00045,-.0463,dark,192,6)
torus('Detailed rim | fine dark turning groove inner',.391,.00040,-.0465,dark,192,6)
changes.append('Two fine recessed-color turning grooves complete the layered bronze rim, within its original diameter.')

final_tris,part_counts=triangles()
report={'source':str(SOURCE),'source_sha256':SOURCE_SHA,'source_unchanged':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA,'baseline_visible_parts':len(original),'baseline_evaluated_triangles':baseline_tris,'refined_visible_parts':len(part_counts),'refined_evaluated_triangles':final_tris,'changes':changes,'hidden_replaced_parts':hidden,'hidden_original_geometry_count':len(source_hidden),'hidden_original_geometry_names':source_hidden,'added_geometry_names':added,'face':{'original_vertices':face_original_vertices,'original_polygons':face_original_polygons,'refined_vertices':len(face.data.vertices),'refined_polygons':len(face.data.polygons),'uv_names_original':uv_names,'uv_names_refined':[u.name for u in face.data.uv_layers],'original_uv_hashes':old_uv_hash,'max_uv_affine_mapping_error':uv_errors,'uv_policy':'SIMPLE subdivision linear interpolation of original two channels; never re-unwrapped','max_added_relief_depth_cm':float(height.max()*FACTOR),'mean_added_relief_depth_cm':float(height.mean()*FACTOR)},'grip_center_source':[0,.092,-.01],'nominal_diameter_cm':46.,'original_material_names':[m.name for m in bpy.data.materials],'part_triangle_counts':part_counts}
(OUT/'ModelRefinementAuthoring.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
# Pack source images into the derivative blend. This does not modify the original source file.
for img in bpy.data.images:
    if img.source=='FILE' and not img.packed_file:
        try:img.pack()
        except Exception:pass
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=48;scene.cycles.use_denoising=True
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Jade_Dragon_Shield_Detailed.blend'))
print('MODEL_REFINEMENT_AUTHORING',json.dumps({'baseline':baseline_tris,'refined':final_tris,'face_vertices':len(face.data.vertices),'uv_error':uv_errors,'max_relief_cm':float(height.max()*FACTOR)}),flush=True)
