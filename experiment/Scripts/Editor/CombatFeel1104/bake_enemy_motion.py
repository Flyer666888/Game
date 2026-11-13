"""Author v06 poses from existing skeleton data; run with Blender --background.

No source mesh, animation or blend file is changed. Foot IK keeps the authored
support contacts while the pelvis transfers weight into a cross-body cut.
"""
import copy, json, math, bpy
from pathlib import Path
from mathutils import Matrix, Quaternion, Vector

P = Path(r'D:/game design/experiment')
OUT = P / 'Docs/Gameplay/CombatFeel1104'
OUT.mkdir(parents=True, exist_ok=True)
source = json.loads((P / 'ArtSource/WuxiaMale/RigPolishV04/Attack/NaturalAttackPoses.json').read_text())
attack = source['clips'][0]
other = json.loads((P / 'Docs/Gameplay/RigPolish_v01/UprightCandidatePoses.json').read_text())
walk = next(c for c in other['clips'] if 'Walk' in c['name'])
parents = {'root':None,'pelvis':'root','spine_01':'pelvis','spine_02':'spine_01',
 'spine_03':'spine_02','neck_01':'spine_03','head':'neck_01','clavicle_l':'spine_03',
 'upperarm_l':'clavicle_l','lowerarm_l':'upperarm_l','hand_l':'lowerarm_l',
 'clavicle_r':'spine_03','upperarm_r':'clavicle_r','lowerarm_r':'upperarm_r','hand_r':'lowerarm_r',
 'thigh_l':'pelvis','calf_l':'thigh_l','foot_l':'calf_l','ball_l':'foot_l',
 'thigh_r':'pelvis','calf_r':'thigh_r','foot_r':'calf_r','ball_r':'foot_r'}
def quat(v): return Quaternion((v[3], *v[:3]))
def record(m):
    p,q,s=m.decompose()
    return {'p':list(p),'q':[q.x,q.y,q.z,q.w],'s':list(s)}
def mat(v): return Matrix.LocRotScale(Vector(v['p']),quat(v['q']),Vector(v['s']))
def world(local):
    result={}
    for b,p in parents.items(): result[b]=result[p]@mat(local[b]) if p else mat(local[b])
    return result
def setrot(local,b,q):
    w=world(local); p=parents[b]
    q=w[p].to_quaternion().inverted()@q if p else q
    local[b]['q']=[q.x,q.y,q.z,q.w]
def blend(a,b,u):
    q=quat(a['q']).slerp(quat(b['q']),u)
    return {'p':list(Vector(a['p']).lerp(Vector(b['p']),u)),
        'q':[q.x,q.y,q.z,q.w], 's':list(Vector(a['s']).lerp(Vector(b['s']),u))}
def sample(clip,t):
    f=max(0,min(len(clip['samples'])-1,t/clip['duration']*(len(clip['samples'])-1)))
    a=int(f);b=min(a+1,len(clip['samples'])-1)
    return {k:blend(clip['samples'][a]['local'][k],clip['samples'][b]['local'][k],f-a) for k in parents}
def smooth(u):
    u=max(0,min(1,u));return u*u*(3-2*u)
def curve(t,keys):
    if t<=keys[0][0]:return Vector(keys[0][1])
    if t>=keys[-1][0]:return Vector(keys[-1][1])
    i=next(i for i in range(len(keys)-1) if keys[i][0]<=t<=keys[i+1][0])
    ta,a=keys[i];tb,b=keys[i+1];a=Vector(a);b=Vector(b);u=(t-ta)/(tb-ta)
    ma=Vector((0,0,0)) if i==0 else (Vector(keys[i+1][1])-Vector(keys[i-1][1]))/(keys[i+1][0]-keys[i-1][0])
    mb=Vector((0,0,0)) if i+1==len(keys)-1 else (Vector(keys[i+2][1])-Vector(keys[i][1]))/(keys[i+2][0]-keys[i][0])
    return a*(2*u**3-3*u*u+1)+ma*((tb-ta)*(u**3-2*u*u+u))+b*(-2*u**3+3*u*u)+mb*((tb-ta)*(u**3-u*u))
def limb(local,bones,target,pole,limit=.9999):
    w=world(local);a,b,c=bones;A,B,C=(w[k].translation.copy() for k in bones)
    l1=(B-A).length;l2=(C-B).length;delta=target-A
    reach=max(abs(l1-l2)+.01,min(delta.length,(l1+l2)*limit));axis=delta.normalized()
    bend=(pole-axis*pole.dot(axis)).normalized()
    along=(l1*l1-l2*l2+reach*reach)/(2*reach)
    elbow=A+axis*along+bend*math.sqrt(max(0,l1*l1-along*along))
    setrot(local,a,(B-A).normalized().rotation_difference((elbow-A).normalized())@w[a].to_quaternion())
    w=world(local);B=w[b].translation;C=w[c].translation
    setrot(local,b,(C-B).normalized().rotation_difference((A+axis*reach-B).normalized())@w[b].to_quaternion())
def rotate_world(local,b,axis,degrees):
    setrot(local,b,Quaternion(Vector(axis),math.radians(degrees))@world(local)[b].to_quaternion())
def angle(a,b):return math.degrees(2*math.acos(min(1,abs(a.normalized().dot(b.normalized())))))

idle=attack['samples'][0]['local']; iw=world(idle)
ref={b:mat(v) for b,v in source['reference'].items()}
bind={b:record(ref[parents[b]].inverted()@ref[b]) if parents[b] else record(ref[b]) for b in parents}
# Measure the actual held blade; never invent a wrist aim axis.
bpy.context.scene.unit_settings.scale_length=.01
old_objects=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(P/'ArtSource/Weapons/Yueyao/SlenderBladeRevision/YueyaoPlayerSlender.fbx'))
weapon=max((o for o in bpy.data.objects if o not in old_objects and o.type=='MESH'),key=lambda o:len(o.data.vertices))
grip=json.loads((P/'Docs/Gameplay/RigPolish_v04/CandidateGrip.json').read_text())
attach=Matrix.LocRotScale(Vector(grip['translation']),quat(grip['quaternion']),Vector(grip['scale']))
reflect=Matrix.Diagonal((1,-1,1,1))
prop_points=[ref['hand_r']@attach@reflect@weapon.matrix_world@v.co for v in weapon.data.vertices]
neutral_blade=(max(prop_points,key=lambda v:(v-ref['hand_r'].translation).length)-ref['hand_r'].translation).normalized()
right=[(0,list(iw['hand_r'].translation)),(.20,[-34,12,118]),(.43,[-36,19,129]),
       (.57,[-30,29,123]),(.67,[-22,35,116]),(.80,[-3,36,110]),(.95,[10,28,106]),
       (1.13,[-12,22,110]),(1.34,[-27,13,108]),(1.5,list(iw['hand_r'].translation))]
left=[(0,list(iw['hand_l'].translation)),(.25,[28,16,105]),(.5,[32,14,106]),
      (.72,[33,7,104]),(.95,[31,9,103]),(1.22,[27,16,106]),(1.5,list(iw['hand_l'].translation))]
body=[(0,[0,0,0]),(.28,[1,-2,-1]),(.48,[2,-3,-2]),(.65,[0,1,-3]),(.80,[-2,4,-2.5]),
      (1.0,[-1,3,-1]),(1.3,[0,0,0]),(1.5,[0,0,0])]
twist=[(0,[0,0,0]),(.25,[10,0,0]),(.48,[19,0,0]),(.63,[5,0,0]),(.8,[-22,0,0]),
       (.95,[-26,0,0]),(1.2,[-9,0,0]),(1.5,[0,0,0])]
pref=[(0,[0,1,.1]),(.24,[-.4,.3,.8]),(.48,[-.5,.65,.6]),(.6,[-.18,.98,.08]),
      (.72,[0,1,-.05]),(.83,[.45,.88,-.12]),(.95,[.8,.6,-.2]),(1.15,[.2,1,.1]),(1.5,[0,1,.1])]
old_times=[(0,[0,0,0]),(.6,[.8,0,0]),(.833333333,[1.033333333,0,0]),(1.5,[attack['duration'],0,0])]
samples=[];max_foot_error=0;rows=[];previous_elbow=None;previous_solution=None;wrist_angles=[]
for i in range(91):
    t=i/60;original=sample(attack,curve(t,old_times).x);local=copy.deepcopy(original);ow=world(original)
    local['pelvis']['p']=list(Vector(local['pelvis']['p'])+curve(t,body))
    # Pelvis initiates, thorax follows, head counter-rotates to preserve focus.
    yaw=curve(t,twist).x
    for bone,factor in [('pelvis',.22),('spine_01',.25),('spine_02',.28),('spine_03',.25)]:
        rotate_world(local,bone,(0,0,1),yaw*factor)
    setrot(local,'head',ow['head'].to_quaternion())
    for side in ('l','r'):
        foot='foot_'+side
        limb(local,('thigh_'+side,'calf_'+side,foot),ow[foot].translation,Vector((0,1,0)))
        setrot(local,foot,ow[foot].to_quaternion())
    for side,keys,pole in [('r',right,Vector((-1,.2,-.45))),('l',left,Vector((1,-.4,-1)))]:
        for b in ('upperarm_'+side,'lowerarm_'+side,'hand_'+side):
            local[b]['q']=(idle[b]['q'] if side=='r' and b!='hand_r' else bind[b]['q'])[:]
        limb(local,('upperarm_'+side,'lowerarm_'+side,'hand_'+side),curve(t,keys),pole,.965)
    lw=world(local)
    rotate_world(local,'lowerarm_l',(lw['hand_l'].translation-lw['lowerarm_l'].translation).normalized(),-65)
    # A blade points 78 degrees away from the bound forearm, so forearm roll
    # alone cannot turn a straight reach into a cut. Choose a bent elbow plane
    # that supports the actual blade direction with a nearly neutral wrist.
    desired=curve(t,pref).normalized();w=world(local)
    target=w['hand_r'].translation.copy();shoulder=w['upperarm_r'].translation.copy()
    axis=(target-shoulder).normalized();pole=Vector((-1,.2,-.45));pole=(pole-axis*pole.dot(axis)).normalized()
    aimed=neutral_blade.rotation_difference(desired)@ref['hand_r'].to_quaternion()
    choices=[]
    for degrees in range(-180,181,5):
        candidate=copy.deepcopy(local)
        limb(candidate,('upperarm_r','lowerarm_r','hand_r'),target,Quaternion(axis,math.radians(degrees))@pole,.965)
        cw=world(candidate);elbow=cw['lowerarm_r'].translation
        if elbow.z>shoulder.z+2 or elbow.x>shoulder.x+6:continue
        # Axial forearm roll supplies the sword plane before any wrist bend.
        forearm=(cw['hand_r'].translation-cw['lowerarm_r'].translation).normalized()
        blade=cw['hand_r'].to_quaternion()@ref['hand_r'].to_quaternion().inverted()@neutral_blade
        a=blade-forearm*blade.dot(forearm);b=desired-forearm*desired.dot(forearm)
        if min(a.length,b.length)>1e-7:
            a.normalize();b.normalize()
            rotate_world(candidate,'lowerarm_r',forearm,math.degrees(math.atan2(forearm.dot(a.cross(b)),a.dot(b))))
        cw=world(candidate)
        neutral=cw['lowerarm_r'].to_quaternion()@quat(bind['hand_r']['q'])
        delta=neutral@aimed.inverted()
        roll=2*math.atan2(Vector((delta.x,delta.y,delta.z)).dot(desired),delta.w)
        adjusted=Quaternion(desired,roll)@aimed
        wrist=angle(neutral,adjusted)
        score=wrist*4+abs(degrees)*.008
        if previous_elbow is not None:score+=(elbow-previous_elbow).length*.8
        if previous_solution:
            score+=sum(angle(quat(candidate[b]['q']),quat(previous_solution[b]['q'])) for b in ('upperarm_r','lowerarm_r'))*.7
        choices.append((score,candidate,adjusted,wrist,elbow.copy()))
    assert choices,'No anatomical elbow solution'
    _,local,hand_rotation,wrist,previous_elbow=min(choices,key=lambda c:c[0])
    setrot(local,'hand_r',hand_rotation)
    previous_solution=copy.deepcopy(local)
    wrist_angles.append(wrist)
    weight=smooth(t/.20)*smooth((1.5-t)/.24)
    for b in ('clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r'):
        local[b]['q']=blend(idle[b],local[b],weight)['q']
    if i in (0,90):local=copy.deepcopy(original)
    w=world(local)
    max_foot_error=max(max_foot_error,max((w['foot_'+s].translation-ow['foot_'+s].translation).length for s in ('l','r')))
    samples.append({'time':t,'local':local,'world':{b:record(m) for b,m in w.items()}})
    tip=max((w['hand_r']@ref['hand_r'].inverted()@v for v in prop_points),key=lambda v:(v-w['hand_r'].translation).length)
    rows.append({'t':t,'hand':list(w['hand_r'].translation),'chest_yaw_delta':yaw,
        'wrist_deviation_deg':wrist,'sword_tip':list(tip)})

# Ease short entry/return IK changes without filtering the authored contact arc.
for iteration in range(2):
    old=copy.deepcopy(samples)
    for i in range(1,len(samples)-1):
        t=samples[i]['time']
        amount=1-smooth((t-.30)/.20) if t<.5 else smooth((t-.9)/.20)
        if amount<=0:continue
        for b in ('upperarm_r','lowerarm_r','hand_r'):
            center=quat(old[i]['local'][b]['q'])
            before=center.slerp(quat(old[i-1]['local'][b]['q']),.5)
            after=center.slerp(quat(old[i+1]['local'][b]['q']),.5)
            q=center.slerp(before.slerp(after,.5),amount)
            samples[i]['local'][b]['q']=[q.x,q.y,q.z,q.w]
for s in samples:s['world']={b:record(m) for b,m in world(s['local']).items()}

# Extend the existing planted walk stride, keep every foot's original height
# and orientation, and use a slight forward chest inclination for pursuit.
walk_samples=[];stride=1.3
for original in walk['samples']:
    local=copy.deepcopy(original['local']);ow=world(local)
    # Lowering the pelvis a little gives the longer step a flexed supporting knee.
    local['pelvis']['p'][2]-=2.0
    for side in ('l','r'):
        foot='foot_'+side;target=ow[foot].translation.copy();target.y*=stride
        limb(local,('thigh_'+side,'calf_'+side,foot),target,Vector((0,1,0)))
        setrot(local,foot,ow[foot].to_quaternion())
    rotate_world(local,'spine_01',(1,0,0),-5)
    rotate_world(local,'spine_02',(1,0,0),-3)
    setrot(local,'head',ow['head'].to_quaternion())
    w=world(local)
    walk_samples.append({'time':original['time'],'local':local,'world':{b:record(m) for b,m in w.items()}})

max_step={b:max(angle(quat(a['local'][b]['q']),quat(c['local'][b]['q'])) for a,c in zip(samples,samples[1:])) for b in parents}
print('CONTACT_GEOMETRY',json.dumps([r for r in rows if .6<=r['t']<=.8334]))
print('WORST_STEPS',json.dumps(sorted([{'t':c['time'],'bone':b,'angle':angle(quat(a['local'][b]['q']),quat(c['local'][b]['q']))} for a,c in zip(samples,samples[1:]) for b in ('upperarm_r','lowerarm_r','hand_r')],key=lambda x:x['angle'],reverse=True)[:10]))
assert max_foot_error<.5, ('Foot contact drift',max_foot_error)
assert max(max_step.values())<35, ('Discontinuous authored joint',max_step)
contact_rows=[r for r in rows if .6<=r['t']<=.8334]
assert max(r['wrist_deviation_deg'] for r in contact_rows)<30,'Cut requires excessive wrist bend'
assert any(r['sword_tip'][1]>105 and abs(r['sword_tip'][0])<15 and 90<r['sword_tip'][2]<130
           for r in contact_rows),'Visible blade must cross the close combat target at torso height'
result={'attack':{'samples':samples,'duration':1.5,'fps':60,'notify':[.6,.833333333]},
        'chase':{'samples':walk_samples,'duration':walk['duration'],'fps':30,'stride_scale':stride},
        'metrics':{'max_attack_foot_drift_cm':max_foot_error,'max_joint_step_deg':max_step,
          'maximum_contact_wrist_deg':max(r['wrist_deviation_deg'] for r in rows if .6<=r['t']<=.8334),
          'contact_tip_forward_max_cm':max(r['sword_tip'][1] for r in rows if .6<=r['t']<=.8334),'hand_path':rows}}
(OUT/'EnemyMotionPoses.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
(OUT/'EnemyMotionMetrics.json').write_text(json.dumps(result['metrics'],indent=2),encoding='utf-8')
print('ENEMY_MOTION_BAKED',json.dumps({'foot_error_cm':max_foot_error,'max_joint_step_deg':max(max_step.values())}))
