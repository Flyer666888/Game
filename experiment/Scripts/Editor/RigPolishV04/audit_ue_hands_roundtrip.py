"""Independent source blend -> UE-exported FBX surface/morph/weight audit."""
import bpy, json, math, hashlib, sys
import numpy as np
from pathlib import Path
from collections import Counter
from mathutils import Matrix, Vector, Quaternion
from mathutils.kdtree import KDTree
P=Path(r'D:\game design\experiment');OUT=P/'Docs/Gameplay/RigPolish_v04/Audit/FBXRoundTrip';OUT.mkdir(parents=True,exist_ok=True)
SRC=P/'ArtSource/WuxiaMale/RigPolishV04/Hands/WuxiaMaleHands_v04.blend'
FBX=P/'Docs/Gameplay/RigPolish_v04/Audit/UE_HandsA.fbx'

def capture():
    m=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];rig=max(rigs,key=lambda o:len(o.data.bones))
    def points(key=None):
        values=m.data.shape_keys.key_blocks[key].data if key else m.data.vertices
        return np.asarray([list(m.matrix_world@v.co) for v in values],dtype=float)
    uv=[set() for _ in m.data.vertices]
    if m.data.uv_layers:
        layer=m.data.uv_layers.active
        for loop in m.data.loops:uv[loop.vertex_index].add(tuple(round(float(x),6) for x in layer.data[loop.index].uv))
    uv=[tuple(sorted(x)) for x in uv]
    morphs={k.name:points(k.name) for k in m.data.shape_keys.key_blocks} if m.data.shape_keys else {}
    weights=[{m.vertex_groups[g.group].name:float(g.weight) for g in v.groups if g.weight>1e-8} for v in m.data.vertices]
    m.data.calc_loop_triangles()
    return {'mesh':m.name,'points':points(),'morphs':morphs,'weights':weights,'uv':uv,'polys':[tuple(p.vertices) for p in m.data.polygons],
        'triangles':[tuple(t.vertices) for t in m.data.loop_triangles],'bones':{b.name:np.asarray(rig.matrix_world@b.head_local) for b in rig.data.bones},
        'parents':{b.name:b.parent.name if b.parent else None for b in rig.data.bones},'mesh_matrix':[list(r) for r in m.matrix_world],
        'materials':[x.name if x else None for x in m.data.materials], 'material_indices':[p.material_index for p in m.data.polygons]}

bpy.ops.wm.open_mainfile(filepath=str(SRC));source=capture()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(FBX));imported=capture()
names=sorted(set(source['bones'])&set(imported['bones']))
X=np.asarray([imported['bones'][b] for b in names]);Y=np.asarray([source['bones'][b] for b in names]);mx=X.mean(axis=0);my=Y.mean(axis=0)
U,S,VT=np.linalg.svd((X-mx).T@(Y-my));R=U@VT;scale=float(S.sum()/np.square(X-mx).sum());offset=my-mx@R*scale
def aligned(points):return points@R*scale+offset
B=aligned(imported['points']);bone_error=np.linalg.norm(aligned(X)-Y,axis=1)
tree=KDTree(len(source['points']))
for i,co in enumerate(source['points']):tree.insert(Vector(co),i)
tree.balance()
mapping=[];ambiguities=0;uv_misses=[];nearest=[]
for i,co in enumerate(B):
    close=tree.find_range(Vector(co),.005)
    if not close:close=[tree.find(Vector(co))]
    uv_candidates=[x for x in close if source['uv'][x[1]]==imported['uv'][i]]
    if not uv_candidates:
        # FBX export may split a source vertex into separate UV wedges.
        uv_candidates=[x for x in close if set(imported['uv'][i]).issubset(set(source['uv'][x[1]]))]
    if not uv_candidates:uv_misses.append(i);uv_candidates=close
    if len(uv_candidates)>1:ambiguities+=1
    best=min(uv_candidates,key=lambda x:x[2]);mapping.append(best[1]);nearest.append(best[2])
mapping=np.asarray(mapping);nearest=np.asarray(nearest)
def metric(v):
    return {'max':float(v.max()) if len(v) else 0.,'p99':float(np.percentile(v,99)) if len(v) else 0.,'over_0_01':int((v>.01).sum()),'over_0_001':int((v>.001).sum())}
report={'source_blend':str(SRC),'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'ue_exported_fbx':str(FBX),'ue_exported_fbx_sha256':hashlib.sha256(FBX.read_bytes()).hexdigest(),
    'source_vertex_count':len(source['points']),'ue_fbx_vertex_count':len(B),'source_mesh_matrix':source['mesh_matrix'],'ue_mesh_matrix':imported['mesh_matrix'],
    'axis_alignment':{'scale':scale,'rotation':R.tolist(),'offset':offset.tolist(),'bone_head_error_cm':metric(bone_error),'common_bones':names},
    'basis_error_cm':metric(nearest),'uv_unmatched_count':len(uv_misses),'uv_unmatched_sample':uv_misses[:12],'ambiguous_geometric_uv_matches':ambiguities,
    'source_polygon_sizes':dict(Counter(map(len,source['polys']))),'ue_polygon_sizes':dict(Counter(map(len,imported['polys']))),
    'source_morphs':list(source['morphs']),'ue_exported_morphs':list(imported['morphs']),'morphs':{},'weights':{}}
for name,co in imported['morphs'].items():
    match=next((s for s in source['morphs'] if name==s or name.endswith(s)),None)
    if not match:continue
    err=np.linalg.norm((aligned(co)-B)-(source['morphs'][match]-source['points'])[mapping],axis=1)
    report['morphs'][name]={'source_name':match,'delta_error_cm':metric(err),'worst':[{'imported_index':int(i),'source_index':int(mapping[i]),'error_cm':float(err[i]),'imported_delta':list(aligned(co)[i]-B[i]),'source_delta':list(source['morphs'][match][mapping[i]]-source['points'][mapping[i]])} for i in np.argsort(-err)[:10]]}
werrors=[];wmissing=[]
for i,j in enumerate(mapping):
    a=source['weights'][j];b=imported['weights'][i]
    werrors.append(max([abs(a.get(bone,0)-b.get(bone,0)) for bone in set(a)|set(b)] or [0.]))
    if not b:wmissing.append(i)
werrors=np.asarray(werrors)
report['weights']={'max_abs_influence_error':float(werrors.max()),'vertices_error_over_0_0001':int((werrors>.0001).sum()),'vertices_error_over_0_01':int((werrors>.01).sum()),'missing_weights_count':len(wmissing),'worst':[{'imported_index':int(i),'source_index':int(mapping[i]),'error':float(werrors[i]),'source':source['weights'][mapping[i]],'imported':imported['weights'][i]} for i in np.argsort(-werrors)[:12]]}
# Compare triangle support by matched POSITION + UV key, independent of index order.
def canonical(i):return tuple(round(float(x),4) for x in source['points'][i])+source['uv'][i]
st=Counter(tuple(sorted(canonical(i) for i in tri)) for tri in source['triangles'])
it=Counter(tuple(sorted(canonical(int(mapping[i])) for i in tri)) for tri in imported['triangles'])
report['triangles']={'source_count':len(source['triangles']),'imported_count':len(imported['triangles']),'missing_from_imported_count':sum((st-it).values()),'new_imported_count':sum((it-st).values())}
(OUT/'UE_HandsA_RoundTrip.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('UE_FBX_AUDIT',json.dumps({k:v for k,v in report.items() if k not in ('morphs','weights')}),flush=True)
print('UE_FBX_MORPH_ERRORS',json.dumps({k:v['delta_error_cm'] for k,v in report['morphs'].items()}),flush=True)
print('UE_FBX_WEIGHT_ERRORS',json.dumps({k:v for k,v in report['weights'].items() if k!='worst'}),flush=True)

if '--render' in sys.argv:
    setup=P/'Saved/Scripts/bake_selected_death.py';ctx={'__name__':'round_trip_skin','__file__':str(setup)}
    exec(compile(setup.read_text(encoding='utf-8').split('raw=[];locals=[];support=[]')[0],str(setup),'exec'),ctx)
    for o in bpy.context.scene.objects:o.hide_render=True
    data=json.loads((P/'ArtSource/WuxiaMale/RigPolishV04/Attack/NaturalAttackRuntimePoses.json').read_text(encoding='utf-8'))
    sample=min(data['clips'][0]['samples'],key=lambda s:abs(s['time']-1.0333333));w=ctx['world'](sample['local']);reflect=ctx['reflect'];mat=ctx['mat']
    inv={b:mat(t).inverted() for b,t in data['reference'].items()}
    def skin(co,weights):
        inp=np.column_stack([co,np.ones(len(co))]);out=np.zeros((len(co),3))
        for bone in names:
            if bone not in w or bone not in inv:continue
            ids=np.asarray([i for i,x in enumerate(weights) if x.get(bone,0)>0],dtype=int)
            if not len(ids):continue
            weight=np.asarray([weights[i][bone] for i in ids]);matrix=np.asarray(reflect@w[bone]@inv[bone]@reflect)
            out[ids]+=(inp[ids]@matrix.T)[:,:3]*weight[:,None]
        return out
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1100;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.render.use_compositing=False;scene.render.use_sequencer=False
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=-2.;scene.view_settings.gamma=1.
    scene.world=bpy.data.worlds.new('RoundTripWorld');scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');wo=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(bg.outputs[0],wo.inputs['Surface']);bg.inputs['Color'].default_value=(.045,.045,.045,1);bg.inputs['Strength'].default_value=.5
    clay=bpy.data.materials.new('AuditClay');clay.diffuse_color=(.58,.58,.58,1)
    focus=Vector(w['hand_r'].translation);focus.y=-focus.y;focus*=.01
    bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=.40
    offset_camera=Vector((.95,-.70,-.12));camera.location=focus+offset_camera;camera.rotation_euler=(-offset_camera).to_track_quat('-Z','Y').to_euler()
    for loc,power in [((1,-3,4),750),((-2,-1,3),500),((1,3,2),400)]:
        bpy.ops.object.light_add(type='AREA',location=loc);li=bpy.context.object;li.data.energy=power;li.data.size=3;li.rotation_euler=(focus-li.location).to_track_quat('-Z','Y').to_euler()
    gname=next((n for n in imported['morphs'] if n.endswith('EnemyGrip_R')),None)
    variants=[('Source_HandsA',source['morphs']['EnemyGrip_R'],source['weights'],source['triangles']),('Source_OpenBasis',source['points'],source['weights'],source['triangles'])]
    if gname:variants.append(('UE_Export_HandsA',aligned(imported['morphs'][gname]),imported['weights'],imported['triangles']))
    else:variants.append(('UE_Export_Basis_NoMorph',B,imported['weights'],imported['triangles']))
    if gname:
        posed_source=skin(source['morphs']['EnemyGrip_R'],source['weights'])
        posed_imported=skin(aligned(imported['morphs'][gname]),imported['weights'])
        report['posed_skin_error_cm_at_1_033s']=metric(np.linalg.norm(posed_imported-posed_source[mapping],axis=1))
        (OUT/'UE_HandsA_RoundTrip.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('POSED_SKIN_ERROR',json.dumps(report['posed_skin_error_cm_at_1_033s']),flush=True)
    for label,co,weights,tris in variants:
        posed=skin(co,weights);md=bpy.data.meshes.new(label);md.from_pydata((posed*.01).tolist(),[],tris);md.materials.append(clay)
        for poly in md.polygons:poly.use_smooth=True
        ob=bpy.data.objects.new(label,md);scene.collection.objects.link(ob)
        scene.render.filepath=str(OUT/(label+'_103_Palm_Clay.png'));bpy.ops.render.render(write_still=True);ob.hide_render=True
    print('UE_FBX_CLAY_RENDERED',flush=True)
