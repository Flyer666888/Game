"""Author grounded DeathPL on the fixed combat skin, with exact held prop.

Never saves or edits the source blend, skeleton or mesh. Keeps complete source
motion, removes the old baked idle entry, smooths support and solves only local
contacts. Outputs a new animation proposal and its actually skinned evidence.
"""
import copy,json,math,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Quaternion,Vector
PROJECT=Path(__file__).resolve().parents[2]
OUT=PROJECT/'ArtSource/WuxiaMale/DeathSelection20261012';OUT.mkdir(parents=True,exist_ok=True)
OLD=PROJECT/'ArtSource/WuxiaMale/NaturalDeath'
before=json.loads((OLD/'NaturalDeathAuthoredPoses.json').read_text(encoding='utf-8'))
candidates=json.loads((OLD/'NaturalCandidatePoses.json').read_text(encoding='utf-8'))
source=next(c for c in candidates['clips'] if c['name']=='NaturalCandidate_Anim_DeathPL')
FPS=30;DURATION=3.3;SOURCE_DURATION=2.7;CLEARANCE=.15
PARENTS={'root':None,'pelvis':'root','spine_01':'pelvis','spine_02':'spine_01',
 'spine_03':'spine_02','neck_01':'spine_03','head':'neck_01','clavicle_l':'spine_03',
 'upperarm_l':'clavicle_l','lowerarm_l':'upperarm_l','hand_l':'lowerarm_l',
 'clavicle_r':'spine_03','upperarm_r':'clavicle_r','lowerarm_r':'upperarm_r','hand_r':'lowerarm_r',
 'thigh_l':'pelvis','calf_l':'thigh_l','foot_l':'calf_l','ball_l':'foot_l',
 'thigh_r':'pelvis','calf_r':'thigh_r','foot_r':'calf_r','ball_r':'foot_r'}
def mat(t):
 q=t['q'];return Matrix.LocRotScale(Vector(t['p']),Quaternion((q[3],*q[:3])),Vector(t['s']))
def record(m):
 p,q,s=m.decompose();return {'p':list(p),'q':[q.x,q.y,q.z,q.w],'s':list(s)}
def world(local):
 result={}
 for b,p in PARENTS.items():result[b]=result[p]@mat(local[b]) if p else mat(local[b])
 return result
def smooth(t):
 t=max(0.,min(1.,t));return t*t*(3.-2.*t)
def blend(a,b,w):
 q=Quaternion((a['q'][3],*a['q'][:3])).slerp(Quaternion((b['q'][3],*b['q'][:3])),w)
 return {'p':list(Vector(a['p']).lerp(Vector(b['p']),w)),'q':[q.x,q.y,q.z,q.w],
 's':list(Vector(a['s']).lerp(Vector(b['s']),w))}
def source_pose(t):
 def sampled(time):
  phase=min(len(source['samples'])-1,time/SOURCE_DURATION*source['frames']);lo=int(phase);hi=min(lo+1,len(source['samples'])-1)
  return {b:blend(source['samples'][lo]['local'][b],source['samples'][hi]['local'][b],phase-lo) for b in PARENTS}
 if t<=1.65:return sampled(t)
 # The source raises its head again after landing. Preserve the complete real
 # fall, then author a continuous relaxation to its genuine final corpse pose.
 weight=smooth((t-1.65)/.90);a=sampled(1.65);b=sampled(2.70)
 return {bone:blend(a[bone],b[bone],weight) for bone in PARENTS}
mesh=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
n=len(mesh.data.vertices);flat=np.empty(n*3);mesh.data.vertices.foreach_get('co',flat)
coords=np.ones((n,4));coords[:,:3]=flat.reshape((-1,3));basis=coords.copy()
# The runtime keeps the fist closed while this sword remains on hand_r.
grip=mesh.data.shape_keys.key_blocks.get('EnemyGrip_R') if mesh.data.shape_keys else None
if grip is None:raise RuntimeError('Actual Combat EnemyGrip_R is required for this authoring preview.')
grip_flat=np.empty(n*3);grip.data.foreach_get('co',grip_flat);coords[:,:3]=grip_flat.reshape((-1,3))
weights=[{mesh.vertex_groups[g.group].name:float(g.weight) for g in v.groups if g.weight>0} for v in mesh.data.vertices]
groups={}
for i,w in enumerate(weights):
 for b,value in w.items():ids,ws=groups.setdefault(b,([],[]));ids.append(i);ws.append(value)
groups={b:(np.asarray(ids),np.asarray(ws)) for b,(ids,ws) in groups.items()}
reflect=Matrix.Diagonal((1.,-1.,1.,1.));inverse={b:mat(candidates['reference'][b]).inverted() for b in groups}
patch=json.loads((OLD/'RobeWeightPatch.json').read_text(encoding='utf-8'))
garment={p['index'] for p in patch['vertices']};body_ids=np.asarray(sorted(set(range(n))-garment))
feet=json.loads((PROJECT/'ArtSource/WuxiaMale/FootCorrection/FeetWeightRepair.json').read_text(encoding='utf-8'))
sole_ids={side:np.asarray([v['index'] for v in feet['sole_vertices'] if v['side']==side]) for side in ('l','r')}
hand_ids={side:np.asarray([i for i,w in enumerate(weights) if w.get('hand_'+side,0.)>.5]) for side in ('l','r')}
forearm_ids={side:np.asarray([i for i,w in enumerate(weights) if w.get('lowerarm_'+side,0.)>.5]) for side in ('l','r')}
boot_ids={side:np.asarray([i for i,w in enumerate(weights) if w.get('foot_'+side,0.)+w.get('ball_'+side,0.)>.5]) for side in ('l','r')}
head_ids=np.asarray([i for i,w in enumerate(weights) if w.get('head',0.)>.5])
face_ids=np.asarray([i for i,w in enumerate(weights) if w.get('head',0.)>.8 and 142.<basis[i,2]<162.
                     and abs(basis[i,0])<8. and basis[i,1]<2.])
morphs=before.get('morph_deltas',{});curve_source=before['clips'][0]['morph_curves']
def skin(local,morph_weights=None):
 w=world(local);adjusted=coords.copy()
 for name,value in (morph_weights or {}).items():
  for d in morphs.get(name,[]):adjusted[d['index'],:3]+=np.asarray(d['delta'])*value
 result=np.zeros((n,3))
 for b,(ids,values) in groups.items():
  transform=np.asarray(reflect@w[b]@inverse[b]@reflect)
  result[ids]+=(adjusted[ids]@transform[:3,:].T)*values[:,None]
 return result,w
def curve_weights(frame):
 t=frame/FPS
 if t>1.65:t=1.65+(2.7-1.65)*smooth((t-1.65)/.9)
 phase=min(99,t*FPS);lo=int(phase);hi=min(99,lo+1);fraction=phase-lo
 return {name:keys[lo]['value']*(1.-fraction)+keys[hi]['value']*fraction for name,keys in curve_source.items()
         if keys[lo]['value'] or keys[hi]['value']}
def set_world_rotation(local,bone,q):
 w=world(local);p,old,s=w[bone].decompose();desired=Matrix.LocRotScale(p,q,s)
 record_local=record(w[PARENTS[bone]].inverted()@desired)
 local[bone]['q']=record_local['q']
def solve_two_bone(local,side,target,pole_down=0.,limb='arm'):
 result=copy.deepcopy(local)
 a,b,c=(('upperarm_','lowerarm_','hand_') if limb=='arm' else ('thigh_','calf_','foot_'))
 a+=side;b+=side;c+=side;w=world(result)
 A,B,C=(w[k].translation.copy() for k in (a,b,c));l1=(B-A).length;l2=(C-B).length
 delta=target-A;distance=min(delta.length,l1+l2-.02);distance=max(distance,abs(l1-l2)+.02)
 axis=delta.normalized();T=A+axis*distance
 pole=B-A-axis*(B-A).dot(axis)
 if pole.length<1e-5:pole=Vector((1. if side=='l' else -1.,0.,0.));pole-=axis*pole.dot(axis)
 pole.normalize()
 down=Vector((0.,0.,-1.));down-=axis*down.dot(axis)
 if down.length>1e-5:
  down.normalize();pole=pole.lerp(down,pole_down).normalized()
  if pole.length<1e-5:pole=down
 x=(l1*l1-l2*l2+distance*distance)/(2.*distance);height=math.sqrt(max(0.,l1*l1-x*x))
 newB=A+axis*x+pole*height
 qa=(B-A).normalized().rotation_difference((newB-A).normalized())@w[a].decompose()[1]
 set_world_rotation(result,a,qa)
 updated=world(result);B2=updated[b].translation;C2=updated[c].translation
 qb=(C2-B2).normalized().rotation_difference((T-B2).normalized())@updated[b].decompose()[1]
 set_world_rotation(result,b,qb)
 # Props and fingers retain the source world hand/foot orientation.
 set_world_rotation(result,c,w[c].decompose()[1])
 return result

# Exact static-mesh prop imported only into the unsaved authoring session.
old_objects=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(PROJECT/'ArtSource/Weapons/Yueyao/SlenderBladeRevision/YueyaoPlayerSlender.fbx'))
weapon_objects=[o for o in bpy.data.objects if o not in old_objects and o.type=='MESH']
if not weapon_objects:raise RuntimeError('Need actual final sword FBX for held-prop floor measurement.')
weapon=max(weapon_objects,key=lambda o:len(o.data.vertices));weapon_points=np.ones((len(weapon.data.vertices),4))
weapon_flat=np.empty(len(weapon.data.vertices)*3);weapon.data.vertices.foreach_get('co',weapon_flat)
weapon_points[:,:3]=weapon_flat.reshape((-1,3))
# FBX importer returns source centimeters in this .01-unit Combat scene.
weapon_points=(weapon_points@np.asarray(weapon.matrix_world).T)
grip_report=json.loads((PROJECT/'ArtSource/WuxiaMale/GripRefinement/GripAuthoringSummary.json').read_text(encoding='utf-8'))
q=grip_report['sword_relative_quaternion_xyzw'];attach=Matrix.LocRotScale(Vector(grip_report['sword_relative_location_cm']),Quaternion((q[3],*q[:3])),Vector(grip_report['sword_relative_scale']))
def prop_world(local):
 w=world(local);transform=np.asarray(reflect@w['hand_r']@attach@reflect)
 return weapon_points@transform[:3,:].T

raw=[];locals=[];support=[]
for i in range(100):
 t=i/FPS;local=source_pose(min(t,SOURCE_DURATION))
 for axis in (0,1):local['root']['p'][axis]*=.27
 points,w=skin(local,curve_weights(i));idx=int(body_ids[points[body_ids,2].argmin()])
 raw.append(CLEARANCE-float(points[idx,2]));locals.append(local)
 support.append({'time':t,'raw_offset_cm':raw[-1],'support_vertex':idx,'support_groups':weights[idx],
                 'support_rest_cm':list(basis[idx,:3])})
# Minimum-curvature support envelope is solved as a small constrained quadratic
# authoring problem. It anticipates a contact switch and releases it gradually,
# instead of restoring isolated raw spikes by taking max(filter, raw).
count=len(raw);second=np.zeros((count-2,count))
for i in range(count-2):second[i,i:i+3]=[1.,-2.,1.]
H=np.eye(count)+80.*(second.T@second);bound=np.asarray(raw)
fixed={i for i in range(77,count)};active=set(fixed);smooth_offsets=bound.copy()
for iteration in range(250):
 free=sorted(set(range(count))-active);locked=sorted(active)
 smooth_offsets[locked]=bound[locked]
 smooth_offsets[free]=np.linalg.solve(H[np.ix_(free,free)],bound[free]-H[np.ix_(free,locked)]@smooth_offsets[locked])
 violations=[i for i in free if smooth_offsets[i]<bound[i]-1e-7]
 if violations:
  active.add(min(violations,key=lambda i:smooth_offsets[i]-bound[i]));continue
 gradient=H@smooth_offsets-bound
 release=[i for i in active-fixed if gradient[i]<-1e-7]
 if release:active.remove(min(release,key=lambda i:gradient[i]));continue
 break
smooth_offsets[77:]=smooth_offsets[77]
# Final contact pose is solved once on the actual fixed skin, then approached
# continuously. Foot contact uses the boot side/toe rather than an ankle point.
rest=copy.deepcopy(locals[-1]);rest['root']['p'][2]+=float(smooth_offsets[-1]);rest_mw=curve_weights(99)
head_options=[]
for spine_angle in (0,4,8,12,16,20):
 for neck_angle in (0,8,16,24,32,40):
  option=copy.deepcopy(rest)
  for bone,angle in (('spine_03',spine_angle),('neck_01',neck_angle)):
   w=world(option);direction=w['head'].translation-w[bone].translation
   axis=direction.cross(Vector((0,0,-1.)))
   if axis.length>1e-5:
    axis.normalize();set_world_rotation(option,bone,Quaternion(axis,math.radians(angle))@w[bone].decompose()[1])
  posed,_=skin(option,rest_mw);face_min=float(posed[face_ids,2].min());whole_min=float(posed[:,2].min())
  score=abs(face_min-1.)+max(0.,CLEARANCE-whole_min)*100.+.01*(spine_angle+neck_angle)
  head_options.append((score,option,spine_angle,neck_angle,face_min,whole_min))
head_choice=min(head_options,key=lambda x:x[0]);rest=head_choice[1]
w=world(rest);foot_q=w['foot_r'].decompose()[1];direction=w['ball_r'].translation-w['foot_r'].translation
foot_axis=direction.cross(Vector((0,0,-1.)));foot_options=[]
if foot_axis.length>1e-5:
 foot_axis.normalize()
 for angle in (0,10,20,30,40,50):
  rotated=copy.deepcopy(rest);set_world_rotation(rotated,'foot_r',Quaternion(foot_axis,math.radians(angle))@foot_q)
  for drop in (0,4,8,12,16,20):
   for pole in (-.3,-.15,0.,.15,.3):
    target=world(rotated)['foot_r'].translation.copy();target.z-=drop
    option=solve_two_bone(rotated,'r',target,pole,'leg')
    posed,_=skin(option,rest_mw);boot_min=float(posed[boot_ids['r'],2].min());whole_min=float(posed[:,2].min())
    score=abs(boot_min-1.)+max(0.,CLEARANCE-whole_min)*200.+angle*.006+abs(pole)*.3
    foot_options.append((score,option,angle,boot_min,whole_min,drop,pole))
if foot_options:foot_choice=min(foot_options,key=lambda x:x[0]);rest=foot_choice[1]
else:foot_choice=(0,rest,0,0,0)
samples=[];rows=[]
for i,local in enumerate(locals):
 t=i/FPS;local['root']['p'][2]+=float(smooth_offsets[i]);mw=curve_weights(i)
 settle_weight=smooth((t-1.65)/.90)
 for bone in ('spine_03','neck_01','thigh_r','calf_r','foot_r'):local[bone]=blend(local[bone],rest[bone],settle_weight)
 foot_corrections={}
 # Repair only a genuinely penetrating boot after smoothing. Already grounded
 # or airborne boots are unchanged, particularly the final corpse feet.
 for side in ('l','r'):
  points,w=skin(local,mw);need=max(0.,CLEARANCE-float(points[sole_ids[side],2].min()))
  if need>.02:
   target=w['foot_'+side].translation.copy();target.z+=need
   local=solve_two_bone(local,side,target,0.,'leg');foot_corrections[side]=need
 # Left arm becomes a support/relaxed limb after the real body fall. The wrist
 # moves down only through rotation of existing upper/lower arm, never length.
 arm_weight=smooth((t-1.65)/.90)
 points,w=skin(local,mw);left_gap=float(points[hand_ids['l'],2].min())
 candidate=copy.deepcopy(local);target=w['hand_l'].translation.copy();target.z-=max(0.,left_gap-.5)
 shoulder=w['upperarm_l'].translation;reach=(w['lowerarm_l'].translation-shoulder).length+(w['hand_l'].translation-w['lowerarm_l'].translation).length-.02
 horizontal=Vector((target.x-shoulder.x,target.y-shoulder.y,0.))
 available=math.sqrt(max(.01,reach*reach-(target.z-shoulder.z)**2))
 if horizontal.length>available:
  horizontal*=available/horizontal.length;target.x=shoulder.x+horizontal.x;target.y=shoulder.y+horizontal.y
 options=[]
 for down in (0.,.15,.30,.45,.60):
  current_target=target.copy()
  for correction in range(4):
   option=solve_two_bone(candidate,'l',current_target,down);posed,_=skin(option,mw)
   palm=float(posed[hand_ids['l'],2].min());current_target.z+=1.2-palm
  fore=float(posed[forearm_ids['l'],2].min())
  score=abs(palm-1.2)+max(0.,CLEARANCE-fore)*100.+max(0.,fore-2.)*.02+down*.1
  options.append((score,option,fore,palm))
 best=min(options,key=lambda item:item[0])[1]
 for b in ('upperarm_l','lowerarm_l','hand_l'):local[b]=blend(local[b],best[b],arm_weight)
 # A loose sleeve can be a few millimeters deeper than its palm. Small natural
 # forearm pronation clears it without lifting the arm or moving the fingers.
 left_points,left_world=skin(local,mw)
 selected_twist=0.
 if arm_weight>.01 and float(left_points[forearm_ids['l'],2].min())<CLEARANCE:
  axis=left_world['hand_l'].translation-left_world['lowerarm_l'].translation
  if axis.length>1e-5:
   axis.normalize();original_arm_q=left_world['lowerarm_l'].decompose()[1];original_hand_q=left_world['hand_l'].decompose()[1]
   twist_options=[]
   for angle in (-30,-20,-10,0,10,20,30):
    option=copy.deepcopy(local);set_world_rotation(option,'lowerarm_l',Quaternion(axis,math.radians(angle)*arm_weight)@original_arm_q)
    set_world_rotation(option,'hand_l',original_hand_q);posed,_=skin(option,mw)
    fore=float(posed[forearm_ids['l'],2].min());score=max(0.,CLEARANCE-fore)*100.+abs(angle)*.005
    twist_options.append((score,option,angle))
   _,local,selected_twist=min(twist_options,key=lambda item:item[0]);selected_twist*=arm_weight
 # The attached sword relaxes to a near-horizontal rest with the right arm.
 # Nothing detaches and grip=1 remains on the actual mesh throughout.
 current_w=world(local);old_hand_q=current_w['hand_r'].decompose()[1]
 blade_root=(current_w['hand_r']@attach)@Vector((0,0,8.472));blade_tip=(current_w['hand_r']@attach)@Vector((0,0,70.972))
 direction=(blade_tip-blade_root).normalized();horizontal=Vector((direction.x,direction.y,0.))
 if horizontal.length>1e-5:
  align=direction.rotation_difference(horizontal.normalized())
  if align.angle>math.radians(45.):align=Quaternion().slerp(align,math.radians(45.)/align.angle)
  set_world_rotation(local,'hand_r',Quaternion().slerp(align,arm_weight)@old_hand_q)
 points,w=skin(local,mw);prop=prop_world(local)
 right_drop=max(0.,min(float(points[hand_ids['r'],2].min())-.65,float(prop[:,2].min())-.8))
 right_target=w['hand_r'].translation.copy();right_target.z-=right_drop
 right_options=[]
 for down in (0.,.15,.30,.45):
  option=solve_two_bone(local,'r',right_target,down);posed,_=skin(option,mw);prop_option=prop_world(option)
  fore=float(posed[forearm_ids['r'],2].min());palm=float(posed[hand_ids['r'],2].min());prop_min=float(prop_option[:,2].min())
  score=abs(prop_min-.8)+max(0.,CLEARANCE-fore)*100.+max(0.,CLEARANCE-palm)*100.+down*.1
  right_options.append((score,option))
 best_right=min(right_options,key=lambda item:item[0])[1]
 for b in ('upperarm_r','lowerarm_r','hand_r'):local[b]=blend(local[b],best_right[b],arm_weight)
 # Extra small wrist clearance constraint while blending source to rest.
 points,w=skin(local,mw);prop=prop_world(local);sword_min=float(prop[:,2].min())
 right_rotation_degrees=0.
 if t>1.55 and sword_min<CLEARANCE:
  original_q=w['hand_r'].decompose()[1];root=(w['hand_r']@attach)@Vector((0,0,8.472));tip=(w['hand_r']@attach)@Vector((0,0,70.972))
  direction=tip-root;axis=direction.cross(Vector((0,0,1.)))
  if axis.length>1e-5:
   axis.normalize();choices=[]
   for angle in range(-70,71,2):
    opt=copy.deepcopy(local);set_world_rotation(opt,'hand_r',Quaternion(axis,math.radians(angle))@original_q)
    minimum=float(prop_world(opt)[:,2].min());palm=float(skin(opt,mw)[0][hand_ids['r'],2].min())
    if minimum>=CLEARANCE and palm>=CLEARANCE:choices.append((abs(angle),angle,opt))
   if choices:
    _,angle,opt=min(choices,key=lambda item:item[0]);weight=smooth((t-1.55)/.25)
    local['hand_r']=blend(local['hand_r'],opt['hand_r'],weight);right_rotation_degrees=angle*weight
 points,w=skin(local,mw);prop=prop_world(local)
 rows.append({'time':t,'root_floor_cm':float(smooth_offsets[i]),'left_hand_min_cm':float(points[hand_ids['l'],2].min()),
  'right_hand_min_cm':float(points[hand_ids['r'],2].min()),'left_forearm_min_cm':float(points[forearm_ids['l'],2].min()),
  'right_forearm_min_cm':float(points[forearm_ids['r'],2].min()),'sword_mesh_min_cm':float(prop[:,2].min()),
  'whole_skin_min_cm':float(points[:,2].min()),'sole_l_min_cm':float(points[sole_ids['l'],2].min()),
  'sole_r_min_cm':float(points[sole_ids['r'],2].min()),'local_foot_support_correction_cm':foot_corrections,
  'right_wrist_prop_correction_degrees':right_rotation_degrees})
 rows[-1]['left_forearm_twist_degrees']=selected_twist
 rows[-1].update({'right_boot_min_cm':float(points[boot_ids['r'],2].min()),'left_boot_min_cm':float(points[boot_ids['l'],2].min()),
  'head_skin_min_cm':float(points[head_ids,2].min()),'face_skin_min_cm':float(points[face_ids,2].min()),
  'head_bone_z_cm':float(w['head'].translation.z),'right_boot_max_cm':float(points[boot_ids['r'],2].max()),
  'sword_mesh_max_cm':float(prop[:,2].max())})
 samples.append({'time':t,'local':local,'world':{b:record(m) for b,m in w.items()},'morph_weights':mw})
# Contact solution branches may choose neighboring pronation values. Smooth
# only that axial twist, then counter-rotate hand to preserve palm/bone position.
twists=np.asarray([row['left_forearm_twist_degrees'] for row in rows])
twist_filter=np.asarray([1,2,3,4,3,2,1],dtype=float);twist_filter/=twist_filter.sum()
filtered_twists=np.convolve(np.pad(twists,(3,3),mode='edge'),twist_filter,mode='valid')
for sample,row,old_twist,new_twist in zip(samples,rows,twists,filtered_twists):
 local=sample['local'];w=world(local);axis=w['hand_l'].translation-w['lowerarm_l'].translation
 if axis.length>1e-5 and abs(new_twist-old_twist)>1e-8:
  axis.normalize();hand_q=w['hand_l'].decompose()[1]
  set_world_rotation(local,'lowerarm_l',Quaternion(axis,math.radians(float(new_twist-old_twist)))@w['lowerarm_l'].decompose()[1])
  set_world_rotation(local,'hand_l',hand_q)
 points,w=skin(local,sample['morph_weights']);sample['world']={b:record(m) for b,m in w.items()}
 row.update({'left_hand_min_cm':float(points[hand_ids['l'],2].min()),'left_forearm_min_cm':float(points[forearm_ids['l'],2].min()),
  'whole_skin_min_cm':float(points[:,2].min()),'left_forearm_twist_degrees':float(new_twist)})
clip=copy.deepcopy(before['clips'][0]);clip.update({'name':'Wuxia_Death_Grounded',
 'asset':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Grounded','samples':samples})
clip['morph_curves']={name:[{'time':s['time'],'value':s['morph_weights'].get(name,0.)} for s in samples] for name in curve_source}
clip['authoring'].update({'baked_idle_entry_removed':True,'runtime_entry_blend_only':True,
 'root_support_smoothed':True,'left_arm_contact_ik':True,'held_sword_preserved':True,'preview_grip_weight':1.,
 'full_source_fall_retained_to_seconds':1.65,'source_second_head_raise_removed':True,'continuous_relaxation_seconds':[1.65,2.55]})
clip['authoring']['entry_blend_seconds']=0.
clip['authoring']['full_source_sequence']=False
clip['timing']={'full_source_fall_seconds':1.65,'authored_relaxation_end_seconds':2.55,'final_hold_seconds':.75,'loop':False}
result=copy.deepcopy(before);result['clips']=[clip];result['preview_morph_overrides']={'EnemyGrip_R':1.}
(OUT/'OptimizedDeathPoses.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
summary={'source_clip':source['name'],'fps':FPS,'duration_seconds':DURATION,'source_motion_seconds':SOURCE_DURATION,
 'baked_idle_entry_seconds':0.,'before_root_max_frame_step_cm':float(np.abs(np.diff(raw)).max()),
 'after_root_max_frame_step_cm':float(np.abs(np.diff(smooth_offsets)).max()),'root_range_cm':[float(min(smooth_offsets)),float(max(smooth_offsets))],
 'root_max_frame_second_difference_cm':float(np.abs(np.diff(smooth_offsets,n=2)).max()),
 'final_head_contact_pose':{'spine_flexion_degrees':head_choice[2],'neck_flexion_degrees':head_choice[3],
  'face_skin_cm':head_choice[4]},'final_right_boot_relax_degrees':foot_choice[2],
 'final_right_leg_contact':{'ankle_drop_cm':foot_choice[5],'knee_pole':foot_choice[6]},
 'final_contact':rows[-1],'sword_source_bounds_cm':[list(weapon_points[:,:3].min(axis=0)),list(weapon_points[:,:3].max(axis=0))],
 'maximum_sword_penetration_cm':max(0.,-min(r['sword_mesh_min_cm'] for r in rows)),
 'lowest_body_skin_cm':min(r['whole_skin_min_cm'] for r in rows),'raw_support':support,'frames':rows,
 'scope':'New animation only; fixed Combat Basis/weights/morphs and original face/feet remain unchanged.'}
(OUT/'OptimizedDeathContacts.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print('OPTIMIZED_DEATH_AUTHORED',json.dumps({k:v for k,v in summary.items() if k not in ('raw_support','frames')}),flush=True)
