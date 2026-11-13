"""Native Mixamo v07: body-led over-shoulder diagonal cut, continuous IK."""
import sys,copy,math,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from new_rig_common import *
arm,mesh,walk,meta=load_rig()
N=lambda s:'mixamorig:'+s
parents={b.name:b.parent.name if b.parent else None for b in arm.data.bones}
rest={b.name:b.matrix_local.copy() for b in arm.data.bones}
bind={b:rest[p].inverted()@rest[b] if p else rest[b].copy() for b,p in parents.items()}
def world(local):
    w={}
    for b,p in parents.items():w[b]=w[p]@local[b] if p else local[b].copy()
    return w
def setrot(local,b,q):
    w=world(local);p=parents[b];q=w[p].to_quaternion().inverted()@q if p else q
    loc,old,s=local[b].decompose();local[b]=Matrix.LocRotScale(loc,q,s)
def turn(local,b,axis,deg):setrot(local,N(b),Quaternion(Vector(axis),math.radians(deg))@world(local)[N(b)].to_quaternion())
def ik(local,side,kind,target,pole):
    names=(side+'Arm',side+'ForeArm',side+'Hand') if kind=='arm' else (side+'UpLeg',side+'Leg',side+'Foot')
    a,b,c=map(N,names);w=world(local);A,B,C=(w[n].translation.copy() for n in (a,b,c))
    l1=(B-A).length;l2=(C-B).length;d=target-A;axis=d.normalized()
    reach=min(d.length,(l1+l2)*.975);reach=max(reach,abs(l1-l2)+.005)
    bend=(pole-axis*axis.dot(pole)).normalized();along=(l1*l1-l2*l2+reach*reach)/(2*reach)
    elbow=A+axis*along+bend*math.sqrt(max(0,l1*l1-along*along))
    setrot(local,a,(B-A).rotation_difference(elbow-A)@w[a].to_quaternion())
    w=world(local);B=w[b].translation.copy();C=w[c].translation.copy()
    setrot(local,b,(C-B).rotation_difference(A+axis*reach-B)@w[b].to_quaternion())
def curve(t,keys):
    if t<=keys[0][0]:return Vector(keys[0][1])
    if t>=keys[-1][0]:return Vector(keys[-1][1])
    i=next(i for i in range(len(keys)-1) if keys[i][0]<=t<=keys[i+1][0]);ta,a=keys[i];tb,b=keys[i+1]
    a,b=Vector(a),Vector(b);u=(t-ta)/(tb-ta)
    ma=Vector((0,0,0)) if i==0 else (Vector(keys[i+1][1])-Vector(keys[i-1][1]))/(keys[i+1][0]-keys[i-1][0])
    mb=Vector((0,0,0)) if i+1==len(keys)-1 else (Vector(keys[i+2][1])-Vector(keys[i][1]))/(keys[i+2][0]-keys[i][0])
    return a*(2*u**3-3*u*u+1)+ma*((tb-ta)*(u**3-2*u*u+u))+b*(-2*u**3+3*u*u)+mb*((tb-ta)*(u**3-u*u))
def scalar(t,keys):return curve(t,[(a,(v,0,0)) for a,v in keys]).x
DURATION=1.65
right=[(0,(.25,-.24,1.12)),(.25,(.08,-.32,1.39)),(.49,(-.04,-.27,1.60)),(.59,(.02,-.24,1.58)),(.72,(.37,-.10,1.34)),(.84,(.34,.04,1.20)),(1.0,(.16,.13,1.13)),(1.17,(.12,.12,1.15)),(1.42,(.25,-.16,1.10)),(DURATION,(.25,-.24,1.12))]
left=[(0,(.16,.27,1.13)),(.3,(.10,.35,1.20)),(.55,(.15,.36,1.28)),(.8,(-.03,.36,1.23)),(1.0,(-.10,.25,1.17)),(1.3,(.11,.25,1.13)),(DURATION,(.16,.27,1.13))]
theta=[(0,55),(.28,-15),(.49,-65),(.59,-48),(.72,65),(.84,110),(1.,145),(1.15,140),(1.4,85),(DURATION,55)]
hipyaw=[(0,-6),(.26,-20),(.48,-28),(.57,-5),(.72,20),(.9,28),(1.08,24),(1.4,0),(DURATION,-6)]
chestyaw=[(0,0),(.31,-10),(.53,-22),(.65,0),(.81,22),(1.0,25),(1.2,10),(DURATION,0)]
shift=[(0,(0,0,-.025)),(.3,(-.035,-.025,-.055)),(.5,(-.04,-.03,-.06)),(.73,(.04,.015,-.075)),(.96,(.07,.035,-.085)),(1.2,(.025,.015,-.06)),(DURATION,(0,0,-.025))]
lean=[(0,5),(.5,-2),(.78,13),(1.,18),(1.25,8),(DURATION,5)]
gripQ=Matrix(((0,0,1),(-1,0,0),(0,-1,0))).to_quaternion()
gripP=Vector((0,.065,.035))
gripfile=DOC/'NativeSwordGrip.json'
if gripfile.exists():
    gd=json.loads(gripfile.read_text())['blender'];gripQ=Quaternion(gd['quaternion_wxyz']);gripP=Vector(gd['translation_m'])
feet={side:rest[N(side+'Foot')].translation.copy()+Vector((.10 if side=='Left' else -.08,.035 if side=='Left' else -.035,0)) for side in ('Left','Right')}
U=Vector((0,-.65,.76)).normalized();V=Vector((1,0,0))
samples=[];rows=[]
for i in range(100):
    t=i/60;local={b:m.copy() for b,m in bind.items()}
    local[N('Hips')].translation+=curve(t,shift)
    turn(local,'Hips',(0,0,1),scalar(t,hipyaw))
    for b,f in [('Spine',.25),('Spine1',.35),('Spine2',.40)]:
        turn(local,b,(0,0,1),scalar(t,chestyaw)*f)
        turn(local,b,(0,1,0),scalar(t,lean)*f)
    # Focus stays on the opponent while the torso unwinds.
    for b in ('Neck','Head'):setrot(local,N(b),rest[N(b)].to_quaternion())
    for side in ('Left','Right'):
        ik(local,side,'leg',feet[side],Vector((1,0,0)))
        setrot(local,N(side+'Foot'),rest[N(side+'Foot')].to_quaternion())
    # Scapula participates in the overhead draw; fixed smooth elbow poles avoid flips.
    lift=scalar(t,[(0,0),(.3,8),(.5,17),(.7,7),(.9,0),(DURATION,0)])
    turn(local,'RightShoulder',(1,0,0),-lift)
    th=math.radians(scalar(t,theta));B=U*math.cos(th)+V*math.sin(th);E=-U*math.sin(th)+V*math.cos(th)
    X=-E;Y=B.cross(X);bladeQ=Matrix((X,Y,B)).transposed().to_quaternion();handQ=bladeQ@gripQ.inverted()
    # Analytic elbow circle: choose the plane nearest the desired neutral wrist.
    # Unlike per-frame angle searches this has no discrete solution switches.
    w=world(local);A=w[N('RightArm')].translation.copy();target=curve(t,right)
    axis=(target-A).normalized();l2=bind[N('RightHand')].translation.length
    desiredFore=handQ@bind[N('RightHand')].to_quaternion().inverted()@bind[N('RightHand')].translation.normalized()
    idealElbow=target-desiredFore*l2
    pole=idealElbow-A;pole-=axis*pole.dot(axis)
    if pole.length<.001:pole=Vector((-.2,-1,-.3))
    ik(local,'Right','arm',target,pole.normalized())
    ik(local,'Left','arm',curve(t,left),Vector((-.2,1,-.15)))
    w=world(local);fore=(w[N('RightHand')].translation-w[N('RightForeArm')].translation).normalized()
    # Supply axial roll through the forearm, leaving the wrist as a modest swing.
    neutral=w[N('RightForeArm')].to_quaternion()@bind[N('RightHand')].to_quaternion()
    delta=handQ@neutral.inverted();roll=2*math.atan2(Vector((delta.x,delta.y,delta.z)).dot(fore),delta.w)
    setrot(local,N('RightForeArm'),Quaternion(fore,roll)@w[N('RightForeArm')].to_quaternion())
    setrot(local,N('RightHand'),handQ)
    if gripfile.exists():
        for b,degrees in gd.get('finger_basis_local_x_degrees',{}).items():
            name=b if b in local else N(b);p,r,s=bind[name].decompose();local[name]=Matrix.LocRotScale(p,r@Quaternion((1,0,0),math.radians(degrees)),s)
    w=world(local);hand=w[N('RightHand')];origin=hand@gripP;tip=origin+B*.71
    neutral=w[N('RightForeArm')].to_quaternion()@bind[N('RightHand')].to_quaternion()
    wrist=math.degrees(2*math.acos(min(1,abs(neutral.normalized().dot(handQ.normalized())))))
    rows.append({'time':t,'hand':list(hand.translation),'tip':list(tip),'blade_axis':list(B),'cutting_edge':list(E),'wrist_deviation_deg':wrist,'theta_deg':math.degrees(th)})
    samples.append({'time':t,'world':{b:[list(r) for r in m] for b,m in w.items()},'local':{b:[list(r) for r in m] for b,m in local.items()}})

# Smooth the continuous elbow-circle solution near its shallow minimum.
# Preserve the complete authored blade orientation by resolving the hand after
# the upper/forearm filter; endpoints remain bit-identical to the shared guard.
for iteration in range(14):
    previous=copy.deepcopy(samples)
    for i in range(1,len(samples)-1):
        for b in map(N,('RightArm','RightForeArm','LeftArm','LeftForeArm')):
            before=Matrix(previous[i-1]['local'][b]).to_quaternion()
            center=Matrix(previous[i]['local'][b]).to_quaternion()
            after=Matrix(previous[i+1]['local'][b]).to_quaternion()
            q=center.slerp(before.slerp(after,.5),.65)
            p,_,s=Matrix(samples[i]['local'][b]).decompose()
            samples[i]['local'][b]=[list(r) for r in Matrix.LocRotScale(p,q,s)]
for i,sample in enumerate(samples):
    local={b:Matrix(m) for b,m in sample['local'].items()}
    wanted=Matrix(sample['world'][N('RightHand')]).to_quaternion()
    setrot(local,N('RightHand'),wanted);w=world(local)
    sample['local']={b:[list(r) for r in m] for b,m in local.items()}
    sample['world']={b:[list(r) for r in m] for b,m in w.items()}
    row=rows[i];hand=w[N('RightHand')];origin=hand@gripP
    row['hand']=list(hand.translation);row['tip']=list(origin+Vector(row['blade_axis'])*.71)
    neutral=w[N('RightForeArm')].to_quaternion()@bind[N('RightHand')].to_quaternion()
    row['wrist_deviation_deg']=math.degrees(2*math.acos(min(1,abs(neutral.normalized().dot(wanted.normalized())))))

# Capture a shared guard for support clips. World matrices use canonical metres.
(DOC/'NativeGuard.json').write_text(json.dumps(samples[0],indent=2))
arm.animation_data_create();action=bpy.data.actions.new('Wuxia_Attack_Native_v07');arm.animation_data.action=action
for i,s in enumerate(samples):
    apply_world(arm,{b:Matrix(m) for b,m in s['world'].items()})
    assert max((b.matrix.translation-Matrix(s['world'][b.name]).translation).length for b in arm.pose.bones)<1e-4
    key_pose(arm,i+1)
scene=bpy.context.scene;scene.frame_set(1)
export_clip(arm,mesh,OUT/'Wuxia_Attack_Native_v07.fbx',1,100,60,True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Wuxia_Attack_Native_v07.blend'))
maxstep={b:max(math.degrees(2*math.acos(min(1,abs(Matrix(a['local'][b]).to_quaternion().dot(Matrix(c['local'][b]).to_quaternion()))))) for a,c in zip(samples,samples[1:])) for b in parents}
edges=[]
for i in range(1,len(rows)-1):
    if .62<=rows[i]['time']<=.96:
        v=(Vector(rows[i+1]['tip'])-Vector(rows[i-1]['tip']));B=Vector(rows[i]['blade_axis']);v-=B*v.dot(B)
        edges.append(Vector(rows[i]['cutting_edge']).dot(v.normalized()))
report={'duration':DURATION,'fps':60,'frames':100,'notify':[.67,.91],
  'asset':'Wuxia_Attack_Native_v07.fbx','mesh_same_fbx':True,'native_bones':41,
  'source_to_meter_scale':meta['source_to_meter_scale'],'forward':'+X',
  'grip_quaternion_wxyz':list(gripQ),'grip_translation_m':list(gripP),
  'max_joint_step_deg':maxstep,'minimum_edge_velocity_dot':min(edges),
  'maximum_wrist_deviation_deg':max(r['wrist_deviation_deg'] for r in rows),
  'rows':rows}
(DOC/'NativeSlashManifest.json').write_text(json.dumps(report,indent=2))
(DOC/'SlashPoses.json').write_text(json.dumps({'attack':{'duration':DURATION,'fps':60,'notify':[.67,.91],'samples':samples},'metrics':report},separators=(',',':')))
print('NATIVE_SLASH_READY',json.dumps({k:v for k,v in report.items() if k not in ('rows','max_joint_step_deg')}))
print('WORST_STEPS',sorted(maxstep.items(),key=lambda x:-x[1])[:8])
