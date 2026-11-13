"""Second grip candidate: rotate the thumb toward the actual shaft."""
import bpy,json,math
import numpy as np
from pathlib import Path
from mathutils import Vector
P=Path(r'D:\game design\experiment');O=P/'ArtSource/WuxiaMale/RigPolishV04/HandsOpposed';O.mkdir(parents=True,exist_ok=True)
mesh=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices));grip=mesh.data.shape_keys.key_blocks['EnemyGrip_R'];xyz=np.asarray([list(v.co) for v in mesh.data.vertices]);old=np.asarray([list(v.co) for v in grip.data]);result=old.copy()
def smooth(a,b,x):
    t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
pivot=Vector((-43.5,-9.8,95.0));tip_ids=[i for i,p in enumerate(xyz) if -46<p[0]<-39 and p[1]<-12.7 and 91<p[2]<95]
tip=Vector(xyz[tip_ids].mean(axis=0));desired=Vector((-46.7,-9.5,91.5));rot=(tip-pivot).rotation_difference(desired-pivot)
changed=[]
finger_y=np.asarray([-11.4,-8.9,-6.3,-3.5]);finger_tip_z=[]
for lo,hi in [(-14,-10.3),(-10.3,-7.6),(-7.6,-4.8),(-4.8,-1.)]:
    pts=xyz[(xyz[:,0]<-44)&(xyz[:,1]>=lo)&(xyz[:,1]<hi)&(xyz[:,2]<90)&(xyz[:,2]>80)]
    finger_tip_z.append(float(pts[:,2].min()))
for i,p in enumerate(xyz):
    x,y,z=p
    if not (-53<x<-35 and 80<z<99 and -18<y<3):continue
    four=1.-smooth(90.5,91.7,z)*smooth(9.7,11.2,-y)
    thumb=(1-four)*smooth(10,12.8,-y)
    # Start the flexion in the proximal finger/palm base, above the former
    # 90.7cm distal-only curl. The shaft transform remains entirely unchanged.
    s=max(0.,93.-z);tip_z=float(np.interp(y,finger_y,finger_tip_z));progress=max(0.,min(1.,s/(93.-tip_z)))
    # Each finger has its own source length. Proximal, middle and distal arcs
    # close in sequence; there is no shared hard angular cap flattening tips.
    angle=float(np.interp(progress,[0.,.28,.60,1.],[-.8,.2,2.2,4.2]))
    old_s=max(0.,90.7-z);centre=-49+1.65*smooth(0,6,old_s)+1.7*smooth(90.7,94,z)
    # The palm is thicker than the finger strips. Keeping its inner surface
    # inside the bend radius prevents an inverted fold through the shaft axis.
    normal=1.1*math.tanh((x-centre)/1.6)
    target=np.asarray([-46.9-1.65*math.cos(angle)+normal*math.cos(angle),y,90.7-1.65*math.sin(angle)+normal*math.sin(angle)])
    weight=smooth(0,2.5,95-z)*four
    result[i]=p+(target-p)*weight+np.asarray([2.3,2.8,-.45])*thumb
for i,p in enumerate(xyz):
    x,y,z=p
    if x>-35 or x<-53 or z>99 or z<89 or y>-8 or y<-18:continue
    original_four=1.-smooth(90.5,91.7,z)*smooth(9.7,11.2,-y)
    original_thumb=(1-original_four)*smooth(10,12.8,-y)
    weight=smooth(9.3,12.5,-y)*smooth(89.5,91.3,z)*(1-smooth(96.8,99,z))
    if weight<.00001 and original_thumb<.00001:continue
    # Remove the old outward translation and replace it with a soft thumb-base
    # rotation. Preserve the four-finger curl and all wrist geometry.
    base=result[i]-np.asarray([2.3,2.8,-.45])*original_thumb
    delta=np.asarray(pivot+rot@(Vector(p)-pivot)-Vector(p))
    result[i]=base+delta*weight
    changed.append(i)
neighbors=[set() for _ in xyz]
for e in mesh.data.edges:
    a,b=e.vertices;neighbors[a].add(b);neighbors[b].add(a)
deltas=result-xyz
for iteration in range(3):
    upd=deltas.copy()
    for i in changed:
        p=xyz[i];weight=smooth(89.5,91.3,p[2])*(1-smooth(93.5,95,p[2]))*smooth(9.3,11,-p[1])*(1-smooth(12.5,14,-p[1]))
        if not neighbors[i] or weight<.00001:continue
        ns=list(neighbors[i]);ws=1/np.maximum(np.linalg.norm(xyz[ns]-p,axis=1),.2)
        upd[i]=deltas[i]*(1-.35*weight)+np.average(deltas[ns],axis=0,weights=ws)*(.35*weight)
    deltas=upd
result=xyz+deltas
seams={}
for i,p in enumerate(xyz):seams.setdefault(tuple(round(float(v),4) for v in p),[]).append(i)
for ids in seams.values():
    if len(ids)>1 and any(i in changed for i in ids):
        avg=np.mean(deltas[ids],axis=0)
        for i in ids:result[i]=xyz[i]+avg
for v,p in zip(grip.data,result):v.co=p
grip.value=0;mesh.name='SK_WuxiaMale_Hands_v04b';blend=O/'WuxiaMaleHands_v04b.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
(O/'OpposedGripSummary.json').write_text(json.dumps({'source':str(P/'ArtSource/WuxiaMale/RigPolishV04/Hands/WuxiaMaleHands_v04.blend'),'blend':str(blend),'thumb_tip_source_cm':list(tip),'thumb_tip_target_cm':list(desired),'rotation_degrees':math.degrees(rot.angle),'changed_vertices':len(changed),'max_correction_cm':float(np.linalg.norm(result-old,axis=1).max()),'basis_topology_uv_weights_skeleton_other_morphs_changed':False},indent=2),encoding='utf-8')
print('OPPOSED_GRIP_CANDIDATE',str(blend),list(tip),math.degrees(rot.angle),flush=True)
