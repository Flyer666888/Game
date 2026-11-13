import bpy, json, math
from pathlib import Path
from mathutils import Vector
ROOT=Path('D:/game design/experiment')
OUT=ROOT/'ArtSource/WeaponReview/SelectedA_DetailV01'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'ArtSource/WeaponReview/Over9000/SelectedA/SM_PlayerSword_A.blend'))
obj=next(o for o in bpy.data.objects if o.type=='MESH')
data={'materials':[m.name for m in obj.data.materials], 'vertices':[],'polygons':[]}
used=set()
for p in obj.data.polygons:
    if p.material_index==0:
        data['polygons'].append(list(p.vertices));used.update(p.vertices)
data['vertices']=[{'i':i,'co':list(obj.data.vertices[i].co)} for i in sorted(used)]
(OUT/'SourceBladeInspection.json').write_text(json.dumps(data,indent=2))
scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=800;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.color=(.12,.12,.12)
for m in obj.data.materials:
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(.48,.50,.53,1) if m.name=='Blade03' else (.29,.19,.055,1)
    p.inputs['Metallic'].default_value=.75
    p.inputs['Roughness'].default_value=.3
def point(o,t):o.rotation_euler=(Vector(t)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-110,27));cam=bpy.context.object;point(cam,(0,0,27));cam.data.type='ORTHO';cam.data.ortho_scale=85;scene.camera=cam
for pos,power,size in [((-25,-40,55),1000,40),((25,-15,25),800,35),((10,20,65),1500,25)]:
    bpy.ops.object.light_add(type='AREA',location=pos);l=bpy.context.object;l.data.energy=power;l.data.shape='DISK';l.data.size=size;point(l,(0,0,25))
scene.render.filepath=str(OUT/'SourceFront.png');bpy.ops.render.render(write_still=True)
cam.location=(70,-90,28);point(cam,(0,0,27));scene.render.filepath=str(OUT/'SourceAngled.png');bpy.ops.render.render(write_still=True)
print('SOURCE_INSPECTION_DONE')
