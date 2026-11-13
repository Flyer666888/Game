"""Supplement selected edge lengths, exact sword contact, and contact bounds."""
from pathlib import Path
P=Path(r'D:\game design\experiment')
exec(compile((P/'Scripts/Editor/RigPolishV04/audit_hands_blender.py').read_text(encoding='utf-8').split('rows=[]')[0], 'audit_hand_setup','exec'))
weapon.data.calc_loop_triangles();swordtris=[tuple(t.vertices) for t in weapon.data.loop_triangles]
edges=[(968,971),(910,913),(116,117),(950,992)]
rows=[]
for n in range(141):
    t=clip['duration']*n/140.;local=evaluated(t);points,w=skin(local);swordpoints=prop_world(local)
    swordtree=BVHTree.FromPolygons(swordpoints.tolist(),swordtris,all_triangles=True,epsilon=.0001)
    palm=BVHTree.FromPolygons(points.tolist(),tri_sets['palm_l'],all_triangles=True,epsilon=.0001)
    cuff=BVHTree.FromPolygons(points.tolist(),tri_sets['cuff_l'],all_triangles=True,epsilon=.0001)
    rows.append({'t':t,'sword_left_palm_triangle_pairs':len(swordtree.overlap(palm)),'sword_left_cuff_triangle_pairs':len(swordtree.overlap(cuff)),
        'selected_edges_cm':{str(a)+'_'+str(b):float(np.linalg.norm(points[a]-points[b])) for a,b in edges}})
summary={'source_blend':bpy.data.filepath,'source_pose':str(pose_path),'samples':141,'fps':60,'selected_edges':{},'sword_left_palm_max_pairs':max(r['sword_left_palm_triangle_pairs'] for r in rows),'sword_left_cuff_max_pairs':max(r['sword_left_cuff_triangle_pairs'] for r in rows),'rows':rows}
for a,b in edges:
    k=str(a)+'_'+str(b);r=max(rows,key=lambda r:r['selected_edges_cm'][k]);base=float(np.linalg.norm(basis[a,:3]-basis[b,:3]));static=float(np.linalg.norm(coords[a,:3]-coords[b,:3]))
    summary['selected_edges'][k]={'basis_length_cm':base,'static_grip_length_cm':static,'max_posed_length_cm':r['selected_edges_cm'][k],'max_posed_time':r['t'],'max_pose_change_from_static_cm':r['selected_edges_cm'][k]-static,'weights':[weights[a],weights[b]]}
(OUT/'HandSupplementAudit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('HAND_SUPPLEMENT_COMPLETE',json.dumps({k:v for k,v in summary.items() if k!='rows'}),flush=True)
