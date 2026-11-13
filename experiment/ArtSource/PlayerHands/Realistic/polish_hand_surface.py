"""Polish only the proximal dorsal hand without altering topology or skinning."""
import bpy, json, shutil, hashlib, struct
from pathlib import Path
from mathutils import Vector

OUT=Path(__file__).resolve().parent
for name in ('PlayerHandRealistic_R.blend','PlayerHandRealistic_R.fbx','HandsAuthoring.json'):
    source=OUT/name
    backup=source.with_name(source.stem+'_BeforePolish'+source.suffix)
    if not backup.exists():shutil.copy2(source,backup)
bpy.ops.wm.open_mainfile(filepath=str(OUT/'PlayerHandRealistic_R.blend'))
skin=bpy.data.objects['PlayerHandRealistic_R']
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
mesh=skin.data
def signature():
    weights=hashlib.sha256()
    for v in mesh.vertices:
        for g in v.groups:weights.update(struct.pack('<IIf',v.index,g.group,g.weight))
    uv=hashlib.sha256()
    for layer in mesh.uv_layers:
        for point in layer.data:uv.update(struct.pack('<ff',*point.uv))
    color=hashlib.sha256()
    for layer in mesh.color_attributes:
        for point in layer.data:color.update(struct.pack('<ffff',*point.color))
    bones=hashlib.sha256()
    for b in rig.data.bones:
        bones.update((b.name+'|'+(b.parent.name if b.parent else 'root')).encode())
        for row in b.matrix_local:bones.update(struct.pack('<ffff',*row))
    return {'vertices':len(mesh.vertices),'polygons':len(mesh.polygons),'weights':weights.hexdigest(),
        'uv':uv.hexdigest(),'SkinTint':color.hexdigest(),'bones':bones.hexdigest()}
before=signature()
positions=[v.co.copy() for v in mesh.vertices]
skin_vertices={i for p in mesh.polygons if p.material_index==0 for i in p.vertices}
nail_vertices={i for p in mesh.polygons if p.material_index!=0 for i in p.vertices}
adjacency=[set() for _ in mesh.vertices]
for edge in mesh.edges:
    a,b=edge.vertices
    if a in skin_vertices and b in skin_vertices:
        adjacency[a].add(b);adjacency[b].add(a)
def smoothstep(t):
    t=min(1.,max(0.,t))
    return t*t*(3.-2.*t)
mask=[]
for v in mesh.vertices:
    if v.index not in skin_vertices or v.index in nail_vertices:
        mask.append(0.);continue
    # Broad continuous transition, keeping fingers, palm creases and the flat end cap.
    y_mask=smoothstep((v.co.y+5.8)/2.1)
    dorsal=smoothstep((v.normal.z-.02)/.52)
    height=smoothstep((v.co.z+.25)/.8)
    cap_fade=smoothstep((.70-v.co.y)/.48)
    mask.append(y_mask*dorsal*height*cap_fade)
for _ in range(6):
    next_positions=list(positions)
    for i,neighbors in enumerate(adjacency):
        if not neighbors or mask[i]<=0.:continue
        average=sum((positions[j] for j in neighbors),Vector())/len(neighbors)
        next_positions[i]=positions[i].lerp(average,.28*mask[i])
    positions=next_positions
changed=0;max_delta=0.
for v,p in zip(mesh.vertices,positions):
    delta=(v.co-p).length
    if delta>1.e-7:changed+=1
    max_delta=max(max_delta,delta);v.co=p
mesh.update()
after=signature()
if before!=after:raise RuntimeError('Local polish changed protected hand data.')
rig.data.pose_position='REST'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'PlayerHandRealistic_R.blend'))
bpy.ops.object.select_all(action='DESELECT');skin.select_set(True);rig.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.fbx(filepath=str(OUT/'PlayerHandRealistic_R.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},
    add_leaf_bones=False,use_armature_deform_only=False,bake_anim=False,apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',path_mode='STRIP',
    mesh_smooth_type='FACE',use_mesh_modifiers=False,colors_type='LINEAR')
manifest=json.loads((OUT/'HandsAuthoring.json').read_text(encoding='utf-8'))
manifest['local_polish']={'script':'polish_hand_surface.py','region':'Proximal dorsal hand and wrist only',
    'iterations':6,'strength':.28,'changed_vertices':changed,'maximum_delta_cm':max_delta,
    'protected_data_before':before,'protected_data_after':after,'protected_data_identical':before==after,
    'topology_unchanged':True,'fingers_palmar_creases_nails_unchanged':True,
    'backup_suffix':'_BeforePolish','authoring_steps':['author_realistic_hand.py','polish_hand_surface.py']}
(OUT/'HandsAuthoring.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

# Reuse exactly the existing Grip preview lighting, pose, framing and materials.
bpy.ops.wm.open_mainfile(filepath=str(OUT/'PlayerHandRealistic_GripPreview.blend'))
preview=bpy.data.objects['PlayerHandRealistic_R']
if len(preview.data.vertices)!=len(positions):raise RuntimeError('Preview topology changed.')
for v,p in zip(preview.data.vertices,positions):v.co=p
preview.data.update()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'PlayerHandRealistic_GripPreview.blend'))
bpy.context.scene.render.filepath=str(OUT/'HumanHand_Grip.png')
bpy.ops.render.render(write_still=True)
print('HAND_LOCAL_POLISH_SAVED',changed,max_delta,before==after)
