"""Repair a derivative right-hand grip and wrist weights; preserve source data."""
import bpy,json,math,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
P=Path(r'D:\game design\experiment');O=P/'ArtSource/WuxiaMale/RigPolishV04/Hands';O.mkdir(parents=True,exist_ok=True)
mesh=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
source=bpy.data.filepath
coords=np.asarray([list(v.co) for v in mesh.data.vertices]);old=[{mesh.vertex_groups[g.group].name:float(g.weight) for g in v.groups if g.weight>0} for v in mesh.data.vertices]
def digest(v):return hashlib.sha256(repr(v).encode()).hexdigest()
def invariants():
    return {'basis':digest([list(v.co) for v in mesh.data.vertices]),'topology':digest([list(p.vertices) for p in mesh.data.polygons]),'uv':digest([[list(v.uv) for v in l.data] for l in mesh.data.uv_layers]),'materials':[(m.name if m else None) for m in mesh.data.materials],'material_indices':digest([p.material_index for p in mesh.data.polygons]),'skeleton':digest([(b.name,b.parent.name if b.parent else None,list(b.head_local),list(b.tail_local),list(b.matrix_local)) for b in rig.data.bones]),'other_morphs':{k.name:digest([list(v.co) for v in k.data]) for k in mesh.data.shape_keys.key_blocks if k.name!='EnemyGrip_R'}}
before=invariants();grip=mesh.data.shape_keys.key_blocks['EnemyGrip_R'];oldgrip=np.asarray([list(v.co) for v in grip.data]);newgrip=coords.copy()
def smooth(a,b,x):
    t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3.-2*t)
# The original grip had a hard x=-42.5 selection boundary through the thumb.
# Apply the same continuous displacement field to the entire anatomical hand.
for i,(p,w) in enumerate(zip(coords,old)):
    x,y,z=p
    if x>-35 or z>104 or z<80 or y>3 or y<-18 or w.get('hand_r',0)+w.get('lowerarm_r',0)<.5:continue
    mask=(1-smooth(-39,-35,x))*(1-smooth(99,104,z))*smooth(80,82,z)*(1-smooth(1,3,y))*smooth(-18,-16,y)
    four=1.-smooth(90.5,91.7,z)*smooth(9.7,11.2,-y)
    s=max(0.,90.7-z);a=min(4.3,s/1.9);normal=x-(-49.+1.65*smooth(0,6,s))
    finger=np.asarray([-48.8+1.9*(1-math.cos(a))+normal*math.cos(a),y,90.7-1.9*math.sin(a)+normal*math.sin(a)])
    fingerblend=smooth(0,1.2,91.4-z)*four
    thumbweight=(1-four)*smooth(10,12.8,-y)
    target=p+(finger-p)*fingerblend+np.asarray([2.3,2.8,-.45])*thumbweight
    newgrip[i]=p+(target-p)*mask
# Smooth only the displacement field at the thumb web; preserve fingers and
# original surface thickness. Equal source positions share identical deltas.
neighbors=[set() for _ in coords]
for e in mesh.data.edges:
    a,b=e.vertices;neighbors[a].add(b);neighbors[b].add(a)
deltas=newgrip-coords
for iteration in range(5):
    updated=deltas.copy()
    for i,p in enumerate(coords):
        x,y,z=p
        mask=(1-smooth(-37,-34,x))*smooth(-13.5,-10.5,y)*(1-smooth(-9.8,-8.5,y))*smooth(89,90.8,z)*(1-smooth(94,96,z))
        if mask<=0 or not neighbors[i] or old[i].get('hand_r',0)<.02:continue
        ns=list(neighbors[i]);dist=np.linalg.norm(coords[ns]-p,axis=1);ws=1/np.maximum(dist,.2)
        avg=np.average(deltas[ns],axis=0,weights=ws)
        updated[i]=deltas[i]*(1-.45*mask)+avg*(.45*mask)
    deltas=updated
newgrip=coords+deltas
seams={}
for i,p in enumerate(coords):seams.setdefault(tuple(round(float(v),4) for v in p),[]).append(i)
for ids in seams.values():
    if len(ids)>1 and any(np.linalg.norm(deltas[i])>.00001 for i in ids):
        mean=np.mean(deltas[ids],axis=0)
        for i in ids:newgrip[i]=coords[i]+mean
for v,p in zip(grip.data,newgrip):v.co=p
grip.value=0.
reference=json.loads((P/'ArtSource/WuxiaMale/NaturalDeath/NaturalCandidatePoses.json').read_text(encoding='utf-8'))['reference']
wrist=np.asarray(reference['hand_r']['p'])*np.asarray([1,-1,1]);axis=np.asarray([-.3191732196912358,-.5743433374616473,-.7538290167838767])
changes=[]
for i,(p,w) in enumerate(zip(coords,old)):
    d=float((p-wrist)@axis)
    if p[0]>-34 or p[2]>111 or p[2]<80 or w.get('hand_r',0)+w.get('lowerarm_r',0)<.5 or d<=-4:continue
    region=smooth(-4,-2,d);hand=smooth(-3,4,d);target={'hand_r':hand,'lowerarm_r':1-hand}
    new={b:w.get(b,0)*(1-region)+target.get(b,0)*region for b in set(w)|set(target)}
    total=sum(new.values());new={b:v/total for b,v in new.items() if v>1e-7}
    if max(abs(new.get(b,0)-w.get(b,0)) for b in set(w)|set(new))<1e-7:continue
    for g in mesh.vertex_groups:g.remove([i])
    for b,v in new.items():mesh.vertex_groups[b].add([i],v,'REPLACE')
    changes.append({'index':i,'weights':new})
after=invariants();assert before==after,'Unrelated geometry/UV/rig/material/morph changed'
mesh.name='SK_WuxiaMale_Hands_v04';scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
blend=O/'WuxiaMaleHands_v04.blend';fbx=O/'WuxiaMaleHands_v04.fbx'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,use_armature_deform_only=True,bake_anim=False,apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',path_mode='STRIP',mesh_smooth_type='FACE',use_mesh_modifiers=False)
report={'source':source,'blend':str(blend),'fbx':str(fbx),'preserved_invariants':before,'bone_count':len(rig.data.bones),'vertex_count':len(coords),'changed_weight_vertices':len(changes),'weight_patch':changes,'grip_changed_vertices':int((np.linalg.norm(newgrip-oldgrip,axis=1)>.00001).sum()),'grip_max_correction_cm':float(np.linalg.norm(newgrip-oldgrip,axis=1).max()),'status':'candidate_requires_neutral_and_motion_review'}
(O/'HandsRepairSummary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('HAND_REPAIR_SAVED',str(blend),len(changes),'weight vertices',flush=True)
