import bpy,json,math
from pathlib import Path
from mathutils import Matrix,Vector
out=Path(__file__).parent;out.mkdir(exist_ok=True)
scene=bpy.context.scene
objs=[o for o in scene.objects if o.type in ['MESH','CURVE'] and not o.hide_render]
original_parts=len(objs)
materials=[]
images={}
for m in bpy.data.materials:
    bs=m.node_tree.nodes.get('Principled BSDF') if m.use_nodes else None
    if not bs:continue
    entry={'name':m.name,'color':list(bs.inputs['Base Color'].default_value),
           'metallic':float(bs.inputs['Metallic'].default_value),'roughness':float(bs.inputs['Roughness'].default_value),
           'texture':None,'texture_mix':0.,'mix_color':[0,0,0,1]}
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE' and n.image:
            name='T_Yueyao_Patina' if 'patina' in n.image.name else 'T_Yueyao_Reference'
            if name not in images:
                path=out/(name+'.png');n.image.filepath_raw=str(path);n.image.file_format='PNG';n.image.save()
                images[name]=str(path)
            entry['texture']=name
        if n.type=='MIX_RGB':
            entry['texture_mix']=float(n.inputs[0].default_value)
            for socket in [n.inputs[1],n.inputs[2]]:
                if not socket.is_linked:entry['mix_color']=list(socket.default_value)
    materials.append(entry)
for o in objs:
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
    if o.type=='CURVE':bpy.ops.object.convert(target='MESH')
    for mod in list(o.modifiers):
        if mod.show_viewport:bpy.ops.object.modifier_apply(modifier=mod.name)
objs=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
# Blender shades with each object's active render UV; UE uses channel zero.
# Merge that selected layer into a shared channel before joining the pieces.
uv_sources=[]
for o in objs:
    layers=o.data.uv_layers
    if not layers:layers.new(name='UVMap')
    selected=next((layer for layer in layers if layer.active_render),layers.active)
    uv_sources.append({'object':o.name,'render_uv':selected.name,'layers':[l.name for l in layers]})
    coordinates=[tuple(loop.uv) for loop in selected.data]
    first=layers[0]
    for loop,coord in zip(first.data,coordinates):loop.uv=coord
    for layer in list(layers)[1:]:layers.remove(layer)
    first.name='UVMap';first.active_render=True;layers.active=first
bpy.ops.object.select_all(action='DESELECT')
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
bpy.ops.object.join()
mesh=bpy.context.object;mesh.name='SM_Yueyao_Player'
# Place the pivot inside the center of the leather grip. Blade extends +Z.
transform=Matrix.Scale(100,4)@Matrix.Rotation(math.pi/2,4,'Y')@Matrix.Translation(Vector((-.09672,0,0)))@mesh.matrix_world
mesh.data.transform(transform);mesh.matrix_world=Matrix.Identity(4)
# Converted engraving curves have no useful UVs. Give those constant-color
# faces a nondegenerate planar basis; preserve the blade and dragon image UVs.
uv=mesh.data.uv_layers.active or mesh.data.uv_layers.new(name='UVMap')
uv_repaired=0
for poly in mesh.data.polygons:
    loops=list(poly.loop_indices)
    points=[uv.data[i].uv.copy() for i in loops]
    area=abs(sum(points[i].x*points[(i+1)%len(points)].y-points[(i+1)%len(points)].x*points[i].y for i in range(len(points))))
    if area>1e-10:continue
    axis=max(range(3),key=lambda a:abs(poly.normal[a]))
    axes=[a for a in range(3) if a!=axis]
    for i in loops:
        p=mesh.data.vertices[mesh.data.loops[i].vertex_index].co
        uv.data[i].uv=(p[axes[0]]*.1,p[axes[1]]*.1)
    uv_repaired+=1
for i,m in enumerate(mesh.data.materials):
    oldname=m.name;newname='M_Yueyao_'+str(i).zfill(2)
    entry=next(e for e in materials if e['name']==oldname)
    entry['ue_name']=newname;entry['slot']=i;m.name=newname
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
bpy.ops.export_scene.fbx(filepath=str(out/'YueyaoPlayer.fbx'),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',bake_anim=False,path_mode='STRIP')
mesh.data.calc_loop_triangles()
report={'source_parts':original_parts,'vertices':len(mesh.data.vertices),'triangles':len(mesh.data.loop_triangles),
    'bounds_cm':[[min(v.co[a] for v in mesh.data.vertices),max(v.co[a] for v in mesh.data.vertices)] for a in range(3)],
    'materials':materials,'images':images,'grip_pivot_source_m':[.09672,0,0],'blade_axis':'+Z','grip_diameter_cm':2.1,
    'constant_color_faces_uv_repaired':uv_repaired,'source_render_uv_layers':uv_sources}
(out/'YueyaoPrepared.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print('WEAPON_PREPARED',report['triangles'],'triangles',len(mesh.data.materials),'material slots')
