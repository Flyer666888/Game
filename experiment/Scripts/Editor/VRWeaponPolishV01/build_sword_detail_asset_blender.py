"""Refine approved A sword in a new folder; centimeter axes and grip pivot are immutable."""
import bpy, bmesh, json, math, hashlib
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path('D:/game design/experiment')
SOURCE=ROOT/'ArtSource/WeaponReview/Over9000/SelectedA/SM_PlayerSword_A.blend'
OUT=ROOT/'ArtSource/WeaponReview/SelectedA_DetailV01'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene=bpy.context.scene
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
original=next(o for o in bpy.data.objects if o.type=='MESH')
original.data.calc_loop_triangles()
source_tris=len(original.data.loop_triangles)
source_bounds=[[min(v.co[i] for v in original.data.vertices) for i in range(3)],
               [max(v.co[i] for v in original.data.vertices) for i in range(3)]]

def material(name,color,metallic,roughness):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    p=next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if not p:
        p=m.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        output=m.node_tree.nodes.new('ShaderNodeOutputMaterial');m.node_tree.links.new(p.outputs['BSDF'],output.inputs['Surface'])
    p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metallic;p.inputs['Roughness'].default_value=roughness
    return m

steel=material('BladeSteel',(.43,.49,.56),.95,.26)
edge=material('BladeEdge',(.68,.75,.83),.96,.17)
fuller=material('BladeFuller',(.24,.30,.36),.91,.33)
gold=material('GoldDetail',(.48,.29,.09),.92,.28)
# Keep all original UVs and original material slot names on existing parts.
source_mats={m.name:m for m in original.data.materials}
for name,col,metal,rough in [('Guard03',(.38,.235,.075),.9,.31),('Grip04',(.045,.055,.07),.1,.58),('Pommel03',(.38,.235,.075),.9,.31)]:
    p=source_mats[name].node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough

parts=[]
for slot in [1,2,3]:
    ob=original.copy();ob.data=original.data.copy();bpy.context.collection.objects.link(ob)
    ob.name=source_mats[list(source_mats)[slot]].name+'_Refined'
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index!=slot],context='FACES')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    part_mat=ob.data.materials[slot]
    ob.data.materials.clear();ob.data.materials.append(part_mat)
    for f in bm.faces:f.material_index=0
    if slot!=2:
        # Small physical chamfers catch light without rounding the intended stepped silhouette.
        edges=[e for e in bm.edges if e.is_manifold and e.calc_face_angle(0)>.55]
        bmesh.ops.bevel(bm,geom=edges,offset=.048 if slot==1 else .028,segments=2,affect='EDGES',clamp_overlap=True,material=0)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
        bmesh.ops.dissolve_degenerate(bm,dist=.00001,edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free()
    parts.append(ob)
bpy.data.objects.remove(original,do_unlink=True)

z0=8.42043399810791;tip=64.9390869140625
# Authored silhouette samples copied from approved sword A (cm), then interpolated monotonically.
profile=[(z0,3.884810),(10.43146,3.922617),(12.82807,3.249953),(15.02032,2.955697),
 (16.96213,2.794329),(24.18873,2.611676),(31.4153,2.5830),(42.2649,2.5530),
 (48.8087,2.5644),(54.8465,2.4698),(57.8581,2.30345),(59.5172,2.0679),
 (61.9175,1.4736),(63.3679,.9557),(64.1535,.6015),(64.6297,.3008),(tip,0)]
slopes=[(profile[i+1][1]-profile[i][1])/(profile[i+1][0]-profile[i][0]) for i in range(len(profile)-1)]
tangents=[slopes[0]]
for i in range(1,len(profile)-1):
    a,b=slopes[i-1],slopes[i]
    tangents.append(0.0 if a*b<=0 else 2*a*b/(a+b))
tangents.append(slopes[-1])
def width(z):
    for i in range(len(profile)-1):
        a,b=profile[i],profile[i+1]
        if z<=b[0]:
            h=b[0]-a[0];t=(z-a[0])/h
            return (2*t**3-3*t*t+1)*a[1]+(t**3-2*t*t+t)*h*tangents[i]+(-2*t**3+3*t*t)*b[1]+(t**3-t*t)*h*tangents[i+1]
    return 0
# Every band is physical, including the subtle recessed channels beside the center ridge.
half=[(0,.46),(.03,.449),(.31,.317),(.35,.27),(.45,.225),(.49,.244),(.94,.030),(1,.009)]
fractions=[(-x,y) for x,y in reversed(half[1:])]+half
def thickness(z):
    t=min(1.0,max(.005,(tip-z)/10.0))
    return t*t*(3-2*t)
def height(x,z):
    u=min(1,abs(x)/max(.001,width(z)))
    for i in range(len(half)-1):
        a,b=half[i],half[i+1]
        if u<=b[0]:return (a[1]+(b[1]-a[1])*(u-a[0])/(b[0]-a[0]))*thickness(z)
    return half[-1][1]*thickness(z)

zs=sorted(set(round(z,6) for z in ([z0+(tip-z0)*i/56 for i in range(56)]+[p[0] for p in profile[:-1]]+[tip-.08])))
# Ring runs around the actual perimeter, front then back; it has no duplicate seam vertices.
section=[(x,-y) for x,y in fractions]+[(x,y) for x,y in reversed(fractions)]
verts=[(x*width(z),y*thickness(z),z) for z in zs for x,y in section]
faces=[];mats=[];n=len(section)
for r in range(len(zs)-1):
    for j in range(n):
        faces.append((r*n+j,r*n+(j+1)%n,(r+1)*n+(j+1)%n,(r+1)*n+j))
        x=(abs(section[j][0])+abs(section[(j+1)%n][0]))*.5
        mats.append(1 if x>.94 else (2 if .33<x<.47 else 0))
faces.append(tuple(reversed(range(n))));mats.append(0)
tip_i=len(verts);verts.append((0,0,tip))
for j in range(n):faces.append(((len(zs)-1)*n+j,(len(zs)-1)*n+(j+1)%n,tip_i));mats.append(1 if abs(section[j][0])>.94 else 0)
mesh=bpy.data.meshes.new('A_DetailBlade');mesh.from_pydata(verts,[],faces);mesh.update()
blade=bpy.data.objects.new('A_DetailBlade',mesh);bpy.context.collection.objects.link(blade)
for m in [steel,edge,fuller]:mesh.materials.append(m)
for p,mi in zip(mesh.polygons,mats):p.material_index=mi;p.use_smooth=True
bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
# Only intentional ridge and shallow-channel boundaries are sharp. Bevel bands blend smoothly.
for e in bm.edges:
    a,b=e.verts
    u=abs(a.co.x)/max(.001,width(a.co.z))
    if abs(a.co.z-b.co.z)>.01 and min(abs(u-k) for k in [0,.31,.35,.45,.49,.94])<.002:e.smooth=False
bm.to_mesh(mesh);bm.free()
for li in range(2):
    layer=mesh.uv_layers.new(name=f'UVChannel_{li}')
    for p in mesh.polygons:
        for l in p.loop_indices:
            v=mesh.vertices[mesh.loops[l].vertex_index].co
            layer.data[l].uv=(.5+v.x/8.1,(v.z-z0)/(tip-z0))
parts.insert(0,blade)

def curve_path(name,pts,radius=.032):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=4;cu.bevel_depth=radius;cu.bevel_resolution=1;cu.use_fill_caps=True
    sp=cu.splines.new('BEZIER');sp.bezier_points.add(len(pts)-1)
    for b,p in zip(sp.bezier_points,pts):b.co=p;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
    cu.materials.append(gold);ob=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(ob)
    bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.object.convert(target='MESH');ob=bpy.context.object
    for p in ob.data.polygons:p.use_smooth=True
    parts.append(ob);ob.select_set(False)

# Restrained paired ruyi/cloud inlay at the forte, leaving the cutting length clean.
cloud=[(.24,13.9),(.66,14.6),(1.25,14.95),(1.62,15.65),(1.52,16.42),(1.02,16.78),(.60,16.48),(.62,15.98),(.94,15.79),(1.15,16.04)]
tail=[(.24,13.9),(.42,14.9),(.31,15.95),(.21,17.3),(.32,18.4),(.0,19.65)]
for front in [-1,1]:
    for mirror in [-1,1]:
        for k,line in enumerate([cloud,tail]):
            pts=[(mirror*x,front*(height(mirror*x,z)+.012),z) for x,z in line]
            curve_path(f'RuyiInlay_{front}_{mirror}_{k}',pts,.026 if k else .033)

# Ensure newly-created ornament has usable UVs. Original guard/grip/pommel UVs stay untouched.
for ob in parts:
    for li in range(2):
        if li<len(ob.data.uv_layers):
            ob.data.uv_layers[li].name=f'UVChannel_{li}'
        else:
            uv=ob.data.uv_layers.new(name=f'UVChannel_{li}')
            for p in ob.data.polygons:
                for l in p.loop_indices:
                    v=ob.data.vertices[ob.data.loops[l].vertex_index].co
                    uv.data[l].uv=(.5+v.x/16,(v.z+14)/80)

bpy.ops.object.select_all(action='DESELECT')
for ob in parts:ob.select_set(True)
bpy.context.view_layer.objects.active=blade;bpy.ops.object.join();result=bpy.context.object
result.name='SM_PlayerSword_A_DetailV01';result.data.name=result.name+'_Mesh';result.matrix_world=Matrix.Identity(4)
# Remove unreferenced original blade slot and collect clean deterministic slot mapping.
bpy.ops.object.material_slot_remove_unused()
result.data.calc_loop_triangles()
triangles=len(result.data.loop_triangles)
assert triangles<18000,triangles
bounds=[[min(v.co[i] for v in result.data.vertices) for i in range(3)], [max(v.co[i] for v in result.data.vertices) for i in range(3)]]
assert abs(bounds[1][2]-tip)<.001
assert abs(bounds[0][2]-source_bounds[0][2])<.001
assert max(abs(bounds[e][i]-source_bounds[e][i]) for e in range(2) for i in [0,1])<.05
result['original_asset']='SM_PlayerSword_A';result['axis_contract']='centimeters; tip +Z; width X; thickness Y; unchanged grip pivot at origin'
result['blade_root_cm']=z0;result['blade_tip_cm']=tip
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(result.name+'.blend')))
bpy.ops.export_scene.fbx(filepath=str(OUT/(result.name+'.fbx')),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',bake_anim=False,path_mode='STRIP',use_custom_props=True,use_mesh_modifiers=True)

material_contract={
 'BladeSteel':{'base_color_linear':[.43,.49,.56],'metallic':.95,'roughness':.26},
 'BladeEdge':{'base_color_linear':[.68,.75,.83],'metallic':.96,'roughness':.17},
 'BladeFuller':{'base_color_linear':[.24,.30,.36],'metallic':.91,'roughness':.33},
 'GoldDetail':{'base_color_linear':[.48,.29,.09],'metallic':.92,'roughness':.28},
 'Guard03':{'existing_ue_material':'/Game/ModularWeapons/Materials/MI_Sword_Crossguard_03'},
 'Grip04':{'existing_ue_material':'/Game/ModularWeapons/Materials/MI_Sword_Hilt_01'},
 'Pommel03':{'existing_ue_material':'/Game/ModularWeapons/Materials/MI_Sword_Pommel_03'}}
counts={}
for t in result.data.loop_triangles:
    mat=result.data.materials[t.material_index].name;counts[mat]=counts.get(mat,0)+1
report={'state':'built','source_blend':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'output_fbx':str(OUT/(result.name+'.fbx')),'output_blend':str(OUT/(result.name+'.blend')),
 'triangles_before':source_tris,'triangles_after':triangles,'vertices_after':len(result.data.vertices),'triangles_by_material':counts,
 'bounds_cm':{'min':bounds[0],'max':bounds[1]},'blade_sample_cm':[[0,0,8.42],[0,0,36.68],[0,0,64.94]],
 'slot_order':[m.name for m in result.data.materials],'material_contract':material_contract,'uv_layers':[l.name for l in result.data.uv_layers],
 'changes':['Actual central ridge with paired shallow channels','Dedicated narrow physical cutting edge bands','Smooth original A silhouette through 70+ blade sections','Two-segment 0.48mm guard and 0.28mm pommel chamfers','Restrained symmetric cloud inlay near forte','Original grip geometry and pivot retained'],
 'license':'Derived only from user project selected A source; retains source package terms; no external assets or providers',
 'fbx_sha256':hashlib.sha256((OUT/(result.name+'.fbx')).read_bytes()).hexdigest(),
 'limits':'Blender source validation only. UE import, shading, gameplay collision and real-device acceptance owned by integration.'}
(OUT/'AssetGeometryReport.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(ROOT/'Docs/Gameplay/VRWeaponPolish_v01/AssetGeometryReport.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')

# Neutral studio review uses the same proposed linear material values, no texture substitution.
scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1400;scene.render.resolution_y=1800;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.world.use_nodes=True;bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.055,.075,.10,1);bg.inputs['Strength'].default_value=.45
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
def point(o,t):o.rotation_euler=(Vector(t)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(35,-160,29));cam=bpy.context.object;point(cam,(0,0,26));cam.data.type='ORTHO';cam.data.ortho_scale=85;scene.camera=cam
for pos,power,sx,sy in [((-22,-30,55),170000,12,85),((28,-18,35),110000,8,70),((8,25,50),200000,20,70)]:
    bpy.ops.object.light_add(type='AREA',location=pos);l=bpy.context.object;l.data.energy=power;l.data.shape='RECTANGLE';l.data.size=sx;l.data.size_y=sy;point(l,(0,0,28))
scene.render.filepath=str(OUT/'Detail_Whole.png');bpy.ops.render.render(write_still=True)
cam.location=(14,-65,18);point(cam,(0,0,13));cam.data.ortho_scale=36
scene.render.resolution_x=1600;scene.render.resolution_y=1300;scene.render.filepath=str(OUT/'Detail_Forte.png');bpy.ops.render.render(write_still=True)
cam.location=(50,-80,42);point(cam,(0,0,42));cam.data.ortho_scale=32
scene.render.filepath=str(OUT/'Detail_Blade.png');bpy.ops.render.render(write_still=True)
print('DETAILED_A_EXPORTED',json.dumps({'triangles':triangles,'slots':report['slot_order'],'bounds':report['bounds_cm']}),flush=True)
