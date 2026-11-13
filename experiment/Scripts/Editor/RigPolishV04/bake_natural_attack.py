"""Offline v04 sword poses. Joint continuity precedes any blade target."""
import copy, json, math, sys, hashlib
from pathlib import Path
import bpy, numpy as np
from mathutils import Matrix, Vector, Quaternion
PROJECT=Path(r'D:\game design\experiment')
OUT=PROJECT/'ArtSource/WuxiaMale/RigPolishV04/Attack';OUT.mkdir(parents=True,exist_ok=True)
DOC=PROJECT/'Docs/Gameplay/RigPolish_v04';DOC.mkdir(parents=True,exist_ok=True)
setup=PROJECT/'Scripts/Editor/RigPolishV03/bake_compact_attack.py'
prefix=setup.read_text(encoding='utf-8').split('# Weapon extrema measured')[0]
prefix=prefix.replace("RigPolishV03/Attack", "RigPolishV04/Attack")
exec(compile(prefix,str(setup),'exec'),globals())
mat=context['mat']
reference={b:mat(v) for b,v in data['reference'].items()}
bind={b:record(reference[PARENTS[b]].inverted()@reference[b]) if PARENTS[b] else record(reference[b]) for b in PARENTS}
ref_prop=prop_world(bind)*np.array([1.,-1.,1.]);ref_hand=np.asarray(reference['hand_r'].translation)
TIP_INDEX=int(np.linalg.norm(ref_prop-ref_hand,axis=1).argmax())
neutral_blade=(Vector(ref_prop[TIP_INDEX])-reference['hand_r'].translation).normalized()
ref_forearm=(reference['hand_r'].translation-reference['lowerarm_r'].translation).normalized()
print('REFERENCE',json.dumps({'sword_axis':list(neutral_blade),'forearm_axis':list(ref_forearm),'sword_forearm_angle_deg':math.degrees(neutral_blade.angle(ref_forearm)), 'hand_local_q':bind['hand_r']['q']}),flush=True)

# The hand remains on the right of the chest. A raised, lateral elbow allows
# the forearm to descend into the strike without bending the wrist downward.
right_keys=[(0,list(idle_world['hand_r'].translation)),(.25,[-29,12,117]),(.6,[-29,20,130]),(.78,[-28,25,126]),(.9,[-20,38,115]),(1.03,[-19,36,109]),(1.3,[-28,19,106]),(1.7,[-29,12,108]),(2.05,list(idle_world['hand_r'].translation)),(DURATION,list(idle_world['hand_r'].translation))]
right_poles=[(0,[-1,-.2,-.3]),(.25,[-1,.1,-.4]),(.6,[-1,.1,-.65]),(.78,[-1,.3,-.1]),(.9,[-1,.6,.25]),(1.03,[-1,.6,.25]),(1.3,[-1,.3,-.35]),(1.7,[-1,-.1,-.6]),(DURATION,[-1,-.2,-.3])]
left_keys=[(0,list(idle_world['hand_l'].translation)),(.25,[25,14,105]),(.6,[25,16,106]),(.9,[25,13,104]),(1.03,[25,12,103]),(1.3,[25,13,104]),(1.8,[26,17,106]),(DURATION,list(idle_world['hand_l'].translation))]
# This is a preference for FOREARM rotation only. It never aims the wrist;
# projecting it onto the forearm cone keeps the bind palm/forearm relationship.
blade_preferences=[(0,[0,1,.1]),(.25,[-.1,.6,.8]),(.6,[-.12,.48,.87]),(.78,[-.1,.75,.65]),(.9,[.25,1,.1]),(1.03,[.25,1,-.1]),(1.3,[-.18,1,-.1]),(1.7,[-.25,1,.15]),(DURATION,[0,1,.1])]
wrist_swing=[(0,[0,0,0]),(.25,[8,0,0]),(.6,[8,0,0]),(.78,[14,0,0]),(.9,[20,0,0]),(1.03,[20,0,0]),(1.3,[12,0,0]),(1.7,[8,0,0]),(DURATION,[0,0,0])]
wrist_axis=reference['hand_r'].to_quaternion().inverted()@neutral_blade.cross(ref_forearm).normalized()

def twist_forearm(local, side, preference):
    w=world(local);bone='lowerarm_'+side
    axis=(w['hand_'+side].translation-w[bone].translation).normalized()
    prop=prop_world(local)*np.array([1.,-1.,1.])
    blade=(Vector(prop[TIP_INDEX])-w['hand_r'].translation).normalized()
    a=blade-axis*blade.dot(axis);b=preference-axis*preference.dot(axis)
    if min(a.length,b.length)<1e-7:return 0.
    a.normalize();b.normalize();angle=math.atan2(axis.dot(a.cross(b)),a.dot(b))
    # A modest forearm roll is allowed, never a replacement wrist hinge.
    angle=max(math.radians(-85),min(math.radians(85),angle))
    set_world_rotation(local,bone,Quaternion(axis,angle)@w[bone].decompose()[1])
    return math.degrees(angle)

samples=[];rows=[]
for original in source['samples']:
    t=original['time'];local=copy.deepcopy(original['local'])
    for b,factor in [('spine_01',.33),('spine_02',.35),('spine_03',.35),('neck_01',.15),('head',.15),('clavicle_l',.10),('clavicle_r',.15)]:
        local[b]['q']=blend(idle[b],local[b],factor)['q']
    for side,keys,pole in [('r',right_keys,interpolate(t,right_poles)),('l',left_keys,Vector((.25,-1,-.75)))]:
        for bone in ('upperarm_'+side,'lowerarm_'+side,'hand_'+side):local[bone]['q']=bind[bone]['q'][:]
        solve_arm(local,side,interpolate(t,keys),pole)
    # This small swing straightens the true palm axis: in the source mesh the
    # reference open palm is 32.8 deg from the forearm; 20 deg here reduces it
    # to 13.9 deg. It is not a blade-target wrist solve.
    bq=Quaternion((bind['hand_r']['q'][3],*bind['hand_r']['q'][:3]))
    hq=bq@Quaternion(wrist_axis,math.radians(interpolate(t,wrist_swing).x))
    local['hand_r']['q']=[hq.x,hq.y,hq.z,hq.w]
    lw=world(local);la=(lw['hand_l'].translation-lw['lowerarm_l'].translation).normalized()
    set_world_rotation(local,'lowerarm_l',Quaternion(la,math.radians(-65))@lw['lowerarm_l'].to_quaternion())
    roll=twist_forearm(local,'r',interpolate(t,blade_preferences).normalized())
    # Smooth blend from/to the unchanged legacy entry pose, outside contact.
    amount=smooth(t/.25)*smooth((DURATION-t)/.35)
    for b in ('clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r'):
        local[b]['q']=blend(idle[b],local[b],amount)['q']
    if t<1e-6 or abs(t-DURATION)<1e-6:local=copy.deepcopy(original['local'])
    w=world(local);prop=prop_world(local);points,_=skin(local)
    samples.append({'time':t,'local':local,'world':{b:record(m) for b,m in w.items()}})
    rows.append({'time':t,'forearm_roll_deg':roll,'hand_r':list(w['hand_r'].translation),'elbow_r':list(w['lowerarm_r'].translation),'hand_l':list(w['hand_l'].translation),'tip':list(prop[TIP_INDEX]*np.array([1.,-1.,1.])),'wrist_from_bind_deg':{s:qangle(Quaternion((local['hand_'+s]['q'][3],*local['hand_'+s]['q'][:3])),Quaternion((bind['hand_'+s]['q'][3],*bind['hand_'+s]['q'][:3]))) for s in ('r','l')}})
result=copy.deepcopy(data);result['clips']=[{'name':'Wuxia_Attack_Sword_Natural_v04','asset':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Natural_v04','source_asset':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Upright_v01','duration':DURATION,'frames':source['frames'],'samples':samples}]
result['mesh']='/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Shoulder_v02';result['changed_tracks']=list(CHANGED)
(OUT/'NaturalAttackPoses.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
invariant=max(abs(x-y) for a,b in zip(source['samples'],samples) for bone in PARENTS if bone not in CHANGED for k in ('p','q','s') for x,y in zip(a['local'][bone][k],b['local'][bone][k]))
position_error=max(abs(x-y) for a,b in zip(source['samples'],samples) for bone in CHANGED for k in ('p','s') for x,y in zip(a['local'][bone][k],b['local'][bone][k]))
assert invariant==position_error==0.,'Only upper-body rotations can change'
(OUT/'NaturalAttackMetrics.json').write_text(json.dumps({'state':'offline_key_pose_candidate','frames':rows,'neutral_blade_forearm_angle_deg':math.degrees(neutral_blade.angle(ref_forearm)), 'unchanged_lower_body_error':invariant, 'unchanged_local_translation_scale_error':position_error},indent=2),encoding='utf-8')
print('V04_KEY_POSES',json.dumps([r for r in rows if any(abs(r['time']-t)<.005 for t in (.6,.9,1.0333333,1.3))]),flush=True)

if '--render' in sys.argv:
    for o in bpy.context.scene.objects:o.hide_render=True
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1000;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.render.use_compositing=False;scene.render.use_sequencer=False
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0.;scene.view_settings.gamma=1.
    scene.world=bpy.data.worlds.new('NaturalAttackWorld');scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');wo=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(bg.outputs[0],wo.inputs['Surface']);bg.inputs['Color'].default_value=(.12,.12,.12,1);bg.inputs['Strength'].default_value=.65
    md=mesh.data.copy();obj=bpy.data.objects.new('NaturalAttackBody',md);scene.collection.objects.link(obj);obj.shape_key_clear()
    pd=weapon.data.copy();pd.transform(weapon.matrix_world);prop_obj=bpy.data.objects.new('NaturalAttackSword',pd);scene.collection.objects.link(prop_obj)
    bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=1.65
    focus=Vector((-.05,-.22,1.25))
    for loc,power in [((-3,-3,5),1100),((4,-1,4),900),((0,4,5),1100)]:
        bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=5;light.rotation_euler=(focus-light.location).to_track_quat('-Z','Y').to_euler()
    folder=OUT/'KeyFrames';folder.mkdir(parents=True,exist_ok=True)
    for seconds in (.6,.9,1.03,1.3):
        sample=min(samples,key=lambda s:abs(s['time']-seconds));points,w=skin(sample['local']);md.vertices.foreach_set('co',(points*.01).ravel());md.update()
        prop_obj.matrix_world=Matrix.Scale(.01,4)@reflect@w['hand_r']@attach@reflect
        for angle,loc in [('Front',(-1.3,-4,1.8)),('Side',(-4,-.3,1.65))]:
            camera.location=loc;camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(folder/('Natural_%.2fs_%s.png'%(seconds,angle)));bpy.ops.render.render(write_still=True)
    print('V04_KEY_RENDERED',str(folder),flush=True)
