import bpy, json, math, re, sys
from pathlib import Path
from mathutils import Vector, Matrix
ROOT=Path(__file__).resolve().parent
KIND=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'blade'
SETTINGS={'blade':(8,0.27,1.26,2700,1600,'BLADES / 01-08','BladeShapes.png'),'crossguard':(4,0.37,0.29,2300,1700,'CROSSGUARDS / 01-11','CrossguardCatalog.png'),'hilt':(4,0.24,0.32,1900,2000,'GRIPS / 01-11','HiltCatalog.png'),'pommel':(5,0.22,0.25,2400,1800,'POMMELS / 01-14','PommelCatalog.png')}
cols,cw,ch,rx,ry,title,filename=SETTINGS[KIND]
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=24; scene.cycles.use_denoising=True
scene.render.resolution_x=rx; scene.render.resolution_y=ry; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
scene.world.color=(0.12,0.12,0.12); scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.16,.19,.23,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.65

def mat(name,color,metallic=0,rough=.4):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1); p.inputs['Metallic'].default_value=metallic; p.inputs['Roughness'].default_value=rough
    return m
steel=mat('Neutral steel - geometry review only',(.46,.49,.53),.72,.32)
back=mat('Review slate',(.021,.029,.041),0,.9)
fontmat=mat('Review label',(.7,.78,.85),0,.7)
p=fontmat.node_tree.nodes.get('Principled BSDF'); p.inputs['Emission Color'].default_value=(.7,.78,.85,1);p.inputs['Emission Strength'].default_value=.6
files=sorted([p for p in ROOT.glob('*.fbx') if f'_{KIND}_' in p.stem.lower()],key=lambda p:int(re.search(r'(\d+)$',p.stem).group(1)))
rows=math.ceil(len(files)/cols); width=cols*cw; height=rows*ch
center=Vector((0,0,height*.5))
bpy.ops.object.camera_add(location=center+Vector((4,-math.tan(math.radians(6))*4,0)))
camera=bpy.context.object; camera.name='Catalog Camera'; camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler(); camera.data.type='ORTHO'; scene.camera=camera
camera.data.ortho_scale=max(width+.2,(height+.36)*(rx/ry))
camera.data.lens=45

def label(text,y,z,size=.025):
    c=bpy.data.curves.new('label','FONT');c.body=text;c.align_x='CENTER';c.size=size;c.extrude=0
    o=bpy.data.objects.new(text,c);scene.collection.objects.link(o);o.location=(.09,y,z);o.rotation_euler=camera.rotation_euler;c.materials.append(fontmat)

def light(name,pos,power,size,color):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=center+Vector(pos);o.rotation_euler=(center-o.location).to_track_quat('-Z','Y').to_euler()
light('Key softbox',(2,-1.8,2.2),450,2.3,(1,.96,.90))
light('Fill softbox',(1.6,2.1,.6),350,1.8,(.85,.91,1))
light('Top rim',(-.2,.2,2),400,1.5,(1,1,1))
bpy.ops.mesh.primitive_plane_add(size=2,location=(-.16,0,height*.5),rotation=(0,math.pi*.5,0));o=bpy.context.object;o.name='Backdrop';o.scale=(5,5,5);o.data.materials.append(back)
records=[]
for i,path in enumerate(files):
    before=set(bpy.data.objects);bpy.ops.import_scene.fbx(filepath=str(path),use_custom_normals=True)
    imported=[o for o in bpy.data.objects if o not in before]
    meshes=[o for o in imported if o.type=='MESH' and not o.name.upper().startswith(('UCX_','UBX_','USP_','UCP_'))]
    for o in imported:
        if o not in meshes:bpy.data.objects.remove(o,do_unlink=True)
    for o in meshes:
        world=o.matrix_world.copy();o.parent=None;o.data.transform(world);o.matrix_world=Matrix.Identity(4)
    pts=[v.co.copy() for o in meshes for v in o.data.vertices]
    lo=Vector(tuple(min(v[j] for v in pts) for j in range(3)));hi=Vector(tuple(max(v[j] for v in pts) for j in range(3)));dims=hi-lo
    col=i%cols;row=i//cols;y=(col-(cols-1)*.5)*cw;bottom=height-(row+1)*ch+.08
    review_scale=1.0 if KIND=='blade' else min((cw-.065)/max(dims.y,.001),(ch-.135)/max(dims.z,.001))
    zoffset=bottom-lo.z*review_scale
    if KIND!='blade':zoffset+=(ch-.135-dims.z*review_scale)*.5
    for o in meshes:
        o.scale=(review_scale,review_scale,review_scale)
        o.location=(-(lo.x+hi.x)*.5*review_scale,y-(lo.y+hi.y)*.5*review_scale,zoffset)
        o.data.materials.clear();o.data.materials.append(steel)
        for face in o.data.polygons:face.material_index=0
    number=int(re.search(r'(\d+)$',path.stem).group(1))
    label(f'{number:02d}',y,bottom-.043,.031 if KIND=='blade' else .022)
    if KIND=='blade':label(f'{dims.z*100:.1f} cm',y,bottom-.081,.019)
    records.append({'name':path.stem,'id':number,'dimensions_cm':list(dims*100),'triangle_count':sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),'collision_meshes_excluded':True,'review_scale':review_scale})
label(title,0,height+.055,.043 if KIND=='blade' else .032)
label('Actual pack geometry  |  neutral steel  |  '+('original relative scale' if KIND=='blade' else 'NOT SAME SCALE / fitted per cell'),0,-.08,.021 if KIND=='blade' else .016)
scene.render.filepath=str(ROOT/filename)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'{KIND}_catalog.blend'))
bpy.ops.render.render(write_still=True)
(ROOT/f'{KIND}_catalog.json').write_text(json.dumps({'kind':KIND,'preview':filename,'camera_yaw_degrees':6,'materials':'Neutral review steel; not the pack materials','items':records},indent=2))
print('CATALOG_SAVED',filename,flush=True)


