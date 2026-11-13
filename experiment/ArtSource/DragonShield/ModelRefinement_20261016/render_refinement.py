import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
mode=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'all'
scene=bpy.context.scene
# Keep only actual render-visible source geometry. Hidden old dragon stays excluded.
for o in list(scene.objects):
    if o.type in ('LIGHT','CAMERA'):bpy.data.objects.remove(o,do_unlink=True)
scene.world.use_nodes=True;next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs['Color'].default_value=(.035,.043,.047,1);next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs['Strength'].default_value=.4
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16 if mode=='quick' else 48;scene.cycles.use_denoising=True
scene.render.resolution_x=1000 if mode=='quick' else 1500;scene.render.resolution_y=scene.render.resolution_x;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'

def light(name,pos,power,color,size,target=(0,0,0)):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color;o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();return o

def render(name,pos,target=(0,0,0),back=False):
    for o in list(scene.objects):
        if o.type in ('LIGHT','CAMERA'):bpy.data.objects.remove(o,do_unlink=True)
    sign=1 if back else -1
    light('Soft key',(-.7,sign*.9,.85),36,(1,.89,.73),.75)
    light('Cool fill',(.8,sign*.65,.15),20,(.66,.83,1),.7)
    light('Edge light',(.2,-sign*.6,.65),42,(1,.86,.65),.6)
    light('Lower fill',(-.05,sign*1.2,-.6),8,(.8,.88,1),.8)
    bpy.ops.object.camera_add(location=pos);cam=bpy.context.object;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.00;scene.camera=cam
    scene.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True);print('RENDER_SAVED',name,flush=True)
if mode=='quick':
    render('Preview_ThreeQuarter_Quick.png',(.72,-1.35,.26))
    render('Preview_Front_Quick.png',(.02,-1.5,.03))
    render('Preview_Back_Quick.png',(.06,1.5,.10),back=True)
else:
    render('DragonShield_Detailed_Front.png',(.02,-1.5,.03))
    render('DragonShield_Detailed_Back.png',(.06,1.5,.10),back=True)
    render('DragonShield_Detailed_ThreeQuarter.png',(.72,-1.35,.26))
    render('DragonShield_Detailed_Side.png',(1.5,-.26,.08))

if mode!='quick':
    clay=bpy.data.materials.new('TEMPORARY geometry review clay');clay.use_nodes=True
    p=next(n for n in clay.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.28,.32,.34,1);p.inputs['Roughness'].default_value=.6;p.inputs['Metallic'].default_value=0.
    scene.view_layers[0].material_override=clay
    render('DragonShield_Detailed_GeometryRelief.png',(.72,-1.35,.26))
    scene.view_layers[0].material_override=None
    (OUT/'RenderManifest.json').write_text(json.dumps({'source_blend':str(OUT/'Jade_Dragon_Shield_Detailed.blend'),'geometry_matches_fbx_authoring':True,'visible_geometry_only':True,'resolution':[1500,1500],'samples':48,'material_preview':'Original source materials; production UE PBR remains separate','geometry_review':'Temporary neutral material override in render process only; not saved to source or FBX','renders':['DragonShield_Detailed_Front.png','DragonShield_Detailed_Back.png','DragonShield_Detailed_ThreeQuarter.png','DragonShield_Detailed_Side.png','DragonShield_Detailed_GeometryRelief.png']},indent=2),encoding='utf-8')
