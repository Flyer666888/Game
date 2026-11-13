"""Original jade wine flask, centimetre-sized, portable source + fresh FBX validation."""
import bpy, bmesh, math, json, hashlib
from pathlib import Path
from mathutils import Vector
ROOT = Path('D:/game design/experiment')
OUT = ROOT/'ArtSource/Pickups/HealingWine1111'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=.01
contract={
 'JadeGlaze': {'color': [.055,.23,.17], 'roughness':.27,'metallic':.03},
 'AntiqueGold': {'color':[.56,.32,.075], 'roughness':.32,'metallic':.72},
 'CinnabarCloth': {'color':[.30,.014,.025], 'roughness':.83,'metallic':0},
 'RicePaper': {'color':[.78,.65,.39], 'roughness':.78,'metallic':0},
}
mats={}
for name,p in contract.items():
    m=bpy.data.materials.new(name); m.diffuse_color=(*p['color'],1);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*p['color'],1)
    bs.inputs['Roughness'].default_value=p['roughness'];bs.inputs['Metallic'].default_value=p['metallic']
    mats[name]=m
parts=[]
def lathe(name, profile, mat, segments=32):
    verts=[(r*math.cos(i*math.tau/segments),r*math.sin(i*math.tau/segments),z) for z,r in profile for i in range(segments)]
    faces=[]
    for j in range(len(profile)-1):
        for i in range(segments):faces.append((j*segments+i,j*segments+(i+1)%segments,(j+1)*segments+(i+1)%segments,(j+1)*segments+i))
    faces += [tuple(reversed(range(segments))),tuple((len(profile)-1)*segments+i for i in range(segments))]
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.materials.append(mats[mat]);me.update()
    ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob)
    for p in me.polygons:p.use_smooth=len(p.vertices)==4
    parts.append(ob);return ob
lathe('WineVessel',[(0,4.7),(.35,5.4),(1.2,5.8),(4,7.0),(8,8.1),(12,8.4),(16,7.8),(19.3,6.5),(21.2,3.6),(22.1,2.35),(26,2.35),(26.4,2.9),(27.1,2.9),(27.35,2.5)],'JadeGlaze')
lathe('FootBand',[(.25,5.48),(.75,5.72),(1.1,5.85)],'AntiqueGold')
lathe('NeckCord',[(24.2,2.48),(24.45,2.65),(24.8,2.65),(25.0,2.48)],'AntiqueGold')
lathe('Stopper',[(27.1,2.45),(28.4,2.65),(28.65,2.25)],'CinnabarCloth',24)
# Folded red silk over the neck, visibly different from an energy orb.
lathe('SilkSkirt',[(25.4,2.6),(26.3,3.25),(27.3,3.0),(28.2,2.6)],'CinnabarCloth',12)
def cube(name,location,scale,material,bevel=.08):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location);ob=bpy.context.object;ob.name=name;ob.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    ob.data.materials.append(mats[material])
    if bevel:
        mod=ob.modifiers.new('Soft edges','BEVEL');mod.width=bevel;mod.segments=2
        bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_apply(modifier=mod.name)
    parts.append(ob);return ob
# Front paper seal + gold frame. Bottle faces -Y in the preview.
cube('SealGoldFrame',(0,-8.19,11.0),(5.5,.16,7.3),'AntiqueGold')
cube('SealPaper',(0,-8.31,11.0),(4.95,.12,6.8),'RicePaper')
cube('RedSealStamp',(0,-8.43,10.9),(3.3,.10,3.8),'CinnabarCloth',.03)
# Stylized wine-rune strokes are authored geometry, no external font/texture.
for x,z,sx,sz in [(-.85,11.9,.28,1.6),(-.85,10.45,.28,.45),(.35,12.1,1.5,.25),(.35,11.1,1.5,.25),(.35,9.8,1.5,.25),(-.23,10.9,.23,2.2),(.94,10.9,.23,2.2)]:
    cube('RuneStroke',(x,-8.51,z),(sx,.07,sz),'RicePaper',.015)
for side in [-1,1]:
    tail=cube('SilkRibbon',(side*1.7,-2.6,21.2),(1.1,.22,6.0),'CinnabarCloth',.025)
    tail.rotation_euler.y=side*.2
bpy.ops.object.select_all(action='DESELECT')
for ob in parts:ob.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join()
bottle=bpy.context.object;bottle.name='SM_HealingWineV01'
# Triangulate and generate two finite UV channels.
bm=bmesh.new();bm.from_mesh(bottle.data);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(bottle.data);bm.free()
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
bottle.data.uv_layers.new(name='LightmapUV',do_init=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SM_HealingWineV01.blend'))
fbx=OUT/'SM_HealingWineV01.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',bake_anim=False,path_mode='STRIP')
bpy.ops.export_scene.gltf(filepath=str(OUT/'SM_HealingWineV01.glb'),export_format='GLB',use_selection=True)
bottle.data.calc_loop_triangles()
report={'state':'authored','name':bottle.name,'license':'Original procedural geometry authored in this project; no downloaded assets','triangles':len(bottle.data.loop_triangles),'materials':contract,'bounds_cm':[[min(v.co[i] for v in bottle.data.vertices) for i in range(3)],[max(v.co[i] for v in bottle.data.vertices) for i in range(3)]],'fbx_sha256':hashlib.sha256(fbx.read_bytes()).hexdigest()}
assert 500<report['triangles']<10000
# Render a standalone review image.
scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=900;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Studio');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.06,.075,.085,1)
def aim(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(39,-66,36));cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=42;aim(cam,(0,0,13));scene.camera=cam
for pos,power,size in [((-22,-34,52),45000,26),((35,-12,40),25000,20),((8,26,45),55000,22)]:
    bpy.ops.object.light_add(type='AREA',location=pos);l=bpy.context.object;l.data.energy=power;l.data.size=size;aim(l,(0,0,13))
scene.render.filepath=str(OUT/'HealingWine_preview.png');bpy.ops.render.render(write_still=True)
# Fresh FBX readback validates the exported bytes, not just authoring state.
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(fbx),use_custom_normals=True)
obj=next(o for o in bpy.data.objects if o.type=='MESH');obj.data.calc_loop_triangles()
points=[obj.matrix_world@v.co*100 for v in obj.data.vertices]
height=max(p.z for p in points)-min(p.z for p in points)
assert 28<height<30, height
assert all(math.isfinite(x) for p in points for x in p)
assert len(obj.data.uv_layers)>=2
report.update(state='passed',fresh_fbx_height_cm=height,preview='HealingWine_preview.png')
(OUT/'AssetReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('HEALING_WINE_VALIDATED',report['triangles'],height,flush=True)
