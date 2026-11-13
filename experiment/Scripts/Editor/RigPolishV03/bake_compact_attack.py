"""Author one compact front-facing cut on the reviewed mesh; originals read-only."""
import copy,hashlib,json,math,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Quaternion,Vector
PROJECT=Path(r'D:\game design\experiment')
OUT=PROJECT/'ArtSource/WuxiaMale/RigPolishV03/Attack';OUT.mkdir(parents=True,exist_ok=True)
SETUP=PROJECT/'Saved/Scripts/bake_selected_death.py'
context={'__name__':'compact_attack_skin','__file__':str(SETUP)}
exec(compile(SETUP.read_text(encoding='utf-8').split('raw=[];locals=[];support=[]')[0],str(SETUP),'exec'),context)
skin=context['skin'];world=context['world'];record=context['record'];blend=context['blend']
set_world_rotation=context['set_world_rotation'];PARENTS=context['PARENTS']
mesh=context['mesh'];weapon=context['weapon'];attach=context['attach'];reflect=context['reflect']
prop_world=context['prop_world'];weapon_points=context['weapon_points'];basis=context['basis'];weights=context['weights']
data=json.loads((PROJECT/'Docs/Gameplay/RigPolish_v01/UprightCandidatePoses.json').read_text(encoding='utf-8'))
source=next(c for c in data['clips'] if c['name']=='Wuxia_Attack_Sword_Upright_v01')
idle=source['samples'][0]['local'];idle_world=world(idle);FPS=30;DURATION=source['duration']
CHANGED=('spine_01','spine_02','spine_03','neck_01','head','clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r')
def qangle(a,b):return math.degrees(2.*math.acos(min(1.,abs(a.normalized().dot(b.normalized())))))
def smooth(t):t=max(0.,min(1.,t));return t*t*(3.-2.*t)
def interpolate(t,keys):
    if t<=keys[0][0]:return Vector(keys[0][1])
    if t>=keys[-1][0]:return Vector(keys[-1][1])
    i=next(i for i in range(len(keys)-1) if keys[i][0]<=t<=keys[i+1][0])
    ta,a=keys[i];tb,b=keys[i+1];a=Vector(a);b=Vector(b);h=tb-ta;u=(t-ta)/h
    ma=Vector((0,0,0)) if i==0 else (Vector(keys[i+1][1])-Vector(keys[i-1][1]))/(keys[i+1][0]-keys[i-1][0])
    mb=Vector((0,0,0)) if i+1==len(keys)-1 else (Vector(keys[i+2][1])-Vector(keys[i][1]))/(keys[i+2][0]-keys[i][0])
    return a*(2*u**3-3*u*u+1)+ma*(h*(u**3-2*u*u+u))+b*(-2*u**3+3*u*u)+mb*(h*(u**3-u*u))
def solve_arm(local,side,target,pole):
    w=world(local);a,b,c=('upperarm_'+side,'lowerarm_'+side,'hand_'+side)
    A,B,C=(w[k].translation.copy() for k in (a,b,c));l1=(B-A).length;l2=(C-B).length
    delta=target-A;reach=min(delta.length,(l1+l2)*.965);reach=max(reach,abs(l1-l2)+.1);axis=delta.normalized()
    bend=pole-axis*pole.dot(axis);bend.normalize()
    along=(l1*l1-l2*l2+reach*reach)/(2*reach);height=math.sqrt(max(0.,l1*l1-along*along))
    elbow=A+axis*along+bend*height
    set_world_rotation(local,a,(B-A).normalized().rotation_difference((elbow-A).normalized())@w[a].decompose()[1])
    w=world(local);B=w[b].translation;C=w[c].translation
    set_world_rotation(local,b,(C-B).normalized().rotation_difference((A+axis*reach-B).normalized())@w[b].decompose()[1])
    return local

# Weapon extrema measured from the real held static mesh, never an invented line.
idle_prop=prop_world(idle);idle_hand=np.asarray(idle_world['hand_r'].translation)
idle_prop_ue=idle_prop*np.array([1.,-1.,1.])
TIP_INDEX=int(np.linalg.norm(idle_prop_ue-idle_hand,axis=1).argmax())
idle_sword_direction=Vector(idle_prop_ue[TIP_INDEX])-idle_world['hand_r'].translation;idle_sword_direction.normalize()
right_keys=[(0.,list(idle_world['hand_r'].translation)),(.25,[-24.,0.,112.]),(.58,[-29.,22.,130.]),(.78,[-31.,26.,134.]),(.90,[-9.,43.,121.]),(1.03,[15.,35.,107.]),(1.20,[18.,20.,104.]),(1.55,[-17.,17.,109.]),(1.90,[-20.,-7.,105.]),(DURATION,list(idle_world['hand_r'].translation))]
left_keys=[(0.,list(idle_world['hand_l'].translation)),(.35,[31.,18.,100.]),(.75,[36.,7.,99.]),(1.05,[39.,2.,98.]),(1.40,[39.,5.,98.]),(1.90,[30.,25.,97.]),(DURATION,list(idle_world['hand_l'].translation))]
direction_keys=[(0.,list(idle_sword_direction)),(.35,[-.50,.73,.46]),(.65,[-.48,.76,.45]),(.78,[-.43,.84,.33]),(.90,[.08,.99,-.10]),(1.03,[.48,.84,-.24]),(1.20,[.48,.83,-.28]),(1.55,[.12,.96,.25]),(1.90,list(idle_sword_direction)),(DURATION,list(idle_sword_direction))]
samples=[];pose_rows=[];prior_elbow=None
for original in source['samples']:
    t=original['time'];local=copy.deepcopy(original['local'])
    # Remove the 98-degree gaze whip and the wide rib-cage winding. The pelvis
    # and feet retain their existing planted motion, including exact endpoints.
    for b,factor in [('spine_01',.38),('spine_02',.42),('spine_03',.42),('neck_01',.20),('head',.20),('clavicle_l',.15),('clavicle_r',.20)]:
        local[b]['q']=blend(idle[b],local[b],factor)['q']
    for side,keys,pole in [('r',right_keys,Vector((-1.,-.15,-.75))),('l',left_keys,Vector((1.,-.4,-1.2)))]:
        for b in ('upperarm_'+side,'lowerarm_'+side,'hand_'+side):local[b]['q']=idle[b]['q'][:]
        solve_arm(local,side,interpolate(t,keys),pole)
        hand_q=idle_world['hand_'+side].decompose()[1]
        set_world_rotation(local,'hand_'+side,hand_q)
    desired=interpolate(t,direction_keys).normalized()
    aimed=idle_sword_direction.rotation_difference(desired)@idle_world['hand_r'].decompose()[1]
    # Twist about the already-aimed blade axis to minimize local wrist rotation
    # from the established grip. This keeps the real blade tip trajectory fixed.
    w=world(local);target=w['hand_r'].translation.copy();shoulder=w['upperarm_r'].translation.copy();axis=(target-shoulder).normalized()
    initial_pole=Vector((-1.,-.15,-.75));initial_pole-=axis*initial_pole.dot(axis);initial_pole.normalize()
    options=[];natural=copy.deepcopy(local)
    for degrees in range(-180,181,10):
        option=copy.deepcopy(local);pole=Quaternion(axis,math.radians(degrees))@initial_pole
        solve_arm(option,'r',target,pole);ow=world(option)
        neutral=ow['lowerarm_r'].decompose()[1]@Quaternion((idle['hand_r']['q'][3],*idle['hand_r']['q'][:3]))
        difference=neutral@aimed.inverted()
        roll=2.*math.atan2(Vector((difference.x,difference.y,difference.z)).dot(desired),difference.w)
        if roll>math.pi:roll-=2.*math.pi
        if roll<-math.pi:roll+=2.*math.pi
        adjusted=Quaternion(desired,roll)@aimed
        wrist_angle=qangle(neutral,adjusted)
        elbow=ow['lowerarm_r'].translation
        chest_z=ow['spine_03'].translation.z
        # Hard anatomical presentation limits outrank an artificially neutral
        # wrist: the sleeve/elbow must not rise into the chin or cross the face.
        if elbow.z>chest_z or elbow.x>shoulder.x+5.:continue
        score=wrist_angle*.6+abs(degrees)*.025+max(0.,-25.-elbow.y)
        if prior_elbow is not None:score+=(elbow-prior_elbow).length*.30
        options.append((score,option,adjusted,roll,wrist_angle,elbow.copy()))
    if options:
        _,best,adjusted,roll,wrist_angle,prior_elbow=min(options,key=lambda x:x[0])
    else:best=natural
    optimize_weight=smooth((t-.72)/.12)*(1.-smooth((t-1.04)/.18))
    local=copy.deepcopy(natural)
    natural_elbow=world(natural)['lowerarm_r'].translation-shoulder
    best_elbow=world(best)['lowerarm_r'].translation-shoulder
    p0=(natural_elbow-axis*natural_elbow.dot(axis)).normalized()
    p1=(best_elbow-axis*best_elbow.dot(axis)).normalized()
    signed=math.atan2(axis.dot(p0.cross(p1)),p0.dot(p1))
    solve_arm(local,'r',target,Quaternion(axis,signed*optimize_weight)@p0)
    neutral=world(local)['lowerarm_r'].decompose()[1]@Quaternion((idle['hand_r']['q'][3],*idle['hand_r']['q'][:3]))
    difference=neutral@aimed.inverted();roll=2.*math.atan2(Vector((difference.x,difference.y,difference.z)).dot(desired),difference.w)
    if roll>math.pi:roll-=2*math.pi
    if roll<-math.pi:roll+=2*math.pi
    adjusted=Quaternion(desired,roll)@aimed;wrist_angle=qangle(neutral,adjusted)
    set_world_rotation(local,'hand_r',adjusted)
    # Blend the arm IK into/out of the unchanged idle pose without a snap.
    entry=smooth(t/.22);exit_weight=smooth((DURATION-t)/.35);amount=entry*exit_weight
    for b in ('clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r'):
        local[b]['q']=blend(idle[b],local[b],amount)['q']
    if t<1e-6 or abs(t-DURATION)<1e-6:local=copy.deepcopy(original['local'])
    w=world(local);prop=prop_world(local);points,_=skin(local)
    sample={'time':t,'local':local,'world':{b:record(m) for b,m in w.items()}}
    samples.append(sample)
    pose_rows.append({'time':t,'hand_r':list(w['hand_r'].translation),'hand_l':list(w['hand_l'].translation),
        'wrist_roll_correction_degrees':math.degrees(roll),
        'optimized_wrist_deviation_deg':wrist_angle,
        'sword_tip_ue':list(prop[TIP_INDEX]*np.array([1.,-1.,1.])),
        'skin_min_z_cm':float(points[:,2].min()),'sword_min_z_cm':float(prop[:,2].min())})

def metrics(items):
    rows=[];tips=[]
    for sample in items:
        w=world(sample['local']);p=prop_world(sample['local']);tip=Vector(p[TIP_INDEX]*np.array([1.,-1.,1.]));tips.append(tip)
        row={'time':sample['time'],'tip_cm':list(tip)}
        for side in ('l','r'):
            A,B,C=(w[b+'_'+side].translation for b in ('upperarm','lowerarm','hand'))
            row['elbow_bend_'+side]=math.degrees((B-A).angle(C-B))
        rows.append(row)
    return {'peak_hand_speed_cm_s':{side:max((Vector(b['world']['hand_'+side]['p'])-Vector(a['world']['hand_'+side]['p'])).length/(b['time']-a['time']) for a,b in zip(items,items[1:])) for side in ('l','r')},
        'peak_sword_tip_speed_cm_s':max((b-a).length*FPS for a,b in zip(tips,tips[1:])),
        'sword_tip_path_cm':sum((b-a).length for a,b in zip(tips,tips[1:])),
        'max_chest_rotation_from_idle_deg':max(qangle(idle_world['spine_03'].decompose()[1],world(s['local'])['spine_03'].decompose()[1]) for s in items),
        'max_head_rotation_from_idle_deg':max(qangle(idle_world['head'].decompose()[1],world(s['local'])['head'].decompose()[1]) for s in items),
        'hand_r_height_range_cm':[min(s['world']['hand_r']['p'][2] for s in items),max(s['world']['hand_r']['p'][2] for s in items)],
        'hand_l_y_range_cm':[min(s['world']['hand_l']['p'][1] for s in items),max(s['world']['hand_l']['p'][1] for s in items)],
        'minimum_elbow_bend_deg':{side:min(r['elbow_bend_'+side] for r in rows) for side in ('l','r')},
        'damage_window_tip_samples':[r for r in rows if .8-1e-5<=r['time']<=1.0334]}
invariant=max(abs(x-y) for a,b in zip(source['samples'],samples) for bone in PARENTS if bone not in CHANGED for k in ('p','q','s') for x,y in zip(a['local'][bone][k],b['local'][bone][k]))
position_error=max(abs(x-y) for a,b in zip(source['samples'],samples) for bone in CHANGED for k in ('p','s') for x,y in zip(a['local'][bone][k],b['local'][bone][k]))
assert invariant==position_error==0.,'Only upper-body rotation tracks may change'
before_metrics=metrics(source['samples']);after_metrics=metrics(samples)
result=copy.deepcopy(data);result['clips']=[{'name':'Wuxia_Attack_Sword_Compact_v03','asset':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Compact_v03','source_asset':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Upright_v01','duration':DURATION,'frames':source['frames'],'samples':samples}]
result['mesh']='/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Shoulder_v02';result['changed_tracks']=list(CHANGED)
(OUT/'CompactAttackPoses.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
report={'state':'candidate','source_blend':bpy.data.filepath,'source_blend_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'source_vertices':len(mesh.data.vertices),'duration_seconds':DURATION,'damage_window_seconds':[.8,1.03],'unchanged_lower_body_error':invariant,'unchanged_local_translation_scale_error':position_error,'before':before_metrics,'after':after_metrics,'frames':pose_rows,'scope':'Offline candidate; review real-mesh renders and UE contact timings before assignment.'}
(OUT/'CompactAttackMetrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('COMPACT_ATTACK_BAKED',json.dumps({k:report[k] for k in ('state','before','after')}),flush=True)

if '--render' in sys.argv:
    for o in bpy.context.scene.objects:o.hide_render=True
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1000;scene.render.resolution_y=800;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.render.use_compositing=False;scene.render.use_sequencer=False
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0.;scene.view_settings.gamma=1.
    scene.world=bpy.data.worlds.new('CompactAttackWorld');scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');out=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(bg.outputs[0],out.inputs['Surface']);bg.inputs['Color'].default_value=(.18,.18,.18,1.);bg.inputs['Strength'].default_value=.65
    md=mesh.data.copy();obj=bpy.data.objects.new('CompactAttackBody',md);scene.collection.objects.link(obj);obj.shape_key_clear()
    pd=weapon.data.copy();pd.transform(weapon.matrix_world);prop_obj=bpy.data.objects.new('CompactAttackSword',pd);scene.collection.objects.link(prop_obj)
    bpy.ops.mesh.primitive_plane_add(size=20.,location=(0,0,-.005));floor=bpy.context.object
    mat=bpy.data.materials.new('CompactAttackFloor');mat.diffuse_color=(.035,.035,.035,1.);floor.data.materials.append(mat)
    bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=3.15
    focus=Vector((0,-.25,.95))
    for loc,power in [((-3,-3,5),1100),((4,-1,4),900),((0,4,5),1100)]:
        bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=5;light.rotation_euler=(focus-light.location).to_track_quat('-Z','Y').to_euler()
    folder=OUT/'Frames';folder.mkdir(parents=True,exist_ok=True)
    variants=[('After',samples)] if '--quick' in sys.argv else [('Before',source['samples']),('After',samples)]
    for variant,items in variants:
        for i,seconds in enumerate((0.,.6,.8,.9,1.03,1.3,1.8,2.3333)):
            if '--quick' in sys.argv and i not in (1,3,4,5):continue
            sample=min(items,key=lambda s:abs(s['time']-seconds));points,w=skin(sample['local']);md.vertices.foreach_set('co',(points*.01).ravel());md.update()
            prop_obj.matrix_world=Matrix.Scale(.01,4)@reflect@w['hand_r']@attach@reflect
            for angle,loc in [('Front',(-2.,-4.,2.1)),('Side',(4.,-.2,1.8))]:
                camera.location=loc;camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler()
                scene.render.filepath=str(folder/('%s_%02d_%.2fs_%s.png'%(variant,i,seconds,angle)));bpy.ops.render.render(write_still=True)
    print('COMPACT_ATTACK_RENDERED',str(folder),flush=True)
