"""V02: a slim cloud-shoulder jian, clean tapered blade, original immutable contact grip."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path('D:/game design/experiment')
SOURCE=ROOT/'ArtSource/WeaponReview/Over9000/SelectedA/SM_PlayerSword_A.blend'
OUT=ROOT/'ArtSource/WeaponReview/SelectedA_DetailV02';OUT.mkdir(parents=True,exist_ok=True)
DOC=ROOT/'Docs/Gameplay/VRWeaponPolish_v02';DOC.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));scene=bpy.context.scene
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
original=next(o for o in bpy.data.objects if o.type=='MESH')
gripmat=next(m for m in original.data.materials if m.name=='Grip04')
for m in list(bpy.data.materials):
    if m!=gripmat:m.name='Legacy_'+m.name
grip=original.copy();grip.data=original.data.copy();bpy.context.collection.objects.link(grip);grip.name='OriginalContactGrip'
bm=bmesh.new();bm.from_mesh(grip.data)
keep=next(i for i,m in enumerate(grip.data.materials) if m==gripmat)
bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index!=keep],context='FACES')
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
for f in bm.faces:f.material_index=0
bm.to_mesh(grip.data);bm.free();grip.data.materials.clear();grip.data.materials.append(gripmat)
bpy.data.objects.remove(original,do_unlink=True)
parts=[grip]

contract={
 'BladeSteel':{'base_color_linear':[.52,.54,.56],'metallic':.94,'roughness':.26},
 'BladeEdge':{'base_color_linear':[.65,.68,.70],'metallic':.96,'roughness':.20},
 'BladeFuller':{'base_color_linear':[.52,.54,.56],'metallic':.94,'roughness':.26},
 'Guard03':{'base_color_linear':[.31,.205,.085],'metallic':.88,'roughness':.32},
 'Grip04':{'existing_ue_material':'/Game/ModularWeapons/Materials/MI_Sword_Hilt_01'},
 'Pommel03':{'base_color_linear':[.035,.12,.085],'metallic':.08,'roughness':.22},
 'GoldDetail':{'base_color_linear':[.51,.34,.14],'metallic':.92,'roughness':.26}}
mats={'Grip04':gripmat}
for name,c in contract.items():
    if name=='Grip04':continue
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*c['base_color_linear'],1)
    p=next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if p is None:
        p=m.node_tree.nodes.new('ShaderNodeBsdfPrincipled');o=m.node_tree.nodes.new('ShaderNodeOutputMaterial');m.node_tree.links.new(p.outputs['BSDF'],o.inputs['Surface'])
    p.inputs['Base Color'].default_value=(*c['base_color_linear'],1);p.inputs['Metallic'].default_value=c['metallic'];p.inputs['Roughness'].default_value=c['roughness'];mats[name]=m
gp=next(n for n in gripmat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
gp.inputs['Base Color'].default_value=(.025,.036,.047,1);gp.inputs['Metallic'].default_value=.05;gp.inputs['Roughness'].default_value=.58

def newmesh(name,verts,faces,slots,face_mats=None,smooth=True):
    me=bpy.data.meshes.new(name+'_Geometry');me.from_pydata(verts,[],faces);me.update()
    ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob)
    for s in slots:me.materials.append(mats[s])
    for i,p in enumerate(me.polygons):p.material_index=face_mats[i] if face_mats else 0;p.use_smooth=smooth
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    parts.append(ob);return ob

def interp_profile(profile):
    slopes=[(b[1]-a[1])/(b[0]-a[0]) for a,b in zip(profile,profile[1:])]
    tan=[slopes[0]]+[0 if a*b<=0 else 2*a*b/(a+b) for a,b in zip(slopes,slopes[1:])]+[slopes[-1]]
    def value(z):
        for i,(a,b) in enumerate(zip(profile,profile[1:])):
            if z<=b[0]:
                h=b[0]-a[0];t=(z-a[0])/h
                return (2*t**3-3*t*t+1)*a[1]+(t**3-2*t*t+t)*h*tan[i]+(-2*t**3+3*t*t)*b[1]+(t**3-t*t)*h*tan[i+1]
        return profile[-1][1]
    return value

z0=8.42043399810791;tip=64.9390869140625;bottom=-13.375218391418457
profile=[(z0,3.05),(10,3.06),(13,2.78),(18,2.61),(28,2.40),(38,2.18),(48,1.93),(54,1.65),(58,1.25),(61,.80),(63.4,.37),(tip,0)]
width=interp_profile(profile)
thick=interp_profile([(z0,.345),(18,.318),(30,.280),(42,.242),(52,.194),(58,.128),(62,.065),(tip,0)])
def groove(z):
    # Short engraved channel fades continuously to an uninterrupted diamond blade.
    if z<11 or z>32:return 0
    return math.sin(math.pi*(z-11)/21)**2
fractions=[-1,-.965,-.72,-.50,-.45,-.35,-.30,-.055,0,.055,.30,.35,.45,.50,.72,.965,1]
def height(x,z):
    u=min(1,abs(x)/max(.00001,width(z)))
    # Broad planes meet at a lightly radiused ridge; edge is a real 0.15mm thickness band.
    h=thick(z)*(1-u*.975)
    if u<.055:h=thick(z)*(1-.055*.975*.45-(u/.055)**2*.055*.975*.55)
    depression=0
    if .30<u<.50:
        depression=.022*groove(z)*math.sin(math.pi*(u-.30)/.20)**2
    return max(.00003,h-depression)
zs=sorted(set(round(z,6) for z in ([z0+(tip-z0)*i/72 for i in range(72)]+[p[0] for p in profile[:-1]]+[11,15,24,29,32,tip-.10])))
section=[(u,-1) for u in fractions]+[(u,1) for u in reversed(fractions)]
verts=[(u*width(z),s*height(u*width(z),z),z) for z in zs for u,s in section]
faces=[];idx=[];n=len(section)
for r in range(len(zs)-1):
    for j in range(n):
        faces.append((r*n+j,r*n+(j+1)%n,(r+1)*n+(j+1)%n,(r+1)*n+j))
        u=(abs(section[j][0])+abs(section[(j+1)%n][0]))*.5
        idx.append(1 if u>.965 else (2 if .32<u<.48 and groove((zs[r]+zs[r+1])*.5)>.12 else 0))
base_i=len(verts);verts.append((0,0,zs[0]))
for j in range(n):faces.append((base_i,(j+1)%n,j));idx.append(0)
tip_i=len(verts);verts.append((0,0,tip))
for j in range(n):faces.append(((len(zs)-1)*n+j,(len(zs)-1)*n+(j+1)%n,tip_i));idx.append(1 if abs(section[j][0])>.965 else 0)
blade=newmesh('FlowingTaperedBlade',verts,faces,['BladeSteel','BladeEdge','BladeFuller'],idx)
bm=bmesh.new();bm.from_mesh(blade.data)
for e in bm.edges:
    a,b=e.verts;u=abs(a.co.x)/max(.00001,width(a.co.z))
    if abs(a.co.z-b.co.z)>.01 and abs(u-.965)<.002:e.smooth=False
bm.to_mesh(blade.data);bm.free()

def catmull(points,steps=3,closed=False):
    p=[Vector(v) for v in points];out=[]
    for i in range(len(p) if closed else len(p)-1):
        a=p[(i-1)%len(p)] if closed or i else p[0]
        b=p[i];c=p[(i+1)%len(p)];d=p[(i+2)%len(p)] if closed or i+2<len(p) else p[-1]
        for k in range(steps):
            t=k/steps
            out.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    if not closed:out.append(p[-1])
    return out

def plate(name,outline,halfdepth,bevel,main='Guard03',edge='GoldDetail',steps=3):
    # Build constant-width rounded rim explicitly; generic bevel clamp made curved wings stepped.
    line=catmull(outline,steps,True);num=len(line)
    area=sum(p.x*line[(i+1)%num].y-line[(i+1)%num].x*p.y for i,p in enumerate(line))
    inward=[]
    for i,p in enumerate(line):
        t=(line[(i+1)%num]-line[(i-1)%num]).normalized()
        inward.append(Vector((-t.y,t.x))*(1 if area>0 else -1))
    rings=4;v=[]
    for side in [-1,1]:
        for r in range(rings):
            angle=math.pi*.5*r/(rings-1);offset=bevel*(1-math.cos(angle));depth=halfdepth-bevel+bevel*math.sin(angle)
            for p,normal in zip(line,inward):
                q=p+normal*offset;v.append((q.x,side*depth,q.y))
    f=[];mi=[]
    for side_i in [0,1]:
        start=side_i*rings*num
        for r in range(rings-1):
            for i in range(num):
                a=start+r*num+i;b=start+r*num+(i+1)%num
                f.append((a,b,b+num,a+num));mi.append(1)
        f.append(tuple(start+(rings-1)*num+i for i in range(num)));mi.append(0)
    for i in range(num):f.append((i,(i+1)%num,rings*num+(i+1)%num,rings*num+i));mi.append(0)
    ob=newmesh(name,v,f,[main,edge],mi,smooth=True)
    # Caps are truly flat; the rounded edge and curved side wall remain smooth.
    for p in ob.data.polygons:
        if len(p.vertices)>4:p.use_smooth=False
    return ob

right=[(0,9.85),(1.8,9.75),(3.4,10.15),(4.75,11.18),(5.6,11.55),(6.35,11.25),(6.65,10.6),
       (6.34,10.18),(5.85,10.06),(5.55,10.40),(5.10,10.16),(4.5,9.30),(3.85,8.53),(2.7,7.66),(1.5,7.27),(0,7.15)]
outline=right+[(-x,z) for x,z in reversed(right[1:-1])]
guard=plate('SingleCloudShoulderGuard',outline,.70,.10,steps=6)

# A slim centered bronze collar joins the blade root to the cloud guard. No additions touch the grip contact interval.
collar=[(-1.45,7.12),(-2.52,7.65),(-3.10,8.55),(-3.12,9.22),(-2.72,9.56),(0,9.42),(2.72,9.56),(3.12,9.22),(3.10,8.55),(2.52,7.65),(1.45,7.12)]
plate('BladeRootCollar',collar,.82,.065,steps=5)

# Closed, nearly flush metal inlay strips. Visible surface protrusion is 0.003cm (0.03mm).
def inlay(name,points,surface,width_cm=.055,side=-1):
    line=catmull(points,4,False);num=len(line);v=[]
    for depth in [-.005,.003]:
        for i,p in enumerate(line):
            tangent=(line[min(i+1,num-1)]-line[max(0,i-1)]).normalized();normal=Vector((-tangent.y,tangent.x))
            taper=.25+.75*math.sin(math.pi*i/max(1,num-1))**.35
            for s in [-1,1]:
                q=p+normal*s*width_cm*.5*taper;v.append((q.x,side*(surface(q.x,q.y)+depth),q.y))
    f=[];off=num*2
    for i in range(num-1):
        a=i*2;b=(i+1)*2
        f.extend([(off+a,off+a+1,off+b+1,off+b),(a,b,b+1,a+1),(a,off+a,off+b,b),(a+1,b+1,off+b+1,off+a+1)])
    f.extend([(0,1,off+1,off),(off-2,off+off-2,off+off-1,off-1)])
    return newmesh(name,v,f,['GoldDetail'],smooth=False)

cloud=[(.12,11.5),(.6,12.2),(1.02,12.65),(1.08,13.26),(.75,13.62),(.39,13.44),(.44,13.08),(.70,13.03)]
plume=[(.12,11.5),(.22,12.45),(.12,13.6),(0,14.65)]
wingline=[(2.25,8.55),(3.2,8.95),(4.08,9.65),(4.50,10.20),(4.46,10.62),(4.13,10.69),(4.01,10.42)]
for side in [-1,1]:
    for sign in [-1,1]:
        for j,points in enumerate([cloud,plume]):inlay(f'FlushForteCloud_{side}_{sign}_{j}',[(sign*x,z) for x,z in points],height,.052,side)
        # The wing silhouette remains uninterrupted; ornament stays on the wide center collar.
    # A restrained stamped seal on the collar is flat inlay, not a floating wire ornament.
    seal=[(0,7.75),(.66,8.15),(0,8.87),(-.66,8.15),(0,7.75)]
    inlay(f'CollarSeal_{side}',seal,lambda x,z:.82,.065,side)

# Compact leaf-form bronze pommel with a shallow jade cabochon, retaining original total length.
pomright=[(0,-7.06),(.83,-7.20),(1.33,-7.92),(1.48,-8.85),(1.40,-9.84),(1.09,-10.94),(.61,-12.18),(0,bottom)]
pomoutline=pomright+[(-x,z) for x,z in reversed(pomright[1:-1])]
pommel=plate('LeafBronzePommel',pomoutline,.63,.055,steps=4)
# Restore only the last 0.9cm after rim bevel rounding so total length remains exact.
pom_min=min(v.co.z for v in pommel.data.vertices)
for v in pommel.data.vertices:
    if v.co.z<-12.5:v.co.z+=(bottom-pom_min)*(-12.5-v.co.z)/(-12.5-pom_min)

def cabochon(side):
    center_z=-9.65;rz=1.70;rx=.90
    loops=6;segments=32;v=[]
    # Lenticular stone sinks into bronze at its outer rim.
    for j in range(loops):
        r=1-j/loops
        for k in range(segments):
            a=2*math.pi*k/segments;x=rx*r*math.cos(a);z=center_z+rz*r*math.sin(a)
            v.append((x,side*(.615+.14*(1-r*r)),z))
    top=len(v);v.append((0,side*.755,center_z));back=len(v);v.append((0,side*.57,center_z))
    f=[]
    for j in range(loops-1):
        for k in range(segments):f.append((j*segments+k,j*segments+(k+1)%segments,(j+1)*segments+(k+1)%segments,(j+1)*segments+k))
    for k in range(segments):
        f.append(((loops-1)*segments+k,(loops-1)*segments+(k+1)%segments,top));f.append(((k+1)%segments,k,back))
    return newmesh('InsetJadePommel_'+str(side),v,f,['Pommel03'])
for s in [-1,1]:cabochon(s)

# Narrow mechanical neck is tucked into the unchanged grip end and fills the previous visual seam.
levels=[(-7.52,.98),(-7.40,1.22),(-7.23,1.26),(-7.06,1.19),(-6.97,1.16)]
segments=32;v=[(r*math.cos(2*math.pi*k/segments),r*math.sin(2*math.pi*k/segments),z) for z,r in levels for k in range(segments)]
f=[]
for j in range(len(levels)-1):
    for k in range(segments):f.append((j*segments+k,j*segments+(k+1)%segments,(j+1)*segments+(k+1)%segments,(j+1)*segments+k))
f.extend([tuple(reversed(range(segments))),tuple((len(levels)-1)*segments+i for i in range(segments))])
newmesh('PommelNeckFerrule',v,f,['Guard03'])

# Unchanged source grip keeps its existing UVs. Every newly authored component gets consistent planar UVs.
for ob in parts:
    for li in range(2):
        if li<len(ob.data.uv_layers):ob.data.uv_layers[li].name=f'UVChannel_{li}'
        else:
            uv=ob.data.uv_layers.new(name=f'UVChannel_{li}')
            for p in ob.data.polygons:
                for l in p.loop_indices:
                    co=ob.data.vertices[ob.data.loops[l].vertex_index].co
                    uv.data[l].uv=(.5+co.x/15,(co.z-bottom)/(tip-bottom))
    if ob.type=='MESH':
        ob.data.calc_loop_triangles()
        triangles_by_face={p.index:[] for p in ob.data.polygons}
        for tri in ob.data.loop_triangles:triangles_by_face[tri.polygon_index].append(tri)
        for face in ob.data.polygons:
            candidates=[]
            for axes in [(0,1),(0,2),(1,2)]:
                areas=[]
                for tri in triangles_by_face[face.index]:
                    a,b,c=[ob.data.vertices[i].co for i in tri.vertices];u,v=axes
                    areas.append(abs((b[u]-a[u])*(c[v]-a[v])-(b[v]-a[v])*(c[u]-a[u]))*.5)
                candidates.append((min(areas),axes))
            area,axes=max(candidates,key=lambda x:x[0]);assert area>1e-10
            for uv in ob.data.uv_layers:
                if ob==grip:
                    bad=False
                    for tri in triangles_by_face[face.index]:
                        a,b,c=[uv.data[l].uv for l in tri.loops]
                        uv_area=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5
                        bad|=uv_area<=1e-10
                    if not bad:continue
                for loop in face.loop_indices:
                    co=ob.data.vertices[ob.data.loops[loop].vertex_index].co
                    uv.data[loop].uv=(co[axes[0]]*.25,co[axes[1]]*.25)

bpy.ops.object.select_all(action='DESELECT')
for ob in parts:ob.select_set(True)
bpy.context.view_layer.objects.active=blade;bpy.ops.object.join();result=bpy.context.object
result.name='SM_PlayerSword_A_DetailV02';result.data.name=result.name+'_Mesh';result.matrix_world=Matrix.Identity(4)
# Stable 7-slot contract independent of authoring order.
order=['BladeSteel','BladeEdge','BladeFuller','Guard03','Grip04','Pommel03','GoldDetail']
old=[m.name for m in result.data.materials];indices=[order.index(old[p.material_index]) for p in result.data.polygons]
result.data.materials.clear()
for s in order:result.data.materials.append(mats[s])
for p,i in zip(result.data.polygons,indices):p.material_index=i
result.data.calc_loop_triangles();triangles=len(result.data.loop_triangles)
assert triangles<18000,triangles
bounds=[[min(v.co[i] for v in result.data.vertices) for i in range(3)],[max(v.co[i] for v in result.data.vertices) for i in range(3)]]
assert abs(bounds[1][2]-tip)<.001 and abs(bounds[0][2]-bottom)<.001,bounds
assert bounds[1][0]-bounds[0][0]<=15 and bounds[1][1]-bounds[0][1]<=4,bounds
result['axis_contract']='centimeters; tip +Z; unchanged source grip and pivot';result['revision']='V02 cloud-shoulder jian'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(result.name+'.blend')))
bpy.ops.export_scene.fbx(filepath=str(OUT/(result.name+'.fbx')),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',bake_anim=False,path_mode='STRIP',use_custom_props=True,use_mesh_modifiers=True)
counts={s:sum(1 for t in result.data.loop_triangles if order[t.material_index]==s) for s in order}
report={'state':'built','source_blend':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'output_fbx':str(OUT/(result.name+'.fbx')),'output_blend':str(OUT/(result.name+'.blend')),
 'triangles_before':11878,'triangles_after':triangles,'vertices_after':len(result.data.vertices),'triangles_by_material':counts,
 'bounds_cm':{'min':bounds[0],'max':bounds[1]},'blade_sample_cm':[[0,0,8.42],[0,0,36.68],[0,0,64.94]],
 'slot_order':order,'material_contract':contract,'uv_layers':[l.name for l in result.data.uv_layers],
 'changes':['Continuously tapering blade outline and thickness','Broad clean diamond planes, shallow channel fades out by z32cm','Single slim sculpted cloud-shoulder guard replaces three stacked guard plates','Physical beveled rim and centered blade-root collar','Near-flush cloud inlay, only 0.03mm above blade surface','Compact bronze leaf pommel with inset jade','Exact original contact grip geometry and nondegenerate UVs retained; 16 degenerate collar UV faces repaired'],
 'license':'Derived from user project sword A plus local original procedural geometry; no external asset/provider',
 'fbx_sha256':hashlib.sha256((OUT/(result.name+'.fbx')).read_bytes()).hexdigest(),
 'limits':'Offline source; root owns UE import and real VR acceptance. Grip04 is the only retained textured material; remapped clean parameters for new guard/pommel geometry.'}
for out in [OUT/'AssetGeometryReport.json',DOC/'AssetGeometryReport.json']:out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')

scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1300;scene.render.resolution_y=1800;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.world.use_nodes=True;bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.075,.085,.10,1);bg.inputs['Strength'].default_value=.55
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
def point(o,t):o.rotation_euler=(Vector(t)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(25,-160,28));cam=bpy.context.object;point(cam,(0,0,26));cam.data.type='ORTHO';cam.data.ortho_scale=85;scene.camera=cam
for pos,power,sx,sy in [((-22,-30,52),100000,12,85),((28,-18,35),65000,8,70),((8,25,50),120000,20,70)]:
    bpy.ops.object.light_add(type='AREA',location=pos);l=bpy.context.object;l.data.energy=power;l.data.shape='RECTANGLE';l.data.size=sx;l.data.size_y=sy;point(l,(0,0,28))
scene.render.filepath=str(OUT/'Detail_Whole.png');bpy.ops.render.render(write_still=True)
cam.location=(12,-68,16);point(cam,(0,0,10));cam.data.ortho_scale=26
scene.render.resolution_x=1600;scene.render.resolution_y=1300;scene.render.filepath=str(OUT/'Detail_Forte.png');bpy.ops.render.render(write_still=True)
cam.location=(45,-80,42);point(cam,(0,0,43));cam.data.ortho_scale=35
scene.render.filepath=str(OUT/'Detail_Blade.png');bpy.ops.render.render(write_still=True)
cam.location=(8,-45,-7.5);point(cam,(0,0,-7.5));cam.data.ortho_scale=15
scene.render.filepath=str(OUT/'Detail_Pommel.png');bpy.ops.render.render(write_still=True)
print('V02_ASSET_EXPORTED',json.dumps({'triangles':triangles,'slots':order,'bounds':report['bounds_cm']}),flush=True)
