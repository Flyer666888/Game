"""Create a shoulder-only weight derivative; preserve geometry, rig and morphs.

Run with WuxiaMaleCombat.blend. No changes are saved to the source asset.
The old face repair used a global height head mask, pulling shoulder cloth with
the head. Anatomical local fields replace that mask and avoid cross-side bones.
"""
import bpy,json,hashlib,math
import numpy as np
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
from mathutils.kdtree import KDTree
P=Path(r'D:\game design\experiment')
O=P/'ArtSource/WuxiaMale/RigPolishV02/Shoulder';O.mkdir(parents=True,exist_ok=True)
D=P/'Docs/Gameplay/RigPolish_v02/ShoulderCandidate';D.mkdir(parents=True,exist_ok=True)
mesh=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
source_path=bpy.data.filepath
coords=[v.co.copy() for v in mesh.data.vertices]
original=[{mesh.vertex_groups[g.group].name:g.weight for g in v.groups if g.weight>0} for v in mesh.data.vertices]
bones=[b.name for b in rig.data.bones];bindices={b:i for i,b in enumerate(bones)}
def signature():
    h=hashlib.sha256()
    for v in mesh.data.vertices:
        for c in v.co:h.update(float(c).hex().encode()+b'|')
    return h.hexdigest()
def invariants():
    def digest(items):return hashlib.sha256(repr(items).encode()).hexdigest()
    return {'basis':signature(),'vertices':len(mesh.data.vertices),'polygons':digest([list(p.vertices) for p in mesh.data.polygons]),
        'uv':digest([[list(d.uv) for d in l.data] for l in mesh.data.uv_layers]),
        'morphs':{k.name:{'coordinates':digest([list(v.co) for v in k.data]),'value':k.value} for k in mesh.data.shape_keys.key_blocks},
        'skeleton':digest([(b.name,b.parent.name if b.parent else None,list(b.head_local),list(b.tail_local),list(b.matrix_local)) for b in rig.data.bones]),
        'material_slots':[m.name for m in mesh.data.materials],'material_indices':digest([p.material_index for p in mesh.data.polygons])}
before=invariants()
skin=set(i for p in mesh.data.polygons if p.material_index==1 for i in p.vertices)
face_skin=[i for i in skin if coords[i].z>140.5]
face_tree=KDTree(len(face_skin))
for i in face_skin:face_tree.insert(coords[i],i)
face_tree.balance()
def smooth(a,b,x):
    t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3.-2.*t)
candidate=[];changed=[];discarded=[]
for i,(p,old) in enumerate(zip(coords,original)):
    x,y,z=p;a=abs(x);side='l' if x>=0 else 'r'
    mask=smooth(119,128,z)*(1-smooth(149,154,z))*(1-smooth(26,33,a))
    # Preserve the rigid facial skin and upper head. The long rear hair remains
    # attached to the head through a smooth narrow center-back mask.
    if i in skin and z>=144.5:mask=0.
    if mask<1e-7:candidate.append(dict(old));continue
    upper=smooth(11.5,25,a)
    clav=(1-upper)*smooth(5.5,14,a)*smooth(126,137,z)*.80
    neck=(1-upper-clav)*smooth(136,145,z)*(1-smooth(6,12,a))
    torso=1-upper-clav-neck
    spine=smooth(122,134,z)
    target={'spine_02':torso*(1-spine),'spine_03':torso*spine,'neck_01':neck,
        'clavicle_'+side:clav,'upperarm_'+side:upper}
    # Blend through the true facial skin boundary, rather than resetting the
    # entire central collar to head motion. The 2 cm spatial band includes UV
    # seams and split mesh islands, retaining a continuous jaw/neck join.
    head=smooth(144,148,z)*(1-smooth(7,12,a))
    skin_distance=face_tree.find(p)[2]
    head=max(head,(1-smooth(0,2,skin_distance))*smooth(140.5,144.5,z))
    rear_hair=smooth(6,14,y)*(1-smooth(7,14,a))*smooth(122,137,z)
    head=max(head,rear_hair)
    target={b:w*(1-head) for b,w in target.items()};target['head']=head
    new={b:(1-mask)*old.get(b,0.)+mask*target.get(b,0.) for b in set(old)|set(target)}
    ranked=sorted(((b,w) for b,w in new.items() if w>1e-7),key=lambda r:r[1],reverse=True)
    discarded.append(sum(w for b,w in ranked[4:]))
    ranked=ranked[:4];total=sum(w for b,w in ranked)
    new={b:w/total for b,w in ranked}
    candidate.append(new)
    if max(abs(old.get(b,0.)-new.get(b,0.)) for b in set(old)|set(new))>1e-7:changed.append(i)
grip=json.loads((P/'ArtSource/WuxiaMale/GripRefinement/GripAuthoringSummary.json').read_text(encoding='utf-8'))
robe=json.loads((P/'ArtSource/WuxiaMale/NaturalDeath/RobeWeightPatch.json').read_text(encoding='utf-8'))
grip_ids={v['index'] for v in grip['deltas']};robe_ids={v['index'] for v in robe['vertices']}
assert not(set(changed)&(grip_ids|robe_ids)),'Must not modify hand-grip or death-robe weights'
for i in changed:
    for g in mesh.vertex_groups:g.remove([i])
    for b,w in candidate[i].items():mesh.vertex_groups[b].add([i],w,'REPLACE')
after=invariants();assert before==after,'Geometry, skeleton, UV or morph data changed'
mesh.name='SK_WuxiaMale_Shoulder_v02'
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
blend=O/'WuxiaMaleShoulder_v02.blend';fbx=O/'WuxiaMaleShoulder_v02.fbx'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH','ARMATURE'},
    add_leaf_bones=False,use_armature_deform_only=True,bake_anim=False,apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',path_mode='STRIP',
    mesh_smooth_type='FACE',use_mesh_modifiers=False)
(O/'ShoulderWeightPatch.json').write_text(json.dumps({'vertices':[{'index':i,'weights':candidate[i]} for i in changed]},indent=2),encoding='utf-8')
report={'source':source_path,'derivative_blend':str(blend),'derivative_fbx':str(fbx),'unchanged_invariants':before,
    'changed_vertices':len(changed),'changed_bounds_cm':{'min':[min(coords[i][a] for i in changed) for a in range(3)],'max':[max(coords[i][a] for i in changed) for a in range(3)]},
    'grip_overlap':len(set(changed)&grip_ids),'robe_overlap':len(set(changed)&robe_ids),'max_influences':max(map(len,candidate)),
    'max_pruned_weight':max(discarded),'weight_sum_error':max(abs(sum(w.values())-1) for w in candidate),
    'reason':'Old optimize_wuxia_face head mask was global by z, binding shoulder tops to head; top-four nearest-bone discontinuities pulled collar triangles apart.',
    'metrics':[],'images':[]}
data=json.loads((P/'Docs/Gameplay/RigPolish_v01/UprightCandidatePoses.json').read_text(encoding='utf-8'))
def mat(t):return Matrix.LocRotScale(Vector(t['p']),Quaternion((t['q'][3],*t['q'][:3])),Vector(t['s']))
reflection=Matrix.Diagonal((1.,-1.,1.,1.));inv={b:mat(t).inverted() for b,t in data['reference'].items()}
def clip(name,t):
    c=next(c for c in data['clips'] if c['name']==name)
    s=min(c['samples'],key=lambda s:abs(s['time']-t));return s['world']
specs=[('Reference',data['reference']),('Idle_0',clip('Wuxia_Idle_Planted_Upright_v01',0)),
    ('Attack_0.6',clip('Wuxia_Attack_Sword_Upright_v01',.6)),('Attack_1.1',clip('Wuxia_Attack_Sword_Upright_v01',1.1)),
    ('Attack_1.5',clip('Wuxia_Attack_Sword_Upright_v01',1.5)),('Cast_1.1',clip('Wuxia_Cast_Talisman_Upright_v01',1.1)),
    ('Hit_0.3',clip('Wuxia_Hit_Sword_Upright_v01',.3))]
xyz=np.array([list(v) for v in coords],dtype=np.float64);hom=np.concatenate([xyz,np.ones((len(coords),1))],axis=1)
region=np.array([119<p.z<154 and abs(p.x)<33 for p in coords])
edges=np.array([list(e.vertices) for e in mesh.data.edges],dtype=int)
length=np.linalg.norm(xyz[edges[:,1]]-xyz[edges[:,0]],axis=1)
valid=(region[edges].any(axis=1))&(length>=.25)
edges=edges[valid];length=length[valid]
mesh.data.calc_loop_triangles()
tris=np.array([list(t.vertices) for t in mesh.data.loop_triangles],dtype=int)
tris=tris[region[tris].all(axis=1)]
normal=np.cross(xyz[tris[:,1]]-xyz[tris[:,0]],xyz[tris[:,2]]-xyz[tris[:,0]])
tri_valid=np.linalg.norm(normal,axis=1)>=.01;tris=tris[tri_valid];normal=normal[tri_valid]
def weight_array(weights):
    a=np.zeros((len(coords),len(bones)))
    for i,w in enumerate(weights):
        for b,v in w.items():a[i,bindices[b]]=v
    return a
W=[weight_array(original),weight_array(candidate)]
for obj in list(scene.objects):obj.hide_render=True
scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.device='CPU'
scene.render.resolution_x=760;scene.render.resolution_y=760;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('ShoulderCandidateWorld');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');out=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld')
scene.world.node_tree.links.new(bg.outputs['Background'],out.inputs['Surface']);bg.inputs['Color'].default_value=(.32,.32,.32,1);bg.inputs['Strength'].default_value=.65
cd=bpy.data.cameras.new('CandidateCamera');cd.type='ORTHO';cd.ortho_scale=.90
cam=bpy.data.objects.new('CandidateCamera',cd);scene.collection.objects.link(cam);scene.camera=cam
for idx,(loc,energy,size) in enumerate((((-2,-3,4),400,4),((3,0,3),300,4))):
    ld=bpy.data.lights.new('CandidateLight'+str(idx),'AREA');ld.energy=energy;ld.size=size
    light=bpy.data.objects.new(ld.name,ld);scene.collection.objects.link(light);light.location=loc
    light.rotation_euler=(Vector((0,0,1.4))-light.location).to_track_quat('-Z','Y').to_euler()
for name,world in specs:
    transforms=np.array([list(reflection@mat(world[b])@inv[b]@reflection) for b in bones])
    for variant,weights in zip(('Before','After'),W):
        skin=np.einsum('nb,bjk->njk',weights,transforms)
        posed=np.einsum('njk,nk->nj',skin,hom)[:,:3]
        ratio=np.linalg.norm(posed[edges[:,1]]-posed[edges[:,0]],axis=1)/length
        pn=np.cross(posed[tris[:,1]]-posed[tris[:,0]],posed[tris[:,2]]-posed[tris[:,0]])
        # Expected normal under the local blended transform, using inverse
        # transpose. Negative dot diagnoses a fold, not overall body rotation.
        local=skin[tris,:,:].mean(axis=1)[:,:3,:3]
        expected=np.einsum('nij,nj->ni',np.linalg.pinv(local).transpose(0,2,1),normal)
        dots=np.sum(pn*expected,axis=1)
        report['metrics'].append({'pose':name,'variant':variant,'edge_count':len(edges),'max_edge_ratio':float(ratio.max()),
            'p95_edge_ratio':float(np.percentile(ratio,95)),'p99_edge_ratio':float(np.percentile(ratio,99)),
            'edges_over_2x':int((ratio>2).sum()),'edges_over_4x':int((ratio>4).sum()),'triangle_count':len(tris),'normal_flips':int((dots<0).sum())})
        md=mesh.data.copy();obj=bpy.data.objects.new('CandidatePose',md);scene.collection.objects.link(obj)
        obj.shape_key_clear();md.vertices.foreach_set('co',(posed*.01).reshape(-1).tolist());md.update()
        views=[('Front',(0,-4,1.42))]
        if name in ('Attack_1.1','Idle_0'):views.append(('Back',(0,4,1.42)))
        for view,loc in views:
            cam.location=loc;cam.rotation_euler=(Vector((0,0,1.39))-cam.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(D/(name+'_'+variant+'_'+view+'.png'));bpy.ops.render.render(write_still=True);report['images'].append(scene.render.filepath)
        bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(md)
(O/'ShoulderRepairSummary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(D/'ShoulderRepairSummary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SHOULDER_REPAIR_COMPLETE',json.dumps({k:report[k] for k in ('changed_vertices','changed_bounds_cm','max_influences','max_pruned_weight','metrics')}),flush=True)
