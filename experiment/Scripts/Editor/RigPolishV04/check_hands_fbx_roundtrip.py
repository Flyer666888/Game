import bpy,json,numpy as np
from pathlib import Path
from mathutils.kdtree import KDTree
P=Path(r'D:\game design\experiment');D=P/'Docs/Gameplay/RigPolish_v04/Audit'
m=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices));basis=np.asarray([list(v.co) for v in m.data.vertices]);grip=np.asarray([list(v.co) for v in m.data.shape_keys.key_blocks['EnemyGrip_R'].data]);source=bpy.data.filepath
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.import_scene.fbx(filepath=str(P/'ArtSource/WuxiaMale/RigPolishV04/Hands/WuxiaMaleHands_v04.fbx'))
m=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices));b=np.asarray([list(v.co) for v in m.data.vertices]);g=np.asarray([list(v.co) for v in m.data.shape_keys.key_blocks['EnemyGrip_R'].data]);tree=KDTree(len(basis))
for i,p in enumerate(basis):tree.insert(p,i)
tree.balance();matches=[tree.find(p) for p in b];ids=np.asarray([q[1] for q in matches]);dist=np.asarray([q[2] for q in matches]);delta=np.linalg.norm((g-b)-(grip-basis)[ids],axis=1)
report={'source':source,'basis_vertices':len(basis),'fbx_vertices':len(b),'fbx_shape_keys':[k.name for k in m.data.shape_keys.key_blocks],'nearest_basis_max_error_cm':float(dist.max()),'morph_delta_max_error_cm':float(delta.max()),'morph_delta_p99_error_cm':float(np.percentile(delta,99)),'morph_vertices_error_over_0_01cm':int((delta>.01).sum()),'worst':[{'fbx_vertex':int(i),'basis_vertex':int(ids[i]),'basis_distance':float(dist[i]),'morph_error_cm':float(delta[i])} for i in np.argsort(-delta)[:10]]}
(D/'HandsFbxRoundtrip.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('FBX_ROUNDTRIP',json.dumps(report),flush=True)
