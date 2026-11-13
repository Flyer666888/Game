"""Support clips on the supplied skin/rig; source FBX and old assets are untouched."""
import bpy, json, math, sys, hashlib
from pathlib import Path
from mathutils import Matrix, Vector, Quaternion
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import new_rig_common as common
P=common.P;OUT=common.OUT;DOC=common.DOC
arm,mesh,walk,meta=common.load_rig()
# Applied object normalization changes bone lengths; source evaluated matrices
# still carry its uniform object scale, so keep positions/rotations and unit scale.
for row in walk:
    row['world']={b:Matrix.LocRotScale(m.translation,m.to_quaternion(),Vector((1,1,1))) for b,m in row['world'].items()}
# Supplied animation root has a 90-degree yaw offset from its own bind pose:
# toe direction is -Y during walking versus +X in rest. Correct the animation
# component frame once, keeping every native joint-relative rotation intact.
walk_facing=Matrix.Rotation(math.pi/2,4,'Z')
for row in walk:row['world']={b:walk_facing@m for b,m in row['world'].items()}
guard_data=json.loads((DOC/'NativeGuard.json').read_text())
guard={b:Matrix(m) for b,m in guard_data['world'].items()}
names=list(arm.data.bones.keys())
rest={b.name:b.matrix_local.copy() for b in arm.data.bones}
parent={b.name:b.parent.name if b.parent else None for b in arm.data.bones}
restlocal={b:rest[parent[b]].inverted()@m if parent[b] else m.copy() for b,m in rest.items()}
guardlocal={b:guard[parent[b]].inverted()@m if parent[b] else m.copy() for b,m in guard.items()}
I=Matrix.Identity(4)
def smooth(v):v=max(0,min(1,v));return v*v*(3-2*v)
def blendmat(a,b,w):
    p,q,s=a.decompose();p2,q2,s2=b.decompose()
    return Matrix.LocRotScale(p.lerp(p2,w),q.slerp(q2,w),s.lerp(s2,w))
def fk(locals):
    w={}
    for b in names:w[b]=w[parent[b]]@locals[b] if parent[b] else locals[b].copy()
    return w
def rotate_local(m,axis,degrees):
    p,q,s=m.decompose();return Matrix.LocRotScale(p,q@Quaternion(Vector(axis),math.radians(degrees)),s)
def guard_axis(bone,axis):return guard[bone].to_quaternion().inverted()@Vector(axis)
def arm_target(world,side,target,pole):
    a,b,c=('mixamorig:'+side+n for n in ('Arm','ForeArm','Hand'))
    A,B,C=(world[k].translation.copy() for k in (a,b,c))
    l1=(B-A).length;l2=(C-B).length;delta=target-A;length=min(delta.length,(l1+l2)*.98)
    axis=delta.normalized();bend=(pole-axis*pole.dot(axis)).normalized()
    along=(l1*l1-l2*l2+length*length)/(2*length)
    elbow=A+axis*along+bend*math.sqrt(max(0,l1*l1-along*along))
    desired={a:(B-A).normalized().rotation_difference((elbow-A).normalized())@world[a].to_quaternion(),
             b:(C-B).normalized().rotation_difference((target-elbow).normalized())@world[b].to_quaternion()}
    local={k:world[parent[k]].inverted()@m if parent[k] else m.copy() for k,m in world.items()}
    result={}
    for k in names:
        m=result[parent[k]]@local[k] if parent[k] else local[k].copy()
        if k in desired:m=Matrix.LocRotScale(m.translation,desired[k],Vector((1,1,1)))
        result[k]=m
    return result
def apply_exact(world):
    for b in arm.pose.bones:
        par=parent[b.name]
        local=world[par].inverted()@world[b.name] if par else world[b.name]
        b.matrix_basis=restlocal[b.name].inverted()@local
    bpy.context.view_layer.update()

# Exact weighted skin for measured floor correction; ignores no visible body vertices.
coords=np.ones((len(mesh.data.vertices),4));coords[:,:3]=np.asarray([v.co[:] for v in mesh.data.vertices])
weights={b:[] for b in names}
for v in mesh.data.vertices:
    for g in v.groups:
        name=mesh.vertex_groups[g.group].name
        if name in weights and g.weight>1e-7:weights[name].append((v.index,g.weight))
weight_arrays={b:(np.asarray([v[0] for v in rows]),np.asarray([v[1] for v in rows])) for b,rows in weights.items() if rows}
invrest={b:rest[b].inverted() for b in names}
def skin(world):
    result=np.zeros((len(coords),3))
    for b,(ids,w) in weight_arrays.items():
        transform=np.asarray(world[b]@invrest[b])
        result[ids]+=(coords[ids]@transform.T)[:,:3]*w[:,None]
    return result
def ground(world):
    floor=float(skin(world)[:,2].min());d=Matrix.Translation((0,0,-floor))
    return {b:d@m for b,m in world.items()},floor
def export(kind,worlds,fps,extra=None):
    arm.animation_data_clear()
    for b in arm.pose.bones:b.matrix_basis=I
    rows=[]
    for i,w in enumerate(worlds):
        bpy.context.scene.frame_set(i+1)
        apply_exact(w);common.key_pose(arm,i+1)
        actual=common.capture_world(arm)
        error=max((actual[b].translation-w[b].translation).length for b in names)
        assert error<.0001,(kind,i,'pose application error',error)
        rows.append({'time':i/fps,'head':list(w['mixamorig:Head'].translation),
                     'hip':list(w['mixamorig:Hips'].translation),'right_hand':list(w['mixamorig:RightHand'].translation)})
    name='Wuxia_'+kind+'_Native_v07';arm.animation_data.action.name=name
    bpy.context.scene.frame_set(1)
    path=OUT/(name+'.fbx')
    common.export_clip(arm,mesh,path,1,len(worlds),fps,include_mesh=False)
    entry={'file':str(path),'action':name,'frames':len(worlds),'fps':fps,'duration':(len(worlds)-1)/fps,
           'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bone_count':len(names),'samples':rows}
    if extra:entry.update(extra)
    return entry

reports=[]
# Breathe in the same guarded stance used by the slash. Endpoints coincide exactly.
idle=[]
for i in range(121):
    wave=math.sin(2*math.pi*i/120);loc={b:m.copy() for b,m in guardlocal.items()}
    for bone,amount in [('Spine',.35),('Spine1',.3),('Spine2',.2)]:
        bone='mixamorig:'+bone
        loc[bone]=rotate_local(loc[bone],guard_axis(bone,(0,1,0)),wave*amount)
    idle.append(fk(loc))
reports.append(export('Idle',idle,60,{'purpose':'Shared slash guard, subtle 2-second breathing cycle'}))

# Original native walk keeps its hips and leg animation. Guarded arms follow the
# walking thorax, while a small left-arm counter swing retains visible momentum.
walk_worlds=[];walk_start=walk[0]['world']['mixamorig:Hips'].translation.copy()
walk_end=walk[-1]['world']['mixamorig:Hips'].translation.copy()
guardarm={'mixamorig:'+n for n in ['LeftShoulder','LeftArm','LeftForeArm','LeftHand','RightShoulder','RightArm','RightForeArm','RightHand']}
guardarm.update(b for b in names if 'Hand' in b)
for i,row in enumerate(walk):
    w=row['world'];loc={b:w[parent[b]].inverted()@m if parent[b] else m.copy() for b,m in w.items()}
    # Convert any source travelling root to in-place; preserve cyclic vertical bob.
    delta=(walk_end-walk_start)*(i/(len(walk)-1));delta.z=0
    loc['mixamorig:Hips'].translation-=delta
    for b in guardarm:loc[b]=guardlocal[b].copy()
    loc['mixamorig:LeftArm']=rotate_local(loc['mixamorig:LeftArm'],guard_axis('mixamorig:LeftArm',(0,1,0)),3*math.sin(2*math.pi*i/(len(walk)-1)))
    world=fk(loc);world,floor=ground(world);walk_worlds.append(world)
# Supplied loop repeats its first pose exactly; retain native cadence unchanged.
assert max((walk_worlds[0][b].translation-walk_worlds[-1][b].translation).length for b in names)<.0001
stride_report={}
for side in ('Left','Right'):
    pts=[w['mixamorig:'+side+'ToeBase'].translation for w in walk_worlds]
    foot=[w['mixamorig:'+side+'Foot'].translation for w in walk_worlds]
    contact=[]
    min_z=min(p.z for p in pts)
    for i,(a,b) in enumerate(zip(pts,pts[1:])):
        velocity=-(b.x-a.x)*30
        if max(a.z,b.z)<min_z+.035 and velocity>.02:
            contact.append({'frame':i+1,'speed_m_s':velocity,'toe_height_m':a.z})
    stride_report[side]={'toe_forward_range_m':max(p.x for p in pts)-min(p.x for p in pts),
       'toe_z_range_m':[min(p.z for p in pts),max(p.z for p in pts)],'contact_segments':contact,
       'median_support_speed_m_s':float(np.median([r['speed_m_s'] for r in contact])) if contact else None}
speed_samples=[r['speed_m_s'] for v in stride_report.values() for r in v['contact_segments']]
stride_report['measured_speed_cm_s']=float(np.median(speed_samples))*100
stride_report['source_root_displacement_m']=list(walk_end-walk_start)
stride_report['source_yaw_correction_deg']=90
reports.append(export('Walk',walk_worlds,30,{'purpose':'Original supplied native leg cycle, in-place with guarded arms','source_frames':[1,32],'stride':stride_report}))

hit=[]
for i in range(49):
    t=i/60;weight=smooth(t/.13)*(1-smooth((t-.18)/.62))
    loc={b:m.copy() for b,m in guardlocal.items()}
    for bone,amount in [('Spine',-8),('Spine1',-9),('Spine2',-6),('Neck',3)]:
        bone='mixamorig:'+bone
        loc[bone]=rotate_local(loc[bone],guard_axis(bone,(0,1,0)),amount*weight)
    hit.append(fk(loc))
reports.append(export('Hit',hit,60,{'purpose':'Short guarded recoil, returns to identical guard pose'}))

# Native joint-space fall, rather than reusing old rig rotations or robe morphs.
# Knee flexion and relaxed arms precede a side fall. Each frame uses the actual
# weighted skin floor, so the new robe and head never pass beneath the ground.
death=[];floor_offsets=[]
for i in range(100):
    t=i/30;relax=smooth((t-.12)/.75);fall=smooth((t-.45)/1.25)
    loc={b:m.copy() for b,m in guardlocal.items()}
    for side in ('Left','Right'):
        for part,amount in [('Shoulder',.65),('Arm',.7),('ForeArm',.7),('Hand',.35)]:
            name='mixamorig:'+side+part
            loc[name]=blendmat(guardlocal[name],restlocal[name],relax*amount)
        # Anatomical flexion in the sagittal plane; use rest axes converted from
        # canonical world +Y so no Mixamo Euler axis is assumed.
        for part,degrees in [('UpLeg',-18),('Leg',36),('Foot',-12)]:
            name='mixamorig:'+side+part
            axis=guard[name].to_quaternion().inverted()@Vector((0,1,0))
            loc[name]=rotate_local(loc[name],axis,degrees*relax)
    for part,degrees in [('Spine',9),('Spine1',7),('Spine2',4),('Neck',-9)]:
        name='mixamorig:'+part
        loc[name]=rotate_local(loc[name],guard_axis(name,(0,1,0)),degrees*relax)
    # Let the ribs and head settle toward the supporting left side rather than
    # retain the rigid upright spinal line above the floor after the roll.
    settle=smooth((t-1.1)/.6)
    for part,degrees in [('Spine',-6),('Spine1',-6),('Spine2',-6),('Neck',-10)]:
        name='mixamorig:'+part
        loc[name]=rotate_local(loc[name],guard_axis(name,(1,0,0)),degrees*settle)
    world=fk(loc)
    # Keep the lower arm near the torso during a side fall; a hanging A-pose arm
    # would touch the ground first and hold the whole corpse conspicuously aloft.
    folded=arm_target(world,'Left',Vector((.16,.15,1.10)),Vector((1,.08,-.2)))
    folded=arm_target(folded,'Right',Vector((.18,-.12,1.03)),Vector((1,-.15,-.35)))
    wl={b:world[parent[b]].inverted()@m if parent[b] else m for b,m in world.items()}
    fl={b:folded[parent[b]].inverted()@m if parent[b] else m for b,m in folded.items()}
    world=fk({b:blendmat(wl[b],fl[b],relax) for b in names})
    # Fall onto the character's left side, with a modest forward roll. Side
    # orientation keeps the face clear of the floor and allows a relaxed body.
    root=world['mixamorig:Hips'].translation.copy()
    q=Quaternion(Vector((1,0,0)),math.radians(-88*fall))@Quaternion(Vector((0,1,0)),math.radians(10*fall))
    transform=Matrix.Translation(root+Vector((.10*fall,.32*fall,0)))@q.to_matrix().to_4x4()@Matrix.Translation(-root)
    world={b:transform@m for b,m in world.items()}
    world,offset=ground(world);floor_offsets.append(offset);death.append(world)
reports.append(export('Death',death,30,{'purpose':'Native guarded loss of balance and left-side fall; measured weighted-skin ground contact','floor_offsets_m':floor_offsets,'legacy_garment_morphs_used':False}))

# No sword archetype uses casting, but a matching skeleton asset avoids a stale
# optional reference if the shared enemy class requests one later.
cast=[]
for i in range(121):
    t=i/60;weight=smooth(t/.5)*(1-smooth((t-1.1)/.9))
    loc={b:m.copy() for b,m in guardlocal.items()}
    loc['mixamorig:LeftArm']=rotate_local(loc['mixamorig:LeftArm'],guard_axis('mixamorig:LeftArm',(0,1,0)),-25*weight)
    loc['mixamorig:LeftForeArm']=rotate_local(loc['mixamorig:LeftForeArm'],guard_axis('mixamorig:LeftForeArm',(0,1,0)),-20*weight)
    cast.append(fk(loc))
reports.append(export('Cast',cast,60,{'purpose':'Optional compatible left-hand gesture'}))

result={'state':'exported','source':str(common.SOURCE),'skeleton':'Native supplied Mixamo rest, normalized globally to 1.8m',
 'bone_names':names,'clips':reports,'limitations':['Death garment has native source skin weights; old custom garment morphs are intentionally not copied across meshes.'],
 'guard_file':str(DOC/'NativeGuard.json')}
(DOC/'NativeSupportClips.json').write_text(json.dumps(result,indent=2))
print('NATIVE_SUPPORT_EXPORTED',json.dumps([{k:v for k,v in r.items() if k not in ('samples','floor_offsets_m')} for r in reports]))
