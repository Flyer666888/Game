"""Read-only fixed-grip graft audit using actual mesh shape keys, never old indices."""
import bpy,sys,json,hashlib,math,bisect
from pathlib import Path
import numpy as np
from mathutils import Matrix,Vector,Quaternion
from mathutils.bvhtree import BVHTree
P=Path(r'D:\game design\experiment');OUT=P/'Docs/Gameplay/RigPolish_v04/Audit/GraftedHandMotion';OUT.mkdir(parents=True,exist_ok=True)
NEW=P/'ArtSource/WuxiaMale/RigPolishV04/HandsReplacement/WuxiaMaleRealGrip_v04.blend'
OLD=P/'ArtSource/WuxiaMale/RigPolishV02/Shoulder/WuxiaMaleShoulder_v02.blend'
ATTACK=P/'ArtSource/WuxiaMale/RigPolishV04/Attack/NaturalAttackRuntimePoses.json'
DEATH=P/'ArtSource/WuxiaMale/RigPolishV02/Death/RestrainedDeathRuntimePoses.json'
OTHER=P/'Docs/Gameplay/RigPolish_v01/UprightCandidatePoses.json'
assert '--expected-sha256' in sys.argv,'Require author-frozen expected blend hash'
expected=sys.argv[sys.argv.index('--expected-sha256')+1].lower()
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(NEW)==expected,'Candidate changed before audit'
ref=json.loads(ATTACK.read_text(encoding='utf-8'))['reference']
H=Matrix.Diagonal((1,-1,1,1))
def mat(t):return Matrix.LocRotScale(Vector(t['p']),Quaternion((t['q'][3],*t['q'][:3])),Vector(t.get('s',[1,1,1])))
inverse={b:mat(t).inverted() for b,t in ref.items()}
def capture(path):
    bpy.ops.wm.open_mainfile(filepath=str(path));mesh=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    basis=np.asarray([list(v.co) for v in mesh.data.vertices]);keys={k.name:np.asarray([list(v.co) for v in k.data])-basis for k in mesh.data.shape_keys.key_blocks}
    weights=[{mesh.vertex_groups[g.group].name:float(g.weight) for g in v.groups if g.weight>0} for v in mesh.data.vertices];groups={}
    for i,ws in enumerate(weights):
        for b,v in ws.items():a,c=groups.setdefault(b,([],[]));a.append(i);c.append(v)
    groups={b:(np.asarray(a),np.asarray(c)) for b,(a,c) in groups.items()};mesh.data.calc_loop_triangles()
    return {'path':path,'hash':digest(path),'mesh':mesh,'basis':basis,'deltas':keys,'weights':weights,'groups':groups,'triangles':np.asarray([tuple(t.vertices) for t in mesh.data.loop_triangles],dtype=int),'material':np.asarray([mesh.data.polygons[t.polygon_index].material_index for t in mesh.data.loop_triangles]),'parents':{b.name:b.parent.name if b.parent else None for b in rig.data.bones}}
old=capture(OLD);new=capture(NEW);parents=new['parents']
replacement=json.loads((NEW.parent/'RealGripReplacementSummary.json').read_text(encoding='utf-8'));offset=int(replacement['retained_body_vertices']);retained=np.asarray(replacement['retained_vertex_source_indices'],dtype=int)
added=np.arange(offset,len(new['basis']));wrist=np.asarray(ref['hand_r']['p'])*np.asarray([1,-1,1]);axis=new['basis'][added].mean(0)-wrist;axis/=np.linalg.norm(axis)
distal=(new['basis']-wrist)@axis
def world(local):
    out={}
    def get(b):
        if b not in out:out[b]=get(parents[b])@mat(local[b]) if parents.get(b) else mat(local[b])
        return out[b]
    for b in local:get(b)
    return out
def skin(model,local,mw):
    w=world(local);points=model['basis'].copy();curves=dict(mw);curves.setdefault('EnemyGrip_R',1.)
    for b,val in curves.items():
        if abs(val)>1e-9 and b in model['deltas']:points+=model['deltas'][b]*val
    points=np.column_stack((points,np.ones(len(points))));out=np.zeros((len(points),3))
    for b,(ids,weights) in model['groups'].items():
        transform=np.asarray(H@w[b]@inverse[b]@H);out[ids]+=(points[ids]@transform[:3,:].T)*weights[:,None]
    return out,w
def interpolate(clip,t):
    s=clip['samples'];times=[x['time'] for x in s];lo=max(0,min(len(s)-1,bisect.bisect_right(times,t)-1));hi=min(lo+1,len(s)-1);a=s[lo];b=s[hi];f=(t-a['time'])/(b['time']-a['time']) if hi!=lo else 0.
    local={}
    for bone in a['local']:
        u=a['local'][bone];v=b['local'][bone];q=Quaternion((u['q'][3],*u['q'][:3])).slerp(Quaternion((v['q'][3],*v['q'][:3])),f)
        local[bone]={'p':list(Vector(u['p']).lerp(Vector(v['p']),f)),'q':[q.x,q.y,q.z,q.w],'s':list(Vector(u['s']).lerp(Vector(v['s']),f))}
    aw=a.get('morph_weights',{});bw=b.get('morph_weights',{});mw={k:aw.get(k,0)*(1-f)+bw.get(k,0)*f for k in set(aw)|set(bw)}
    if not mw:
        for k,curve in clip.get('morph_curves',{}).items():
            mw[k]=curve[min(lo,len(curve)-1)]['value']*(1-f)+curve[min(hi,len(curve)-1)]['value']*f
    return local,mw
def all_and_midpoints(clip):
    ts=[s['time'] for s in clip['samples']];return sorted(ts+[(a+b)*.5 for a,b in zip(ts,ts[1:])])
def group_sum(i,bs):return sum(new['weights'][int(i)].get(b,0.) for b in bs)
sets={}
hand_distal=set(int(i) for i in added if distal[i]>2.)
left=set(i for i,w in enumerate(new['weights']) if w.get('hand_l',0)>.5)
for name,predicate in {
    'palm_r':lambda tr,ma:all(int(i) in hand_distal for i in tr),
    'full_graft':lambda tr,ma:all(i>=offset for i in tr),
    'cuff_r':lambda tr,ma:ma==0 and any(group_sum(i,('lowerarm_r','hand_r'))>.25 for i in tr),
    'torso':lambda tr,ma:all(group_sum(i,('spine_01','spine_02','spine_03','neck_01','head'))>.5 for i in tr),
    'hand_l':lambda tr,ma:all(int(i) in left for i in tr),
    'cuff_l':lambda tr,ma:ma==0 and any(group_sum(i,('lowerarm_l','hand_l'))>.25 for i in tr),
}.items():
    tris=np.asarray([tr for tr,ma in zip(new['triangles'],new['material']) if predicate(tr,ma)],dtype=int)
    ids=np.unique(tris);mapping={int(v):i for i,v in enumerate(ids)};localtris=np.asarray([[mapping[int(i)] for i in tr] for tr in tris],dtype=int)
    sets[name]=(ids,localtris)
def tree(points,name):
    ids,tris=sets[name];return BVHTree.FromPolygons(points[ids].tolist(),tris.tolist(),all_triangles=True,epsilon=.0001)
edges=set()
for tr in new['triangles']:
    if all(i>=offset for i in tr):
        edges.update(tuple(sorted((int(a),int(b)))) for a,b in ((tr[0],tr[1]),(tr[1],tr[2]),(tr[2],tr[0])))
edges=np.asarray(sorted(edges));base_lengths=np.linalg.norm(new['basis'][edges[:,0]]-new['basis'][edges[:,1]],axis=1);edge_valid=base_lengths>.01
def audit_frame(local,mw,t):
    points,w=skin(new,local,mw);trees={k:tree(points,k) for k in sets};pairs={}
    for b in ('cuff_r','torso','hand_l','cuff_l'):pairs['palm_r__'+b]=len(trees['palm_r'].overlap(trees[b]))
    pairs['full_graft__cuff_r_intentional_join_region']=len(trees['full_graft'].overlap(trees['cuff_r']))
    lengths=np.linalg.norm(points[edges[:,0]]-points[edges[:,1]],axis=1);ratio=lengths[edge_valid]/base_lengths[edge_valid]
    return {'time':t,'triangle_overlaps':pairs,'graft_min_z_cm':float(points[added,2].min()),'edge_length_ratio_range':[float(ratio.min()),float(ratio.max())]},points
report={'state':'running','candidate_blend':str(NEW),'candidate_sha256':new['hash'],'baseline_blend':str(OLD),'baseline_sha256':old['hash'],'pose_sources':{p.name:digest(p) for p in (ATTACK,DEATH,OTHER)},
    'bone_count':len(parents),'graft_vertex_count':len(added),'retained_body_vertex_count':offset,'morphs':list(new['deltas']),
    'morph_evaluation':'Uses actual mesh shape-key delta arrays after topology replacement. Runtime death morph_weights interpolated between compressed samples. Legacy EnemyGrip_R=1 ignored for graft because fixed grip Basis has no such shape key.',
    'triangle_set_sizes':{k:len(v[1]) for k,v in sets.items()},'limits':'Triangle surface intersection sampled at keys and midpoints, not continuous collision or volume containment. Own-cuff overlap inside first 2 cm of wrist is counted separately as intentional graft join; distal palm overlap is not excluded.',
    'retained_basis_max_error_cm':float(np.linalg.norm(new['basis'][:offset]-old['basis'][retained],axis=1).max()),
    'retained_death_morph_max_error_cm':{k:float(np.linalg.norm(new['deltas'][k][:offset]-old['deltas'][k][retained],axis=1).max()) for k in new['deltas'] if k.startswith('EnemyDeathRobe')},'clips':{}}
failures=[];render_cases=[]
attack=json.loads(ATTACK.read_text())['clips'][0]
rows=[]
for t in all_and_midpoints(attack):
    local,mw=interpolate(attack,t);row,points=audit_frame(local,mw,t);rows.append(row)
for key in rows[0]['triangle_overlaps']:
    peak=max(rows,key=lambda x:x['triangle_overlaps'][key])
    if 'intentional' not in key and peak['triangle_overlaps'][key]>0:
        failures.append({'clip':attack['name'],'kind':key,'time':peak['time'],'pairs':peak['triangle_overlaps'][key]});render_cases.append((attack,peak['time'],key))
report['clips'][attack['name']]={'samples':len(rows),'rows':rows,'max_overlaps':{k:max(r['triangle_overlaps'][k] for r in rows) for k in rows[0]['triangle_overlaps']},'max_graft_edge_length_ratio':max(r['edge_length_ratio_range'][1] for r in rows)}
print('GRAFT_ATTACK',json.dumps({k:v for k,v in report['clips'][attack['name']].items() if k!='rows'}),flush=True)
death=json.loads(DEATH.read_text())['clips'][0];rows=[];old_hand=np.asarray([i for i,w in enumerate(old['weights']) if w.get('hand_r',0)>.5])
for t in all_and_midpoints(death):
    local,mw=interpolate(death,t);npnt,w=skin(new,local,mw);opnt,_=skin(old,local,mw)
    rows.append({'time':t,'new_hand_min_z_cm':float(npnt[added,2].min()),'old_hand_min_z_cm':float(opnt[old_hand,2].min()),'new_skin_min_z_cm':float(npnt[:,2].min()),'old_skin_min_z_cm':float(opnt[:,2].min()),'morph_weights':mw})
worst=min(rows,key=lambda r:r['new_hand_min_z_cm']);floor_pass=worst['new_hand_min_z_cm']>=-.25
report['clips'][death['name']]={'samples':len(rows),'minimum_new_hand_cm':worst['new_hand_min_z_cm'],'minimum_old_hand_cm':min(r['old_hand_min_z_cm'] for r in rows),'worst_new_hand_time':worst['time'],'floor_tolerance_cm':.25,'floor_pass':floor_pass,'rows':rows}
if not floor_pass:failures.append({'clip':death['name'],'kind':'graft_floor','time':worst['time'],'height_cm':worst['new_hand_min_z_cm']});render_cases.append((death,worst['time'],'graft_floor'))
print('GRAFT_DEATH',json.dumps({k:v for k,v in report['clips'][death['name']].items() if k!='rows'}),flush=True)
other=json.loads(OTHER.read_text())['clips']
for clip in other:
    if not clip['name'].endswith('_Upright_v01') or not any(s in clip['name'] for s in ('Idle','Walk','Hit')):continue
    indices=sorted(set(round(i*(len(clip['samples'])-1)/16) for i in range(17)));rows=[]
    for i in indices:
        t=clip['samples'][i]['time'];local,mw=interpolate(clip,t);row,points=audit_frame(local,mw,t);rows.append(row)
    peaks={k:max(r['triangle_overlaps'][k] for r in rows) for k in rows[0]['triangle_overlaps']}
    entry={'samples':len(rows),'rows':rows,'max_overlaps':peaks,'max_graft_edge_length_ratio':max(r['edge_length_ratio_range'][1] for r in rows)}
    report['clips'][clip['name']]=entry
    for key,amount in peaks.items():
        if 'intentional' not in key and amount:
            peak=max(rows,key=lambda r:r['triangle_overlaps'][key]);failures.append({'clip':clip['name'],'kind':key,'time':peak['time'],'pairs':amount});render_cases.append((clip,peak['time'],key))
    print('GRAFT_OTHER',clip['name'],json.dumps({k:v for k,v in entry.items() if k!='rows'}),flush=True)
report['failures']=failures;report['state']='failed' if failures else 'passed';report['source_hash_unchanged']=digest(NEW)==expected
if not report['source_hash_unchanged']:report['state']='stale_candidate_changed_during_audit'
(OUT.parent/'GraftedHandMotionValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('GRAFT_MOTION_VALIDATION',report['state'],json.dumps(failures),flush=True)
if render_cases:
    mesh=new['mesh']
    for o in bpy.context.scene.objects:o.hide_render=True
    md=mesh.data.copy();ob=bpy.data.objects.new('GraftAuditBody',md);bpy.context.scene.collection.objects.link(ob);ob.shape_key_clear()
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1100;scene.render.resolution_y=900;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.use_compositing=False;scene.render.use_sequencer=False
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.world=bpy.data.worlds.new('GraftAuditWorld');scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');wo=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(bg.outputs[0],wo.inputs['Surface']);bg.inputs['Color'].default_value=(.06,.06,.06,1);bg.inputs['Strength'].default_value=.5
    bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.75
    for loc,power in [((-3,-3,5),800),((4,-1,4),600),((0,4,5),800)]:
        bpy.ops.object.light_add(type='AREA',location=loc);li=bpy.context.object;li.data.energy=power;li.data.size=5
    bpy.ops.mesh.primitive_plane_add(size=15,location=(0,0,0));floor=bpy.context.object
    for n,(clip,t,kind) in enumerate(render_cases[:8]):
        local,mw=interpolate(clip,t);points,w=skin(new,local,mw);md.vertices.foreach_set('co',(points*.01).ravel());md.update();focus=Vector(points[added].mean(0)*.01)
        if kind=='graft_floor':off=Vector((1,-2,.4));cam.data.ortho_scale=.8
        else:off=Vector((.95,-.70,-.12));cam.data.ortho_scale=.65
        cam.location=focus+off;cam.rotation_euler=(-off).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/f'{n:02d}_{clip["name"]}_{t:.3f}_{kind}.png');bpy.ops.render.render(write_still=True)
