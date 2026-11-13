"""Bake a compact collapse on an existing Combat skin; never save the source blend.

Blender command: blender -b <Combat.blend> --python <this file> [-- --render]
The source body/weapon, source death and upright idle are read-only. Candidate
tracks and actual skin/prop contact evidence are written to a new folder.
"""
import copy,hashlib,json,math,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Quaternion,Vector

PROJECT=Path(r'D:\game design\experiment')
OUT=PROJECT/'ArtSource/WuxiaMale/RigPolishV02/Death'
OUT.mkdir(parents=True,exist_ok=True)
SETUP=PROJECT/'Saved/Scripts/bake_selected_death.py'
context={'__name__':'restrained_skin_setup','__file__':str(SETUP)}
exec(compile(SETUP.read_text(encoding='utf-8').split('raw=[];locals=[];support=[]')[0],str(SETUP),'exec'),context)
skin=context['skin'];world=context['world'];record=context['record'];blend=context['blend']
solve_two_bone=context['solve_two_bone'];set_world_rotation=context['set_world_rotation']
prop_world=context['prop_world'];PARENTS=context['PARENTS'];mesh=context['mesh'];weapon=context['weapon']
reflect=context['reflect'];attach=context['attach'];sole_ids=context['sole_ids']
hand_ids=context['hand_ids'];forearm_ids=context['forearm_ids'];body_ids=context['body_ids']
boot_ids=context['boot_ids'];weights=context['weights'];basis=context['basis']
old_data=json.loads((PROJECT/'ArtSource/WuxiaMale/DeathSelection20261012/OptimizedDeathPoses.json').read_text(encoding='utf-8'))
old=old_data['clips'][0]
upright_data=json.loads((PROJECT/'Docs/Gameplay/RigPolish_v01/UprightCandidatePoses.json').read_text(encoding='utf-8'))
idle=next(c for c in upright_data['clips'] if c['name']=='Wuxia_Idle_Planted_Upright_v01')['samples'][0]['local']
final=copy.deepcopy(old['samples'][-1]['local'])
FPS=30;DURATION=2.6;SETTLE_END=2.1;CLEARANCE=.02
ARM_BONES=('clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r')
def smooth(value):
    value=max(0.,min(1.,value));return value*value*(3.-2.*value)
def sample(t):
    frame=max(0.,min(old['frames'],t*FPS));lo=int(frame);hi=min(lo+1,old['frames']);a=frame-lo
    return {b:blend(old['samples'][lo]['local'][b],old['samples'][hi]['local'][b],a) for b in PARENTS}
def morph_at(t):
    frame=max(0.,min(old['frames'],t*FPS));lo=int(frame);hi=min(lo+1,old['frames']);w=frame-lo
    return {name:keys[lo]['value']*(1-w)+keys[hi]['value']*w for name,keys in old['morph_curves'].items()}
def weights_blend(a,b,w):return {k:a.get(k,0.)*(1-w)+b.get(k,0.)*w for k in set(a)|set(b)}
def scalar_keys(t,keys):
    if t<=keys[0][0]:return keys[0][1]
    if t>=keys[-1][0]:return keys[-1][1]
    for (ta,a),(tb,b) in zip(keys,keys[1:]):
        if ta<=t<=tb:return a+(b-a)*smooth((t-ta)/(tb-ta))
def grounded_leg(local,side,knee_z,foot_z,foot_q):
    """Pose an articulated kneeling leg with a low knee and calf contact.

    Boot XY can retreat as the knees fold, avoiding the source's upward knee
    pole. Both segment lengths and the pelvis location are exactly retained.
    """
    result=copy.deepcopy(local);w=world(result);a='thigh_'+side;b='calf_'+side;c='foot_'+side
    A,B,C=(w[k].translation.copy() for k in (a,b,c));l1=(B-A).length;l2=(C-B).length
    dz=max(-l1+.02,min(l1-.02,knee_z-A.z))
    backward=Vector((.18 if side=='l' else -.18,-1.,0.)).normalized()
    knee=A+backward*math.sqrt(max(0.,l1*l1-dz*dz))+Vector((0.,0.,dz))
    set_world_rotation(result,a,(B-A).normalized().rotation_difference((knee-A).normalized())@w[a].decompose()[1])
    for iteration in range(3):
        w=world(result);B=w[b].translation;C=w[c].translation
        dz=max(-l2+.02,min(l2-.02,foot_z-B.z))
        ankle=B+backward*math.sqrt(max(0.,l2*l2-dz*dz))+Vector((0.,0.,dz))
        set_world_rotation(result,b,(C-B).normalized().rotation_difference((ankle-B).normalized())@w[b].decompose()[1])
        set_world_rotation(result,c,foot_q)
    return result
def arm_with_pole(local,side,target,preferred_pole):
    result=copy.deepcopy(local);w=world(result);a='upperarm_'+side;b='lowerarm_'+side;c='hand_'+side
    A,B,C=(w[k].translation.copy() for k in (a,b,c));l1=(B-A).length;l2=(C-B).length
    delta=target-A;distance=max(abs(l1-l2)+.02,min(delta.length,l1+l2-.02));axis=delta.normalized()
    pole=preferred_pole-axis*preferred_pole.dot(axis);pole.normalize()
    x=(l1*l1-l2*l2+distance*distance)/(2*distance);height=math.sqrt(max(0.,l1*l1-x*x))
    elbow=A+axis*x+pole*height
    set_world_rotation(result,a,(B-A).normalized().rotation_difference((elbow-A).normalized())@w[a].decompose()[1])
    w2=world(result);B=w2[b].translation;C=w2[c].translation;T=A+axis*distance
    set_world_rotation(result,b,(C-B).normalized().rotation_difference((T-B).normalized())@w2[b].decompose()[1])
    set_world_rotation(result,c,w[c].decompose()[1])
    return result

# Reuse only compact weakness, forward fall and the validated final contacts.
# The broad overhead flail and recoiling up/down source section are omitted.
keyframes=[(0.,idle,{}),(.45,sample(.35),morph_at(.35)),(.95,sample(1.35),morph_at(1.35)),
           (1.5,sample(1.65),morph_at(1.65)),(SETTLE_END,final,morph_at(3.3))]
final_root=Vector(final['root']['p']);start_root=Vector(idle['root']['p'])
travel=Vector((final_root.x-start_root.x,final_root.y-start_root.y,0.))
compact_scale=min(1.,35./max(travel.length,1e-6))
final_shift=travel*(compact_scale-1.)
idle_world=world(idle);final_world=world(final)
knee_ids={}
for side in ('l','r'):
    rest=context['mat'](old_data['reference']['calf_'+side]).translation
    rest=np.asarray((rest.x,-rest.y,rest.z))
    knee_ids[side]=np.asarray([i for i in range(len(weights)) if weights[i].get('thigh_'+side,0.)+weights[i].get('calf_'+side,0.)>.25 and np.linalg.norm(basis[i,:3]-rest)<18.])
    if not len(knee_ids[side]):raise RuntimeError('Need actual knee contact region')
foot_final={side:final_world['foot_'+side].translation+final_shift for side in ('l','r')}
foot_idle={side:idle_world['foot_'+side].translation.copy() for side in ('l','r')}
root_final_xy=start_root+travel*compact_scale
samples=[];raw_support=[];pre_rows=[]
for frame in range(round(DURATION*FPS)+1):
    t=frame/FPS
    if t>=SETTLE_END:
        local=copy.deepcopy(final);mw=morph_at(3.3)
    else:
        index=next(i for i in range(len(keyframes)-1) if keyframes[i][0]<=t<=keyframes[i+1][0])
        a,b=keyframes[index],keyframes[index+1]
        w=smooth((t-a[0])/(b[0]-a[0]))
        local={bone:blend(a[1][bone],b[1][bone],w) for bone in PARENTS}
        mw=weights_blend(a[2],b[2],w)
    # Move the same terminal body configuration closer to its starting footprint.
    travel_w=smooth(t/1.55)
    local['root']['p'][0]=start_root.x+(root_final_xy.x-start_root.x)*travel_w
    local['root']['p'][1]=start_root.y+(root_final_xy.y-start_root.y)*travel_w
    if t<SETTLE_END:
        # A body losing support descends continuously; remove the source's
        # initial upward recoil before knee contact and the flying hip arc.
        desired_pelvis=scalar_keys(t,[(0.,idle_world['pelvis'].translation.z),(.45,59.),(.8,43.),(1.25,29.),(1.65,final_world['pelvis'].translation.z)])
        local['root']['p'][2]+=desired_pelvis-world(local)['pelvis'].translation.z
        # After the knees yield, the chest and head relax forward/down instead
        # of holding the source push-up silhouette above the ground.
        chest_w=smooth((t-.7)/.65)
        for bone in ('spine_01','spine_02','spine_03','neck_01','head'):
            local[bone]=blend(local[bone],final[bone],chest_w)
        # Keep arms near the trunk during loss of support, then reach the
        # genuinely grounded resting chain. Do not use the source high raise.
        arm_w=smooth((t-.25)/1.65)
        for bone in ARM_BONES:local[bone]=blend(idle[bone],final[bone],arm_w)
        # Plant the boot chains through the knee-softening phase; once the body
        # tips, allow a small controlled glide toward the validated side contact.
        foot_w=smooth((t-.25)/1.75)
        for side in ('l','r'):
            target=foot_idle[side].lerp(foot_final[side],foot_w)
            local=solve_two_bone(local,side,target,0.,'leg')
            desired_q=idle_world['foot_'+side].decompose()[1].slerp(final_world['foot_'+side].decompose()[1],foot_w)
            set_world_rotation(local,'foot_'+side,desired_q)
            for iteration in range(2):
                points,w=skin(local,mw)
                need=max(0.,CLEARANCE-float(points[sole_ids[side],2].min()))
                if need<.005:break
                target=w['foot_'+side].translation.copy();target.z+=need
                local=solve_two_bone(local,side,target,0.,'leg')
        # Knees fold down/back and calves remain near the floor through the
        # collapse. At the end only, relax to the original side-lying corpse.
        kneel_w=smooth((t-.4)/.35)*(1.-smooth((t-1.6)/.5))
        for side in ('l','r'):
            foot_q=idle_world['foot_'+side].decompose()[1].slerp(final_world['foot_'+side].decompose()[1],smooth((t-.2)/.6))
            grounded=grounded_leg(local,side,7.,12. if side=='l' else 8.,foot_q)
            for bone in ('thigh_'+side,'calf_'+side,'foot_'+side):local[bone]=blend(local[bone],grounded[bone],kneel_w)
        # Wrist smoothly relaxes to the final supported sword orientation. This
        # avoids an upright overhead blade during the forward fall.
        w=world(local);relax=smooth((t-.35)/1.35)
        for side in ('l','r'):
            q=w['hand_'+side].decompose()[1].slerp(final_world['hand_'+side].decompose()[1],relax)
            set_world_rotation(local,'hand_'+side,q)
        # Brace below the chest with a folded elbow, instead of extending both
        # arms beyond the head. The sword arm relaxes slightly later.
        for side in ('l','r'):
            w=world(local);shoulder=w['upperarm_'+side].translation
            current=w['hand_'+side].translation
            target=Vector((shoulder.x+(9. if side=='l' else -10.),shoulder.y+2.,6. if side=='l' else 9.))
            weight=smooth((t-(.55 if side=='l' else .65))/.45)*(1.-smooth((t-1.55)/.55))
            target=current.lerp(target,weight)
            local=solve_two_bone(local,side,target,.7,'arm')
        # Hands may brace on the floor but must not determine a deep whole-body
        # lift because a rigid downward forearm entered the floor first.
        for side in ('l','r'):
            for iteration in range(3):
                points,w=skin(local,mw)
                need=max(0.,.3-float(points[hand_ids[side],2].min()))
                if need<.005:break
                target=w['hand_'+side].translation.copy();target.z+=need
                local=solve_two_bone(local,side,target,.25,'arm')
        # Correct only a held blade that would penetrate; no prop detachment.
        for iteration in range(2):
            points,w=skin(local,mw);prop=prop_world(local)
            sword_min=float(prop[:,2].min())
            if sword_min>=.05:break
            target=w['hand_r'].translation.copy();target.z+=.05-sword_min
            local=solve_two_bone(local,'r',target,.20,'arm')
        # Last part closes exactly onto the existing validated final body.
        close=smooth((t-1.75)/.35)
        if close>0.:
            for bone in PARENTS:
                if bone!='root':local[bone]=blend(local[bone],final[bone],close)
            local['root']['p'][2]=local['root']['p'][2]*(1-close)+final['root']['p'][2]*close
        # Do not let an elbow swinging through the floor lift the entire corpse
        # (and both legs) during the final kneel-to-side-lying transition.
        if 1.0<t<SETTLE_END:
            relax_contact=smooth((t-1.)/.25)*(1.-smooth((t-1.95)/.15))
            for side in ('l','r'):
                points,w=skin(local,mw)
                target=w['hand_'+side].translation.copy()
                trials=[]
                for up in (.5,1.,2.):
                    option=arm_with_pole(local,side,target,Vector((1. if side=='l' else -1.,0.,up)))
                    posed,_=skin(option,mw)
                    low=min(float(posed[hand_ids[side],2].min()),float(posed[forearm_ids[side],2].min()))
                    trials.append((max(0.,.02-low)+.01*up,option))
                best=min(trials,key=lambda row:row[0])[1]
                hand_world_q=w['hand_'+side].decompose()[1]
                for bone in ('upperarm_'+side,'lowerarm_'+side,'hand_'+side):
                    local[bone]=blend(local[bone],best[bone],relax_contact)
                set_world_rotation(local,'hand_'+side,hand_world_q)
    points,w=skin(local,mw);prop=prop_world(local)
    minimum=min(float(points[:,2].min()),float(prop[:,2].min()))
    raw_support.append(CLEARANCE-minimum)
    samples.append({'time':t,'local':local,'morph_weights':mw})
    support_index=int(points[:,2].argmin())
    pre_rows.append({'time':t,'raw_skin_min_cm':float(points[:,2].min()),'raw_prop_min_cm':float(prop[:,2].min()),
                    'support_index':support_index,'support_weights':weights[support_index]})

# Minimum-curvature support envelope. This retains exact final pose height;
# only the minimum amount of vertical support needed by the actual skin is used.
n=len(samples);second=np.zeros((n-2,n))
for i in range(n-2):second[i,i:i+3]=[1.,-2.,1.]
H=np.eye(n)+60.*(second.T@second);bound=np.asarray(raw_support)
fixed={i for i,s in enumerate(samples) if s['time']>=SETTLE_END};active=set(fixed)
offsets=bound.copy()
for i in fixed:
    if bound[i]>.01:raise RuntimeError('Expected final validated skin/prop to remain above the floor')
    offsets[i]=0.
for iteration in range(300):
    free=sorted(set(range(n))-active);locked=sorted(active)
    for i in locked:offsets[i]=0. if i in fixed else bound[i]
    offsets[free]=np.linalg.solve(H[np.ix_(free,free)],bound[free]-H[np.ix_(free,locked)]@offsets[locked])
    violations=[i for i in free if offsets[i]<bound[i]-1e-7]
    if violations:active.add(min(violations,key=lambda i:offsets[i]-bound[i]));continue
    gradient=H@offsets-bound
    release=[i for i in active-fixed if gradient[i]<-1e-7]
    if release:active.remove(min(release,key=lambda i:gradient[i]));continue
    break
else:raise RuntimeError('Support constraint solve did not converge')
rows=[]
for sample,offset in zip(samples,offsets):
    sample['local']['root']['p'][2]+=float(offset)
    # Actual support raises the whole figure by the robe thickness. Compensate
    # that lift at the bracing palm so it touches the same floor as the knees.
    t=sample['time'];brace=smooth((t-.65)/.4)*(1.-smooth((t-1.65)/.45))
    if brace>0.:
        for iteration in range(3):
            points,w=skin(sample['local'],sample['morph_weights'])
            low=min(float(points[hand_ids['l'],2].min()),float(points[forearm_ids['l'],2].min()))
            target=w['hand_l'].translation.copy();target.z+=(.3-low)*brace
            candidate=solve_two_bone(sample['local'],'l',target,.45,'arm')
            new_points,_=skin(candidate,sample['morph_weights'])
            if float(new_points[:,2].min())<.015:break
            sample['local']=candidate
    points,w=skin(sample['local'],sample['morph_weights']);prop=prop_world(sample['local'])
    sample['world']={bone:record(m) for bone,m in w.items()}
    rows.append({'time':sample['time'],'support_offset_cm':float(offset),'whole_skin_min_cm':float(points[:,2].min()),
                 'sword_min_cm':float(prop[:,2].min()),
                 'sole_l_min_cm':float(points[sole_ids['l'],2].min()),'sole_r_min_cm':float(points[sole_ids['r'],2].min()),
                 'head_z_cm':float(w['head'].translation.z),'pelvis_z_cm':float(w['pelvis'].translation.z),
                 'hand_r_z_cm':float(w['hand_r'].translation.z)})
    for side in ('l','r'):
        rows[-1]['knee_'+side+'_skin_min_cm']=float(points[knee_ids[side],2].min())
        rows[-1]['knee_'+side+'_joint_z_cm']=float(w['calf_'+side].translation.z)
        rows[-1]['boot_'+side+'_skin_min_cm']=float(points[boot_ids[side],2].min())
        rows[-1]['hand_'+side+'_skin_min_cm']=float(points[hand_ids[side],2].min())
        rows[-1]['forearm_'+side+'_skin_min_cm']=float(points[forearm_ids[side],2].min())
if min(r['whole_skin_min_cm'] for r in rows)<-.005 or min(r['sword_min_cm'] for r in rows)<-.005:
    raise RuntimeError('Actually skinned body or held sword penetrates the floor')
hold=samples[round(SETTLE_END*FPS):]
hold_error=max(abs(a-b) for sample in hold for bone in PARENTS for field in ('p','q','s')
               for a,b in zip(sample['local'][bone][field],hold[0]['local'][bone][field]))
if hold_error>1e-7:raise RuntimeError('Final pose does not hold still')
clip={'name':'Wuxia_Death_Restrained_v02','asset':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Restrained_v02',
      'source_asset':old['asset'],'role':'death','duration':DURATION,'frames':round(DURATION*FPS),'samples':samples,
      'timing':{'collapse_end_seconds':SETTLE_END,'final_hold_seconds':DURATION-SETTLE_END,'loop':False},
      'morph_curves':{name:[{'time':s['time'],'value':s['morph_weights'].get(name,0.)} for s in samples] for name in old['morph_curves']}}
result=copy.deepcopy(old_data);result['clips']=[clip];result['preview_morph_overrides']={'EnemyGrip_R':1.}
(OUT/'RestrainedDeathPoses.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
def motion_metrics(samples):
    return {'head_z_range_cm':[min(s['world']['head']['p'][2] for s in samples),max(s['world']['head']['p'][2] for s in samples)],
            'hand_r_z_max_cm':max(s['world']['hand_r']['p'][2] for s in samples),
            'root_xy_travel_cm':(Vector(samples[-1]['world']['root']['p'])-Vector(samples[0]['world']['root']['p'])).to_2d().length,
            'max_bone_speed_cm_s':{bone:max((Vector(b['world'][bone]['p'])-Vector(a['world'][bone]['p'])).length*FPS for a,b in zip(samples,samples[1:])) for bone in ('pelvis','head','hand_l','hand_r','foot_l','foot_r')}}
report={'state':'passed','source_blend':bpy.data.filepath,'source_blend_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'source_mesh':mesh.name,'vertex_count':len(mesh.data.vertices),
        'method':'Compact weakness-to-forward-fall key poses, restrained arms, two-bone contact correction, actually skinned support envelope.',
        'duration_seconds':DURATION,'final_hold_seconds':DURATION-SETTLE_END,'final_hold_error':hold_error,
        'final_pose_xy_translation_cm':list(final_shift),'final_pose_preserved_except_xy':True,
        'minimum_skin_height_cm':min(r['whole_skin_min_cm'] for r in rows),'minimum_sword_height_cm':min(r['sword_min_cm'] for r in rows),
        'support_offset_range_cm':[float(min(offsets)),float(max(offsets))],'before':motion_metrics(old['samples']),
        'after':motion_metrics(samples),'frames':rows,'raw_contact_supports':pre_rows,'scope':'Offline authoring only. Candidate has not been imported or assigned to gameplay.'}
(OUT/'RestrainedDeathContacts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('RESTRAINED_DEATH_BAKED',json.dumps({k:v for k,v in report.items() if k not in ('frames','raw_contact_supports')}),flush=True)

if '--render' in sys.argv:
    for obj in bpy.context.scene.objects:obj.hide_render=True
    scene=bpy.context.scene
    for engine in ('BLENDER_EEVEE','BLENDER_EEVEE_NEXT'):
        try:scene.render.engine=engine;break
        except TypeError:pass
    scene.render.resolution_x=900;scene.render.resolution_y=750;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.film_transparent=False
    scene.render.use_compositing=False;scene.render.use_sequencer=False
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0.;scene.view_settings.gamma=1.
    scene.world=bpy.data.worlds.new('RestrainedDeathWorld');scene.world.use_nodes=True
    background=next((node for node in scene.world.node_tree.nodes if node.type=='BACKGROUND'),None) or scene.world.node_tree.nodes.new('ShaderNodeBackground')
    output=next((node for node in scene.world.node_tree.nodes if node.type=='OUTPUT_WORLD'),None) or scene.world.node_tree.nodes.new('ShaderNodeOutputWorld')
    scene.world.node_tree.links.new(background.outputs['Background'],output.inputs['Surface'])
    background.inputs['Color'].default_value=(.22,.22,.22,1.);background.inputs['Strength'].default_value=.6
    posed_data=mesh.data.copy();posed_obj=bpy.data.objects.new('RestrainedDeathBody',posed_data);scene.collection.objects.link(posed_obj)
    if posed_obj.data.shape_keys:posed_obj.shape_key_clear()
    prop_data=weapon.data.copy();prop_data.transform(weapon.matrix_world)
    prop_obj=bpy.data.objects.new('RestrainedDeathSword',prop_data);scene.collection.objects.link(prop_obj)
    bpy.ops.mesh.primitive_plane_add(size=20.,location=(0,0,-.002));floor=bpy.context.object
    material=bpy.data.materials.new('RestrainedDeathFloor');material.use_nodes=True
    shader=next((node for node in material.node_tree.nodes if node.type=='BSDF_PRINCIPLED'),None) or material.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    output=next((node for node in material.node_tree.nodes if node.type=='OUTPUT_MATERIAL'),None) or material.node_tree.nodes.new('ShaderNodeOutputMaterial')
    material.node_tree.links.new(shader.outputs['BSDF'],output.inputs['Surface'])
    shader.inputs['Base Color'].default_value=(.025,.025,.025,1.);shader.inputs['Roughness'].default_value=.9
    checker=material.node_tree.nodes.new('ShaderNodeTexChecker')
    checker.inputs['Color1'].default_value=(.023,.023,.023,1.);checker.inputs['Color2'].default_value=(.04,.04,.04,1.);checker.inputs['Scale'].default_value=2.
    coordinates=material.node_tree.nodes.new('ShaderNodeTexCoord');material.node_tree.links.new(coordinates.outputs['Object'],checker.inputs['Vector'])
    material.node_tree.links.new(checker.outputs['Color'],shader.inputs['Base Color'])
    floor.data.materials.append(material)
    bpy.ops.object.camera_add(location=(4.,-.15,1.65));camera=bpy.context.object;scene.camera=camera
    focus=Vector((.05,-.45,.75));camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=3.0
    for loc,power in [((-3,-3,5),1100),((4,-1,4),900),((0,4,5),1100)]:
        bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=5
        light.rotation_euler=(focus-light.location).to_track_quat('-Z','Y').to_euler()
    folder=OUT/'Frames';folder.mkdir(parents=True,exist_ok=True)
    for i,seconds in enumerate((0.,.25,.45,.70,.95,1.2,1.5,1.8,2.1,2.6)):
        s=samples[round(seconds*FPS)];points,w=skin(s['local'],s['morph_weights'])
        posed_data.vertices.foreach_set('co',(points*.01).ravel());posed_data.update()
        prop_obj.matrix_world=Matrix.Scale(.01,4)@reflect@w['hand_r']@attach@reflect
        scene.render.filepath=str(folder/('%02d_%.2fs.png'%(i,seconds)));bpy.ops.render.render(write_still=True)
    print('RESTRAINED_DEATH_RENDERED',str(folder),flush=True)
