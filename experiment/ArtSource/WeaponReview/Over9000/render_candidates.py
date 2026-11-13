import bpy, json, math, re
from pathlib import Path
from mathutils import Vector, Matrix
ROOT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=40;scene.cycles.use_denoising=True
scene.render.resolution_x=2300;scene.render.resolution_y=1900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.view_settings.view_transform='AgX'
scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.12,.15,.19,1);scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.55

def mat(name,color,metallic=0,rough=.4):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metallic;p.inputs['Roughness'].default_value=rough;return m
steel=mat('Neutral steel - supplied geometry review',(.31,.34,.38),.78,.29)
back=mat('Slate backdrop',(.018,.027,.040),0,.9)
fontmat=mat('Labels',(.7,.78,.85),0,.7);p=fontmat.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(.7,.78,.85,1);p.inputs['Emission Strength'].default_value=.7
center=Vector((0,0,.45));bpy.ops.object.camera_add(location=center+Vector((4,-math.tan(math.radians(6))*4,0)))
cam=bpy.context.object;cam.name='Candidate Review Camera';cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.48;scene.camera=cam

def text(s,y,z,size):
    c=bpy.data.curves.new('label','FONT');c.body=s;c.align_x='CENTER';c.size=size;c.extrude=0;o=bpy.data.objects.new(s,c);scene.collection.objects.link(o);o.location=(.09,y,z);o.rotation_euler=cam.rotation_euler;c.materials.append(fontmat)
def light(name,pos,energy,size,color):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;d.color=color;o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=center+Vector(pos);o.rotation_euler=(center-o.location).to_track_quat('-Z','Y').to_euler()
light('Key',(1.8,-1.5,2),260,2.0,(1,.97,.91));light('Fill',(1.6,1.8,.4),190,1.8,(.85,.93,1));light('Rim',(-.12,.5,1.7),260,1.5,(1,1,1))
bpy.ops.mesh.primitive_plane_add(size=2,location=(-.15,0,.5),rotation=(0,math.pi*.5,0));bpy.context.object.scale=(4,4,4);bpy.context.object.data.materials.append(back)
choices=[('A',3,3,4,3),('B',1,5,9,12),('C',2,1,2,1)]
files=list(ROOT.glob('*.fbx'));records=[]
for col,(label,blade,guard,hilt,pommel) in enumerate(choices):
    collection=bpy.data.collections.new('Candidate '+label);scene.collection.children.link(collection)
    pieces=[];names=[]
    for kind,num in [('blade',blade),('crossguard',guard),('hilt',hilt),('pommel',pommel)]:
        path=next(p for p in files if f'_{kind}_' in p.stem.lower() and int(re.search(r'(\d+)$',p.stem).group(1))==num)
        before=set(bpy.data.objects);bpy.ops.import_scene.fbx(filepath=str(path),use_custom_normals=True)
        imported=[o for o in bpy.data.objects if o not in before]
        meshes=[o for o in imported if o.type=='MESH' and not o.name.upper().startswith(('UCX_','UBX_','USP_','UCP_'))]
        for o in imported:
            if o not in meshes:bpy.data.objects.remove(o,do_unlink=True)
        for o in meshes:
            world=o.matrix_world.copy();o.parent=None;o.data.transform(world);o.matrix_world=Matrix.Identity(4)
            for c in list(o.users_collection):c.objects.unlink(o)
            collection.objects.link(o)
            o.name=f'{label}_{path.stem}';o.data.materials.clear();o.data.materials.append(steel)
            for face in o.data.polygons:face.material_index=0
        pieces.extend(meshes);names.append(path.stem)
    coords=[v.co.copy() for o in pieces for v in o.data.vertices];lo=Vector(tuple(min(v[j] for v in coords) for j in range(3)));hi=Vector(tuple(max(v[j] for v in coords) for j in range(3)));dims=hi-lo
    scale=.64;y=(col-1)*.41;bottom=.075
    assembly=bpy.data.objects.new('Assembly '+label,None);collection.objects.link(assembly);assembly.empty_display_type='PLAIN_AXES';assembly.scale=(scale,)*3
    assembly.location=(-(lo.x+hi.x)*.5*scale,y-(lo.y+hi.y)*.5*scale,bottom-lo.z*scale)
    for o in pieces:o.parent=assembly
    text(label+'  /  '+('RECOMMENDED' if label=='A' else 'ALTERNATIVE'),y,.023,.023)
    text(f'Blade {blade:02d} | Guard {guard:02d} | Grip {hilt:02d} | Pommel {pommel:02d}',y,-.009,.013)
    text(f'{dims.z*100*scale:.1f} cm overall',y,-.035,.015)
    records.append({'candidate':label,'mesh_names':names,'assembly':'Original FBX coordinate origins preserved; only whole assembly offset and uniform scale applied','uniform_scale':scale,'dimensions_cm_at_display_scale':list(dims*100*scale),'triangles':sum(len(p.vertices)-2 for o in pieces for p in o.data.polygons)})
text('OVER 9000 SWORDS / THREE CANDIDATES',0,.98,.032)
text('Actual supplied geometry  /  neutral material review',0,-.087,.019)
text('Same scale: 0.64   |   Original component positions   |   No gameplay replacement',0,-.116,.015)
scene.render.filepath=str(ROOT/'CandidateShapes.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CandidateShapes.blend'))
bpy.ops.render.render(write_still=True)
(ROOT/'CandidateShapes.json').write_text(json.dumps({'preview':'CandidateShapes.png','camera_angle_degrees':6,'material':'Neutral steel only; not an original material reproduction','choices':records},indent=2))
print('CANDIDATE_SHAPES_SAVED',flush=True)
