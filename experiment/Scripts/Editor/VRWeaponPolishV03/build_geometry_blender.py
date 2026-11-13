"""V03 local revision: immutable V02 blade/grip; shallow chased dragon fittings and ice jade."""
import bpy,bmesh,json,math,hashlib,ast
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path('D:/game design/experiment')
SOURCE=ROOT/'ArtSource/WeaponReview/SelectedA_DetailV02/SM_PlayerSword_A_DetailV02.blend'
OUT=ROOT/'ArtSource/WeaponReview/SelectedA_DetailV03';OUT.mkdir(parents=True,exist_ok=True)
TEX=OUT/'Textures'
NAME='SM_PlayerSword_A_DetailV03'
tip=64.9390869140625;bottom=-13.375218391418457
order=['BladeSteel','BladeEdge','BladeFuller','Guard03','Grip04','Pommel03','GoldDetail']
contract={
 'BladeSteel':{'base_color_linear':[.52,.55,.58],'metallic':1.,'roughness':.275},
 'BladeEdge':{'base_color_linear':[.61,.64,.67],'metallic':1.,'roughness':.195},
 'BladeFuller':{'base_color_linear':[.52,.55,.58],'metallic':1.,'roughness':.275},
 'Guard03':{'base_color_linear':[.48,.50,.52],'metallic':.98,'roughness':.335},
 'Grip04':{'base_color_linear':[.012,.019,.024],'metallic':0.,'roughness':.610},
 'Pommel03':{'base_color_linear':[.42,.62,.70],'metallic':0.,'roughness':.285},
 'GoldDetail':{'base_color_linear':[.30,.22,.12],'metallic':.94,'roughness':.280}}
textures={'BladeSteel':('SteelSurface',1,.07,0.),'BladeEdge':('SteelSurface',1,.04,-.08),'BladeFuller':('SteelSurface',1,.07,0.),'Guard03':('AgedSilver',1,.10,0.),'Grip04':('DarkLeather',4,.35,0.),'Pommel03':('IceJade',2,.20,0.),'GoldDetail':('AgedSilver',1,.08,-.055)}
roughness_variation={'SteelSurface':(.35,.2750002068),'AgedSilver':(.4,.3350003159),'DarkLeather':(.8,.6100027730),'IceJade':(1.,.2851041843)}
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));scene=bpy.context.scene
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
original=next(o for o in bpy.data.objects if o.type=='MESH')
for ob in list(bpy.data.objects):
    if ob!=original:bpy.data.objects.remove(ob,do_unlink=True)
source_slots=[m.name for m in original.data.materials]
bm=bmesh.new();bm.from_mesh(original.data)
bmesh.ops.delete(bm,geom=[f for f in bm.faces if source_slots[f.material_index] not in ['BladeSteel','BladeEdge','BladeFuller','Grip04']],context='FACES')
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
bm.to_mesh(original.data);bm.free();original.name='V02_ImmutableBladeAndContactGrip'
parts=[original];mats={m.name:m for m in original.data.materials}

# Same map bytes and scalar settings as the UE material library. DirectX normals flip G here only.
for name,c in contract.items():
    m=mats[name];m.use_nodes=True;m.diffuse_color=(*c['base_color_linear'],1)
    nt=m.node_tree;nt.nodes.clear();p=nt.nodes.new('ShaderNodeBsdfPrincipled');out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(p.outputs['BSDF'],out.inputs['Surface'])
    p.inputs['Base Color'].default_value=(*c['base_color_linear'],1);p.inputs['Metallic'].default_value=c['metallic'];p.inputs['Roughness'].default_value=c['roughness']
    p.inputs['Alpha'].default_value=1.;p.inputs['Transmission Weight'].default_value=0.;p.inputs['Emission Strength'].default_value=0.
    family,uvscale,strength,offset=textures[name]
    uv=nt.nodes.new('ShaderNodeTexCoord');scale=nt.nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs['Scale'].default_value=uvscale;nt.links.new(uv.outputs['UV'],scale.inputs[0])
    for kind in ['Roughness','Normal']+(['BaseColor'] if name=='Pommel03' else []):
        t=nt.nodes.new('ShaderNodeTexImage');t.image=bpy.data.images.load(str(TEX/(family+'_'+kind+'.png')),check_existing=True);t.image.colorspace_settings.name='sRGB' if kind=='BaseColor' else 'Non-Color';t.extension='REPEAT';nt.links.new(scale.outputs['Vector'],t.inputs['Vector'])
        if kind=='BaseColor':nt.links.new(t.outputs['Color'],p.inputs['Base Color'])
        elif kind=='Roughness':
            variation,mean=roughness_variation[family]
            mul=nt.nodes.new('ShaderNodeMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=variation;nt.links.new(t.outputs['Color'],mul.inputs[0])
            add=nt.nodes.new('ShaderNodeMath');add.operation='ADD';add.inputs[1].default_value=mean*(1-variation)+offset;nt.links.new(mul.outputs[0],add.inputs[0]);nt.links.new(add.outputs[0],p.inputs['Roughness'])
        else:
            sep=nt.nodes.new('ShaderNodeSeparateColor');sep.mode='RGB';nt.links.new(t.outputs['Color'],sep.inputs['Color'])
            inv=nt.nodes.new('ShaderNodeMath');inv.operation='SUBTRACT';inv.inputs[0].default_value=1.;nt.links.new(sep.outputs['Green'],inv.inputs[1])
            comb=nt.nodes.new('ShaderNodeCombineColor');comb.mode='RGB';nt.links.new(sep.outputs['Red'],comb.inputs['Red']);nt.links.new(inv.outputs[0],comb.inputs['Green']);nt.links.new(sep.outputs['Blue'],comb.inputs['Blue'])
            nm=nt.nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=strength;nt.links.new(comb.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs['Normal'],p.inputs['Normal'])
    c.update({'texture_set':family,'uv_scale':uvscale,'normal_strength':strength,'roughness_offset':offset,'roughness_variation_scale':roughness_variation[family][0],'roughness_texture_mean':roughness_variation[family][1],'opacity':1.,'emissive':0.})

# Reuse the proven explicitly rounded metal plate and watertight inlay primitives only.
old_code=(ROOT/'Scripts/Editor/VRWeaponPolishV02/build_sword_v02_asset_blender.py').read_text(encoding='utf-8')
tree=ast.parse(old_code)
for n in tree.body:
    if isinstance(n,ast.FunctionDef) and n.name in ['newmesh','catmull','plate','inlay','interp_profile']:
        exec(compile(ast.Module(body=[n],type_ignores=[]),str(SOURCE),'exec'))

right=[(0,9.85),(1.9,9.68),(3.35,10.12),(4.8,10.95),(5.7,11.16),(6.42,10.99),(6.62,10.60),(6.40,10.30),(5.74,10.20),(4.72,9.76),(3.72,8.83),(2.45,7.95),(1.35,7.38),(0,7.20)]
outline=right+[(-x,z) for x,z in reversed(right[1:-1])]
guard=plate('RoundedSilverGuard',outline,.65,.10,main='Guard03',edge='Guard03',steps=4)
collar=[(-1.36,7.17),(-2.20,7.69),(-2.84,8.50),(-2.83,9.12),(-2.25,9.48),(0,9.62),(2.25,9.48),(2.83,9.12),(2.84,8.50),(2.20,7.69),(1.36,7.17)]
plate('BladeRootSilverCollar',collar,.76,.065,main='Guard03',edge='Guard03',steps=3)

def relief(name,outline,surface,depth,side,material='Guard03',steps=2):
    ob=plate(name,outline,depth/2,min(depth*.30,.035),main=material,edge=material,steps=steps)
    for v in ob.data.vertices:v.co.y=side*(surface+depth/2-.012+v.co.y)
    return ob

def chase(name,points,surface,width,side,material='GoldDetail'):
    ob=inlay(name,points,lambda x,z:surface,width,side)
    ob.data.materials[0]=mats[material]
    return ob

for side in [-1,1]:
    # Quiet inset jade seal lets the thin cast collar read as a functional fitting.
    n=8;verts=[]
    for radius,depth in [(1,.754),(.82,.83)]:
        for k in range(n):
            a=2*math.pi*k/n+math.pi/8;verts.append((.52*radius*math.cos(a),side*depth,8.56+.66*radius*math.sin(a)))
    faces=[(k,(k+1)%n,n+(k+1)%n,n+k) for k in range(n)]+[tuple(range(n,2*n)),tuple(reversed(range(n)))]
    newmesh('SmallJadeGuardSeal_'+str(side),verts,faces,['Pommel03'],smooth=False)
    bezel=[(.565*math.cos(2*math.pi*k/8+math.pi/8),8.56+.71*math.sin(2*math.pi*k/8+math.pi/8)) for k in range(9)]
    chase('GuardSealCopperBezel_'+str(side),bezel,.766,.045,side)
    for sign in [-1,1]:
        # Long-snouted profile dragon heads in each wing, swept horn at the inner end.
        head=[(3.18,9.41),(3.49,9.78),(3.92,10.16),(4.22,10.35),(4.50,10.62),(4.84,10.70),(5.06,10.57),(5.64,10.72),(5.98,10.67),(6.04,10.51),(5.83,10.40),(5.19,10.40),(4.89,10.17),(4.58,9.96),(4.22,9.85),(3.70,9.30)]
        relief('WingDragonProfile_%s_%s'%(side,sign),[(sign*x,z) for x,z in head],.65,.085,side,steps=2)
        horn=[(4.30,10.38),(4.05,10.54),(3.68,10.41),(3.35,10.21),(3.91,10.25),(4.21,10.18)]
        relief('WingSweptHorn_%s_%s'%(side,sign),[(sign*x,z) for x,z in horn],.65,.072,side,steps=2)
        brow=[(4.62,10.57),(4.83,10.61),(5.08,10.50),(4.91,10.43),(4.67,10.47)]
        relief('WingBrow_%s_%s'%(side,sign),[(sign*x,z) for x,z in brow],.735,.037,side,steps=1)
        chase('WingEye_%s_%s'%(side,sign),[(sign*4.72,10.43),(sign*4.88,10.41)],.775,.045,side)
        chase('WingMouth_%s_%s'%(side,sign),[(sign*5.05,10.43),(sign*5.52,10.48),(sign*5.82,10.51)],.738,.035,side)
        whisker=[(4.92,10.30),(5.16,10.17),(5.34,10.21),(5.36,10.37),(5.42,10.32),(5.45,10.16),(5.25,10.08),(5.05,10.10),(4.82,10.20)]
        relief('WingChasedWhisker_%s_%s'%(side,sign),[(sign*x,z) for x,z in whisker],.65,.048,side,steps=2)
        for j in range(3):
            x=3.25+j*.30;z=9.25+j*.20
            sc=[(x-.16,z+.17),(x+.12,z+.18),(x+.18,z),(x,z-.12),(x-.17,z-.01)]
            relief('WingScale_%s_%s_%s'%(side,sign,j),[(sign*a,b) for a,b in sc],.65,.035,side,steps=1)

# Blade-root inlay follows the existing blade planes, replacing the old heart/cloud motif.
width=interp_profile([(8.420434,3.05),(10,3.06),(13,2.78),(18,2.61),(28,2.40),(38,2.18),(48,1.93),(54,1.65),(58,1.25),(61,.8),(63.4,.37),(tip,0)])
thick=interp_profile([(8.420434,.345),(18,.318),(30,.280),(42,.242),(52,.194),(58,.128),(62,.065),(tip,0)])
def bladeheight(x,z):
    u=min(1,abs(x)/max(.00001,width(z)));h=thick(z)*(1-u*.975)
    if u<.055:h=thick(z)*(1-.055*.975*.45-(u/.055)**2*.055*.975*.55)
    if .30<u<.50 and 11<z<32:h-=.022*math.sin(math.pi*(z-11)/21)**2*math.sin(math.pi*(u-.30)/.20)**2
    return max(.00003,h)
for side in [-1,1]:
    for row in range(4):
        z=10.55+row*.55
        for sign in [-1,1]:
            x=sign*(.32+(.18 if row%2 else 0))
            points=[(x-.28,z+.22),(x-.22,z-.02),(x,z-.21),(x+.22,z-.02),(x+.28,z+.22)]
            inlay('ForteDragonScale_%s_%s_%s'%(side,row,sign),points,bladeheight,.043,side)

# Compact silver leaf pommel retains V02 bottom. A ten-sided shallow stone has few broad facets.
pomright=[(0,-7.06),(.83,-7.20),(1.33,-7.92),(1.48,-8.85),(1.40,-9.84),(1.09,-10.94),(.61,-12.18),(0,bottom)]
pomoutline=pomright+[(-x,z) for x,z in reversed(pomright[1:-1])]
pommel=plate('SilverPommelSetting',pomoutline,.63,.055,main='Guard03',edge='Guard03',steps=4)
pom_min=min(v.co.z for v in pommel.data.vertices)
for v in pommel.data.vertices:
    if v.co.z<-12.5:v.co.z+=(bottom-pom_min)*(-12.5-v.co.z)/(-12.5-pom_min)
for side in [-1,1]:
    n=10;verts=[]
    for radius,depth in [(1,.622),(.82,.76),(.44,.82)]:
        for k in range(n):
            a=2*math.pi*k/n+math.pi/2;verts.append((.91*radius*math.cos(a),side*depth,-9.65+1.72*radius*math.sin(a)))
    faces=[]
    for ring in range(2):
        for k in range(n):faces.append((ring*n+k,ring*n+(k+1)%n,(ring+1)*n+(k+1)%n,(ring+1)*n+k))
    faces.append(tuple(range(2*n,3*n)));faces.append(tuple(reversed(range(n))))
    newmesh('FacetedIceJade_'+str(side),verts,faces,['Pommel03'],smooth=False)
    # Fine mechanically continuous copper bezel lies only around the inset stone.
    outline=[(.98*math.cos(2*math.pi*k/10+math.pi/2),-9.65+1.82*math.sin(2*math.pi*k/10+math.pi/2)) for k in range(11)]
    chase('ThinCopperStoneBezel_'+str(side),outline,.636,.055,side)
levels=[(-7.52,.98),(-7.40,1.22),(-7.23,1.26),(-7.06,1.19),(-6.97,1.16)]
n=32;verts=[(r*math.cos(2*math.pi*k/n),r*math.sin(2*math.pi*k/n),z) for z,r in levels for k in range(n)]
faces=[]
for j in range(len(levels)-1):
    for k in range(n):faces.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
faces.extend([tuple(reversed(range(n))),tuple((len(levels)-1)*n+i for i in range(n))])
newmesh('PommelNeckFerrule',verts,faces,['Guard03'])

# Triangulate authored fittings before deterministic box projection. Original V02 blade/grip stays intact.
for ob in parts:
    if ob==original:continue
    bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free()
    me=ob.data;me.calc_loop_triangles()
    for i in range(2):me.uv_layers.new(name='UVChannel_'+str(i))
    for p in me.polygons:
        a,b,c=[me.vertices[i].co for i in p.vertices]
        candidates=[]
        for axes in [(0,2),(1,2),(0,1)]:
            u,v=axes;area=abs((b[u]-a[u])*(c[v]-a[v])-(b[v]-a[v])*(c[u]-a[u]))*.5;candidates.append((area,axes))
        area,axes=max(candidates,key=lambda x:x[0]);assert area>1e-10,(ob.name,p.index,area)
        for layer in me.uv_layers:
            for loop in p.loop_indices:
                co=me.vertices[me.loops[loop].vertex_index].co;layer.data[loop].uv=(co[axes[0]]*.25,co[axes[1]]*.25)

bpy.ops.object.select_all(action='DESELECT')
for ob in parts:ob.select_set(True)
bpy.context.view_layer.objects.active=original;bpy.ops.object.join();result=bpy.context.object
result.name=NAME;result.data.name=NAME+'_Mesh';result.matrix_world=Matrix.Identity(4)
old=[m.name for m in result.data.materials];indices=[order.index(old[p.material_index]) for p in result.data.polygons]
result.data.materials.clear()
for s in order:result.data.materials.append(mats[s])
for p,i in zip(result.data.polygons,indices):p.material_index=i
result.data.calc_loop_triangles();triangles=len(result.data.loop_triangles);assert triangles<=24000,triangles
bounds=[[min(v.co[i] for v in result.data.vertices) for i in range(3)],[max(v.co[i] for v in result.data.vertices) for i in range(3)]]
assert abs(bounds[1][2]-tip)<.001 and abs(bounds[0][2]-bottom)<.001,bounds
assert len(result.data.uv_layers)==2
for layer in result.data.uv_layers:
    for t in result.data.loop_triangles:
        a,b,c=[layer.data[l].uv for l in t.loops];area=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5
        assert area>1e-10,(layer.name,t.polygon_index,order[t.material_index],area)
result['axis_contract']='centimeters; tip +Z; preserved V02 grip geometry, UVs and pivot';result['revision']='V03 chased dragon silver and faceted ice jade'
fbx=OUT/(NAME+'.fbx');blend=OUT/(NAME+'.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',bake_anim=False,path_mode='STRIP',use_custom_props=True,use_mesh_modifiers=True)
report={'state':'built','source_blend':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'output_fbx':str(fbx),'output_blend':str(blend),'fbx_sha256':hashlib.sha256(fbx.read_bytes()).hexdigest(),'blend_sha256':hashlib.sha256(blend.read_bytes()).hexdigest(),'triangles_before':13580,'triangles_after':triangles,'vertices_after':len(result.data.vertices),'triangles_by_material':{s:sum(1 for t in result.data.loop_triangles if order[t.material_index]==s) for s in order},'bounds_cm':{'min':bounds[0],'max':bounds[1]},'blade_sample_cm':[[0,0,8.42],[0,0,36.68],[0,0,64.94]],'slot_order':order,'material_contract':contract,'uv_layers':[l.name for l in result.data.uv_layers],'changes':['V02 physical blade and grip retained, including repaired UVs','Thin rounded old-silver guard with shallow long-snouted dragon relief in both wings; small central ice-jade seal','Mirrored profile dragons with swept horns, solid shallow whiskers and restrained scales','Dragon scales replace heart/cloud decoration at blade root','Opaque ten-sided ice-blue jade stone in metal pommel setting','Nine frozen PBR maps shared with UE, DirectX green channel inverted in Blender preview only'],'license':'Derived from user project sword A and original local procedural geometry; no external provider assets','limits':'Static offline build. UE import and VR acceptance owned by integration.'}
(OUT/'AssetGeometryReport.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print('V03_ASSET_EXPORTED',json.dumps({'triangles':triangles,'hash':report['fbx_sha256'],'bounds':report['bounds_cm']}),flush=True)

scene.render.engine='BLENDER_EEVEE';scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.world.use_nodes=True;bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.055,.065,.082,1);bg.inputs['Strength'].default_value=.45
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
def point(o,t):o.rotation_euler=(Vector(t)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(12,-140,24));cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam
for pos,power,sx,sy in [((-22,-30,52),105000,12,85),((28,-18,35),55000,8,70),((8,25,50),125000,20,70)]:
    bpy.ops.object.light_add(type='AREA',location=pos);l=bpy.context.object;l.data.energy=power;l.data.shape='RECTANGLE';l.data.size=sx;l.data.size_y=sy;point(l,(0,0,28))
for filename,loc,target,scale,res in [('Detail_Forte',(5,-70,13),(0,0,10),17,(1700,1300)),('Detail_Whole',(12,-140,25),(0,0,25.6),84,(1100,1900)),('Detail_Pommel',(5,-48,-7),(0,0,-8.5),11,(1300,1500))]:
    cam.location=loc;point(cam,target);cam.data.ortho_scale=scale;scene.render.resolution_x=res[0];scene.render.resolution_y=res[1];scene.render.filepath=str(OUT/(filename+'.png'));bpy.ops.render.render(write_still=True)
print('V03_PREVIEWS_COMPLETE',flush=True)
