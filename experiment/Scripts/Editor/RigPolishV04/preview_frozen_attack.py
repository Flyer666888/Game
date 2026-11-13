"""Read-only animation checks and renders against a selected v04 hand mesh."""
import sys
from pathlib import Path
p=Path(r'D:\game design\experiment\Scripts\Editor\RigPolishV04\bake_natural_attack.py')
exec(compile(p.read_text(encoding='utf-8').split('# The hand remains')[0],str(p),'exec'),globals())
pose_path=OUT/'NaturalAttackPoses.json';frozen=hashlib.sha256(pose_path.read_bytes()).hexdigest()
candidate=json.loads(pose_path.read_text(encoding='utf-8'))
samples=candidate['clips'][0]['samples'];tip_path=[];report={'pose_sha256':frozen,'mesh_source':bpy.data.filepath,'frames':len(samples),'duration':DURATION}
for s in samples:
    tip_path.append(Vector(prop_world(s['local'])[TIP_INDEX]*np.array([1,-1,1])))
report['peak_hand_speed_cm_s']={side:max((Vector(b['world']['hand_'+side]['p'])-Vector(a['world']['hand_'+side]['p'])).length/(b['time']-a['time']) for a,b in zip(samples,samples[1:])) for side in ('l','r')}
report['peak_tip_speed_cm_s']=max((b-a).length*FPS for a,b in zip(tip_path,tip_path[1:]))
report['peak_local_frame_rotation_deg']={bone:max(qangle(Quaternion((a['local'][bone]['q'][3],*a['local'][bone]['q'][:3])),Quaternion((b['local'][bone]['q'][3],*b['local'][bone]['q'][:3]))) for a,b in zip(samples,samples[1:])) for bone in CHANGED}
report['sharpest_intervals']=sorted([{'time':b['time'],'tip_step_cm':(tb-ta).length,'hand_step_cm':(Vector(b['world']['hand_r']['p'])-Vector(a['world']['hand_r']['p'])).length} for a,b,ta,tb in zip(samples,samples[1:],tip_path,tip_path[1:])],key=lambda r:r['tip_step_cm'],reverse=True)[:8]
report['right_hand_x_bounds_cm']=[min(s['world']['hand_r']['p'][0] for s in samples),max(s['world']['hand_r']['p'][0] for s in samples)]
report['damage_tip_path_cm']=[{'time':s['time'],'p':list(tip)} for s,tip in zip(samples,tip_path) if .8-1e-5<=s['time']<=1.0334]
report['max_chest_rotation_from_idle_deg']=max(qangle(idle_world['spine_03'].to_quaternion(),world(s['local'])['spine_03'].to_quaternion()) for s in samples)
(OUT/'NaturalAttackContinuity.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('CONTINUITY',json.dumps(report),flush=True)
if '--render' not in sys.argv:sys.exit(0)
for o in bpy.context.scene.objects:o.hide_render=True
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=720;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.render.use_compositing=False;scene.render.use_sequencer=False
scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0.;scene.view_settings.gamma=1.
scene.world=bpy.data.worlds.new('FrozenAttackWorld');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');wo=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(bg.outputs[0],wo.inputs['Surface']);bg.inputs['Color'].default_value=(.12,.12,.12,1);bg.inputs['Strength'].default_value=.65
md=mesh.data.copy();obj=bpy.data.objects.new('FrozenAttackBody',md);scene.collection.objects.link(obj);obj.shape_key_clear()
pd=weapon.data.copy();pd.transform(weapon.matrix_world);prop_obj=bpy.data.objects.new('FrozenAttackSword',pd);scene.collection.objects.link(prop_obj)
bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=2.05
focus=Vector((-.05,-.25,1.15))
for loc,power in [((-3,-3,5),1100),((4,-1,4),900),((0,4,5),1100)]:
    bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=5;light.rotation_euler=(focus-light.location).to_track_quat('-Z','Y').to_euler()
folder=OUT/'PreviewFrames';folder.mkdir(parents=True,exist_ok=True)
for i,sample in enumerate(samples):
    points,w=skin(sample['local']);md.vertices.foreach_set('co',(points*.01).ravel());md.update()
    prop_obj.matrix_world=Matrix.Scale(.01,4)@reflect@w['hand_r']@attach@reflect
    for angle,loc in [('Front',(-1.3,-4,1.8)),('Side',(-4,-.3,1.65))]:
        camera.location=loc;camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(folder/('%s_%03d.png'%(angle,i)));bpy.ops.render.render(write_still=True)
assert hashlib.sha256(pose_path.read_bytes()).hexdigest()==frozen
print('FROZEN_PREVIEW_COMPLETE',frozen,flush=True)
