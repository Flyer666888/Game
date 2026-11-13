"""Read-only weight and deformation audit, plus whole right arm contact check."""
from pathlib import Path
P=Path(r'D:\game design\experiment')
exec(compile((P/'Scripts/Editor/RigPolishV04/audit_hands_blender.py').read_text(encoding='utf-8').split('rows=[]')[0], 'audit_hand_setup','exec'))
out={'hands':{},'arm_contacts':[],'deformation':[]}
for side in ('r','l'):
    ids=side_data[side]['ids'];wrist=side_data[side]['wrist'];hand='hand_'+side;fore='lowerarm_'+side
    openaxis=basis[ids,:3].mean(axis=0)-wrist;openaxis/=np.linalg.norm(openaxis)
    bind_fore=np.asarray(reference[hand]['p'])-np.asarray(reference[fore]['p']);bind_fore*=np.array([1.,-1.,1.]);bind_fore/=np.linalg.norm(bind_fore)
    weightsummary={b:{'count':sum(weights[int(i)].get(b,0)>0.00001 for i in ids),'max':max(weights[int(i)].get(b,0) for i in ids),'mean':float(np.mean([weights[int(i)].get(b,0) for i in ids]))} for b in sorted({b for i in ids for b in weights[int(i)]})}
    suspicious=[{'vertex':int(i),'weights':weights[int(i)],'basis_cm':list(basis[int(i),:3]),'morph_cm':list(coords[int(i),:3]),'morph_displacement_cm':float(np.linalg.norm(coords[int(i),:3]-basis[int(i),:3]))} for i in ids if any(b not in (hand,fore) and v>.00001 for b,v in weights[int(i)].items())]
    exacthand=[int(i) for i in ids if weights[int(i)].get(hand,0)>.9999]
    matref=context['mat'](reference[hand]);localaxis=matref.to_3x3().inverted()@Vector(openaxis*np.array([1.,-1.,1.]))
    out['hands'][side]={'strong_hand_vertex_count':len(ids),'rigid_hand_vertex_count':len(exacthand),'weights':weightsummary,'non_hand_or_lowerarm_vertices':suspicious,'basis_open_palm_axis_blender':list(openaxis),'basis_open_palm_axis_hand_local':list(localaxis),'reference_forearm_to_open_palm_degrees':math.degrees(math.acos(float(np.clip(bind_fore@openaxis,-1,1)))),'grip_forearm_to_palm_degrees':math.degrees(math.acos(float(np.clip(bind_fore@side_data[side]['direction'],-1,1)))),'max_grip_displacement_cm':float(np.linalg.norm(coords[ids,:3]-basis[ids,:3],axis=1).max())}

armbones=['upperarm_r','lowerarm_r','hand_r']
armtris=[tr for tr in triangles if all(group_sum(i,armbones)>.5 for i in tr)]
foretris=[tr for tr in triangles if all(group_sum(i,['lowerarm_r'])>.5 for i in tr)]
torsotris=tri_sets['torso'];out['contact_triangle_counts']={'arm_r':len(armtris),'lowerarm_r':len(foretris),'torso':len(torsotris)}
edges=sorted({tuple(sorted((a,b))) for tr in triangles if any(i in side_data['r']['palm'] for i in tr) for a,b in ((tr[0],tr[1]),(tr[1],tr[2]),(tr[2],tr[0]))})
edge=np.asarray(edges);morphlength=np.linalg.norm(coords[edge[:,0],:3]-coords[edge[:,1],:3],axis=1);basislength=np.linalg.norm(basis[edge[:,0],:3]-basis[edge[:,1],:3],axis=1)
ratio=morphlength/np.maximum(basislength,.0001)
out['right_grip_edge_stretch_vs_basis']=[{'edge':list(edges[int(i)]),'basis_length_cm':float(basislength[i]),'grip_length_cm':float(morphlength[i]),'ratio':float(ratio[i]),'weights':[weights[k] for k in edges[int(i)]]} for i in np.argsort(-ratio)[:20]]
for n in range(141):
    t=clip['duration']*n/140.;local=evaluated(t);points,w=skin(local)
    torso=BVHTree.FromPolygons(points.tolist(),torsotris,all_triangles=True,epsilon=.0001)
    arm=BVHTree.FromPolygons(points.tolist(),armtris,all_triangles=True,epsilon=.0001)
    fore=BVHTree.FromPolygons(points.tolist(),foretris,all_triangles=True,epsilon=.0001)
    armhit=arm.overlap(torso);forehit=fore.overlap(torso)
    out['arm_contacts'].append({'t':t,'arm_torso_triangle_pairs':len(armhit),'forearm_torso_triangle_pairs':len(forehit),'example_forearm_triangle_ids':forehit[:8]})
    length=np.linalg.norm(points[edge[:,0]]-points[edge[:,1]],axis=1);stretch=length/np.maximum(morphlength,.0001)
    order=np.argsort(-stretch)
    out['deformation'].append({'t':t,'right_hand_edge_max_stretch_vs_grip':float(stretch.max()),'right_hand_edge_min_stretch_vs_grip':float(stretch.min()),'max_edge':list(edges[int(order[0])]),'worst_weights':[weights[i] for i in edges[int(order[0])]]})
out['worst_arm_contact']=max(out['arm_contacts'],key=lambda a:a['arm_torso_triangle_pairs'])
out['worst_forearm_contact']=max(out['arm_contacts'],key=lambda a:a['forearm_torso_triangle_pairs'])
out['worst_hand_stretch']=max(out['deformation'],key=lambda a:a['right_hand_edge_max_stretch_vs_grip'])
(OUT/'HandWeightsAudit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print('HAND_WEIGHT_AUDIT_COMPLETE',str(OUT/'HandWeightsAudit.json'))
