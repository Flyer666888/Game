"""Bake original shield palette plus restrained material wear on seamless tiles.

Run Blender background --disable-autoexec with the copied original blend. This
script writes only its own directory and never saves or modifies the source.
The material preview uses new geometry, without loading game code or input.
"""
import bpy
import json
import hashlib
import math
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = Path(bpy.data.filepath).resolve()
source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
source_mats = sorted([m for m in bpy.data.materials if m.use_nodes], key=lambda m: m.name)
assert len(source_mats) == 8
specs = [
    ('bronze', 0, 12, .36, .54, .90, .22, .22),
    ('worn_bronze', 1, 12, .25, .43, .94, .10, .17),
    ('dark_bronze', 2, 12, .42, .60, .85, .28, .20),
    ('jade', 3, 12, .30, .44, .02, .00, .09),
    ('patina', 4, 12, .56, .73, .08, .12, .15),
    ('leather', 5, 5, .53, .70, .00, .00, .31),
    ('brass', 6, 12, .27, .43, .93, .08, .14),
]
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 4
scene.cycles.use_denoising = False
scene.render.bake.margin = 0
scene.render.bake.use_clear = True
scene.render.bake.normal_space = 'TANGENT'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1
bpy.ops.mesh.primitive_plane_add(size=0.12)
plane = bpy.context.object
plane.name = 'Temporary PBR bake tile'
# UVs from Blender plane operator occupy exactly [0,1] in both axes.
report = {'source': str(SOURCE), 'source_sha256': source_sha,
          'blender_version': bpy.app.version_string,
          'profiles': {}, 'material_profile_by_ue_name': {},
          'notes': [
              'Original 7 Noise/ColorRamp palettes copied, surface nodes restored and enhanced.',
              '4D toroidal procedural coordinates repeat continuously at every tile boundary.',
              'BaseColor is sRGB; ORM is linear R=micro cavity AO, G=roughness, B=metallic.',
              'Normal is linear OpenGL +Y tangent-space; UE importer must enable FlipGreenChannel.',
              'Local micro cavity AO only: mesh occlusion is left to UE scene shading.',
              'Original face reference BaseColor/Normal and mesh are unchanged.',
              'Jade and leather have near-zero/zero metallic; aged copper oxide reduces metal response.',
          ]}
profiles = []

def mathnode(nt, op, a, b=None, name=''):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op
    n.name = name or op
    for index, value in enumerate((a, b)):
        if value is None: continue
        if hasattr(value, 'node'): nt.links.new(value, n.inputs[index])
        else: n.inputs[index].default_value = value
    return n.outputs[0]

def ramp(nt, value, stops, name):
    n = nt.nodes.new('ShaderNodeValToRGB'); n.name = name
    n.color_ramp.interpolation = 'EASE'
    while len(n.color_ramp.elements) > 2:
        n.color_ramp.elements.remove(n.color_ramp.elements[-1])
    for i, (pos, col) in enumerate(stops):
        e = n.color_ramp.elements[i] if i < 2 else n.color_ramp.elements.new(pos)
        e.position = pos; e.color = tuple(col[:3]) + (1.0,)
    nt.links.new(value, n.inputs[0])
    return n.outputs['Color']

def mix(nt, factor, a, b, name):
    n = nt.nodes.new('ShaderNodeMixRGB'); n.blend_type = 'MIX'; n.name = name
    for i, v in enumerate((factor, a, b)):
        if hasattr(v, 'node'): nt.links.new(v, n.inputs[i])
        else: n.inputs[i].default_value = v
    return n.outputs[0]

def make_torus(nt, uv):
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(uv, sep.inputs[0])
    u = mathnode(nt, 'MULTIPLY', sep.outputs['X'], math.tau)
    v = mathnode(nt, 'MULTIPLY', sep.outputs['Y'], math.tau)
    cu = mathnode(nt, 'COSINE', u); su = mathnode(nt, 'SINE', u)
    cv = mathnode(nt, 'COSINE', v); sv = mathnode(nt, 'SINE', v)
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    for sock, val in zip(comb.inputs, (cu, su, cv)): nt.links.new(val, sock)
    return comb.outputs[0], sv, sep.outputs['X'], sep.outputs['Y']

def noise(nt, torus, scale, detail, name):
    n = nt.nodes.new('ShaderNodeTexNoise'); n.name = name
    n.noise_dimensions = '4D'
    nt.links.new(torus[0], n.inputs['Vector']); nt.links.new(torus[1], n.inputs['W'])
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = .62
    return n.outputs['Fac']

def sampled_height(nt, uv, key, label):
    """Same seamless height evaluated at neighboring coordinates for bake normals."""
    torus=make_torus(nt,uv)
    broad=noise(nt,torus,1.3,4.0,label+' broad')
    grain=noise(nt,torus,25 if key=='leather' else 95,2.4,label+' grain')
    fine=noise(nt,torus,210,1.5,label+' fine')
    weather=noise(nt,torus,3.7,4.5,label+' weather')
    warped=mathnode(nt,'ADD',torus[2],mathnode(nt,'MULTIPLY',broad,.022))
    stripe=mathnode(nt,'SINE',mathnode(nt,'MULTIPLY',warped,math.tau*137))
    line=mathnode(nt,'GREATER_THAN',stripe,.994)
    gate=ramp(nt,weather,[(.33,(0,0,0)),(.58,(.5,.5,.5)),(.75,(1,1,1))],label+' scratch gate')
    scratches=mathnode(nt,'MULTIPLY',line,gate)
    if key in ('jade','leather'):
        scratches=mathnode(nt,'MULTIPLY',scratches,.10 if key=='jade' else .13)
    h=mathnode(nt,'ADD',mathnode(nt,'MULTIPLY',grain,.74),mathnode(nt,'MULTIPLY',fine,.26))
    return mathnode(nt,'SUBTRACT',h,mathnode(nt,'MULTIPLY',scratches,.27))

def tangent_normal_from_height(nt, uv, key, tile_cm, distance, strength):
    delta=.5/1024
    neighbors=[]
    for label,offset in [('X+', (delta,0,0)),('X-',(-delta,0,0)),
                         ('Y+', (0,delta,0)),('Y-',(0,-delta,0))]:
        add=nt.nodes.new('ShaderNodeVectorMath'); add.operation='ADD'
        nt.links.new(uv,add.inputs[0]); add.inputs[1].default_value=offset
        neighbors.append(sampled_height(nt,add.outputs['Vector'],key,label))
    scale=-distance*strength/(2*delta*(tile_cm/100))
    dx=mathnode(nt,'MULTIPLY',mathnode(nt,'SUBTRACT',neighbors[0],neighbors[1]),scale)
    dy=mathnode(nt,'MULTIPLY',mathnode(nt,'SUBTRACT',neighbors[2],neighbors[3]),scale)
    c=nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(dx,c.inputs['X']); nt.links.new(dy,c.inputs['Y']); c.inputs['Z'].default_value=1
    norm=nt.nodes.new('ShaderNodeVectorMath'); norm.operation='NORMALIZE'; nt.links.new(c.outputs[0],norm.inputs[0])
    half=nt.nodes.new('ShaderNodeVectorMath'); half.operation='SCALE'; half.inputs['Scale'].default_value=.5
    nt.links.new(norm.outputs[0],half.inputs[0])
    add=nt.nodes.new('ShaderNodeVectorMath'); add.operation='ADD'; add.inputs[1].default_value=(.5,.5,.5)
    nt.links.new(half.outputs[0],add.inputs[0]); return add.outputs['Vector']

def image_save_bake(material, socket, name, color_space):
    nt = material.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    target = bpy.data.images.new(name, width=1024, height=1024, alpha=False, float_buffer=False)
    target.colorspace_settings.name = color_space
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = target; tn.name = 'Bake target '+name
    for node in nt.nodes: node.select = False
    tn.select = True; nt.nodes.active = tn
    temporary_nodes = []
    if socket is None:
        # Cycles normal bake stores geometric normals, excluding shader bump.
        # On this identity XY plane world X/Y/Z exactly equal UV tangent X/Y/Z.
        # Encode the evaluated procedural bump normal explicitly without light.
        bump = next(n for n in nt.nodes if n.type == 'BUMP')
        scale = nt.nodes.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'
        scale.inputs['Scale'].default_value=.5; nt.links.new(bump.outputs['Normal'], scale.inputs[0])
        add = nt.nodes.new('ShaderNodeVectorMath'); add.operation = 'ADD'
        nt.links.new(scale.outputs['Vector'], add.inputs[0]); add.inputs[1].default_value=(.5,.5,.5)
        socket=add.outputs['Vector']; temporary_nodes.extend([scale,add])
    emit = nt.nodes.new('ShaderNodeEmission')
    emit.inputs['Strength'].default_value = 1
    nt.links.new(socket, emit.inputs['Color']); nt.links.new(emit.outputs[0], out.inputs['Surface'])
    bpy.ops.object.bake(type='EMIT', use_clear=True, margin=0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    nt.nodes.remove(emit)
    for temporary in temporary_nodes: nt.nodes.remove(temporary)
    target.filepath_raw = str(OUT / (name+'.png')); target.file_format = 'PNG'; target.save()
    nt.nodes.remove(tn)
    return str((OUT/(name+'.png')).resolve())

for key, slot, tile_cm, rough_lo, rough_hi, metal, patina_amount, bump_strength in specs:
    source = source_mats[slot]
    material = source.copy(); material.name = 'Realistic '+key
    nt = material.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    original_ramp = next(n for n in nt.nodes if n.type == 'VALTORGB')
    original_bump = next(n for n in nt.nodes if n.type == 'BUMP')
    original_noise = next(n for n in nt.nodes if n.type == 'TEX_NOISE')
    row_source = {'name': source.name,
                  'noise_scale': original_noise.inputs['Scale'].default_value,
                  'noise_detail': original_noise.inputs['Detail'].default_value,
                  'bump_strength': original_bump.inputs['Strength'].default_value,
                  'bump_distance': original_bump.inputs['Distance'].default_value,
                  'color_ramp': [{'position': e.position, 'color': list(e.color)} for e in original_ramp.color_ramp.elements]}
    uv = nt.nodes.new('ShaderNodeTexCoord').outputs['UV']
    torus = make_torus(nt, uv)
    broad = noise(nt, torus, 1.3, 4.0, 'Seamless original surface variation')
    grain = noise(nt, torus, 95 if key != 'leather' else 25, 2.4, 'Microscopic pores')
    weather = noise(nt, torus, 3.7, 4.5, 'Gentle aged oxide islands')
    fine = noise(nt, torus, 210, 1.5, 'Fine finish micrograin')
    nt.links.new(broad, original_ramp.inputs[0])
    nt.nodes.remove(original_noise)
    # The worn metal retains its original palette. Only oxide islands introduce green.
    oxide = ramp(nt, weather, [(0.54,(0,0,0)),(.70,(patina_amount,)*3),(.86,(patina_amount,)*3)], 'Restrained patina mask')
    bronze_color = mix(nt, oxide, original_ramp.outputs['Color'], (.044,.12,.078,1), 'Copper oxide islands')
    base = bronze_color
    # Fine, broken directional hairlines use integer UV periods, so seams remain exact.
    warped_u = mathnode(nt, 'ADD', torus[2], mathnode(nt,'MULTIPLY',broad,.022))
    stripe = mathnode(nt, 'SINE', mathnode(nt,'MULTIPLY',warped_u,math.tau*137))
    line = mathnode(nt, 'GREATER_THAN', stripe, .994)
    gate = ramp(nt, weather, [(.33,(0,0,0)),(.58,(.5,.5,.5)),(.75,(1,1,1))], 'Broken scratch length')
    scratches = mathnode(nt,'MULTIPLY',line,gate)
    if key == 'leather':
        # Organic grain, tiny pores and pigment variation; no deep cracking.
        scratches = mathnode(nt,'MULTIPLY',scratches,.13)
        leather_grain = ramp(nt,grain,[(.25,(.76,.76,.76)),(.70,(1.1,1.1,1.1))], 'Leather pigment grain')
        mult = nt.nodes.new('ShaderNodeMixRGB'); mult.blend_type='MULTIPLY'; mult.inputs[0].default_value=1
        nt.links.new(base,mult.inputs[1]); nt.links.new(leather_grain,mult.inputs[2]); base=mult.outputs[0]
    elif key == 'jade':
        scratches = mathnode(nt,'MULTIPLY',scratches,.10)
    else:
        # Polished hairlines remain close to the base color, no white painted scratches.
        base = mix(nt, mathnode(nt,'MULTIPLY',scratches,.18), base,
                   tuple(original_ramp.color_ramp.elements[-1].color), 'Subtle burnished scratch color')
    nt.links.new(base,bsdf.inputs['Base Color'])
    rough = ramp(nt,grain,[(.18,(rough_lo,)*3),(.82,(rough_hi,)*3)], 'Physical roughness variation')
    rough = mix(nt, oxide, rough, (.76,.76,.76,1), 'Rough oxide finish')
    nt.links.new(rough,bsdf.inputs['Roughness'])
    metallic = mix(nt, oxide, (metal,metal,metal,1), (.08,.08,.08,1), 'Metal exposed under oxide')
    nt.links.new(metallic,bsdf.inputs['Metallic'])
    bsdf.inputs['Specular IOR Level'].default_value = .5
    height = mathnode(nt,'ADD',mathnode(nt,'MULTIPLY',grain,.74),mathnode(nt,'MULTIPLY',fine,.26))
    height = mathnode(nt,'SUBTRACT',height,mathnode(nt,'MULTIPLY',scratches,.27))
    nt.links.new(height,original_bump.inputs['Height'])
    original_bump.inputs['Strength'].default_value = bump_strength
    normal_distance=.00030 if key=='leather' else (.00008 if key=='jade' else .00020)
    original_bump.inputs['Distance'].default_value = normal_distance
    nt.links.new(original_bump.outputs[0],bsdf.inputs['Normal'])
    # ORM packs micro cavity only. It adds mild shading to pores without painting shadows.
    ao = ramp(nt,grain,[(.17,(.90,.90,.90)),(.50,(1,1,1))], 'Micro cavity occlusion')
    pack = nt.nodes.new('ShaderNodeCombineColor'); pack.mode='RGB'; pack.name='Linear ORM pack'
    nt.links.new(ao,pack.inputs['Red']); nt.links.new(rough,pack.inputs['Green']); nt.links.new(metallic,pack.inputs['Blue'])
    plane.data.materials.clear(); plane.data.materials.append(material)
    for vertex in plane.data.vertices:
        vertex.co.x = math.copysign(tile_cm / 200.0, vertex.co.x)
        vertex.co.y = math.copysign(tile_cm / 200.0, vertex.co.y)
    bpy.context.view_layer.objects.active = plane; plane.select_set(True)
    paths = {
        'base_color': image_save_bake(material,base,'T_DragonShield_'+key+'_BaseColor','sRGB'),
        'orm': image_save_bake(material,pack.outputs[0],'T_DragonShield_'+key+'_ORM','Non-Color'),
        'normal': image_save_bake(material,tangent_normal_from_height(nt,uv,key,tile_cm,normal_distance,bump_strength),
                                  'T_DragonShield_'+key+'_Normal','Non-Color')}
    paths.update({'tile_size_cm':tile_cm, 'normal_convention':'OpenGL', 'source_material':row_source,
                  'roughness_range':[rough_lo,rough_hi], 'base_metallic':metal,
                  'normal_strength_ue':1.0,
                  'normal_method':'Central UV finite differences of seamless procedural height, physical tile scale; +Y OpenGL',
                  'height_distance_m':normal_distance, 'height_strength':bump_strength})
    report['profiles'][key]=paths
    report['material_profile_by_ue_name']['M_DragonShield_%02d'%slot]=key
    profiles.append((key,material))
    print('REALISTIC_PROFILE_SAVED',key,flush=True)

# A PBR material authoring preview: new spheres are not game actors or test input.
plane.hide_render = True
for index,(key,material) in enumerate(profiles):
    x=(index%4-1.5)*.36; z=(1-index//4)*.36
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96,ring_count=64,radius=.14,location=(x,0,z))
    obj=bpy.context.object; obj.name='Surface preview '+key
    obj.data.materials.append(material)
    for poly in obj.data.polygons: poly.use_smooth=True
world=bpy.data.worlds.new('Realistic surface preview world'); scene.world=world; world.use_nodes=True
background=next(n for n in world.node_tree.nodes if n.type=='BACKGROUND')
background.inputs['Color'].default_value=(.07,.08,.10,1)
background.inputs['Strength'].default_value=.35
for name,pos,power,size,color in [
    ('Broad neutral softbox',(-.8,-1.1,1.25),90,1.0,(1,1,1)),
    ('Warm grazing edge',(1.2,-.5,.8),60,.7,(1,.85,.7)),
    ('Cool rim',(0,.8,1.1),100,.8,(.72,.83,1))]:
    data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.shape='DISK'; data.size=size; data.color=color
    obj=bpy.data.objects.new(name,data); scene.collection.objects.link(obj); obj.location=pos
    obj.rotation_euler=(Vector((0,0,.2))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Material preview camera'); camera=bpy.data.objects.new(data.name,data); scene.collection.objects.link(camera)
camera.location=(0,-2.4,.2); camera.rotation_euler=(Vector((0,0,.2))-camera.location).to_track_quat('-Z','Y').to_euler()
data.type='ORTHO'; data.ortho_scale=1.52; scene.camera=camera
scene.render.resolution_x=1400; scene.render.resolution_y=760; scene.render.resolution_percentage=100
scene.cycles.samples=32; scene.cycles.use_denoising=True
scene.view_settings.view_transform='AgX'
scene.render.filepath=str(OUT/'SurfaceMaterialPreview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'RealisticSurface_Authoring.blend'))
bpy.ops.render.render(write_still=True)
report['preview']=str((OUT/'SurfaceMaterialPreview.png').resolve())
report['authoring_blend']=str((OUT/'RealisticSurface_Authoring.blend').resolve())
report['source_sha256_after']=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert report['source_sha256_after']==source_sha
(OUT/'RealisticSurface.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('REALISTIC_SURFACE_FINISHED',flush=True)
