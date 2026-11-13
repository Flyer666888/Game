"""Read-only anatomical guide for the unrigged enemy fingers and existing XR grip."""
import bpy,json,math
from pathlib import Path
from collections import defaultdict,deque
import numpy as np
from mathutils import Vector,Quaternion
P=Path(r'D:\game design\experiment');OUT=P/'Docs/Gameplay/RigPolish_v04/Audit/FBXRoundTrip';OUT.mkdir(parents=True,exist_ok=True)
m=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
co=np.asarray([list(v.co) for v in m.data.vertices]);weights=[{m.vertex_groups[g.group].name:float(g.weight) for g in v.groups} for v in m.data.vertices]
ids=[i for i,p in enumerate(co) if p[0]<-35 and 80<p[2]<102 and weights[i].get('hand_r',0)>.05]
# Weld only exact coincident Basis points to reconnect the UV seams for diagnosis.
key=lambda i:tuple(round(float(x),5) for x in co[i])
groups=defaultdict(list)
for i in ids:groups[key(i)].append(i)
verts=list(groups);vi={k:i for i,k in enumerate(verts)};adj=[set() for _ in verts]
for poly in m.data.polygons:
    vs=[vi[key(i)] for i in poly.vertices if key(i) in vi]
    for a in vs:
        for b in vs:
            if a!=b:adj[a].add(b)
vco=np.asarray(verts)
cuts=[]
for zcut in (91.,90.5,90.,89.5,89.,88.5,88.):
    selected=set(np.flatnonzero(vco[:,2]<zcut));parts=[]
    while selected:
        start=selected.pop();seen={start};queue=[start]
        while queue:
            a=queue.pop()
            for b in adj[a]&selected:selected.remove(b);seen.add(b);queue.append(b)
        if len(seen)>=5:parts.append(sorted(seen))
    parts.sort(key=lambda p:len(p),reverse=True)
    cuts.append({'z':zcut,'components':[{'count':len(x),'center':list(vco[x].mean(0)),'min_z':float(vco[x,2].min())} for x in parts]})
chosen=next((x for x in cuts if len(x['components'])==4),None)
# Each lane follows an actual separate fingertip component below the webbing.
zcut=chosen['z'] if chosen else 89.
selected=set(np.flatnonzero(vco[:,2]<zcut));parts=[]
while selected:
    start=selected.pop();seen={start};queue=[start]
    while queue:
        a=queue.pop()
        for b in adj[a]&selected:selected.remove(b);seen.add(b);queue.append(b)
    if len(seen)>=5:parts.append(sorted(seen))
parts=sorted(sorted(parts,key=len,reverse=True)[:4],key=lambda ids:float(vco[ids,1].mean()))
finger_rows=[]
for name,lo,hi in [('index',-14,-10.3),('middle',-10.3,-7.6),('ring',-7.6,-4.8),('pinky',-4.8,-1.)]:
    # The source has cross-lane connections and seam fragments below the web;
    # report geometric lanes honestly instead of mislabelling graph fragments.
    lane=[i for i in ids if lo<=co[i,1]<hi and co[i,2]<=93.5 and co[i,0]<(-45. if name=='index' else -40.)]
    pc=co[lane]
    tipz=float(pc[:,2].min());cy=float(np.median(pc[:,1]));part=[]
    root_ids=np.argsort(np.abs(pc[:,2]-92.8))[:min(12,len(pc))]
    root=pc[root_ids].mean(0);tip=pc[np.argsort(pc[:,2])[:min(8,len(pc))]].mean(0)
    levels={'MCP_root_estimate':float(root[2]),'PIP_virtual_seed':float(root[2]+.45*(tip[2]-root[2])),'DIP_virtual_seed':float(root[2]+.75*(tip[2]-root[2])),'tip':float(tip[2])}
    centers={}
    for label,z in levels.items():
        n=min(16,len(pc));dist=np.abs(pc[:,2]-z);near=pc[np.argsort(dist)[:n]]
        centers[label]=near.mean(0).tolist()
    center=np.asarray(centers['MCP_root_estimate']);handle=np.asarray([-46.9,cy,90.7])
    finger_rows.append({'finger':name,'y_lane':[lo,hi],'tip_z':tipz,'landmarks_cm':centers,'root_to_handle_radial_xz_cm':float(np.linalg.norm((center-handle)[[0,2]])), 'lane_source_indices':lane})

poses=json.loads((P/'ArtSource/PlayerHands/Source/PlayerHandSourceExport.json').read_text())['poses']
def q(v):return Quaternion((v[3],*v[:3]))
def p(label,bone):return Vector(poses[label][bone]['world']['p'])
def direction(label,bone):return q(poses[label][bone]['world']['q'])@Vector((0,0,-1))
refs=[]
for f in ('index','middle','ring','pinky'):
    b=[f+'_metacarpal_r',f+'_01_r',f+'_02_r',f+'_03_r'];vs=[p('Grip',x) for x in b]
    a=(vs[1]-vs[0]).normalized();b1=(vs[2]-vs[1]).normalized();b2=(vs[3]-vs[2]).normalized();b3=direction('Grip',b[3])
    refs.append({'finger':f,'MCP_cm':list(vs[1]),'PIP_cm':list(vs[2]),'DIP_cm':list(vs[3]),'distal_direction':list(b3),
        'closed_chain_bend_degrees':{'MCP':math.degrees(a.angle(b1)),'PIP':math.degrees(b1.angle(b2)),'DIP':math.degrees(b2.angle(b3))},
        'proximal_length_cm':(vs[2]-vs[1]).length,'middle_length_cm':(vs[3]-vs[2]).length,
        'joint_local_q_xyzw':{j:poses['Grip'][f+'_'+j+'_r']['local']['q'] for j in ('01','02','03')}})
report={'source':bpy.data.filepath,'space':'enemy source Blender centimeters; exact Basis, not Grip morph',
    'hand_bounds_cm':[co[ids].min(0).tolist(),co[ids].max(0).tolist()], 'topology_cut_scan':cuts,'selected_finger_cut_z_cm':zcut,
    'fingers':finger_rows,'actual_handle_axis':{'center_cm':[-46.9,-7.7,90.7],'direction':[0,1,0],'note':'Established actual SwordGripTransform source-space hilt axis; positive Y goes toward pinky.'},
    'landmark_limit':'Enemy has no finger bones. The topology cut scan does NOT produce four stable anatomically separated branches: index/middle remain connected or split into seam fragments. Four finger labels therefore use author-confirmed Y lanes. MCP is a surface-band estimate; PIP/DIP are virtual joint seeds at 45%/75% of measured root-to-tip length, not measured anatomical joints. Lane vertex IDs are supplied as a starting region, not a hard morph mask.',
    'xr_closed_grasp_reference':refs,'xr_pose_source':'ArtSource/PlayerHands/Source/PlayerHandSourceExport.json / poses.Grip',
    'ready_reference_mesh':'ArtSource/PlayerHands/Realistic/PlayerHandRealistic_GripPreview.blend',
    'implementation_recommendation':['Use per-finger virtual MCP/PIP/DIP transforms, with a short smooth weight blend around each virtual joint; preserve cross-sectional volume.',
      'Start with the measured XR grasp chain angles, scaled to the enemy finger lengths. The whole proximal phalanx must move onto the far side of the hilt; curling distal tips alone cannot close the grip.',
      'Keep the palm heel stable near the cuff, cup the metacarpal area gradually toward the hilt, and let fingertip pads end near the proximal palm with positive skin clearance.',
      'Treat thumb as its own opposition chain from thenar pivot toward index/middle proximal pads, not as a fifth finger sharing global Z curl.',
      'Use the existing rigged realistic hand GripPreview if the original enemy hand topology cannot form closed grasp without folded triangles.']}
(OUT/'BasisFingerChainGuide.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FINGER_CUTS',json.dumps(cuts),flush=True)
print('ENEMY_FINGER_LANDMARKS',json.dumps([{k:v for k,v in f.items() if 'indices' not in k} for f in finger_rows]),flush=True)
print('XR_GRASP_ANGLES',json.dumps([{k:v for k,v in f.items() if k not in ('joint_local_q_xyzw',)} for f in refs]),flush=True)
