import bpy,math,json,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
scene=bpy.context.scene
face=next(o for o in scene.objects if o.name.startswith('Front face | exact dragon reference'))
material=face.data.materials[0]
# Uniform planar sampling, clipped to the identical original radius. Same analytic UV mapping.
N=208;R=.331;verts=[];polys=[];lookup={}
def vi(p):
    key=(round(p[0],10),round(p[1],10))
    if key not in lookup:
        lookup[key]=len(verts);rr=(p[0]*p[0]+p[1]*p[1])/(R*R);verts.append((p[0],-.058-.003*(1-rr),p[1]))
    return lookup[key]
def clip(points):
    result=[]
    for a,b in zip(points,points[1:]+points[:1]):
        ina=a[0]*a[0]+a[1]*a[1]<=R*R+1e-12;inb=b[0]*b[0]+b[1]*b[1]<=R*R+1e-12
        if ina!=inb:
            dx=b[0]-a[0];dz=b[1]-a[1];aa=dx*dx+dz*dz;bb=2*(a[0]*dx+a[1]*dz);cc=a[0]*a[0]+a[1]*a[1]-R*R;disc=max(0,bb*bb-4*aa*cc);roots=[(-bb-math.sqrt(disc))/(2*aa),(-bb+math.sqrt(disc))/(2*aa)];t=next((t for t in roots if -1e-6<=t<=1+1e-6),.5);result.append((a[0]+t*dx,a[1]+t*dz))
        if inb:result.append(b)
    return result
for iz in range(N):
    z0=-R+2*R*iz/N;z1=-R+2*R*(iz+1)/N
    for ix in range(N):
        x0=-R+2*R*ix/N;x1=-R+2*R*(ix+1)/N
        p=clip([(x0,z0),(x1,z0),(x1,z1),(x0,z1)])
        if len(p)<3:continue
        ids=[]
        for q in p:
            k=vi(q)
            if not ids or ids[-1]!=k:ids.append(k)
        if len(ids)>1 and ids[-1]==ids[0]:ids.pop()
        if len(set(ids))>=3:polys.append(tuple(ids))
mesh=bpy.data.meshes.new('Uniform reference-aligned raised dragon face');mesh.from_pydata(verts,[],polys);mesh.materials.append(material);mesh.update();face.data=mesh
for name in ('ReferenceCropUV','ReferenceNormalUV'):mesh.uv_layers.new(name=name)
for p in mesh.polygons:
    p.use_smooth=True
    for li in p.loop_indices:
        v=mesh.vertices[mesh.loops[li].vertex_index].co
        mesh.uv_layers[0].data[li].uv=((640+362*v.x/R)/1280,1-(640-362*v.z/R)/1280)
        mesh.uv_layers[1].data[li].uv=((v.x/R+1)*.5,(v.z/R+1)*.5)
image=next(n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.name=='Original shield reference crop')
w,h=image.size;raw=np.empty(w*h*4,dtype=np.float32);image.pixels.foreach_get(raw);pixels=raw.reshape(h,w,4)[:,:,:3]
def blur_axis(a,r,axis):
    pad=[(0,0)]*a.ndim;pad[axis]=(r,r);b=np.pad(a,pad,mode='edge');cum=np.cumsum(b,axis=axis,dtype=np.float64);zeros=list(cum.shape);zeros[axis]=1;cum=np.concatenate((np.zeros(zeros),cum),axis=axis);sl1=[slice(None)]*a.ndim;sl2=list(sl1);sl1[axis]=slice(2*r+1,None);sl2[axis]=slice(None,-(2*r+1));return (cum[tuple(sl1)]-cum[tuple(sl2)])/(2*r+1)
for _ in range(3):pixels=blur_axis(blur_axis(pixels,4,0),4,1)
co=np.array([v.co[:] for v in mesh.vertices]);px=640+362*co[:,0]/R;py=640-362*co[:,2]/R
x=np.clip(px,0,w-1);y=np.clip(h-1-py,0,h-1);x0=np.floor(x).astype(int);y0=np.floor(y).astype(int);x1=np.minimum(x0+1,w-1);y1=np.minimum(y0+1,h-1);tx=x-x0;ty=y-y0
rgb=((pixels[y0,x0]*(1-tx)[:,None]+pixels[y0,x1]*tx[:,None])*(1-ty)[:,None]+(pixels[y1,x0]*(1-tx)[:,None]+pixels[y1,x1]*tx[:,None])*ty[:,None])
warm=np.clip(((rgb[:,0]-rgb[:,2])/(rgb.sum(axis=1)+1e-6)-.028)/.105,0,1)
body=[(632,427,30),(690,451,28),(714,488,29),(710,531,31),(674,556,33),(621,568,31),(566,565,33),(521,579,34),(484,614,35),(466,656,34),(483,700,34),(522,736,32),(578,758,31),(637,784,31),(676,817,29),(687,854,28),(674,893,27),(641,918,25),(603,926,23),(565,915,21),(532,892,18),(493,874,16),(463,883,13),(442,903,8)]
envelope=np.zeros(len(co))
for p0,p1 in zip(body,body[1:]):
    a=np.array(p0[:2]);b=np.array(p1[:2]);v=b-a;t=np.clip(((px-a[0])*v[0]+(py-a[1])*v[1])/np.dot(v,v),0,1);dx=px-(a[0]+v[0]*t);dy=py-(a[1]+v[1]*t);r=p0[2]+(p1[2]-p0[2])*t;dist2=(dx*dx+dy*dy)/(r*r);envelope=np.maximum(envelope,np.exp(-1.65*dist2)*np.clip((2.25-dist2)/.75,0,1))
head=np.zeros(len(co))
for x,z,rx,rz,amount in [(548,399,37,21,1.0),(576,438,31,29,.85),(489,415,36,14,.62),(479,460,24,13,.50),(605,471,33,18,.48)]:
    d=((px-x)/rx)**2+((py-z)/rz)**2;head=np.maximum(head,amount*np.exp(-1.6*d)*np.clip((2-d)/.6,0,1))
rad=np.sqrt(co[:,0]**2+co[:,2]**2)/R;edge=np.clip((1-rad)/.055,0,1);edge=edge*edge*(3-2*edge)
height=(.0098*envelope*(.92+.08*warm)+.0105*head+.0005*warm**1.6)*edge
for v,dy in zip(mesh.vertices,height):v.co.y-=float(dy)
mesh.update()
# The old reference model accidentally left four isolated talon sets visible after hiding its old dragon.
# Exclude those detached approximation fragments from this reference-matched derivative.
excluded=[]
archive=bpy.data.collections.get('ARCHIVE | original hidden dragon and replaced parts')
for o in list(scene.objects):
    if o.name.startswith('Claw talon') and not o.hide_render:
        excluded.append(o.name);o.hide_render=True;o.hide_set(True)
        if archive:
            for c in list(o.users_collection):c.objects.unlink(o)
            archive.objects.link(o)
deps=bpy.context.evaluated_depsgraph_get();tri=0
for o in scene.objects:
    if o.type not in ('MESH','CURVE') or o.hide_render:continue
    e=o.evaluated_get(deps);m=e.to_mesh();m.calc_loop_triangles();tri+=len(m.loop_triangles);e.to_mesh_clear()
errors=[0.,0.]
for li in mesh.loops:
    p=mesh.vertices[li.vertex_index].co
    expected=[((640+362*p.x/R)/1280,1-(640-362*p.z/R)/1280),((p.x/R+1)*.5,(p.z/R+1)*.5)]
    for j,ex in enumerate(expected):actual=mesh.uv_layers[j].data[li.index].uv;errors[j]=max(errors[j],abs(actual.x-ex[0]),abs(actual.y-ex[1]))
mesh.calc_loop_triangles()
report={'topology':'208 by 208 uniform XY grid clipped analytically to source XZ circle','uv_policy':'Original affine projection and source crop retained exactly; new topology samples same UV0/UV1 fields, no unwrap or fit','face_vertices':len(mesh.vertices),'face_triangles':len(mesh.loop_triangles),'total_triangles':tri,'max_uv_mapping_error':errors,'max_added_relief_cm':float(height.max()*46/.82),'height_filter':'Three radius4 box passes on source RGB prior to warm mask; warm height reduced to 0.0005 source units','excluded_old_visible_talons':excluded,'grip_unchanged':True,'materials_unchanged':True}
(OUT/'ReliefGridCandidate.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Jade_Dragon_Shield_Detailed_GridCandidate.blend'))
# Direct neutral geometry preview, using the same render rig and a temporary override only.
render_script=(OUT/'render_refinement.py').read_text(encoding='utf-8-sig');render_script=render_script[:render_script.index("if mode=='quick':")]
exec(compile(render_script,str(OUT/'render_refinement.py'),'exec'),globals())
scene.cycles.samples=20;scene.render.resolution_x=1100;scene.render.resolution_y=1100
clay=bpy.data.materials.new('TEMP candidate review clay');clay.use_nodes=True;p=next(n for n in clay.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.28,.32,.34,1);p.inputs['Roughness'].default_value=.65;p.inputs['Metallic'].default_value=0;scene.view_layers[0].material_override=clay
render('GridCandidate_Geometry.png',(.72,-1.35,.26))
scene.view_layers[0].material_override=None
render('GridCandidate_ThreeQuarter.png',(.72,-1.35,.26))
print('GRID_CANDIDATE_SAVED',json.dumps(report),flush=True)
