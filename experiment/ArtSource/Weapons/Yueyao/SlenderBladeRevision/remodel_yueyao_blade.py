"""Replace only the crescent blade; retain every hilt component in source space."""
import bpy, hashlib, json, math
from pathlib import Path
from mathutils import Matrix, Vector

out=Path(__file__).parent;out.mkdir(exist_ok=True)
old_manifest=json.loads((Path(__file__).parent.parent/'YueyaoPrepared.json').read_text(encoding='utf-8'))
old_names={m['name']:m['ue_name'] for m in old_manifest['materials']}
scene=bpy.context.scene
old_blade=next(o for o in scene.objects if o.name.startswith('01 Crescent jade blade'))
hilt=[o for o in scene.objects if o.type in {'MESH','CURVE'} and not o.hide_render and o!=old_blade]

def geometry_signature(objects):
    dep=bpy.context.evaluated_depsgraph_get();rows={}
    for obj in objects:
        ev=obj.evaluated_get(dep);mesh=ev.to_mesh()
        values={'vertices':[[round(x,9) for x in (obj.matrix_world@v.co)] for v in mesh.vertices],
                'polygons':[[list(p.vertices),p.material_index] for p in mesh.polygons],
                'materials':[m.name if m else None for m in mesh.materials]}
        rows[obj.name]=hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest()
        ev.to_mesh_clear()
    return rows
before=geometry_signature(hilt)
bpy.data.objects.remove(old_blade,do_unlink=True)

def material(name,color,metal,rough):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1.)
    m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1.)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    return m
steel=material('M_YueyaoBlade_Steel',(0.38,0.46,0.43),.84,.29)
edge=material('M_YueyaoBlade_Edge',(0.68,0.75,0.71),.92,.19)
spine=material('M_YueyaoBlade_Spine',(0.22,0.28,0.26),.86,.32)

# Source blade extends -X. The convex cutting edge converges to a fine tip.
length=.625
knots=[(0.,.018,-.020),(.035,.0185,-.019),(.13,.021,-.017),(.27,.024,-.012),
       (.43,.029,-.006),(.53,.034,.002),(.575,.038,.011),(.60,.041,.024),(.625,.043,.043)]
def curve(d,column):
    for i in range(len(knots)-1):
        a,b=knots[i],knots[i+1]
        if d<=b[0]:
            t=(d-a[0])/(b[0]-a[0])
            ma=((b[column]-a[column])/(b[0]-a[0]) if i==0 else
                (b[column]-knots[i-1][column])/(b[0]-knots[i-1][0]))
            mb=((b[column]-a[column])/(b[0]-a[0]) if i==len(knots)-2 else
                (knots[i+2][column]-a[column])/(knots[i+2][0]-a[0]))
            return (2*t**3-3*t**2+1)*a[column]+(t**3-2*t**2+t)*(b[0]-a[0])*ma+(-2*t**3+3*t**2)*b[column]+(t**3-t**2)*(b[0]-a[0])*mb
    return knots[-1][column]
stations=97
verts=[];faces=[];bands=[]
for i in range(stations):
    d=length*i/stations;t=d/length;back=curve(d,1);cut=curve(d,2)
    half=.003*(1.-.62*t)
    if t>.90:half*=1.-.6*(t-.90)/.10
    ring=[(1.,-.78*half),(.32,-half),(.07,-.38*half),(0.,-.00010),
          (0.,.00010),(.07,.38*half),(.32,half),(1.,.78*half)]
    verts += [(0.012-d,y,cut+(back-cut)*v) for v,y in ring]
for i in range(stations-1):
    for j in range(8):
        # Counterclockwise from outside, preserving a closed manifold body.
        faces.append((i*8+j,i*8+(j+1)%8,(i+1)*8+(j+1)%8,(i+1)*8+j));bands.append(j)
faces.append(tuple(reversed(range(8))));bands.append(8)
tip=len(verts);verts.append((.012-length,0.,knots[-1][1]))
for j in range(8):
    faces.append(((stations-1)*8+j,(stations-1)*8+(j+1)%8,tip));bands.append(j)
mesh=bpy.data.meshes.new('Yueyao_SlenderSingleEdge_Geometry')
mesh.from_pydata(verts,[],faces);mesh.update()
mesh.flip_normals();mesh.update()
blade=bpy.data.objects.new('01 Yueyao blade | slender single edge',mesh);scene.collection.objects.link(blade)
for m in [steel,edge,spine]:mesh.materials.append(m)
uv=mesh.uv_layers.new(name='UVMap')
for p,band in zip(mesh.polygons,bands):
    p.material_index=2 if band in (3,7,8) else (1 if band in (1,2,4,5) else 0)
    p.use_smooth=True
    for li in p.loop_indices:
        v=mesh.vertices[mesh.loops[li].vertex_index].co
        d=.012-v.x;back=curve(d,1);cut=curve(d,2)
        uv.data[li].uv=(d/length,(v.z-cut)/max(.00001,back-cut))
# Smooth lengthwise curvature; keep the shinogi and the bevel crisp.
normal_sum={}
for p,band in zip(mesh.polygons,bands):
    for vi in p.vertices:
        key=(vi,band);normal_sum[key]=normal_sum.get(key,Vector())+p.normal
normals=[]
for p,band in zip(mesh.polygons,bands):
    normals.extend([normal_sum[(mesh.loops[li].vertex_index,band)].normalized() for li in p.loop_indices])
mesh.normals_split_custom_set(normals)
after=geometry_signature(hilt)
if before!=after:raise RuntimeError('Hilt geometry changed during blade remodeling')

# Save an editable new source before consolidating anything for the engine.
camera=scene.camera
if camera:
    camera.location=(-.19,-1.20,.18)
    camera.rotation_euler=(Vector((-.19,0.,.015))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=.92
scene.render.resolution_x=1600;scene.render.resolution_y=650;scene.render.resolution_percentage=100
scene.render.engine='CYCLES';scene.cycles.samples=32
scene.world.color=(.065,.065,.065)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Yueyao_Hero_Weapon_SlenderBlade.blend'))

objects=[o for o in scene.objects if o.type in {'MESH','CURVE'} and not o.hide_render]
used_materials={m.name:m for o in objects for m in o.data.materials if m}
materials=[]
for name,m in used_materials.items():
    if name in old_names:
        entry=dict(next(e for e in old_manifest['materials'] if e['name']==name))
        entry['preserve_existing_material']=True
    else:
        p=m.node_tree.nodes.get('Principled BSDF')
        entry={'name':name,'ue_name':name,'color':list(p.inputs['Base Color'].default_value),
               'metallic':float(p.inputs['Metallic'].default_value),'roughness':float(p.inputs['Roughness'].default_value),
               'texture':None,'preserve_existing_material':False}
    materials.append(entry)

for obj in objects:
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    if obj.type=='CURVE':bpy.ops.object.convert(target='MESH')
    for mod in list(obj.modifiers):
        if mod.show_viewport:bpy.ops.object.modifier_apply(modifier=mod.name)
    layers=obj.data.uv_layers
    if not layers:layers.new(name='UVMap')
    active=next((l for l in layers if l.active_render),layers.active)
    coords=[tuple(loop.uv) for loop in active.data];first=layers[0]
    for loop,coord in zip(first.data,coords):loop.uv=coord
    for layer in list(layers)[1:]:layers.remove(layer)
    first.name='UVMap';first.active_render=True;layers.active=first
objects=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
bpy.context.view_layer.objects.active=blade;bpy.ops.object.join()
joined=bpy.context.object;joined.name='SM_Yueyao_Player'
transform=Matrix.Scale(100,4)@Matrix.Rotation(math.pi/2,4,'Y')@Matrix.Translation(Vector((-.09672,0,0)))@joined.matrix_world
joined.data.transform(transform);joined.matrix_world=Matrix.Identity(4)
uv=joined.data.uv_layers.active
for p in joined.data.polygons:
    loops=list(p.loop_indices);pts=[uv.data[i].uv.copy() for i in loops]
    area=abs(sum(pts[i].x*pts[(i+1)%len(pts)].y-pts[(i+1)%len(pts)].x*pts[i].y for i in range(len(pts))))
    if area>1e-10:continue
    axes=[a for a in range(3) if a!=max(range(3),key=lambda a:abs(p.normal[a]))]
    for li in loops:
        v=joined.data.vertices[joined.data.loops[li].vertex_index].co
        uv.data[li].uv=(v[axes[0]]*.1,v[axes[1]]*.1)
for m in joined.data.materials:
    m.name=next(e['ue_name'] for e in materials if e['name']==m.name)
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
bpy.ops.export_scene.fbx(filepath=str(out/'YueyaoPlayerSlender.fbx'),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',bake_anim=False,path_mode='STRIP')
joined.data.calc_loop_triangles()
report={'design':'Slender single-edge dao, restrained curve','blade_length_cm':length*100,
        'blade_root_width_cm':(knots[0][1]-knots[0][2])*100,'spine_curve_cm':(knots[-1][1]-knots[0][1])*100,
        'blade_root_thickness_cm':.6,'blade_triangles':(stations-1)*8*2+6+8,
        'total_triangles':len(joined.data.loop_triangles),'materials':materials,
        'hilt_geometry_before':before,'hilt_geometry_after':after,'hilt_unchanged':before==after,
        'preserved_hilt_object_count':len(hilt),'grip_pivot_source_m':[.09672,0,0],
        'bounds_cm':[[min(v.co[a] for v in joined.data.vertices),max(v.co[a] for v in joined.data.vertices)] for a in range(3)]}
(out/'SlenderBladePrepared.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('SLENDER_BLADE_READY',report['total_triangles'],'triangles; hilt unchanged:',report['hilt_unchanged'])
