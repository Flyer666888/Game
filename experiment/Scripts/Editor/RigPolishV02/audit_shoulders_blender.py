"""Read-only source-mesh shoulder audit; render unsaved pose copies only."""
import bpy,json,math
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
P=Path(r'D:\game design\experiment')
O=P/'Docs/Gameplay/RigPolish_v02/ShoulderAudit';O.mkdir(parents=True,exist_ok=True)
source=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
data=json.loads((P/'Docs/Gameplay/RigPolish_v01/UprightCandidatePoses.json').read_text(encoding='utf-8'))
coords=[v.co.copy() for v in source.data.vertices]
weights=[{source.vertex_groups[g.group].name:g.weight for g in v.groups if g.weight>0} for v in source.data.vertices]
region=[v.index for v in source.data.vertices if 123<v.co.z<154 and abs(v.co.x)<32]
region_set=set(region)
edge_faces={}
for f in source.data.polygons:
    for edge in f.edge_keys:edge_faces[edge]=edge_faces.get(edge,0)+1
boundary=[list(e) for e,n in edge_faces.items() if n==1 and any(i in region_set for i in e)]
bone_rows={b.name:{'head':list(b.head_local),'tail':list(b.tail_local),'parent':b.parent.name if b.parent else None} for b in rig.data.bones}
report={'source':bpy.data.filepath,'mesh':source.name,'vertices':len(coords),'bones':bone_rows,
        'materials':[m.name for m in source.data.materials],
        'region_vertices':len(region),'region_boundary_edges':len(boundary),
        'region':[{'index':i,'co':list(coords[i]),'weights':weights[i]} for i in region],
        'boundary_edges':boundary,'images':[]}
(O/'ShoulderMeshAudit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
def mat(t):return Matrix.LocRotScale(Vector(t['p']),Quaternion((t['q'][3],*t['q'][:3])),Vector(t['s']))
reflection=Matrix.Diagonal((1.,-1.,1.,1.));inv={b:mat(t).inverted() for b,t in data['reference'].items()}
for obj in list(bpy.context.scene.objects):obj.hide_render=True
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.device='CPU'
scene.render.resolution_x=700;scene.render.resolution_y=700;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('ShoulderAuditWorld');scene.world.use_nodes=True
background=scene.world.node_tree.nodes.new('ShaderNodeBackground')
world_output=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld')
scene.world.node_tree.links.new(background.outputs['Background'],world_output.inputs['Surface'])
background.inputs['Color'].default_value=(.32,.32,.32,1)
background.inputs['Strength'].default_value=.65
camdata=bpy.data.cameras.new('ShoulderAuditCamera');camdata.type='ORTHO';camdata.ortho_scale=.80
cam=bpy.data.objects.new('ShoulderAuditCamera',camdata);scene.collection.objects.link(cam);scene.camera=cam
for idx,(location,energy,size) in enumerate((((-2,-3,4),400,4),((3,0,3),300,4))):
    ld=bpy.data.lights.new('ShoulderAuditLight'+str(idx),'AREA');ld.energy=energy;ld.size=size
    light=bpy.data.objects.new(ld.name,ld);scene.collection.objects.link(light);light.location=location
    light.rotation_euler=(Vector((0,0,1.4))-light.location).to_track_quat('-Z','Y').to_euler()
def clip(name,t):
    c=next(c for c in data['clips'] if c['name']==name)
    return min(c['samples'],key=lambda s:abs(s['time']-t))['world']
specs=[('ReferenceFront',data['reference'],(0,-4,1.42)),
       ('IdleFront',clip('Wuxia_Idle_Planted_Upright_v01',0),(0,-4,1.42)),
       ('AttackFront',clip('Wuxia_Attack_Sword_Upright_v01',1.1),(0,-4,1.42)),
       ('AttackBack',clip('Wuxia_Attack_Sword_Upright_v01',1.1),(0,4,1.42))]
for name,world,view in specs:
    deform={b:reflection@mat(t)@inv[b]@reflection for b,t in world.items()}
    posed=[]
    for p,w in zip(coords,weights):
        v=Vector((0,0,0))
        for b,a in w.items():v+=(deform[b]@p)*a
        posed.append(v*.01)
    md=source.data.copy();obj=bpy.data.objects.new('AuditPose',md);scene.collection.objects.link(obj)
    obj.shape_key_clear();md.vertices.foreach_set('co',[v for p in posed for v in p]);md.update()
    cam.location=view;cam.rotation_euler=(Vector((0,0,1.39))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
    report['images'].append(scene.render.filepath)
    bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(md)
(O/'ShoulderMeshAudit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SHOULDER_AUDIT_COMPLETE',len(region),len(boundary),flush=True)
