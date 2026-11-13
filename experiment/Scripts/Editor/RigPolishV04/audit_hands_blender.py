"""Read-only compact attack hand/sleeve surface audit and geometric wrist bend."""
import copy,json,math,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Quaternion,Vector
from mathutils.bvhtree import BVHTree
PROJECT=Path(r'D:\game design\experiment')
def option(name,default):return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default
OUT=Path(option('--out',str(PROJECT/'Docs/Gameplay/RigPolish_v04/Audit')));OUT.mkdir(parents=True,exist_ok=True)
SETUP=PROJECT/'Saved/Scripts/bake_selected_death.py';context={'__name__':'hand_audit','__file__':str(SETUP)}
setup_source=SETUP.read_text(encoding='utf-8').split('raw=[];locals=[];support=[]')[0]
if '--fixed-grip' in sys.argv:
    setup_source=setup_source.replace("if grip is None:raise RuntimeError('Actual Combat EnemyGrip_R is required for this authoring preview.')","if grip is None:grip=mesh.data.shape_keys.key_blocks['Basis']")
exec(compile(setup_source,str(SETUP),'exec'),context)
if '--grip-json' in sys.argv:
    spec=json.loads(Path(option('--grip-json','')).read_text(encoding='utf-8'));q=spec['sword_relative_quaternion_xyzw']
    context['attach']=Matrix.LocRotScale(Vector(spec['sword_relative_location_cm']),Quaternion((q[3],*q[:3])),Vector(spec['sword_relative_scale']))
skin=context['skin'];world=context['world'];record=context['record'];blend=context['blend'];mesh=context['mesh'];weights=context['weights'];basis=context['basis'];coords=context['coords'];reflect=context['reflect'];attach=context['attach'];weapon=context['weapon'];prop_world=context['prop_world']
pose_path=Path(option('--poses',str(PROJECT/'ArtSource/WuxiaMale/RigPolishV03/Attack/CompactAttackRuntimePoses.json')))
data=json.loads(pose_path.read_text(encoding='utf-8'))
clip=data['clips'][0];reference=context['candidates']['reference']
mesh.data.calc_loop_triangles();triangles=[tuple(t.vertices) for t in mesh.data.loop_triangles];materials=[mesh.data.polygons[t.polygon_index].material_index for t in mesh.data.loop_triangles]
vmat=[set() for _ in mesh.data.vertices]
for tr,mat in zip(triangles,materials):
    for i in tr:vmat[i].add(mat)
side_data={};tri_sets={}
def group_sum(i,bones):return sum(weights[i].get(b,0.) for b in bones)
for side in ('r','l'):
    hand='hand_'+side;fore='lowerarm_'+side
    ids=np.asarray([i for i,w in enumerate(weights) if w.get(hand,0.)>.5])
    wrist=np.asarray(reference[hand]['p'])*np.array([1.,-1.,1.])
    # The centroid of strong hand vertices defines a geometric distal axis.
    direction=coords[ids,:3].mean(axis=0)-wrist;direction/=np.linalg.norm(direction)
    distal=(coords[:,:3]-wrist)@direction
    palm={int(i) for i in ids if distal[i]>2.0}
    fore_ids={i for i,w in enumerate(weights) if w.get(fore,0.)>.45}
    palm_tris=[tr for tr in triangles if all(i in palm for i in tr)]
    cuff_tris=[tr for tr,mat in zip(triangles,materials) if mat==0 and any(group_sum(i,(fore,hand))>.25 for i in tr)]
    # Cuff may include right hand geometry if the mesh has only a body material.
    cuff_tris=[tr for tr in cuff_tris if not any(i in palm for i in tr)]
    torso_tris=[tr for tr in triangles if all(group_sum(i,('spine_01','spine_02','spine_03','neck_01','head'))>.5 for i in tr)]
    side_data[side]={'ids':ids,'palm':palm,'wrist':wrist,'direction':direction,'forearm':fore_ids}
    tri_sets['palm_'+side]=palm_tris;tri_sets['cuff_'+side]=cuff_tris;tri_sets['torso']=torso_tris
material_groups={str(mat):sum(x==mat for x in materials) for mat in sorted(set(materials))}
def evaluated(t):
    f=t*30.;lo=min(len(clip['samples'])-1,int(f));hi=min(len(clip['samples'])-1,lo+1);alpha=f-lo
    return {b:blend(clip['samples'][lo]['local'][b],clip['samples'][hi]['local'][b],alpha) for b in clip['samples'][0]['local']}
pairs=[('palm_r','cuff_r'),('palm_l','cuff_l'),('palm_r','torso'),('palm_l','torso'),('palm_r','palm_l'),('palm_r','cuff_l'),('palm_l','cuff_r')]
rows=[]
for n in range(141):
    t=clip['duration']*n/140.;local=evaluated(t);points,w=skin(local)
    trees={name:BVHTree.FromPolygons(points.tolist(),tris,all_triangles=True,epsilon=.0001) for name,tris in tri_sets.items() if tris}
    row={'time':t,'intersections':{},'wrist':{}}
    for a,b in pairs:
        overlaps=trees[a].overlap(trees[b]) if a in trees and b in trees else []
        row['intersections'][a+'__'+b]={'triangle_pairs':len(overlaps),'example_triangle_ids':overlaps[:4]}
    for side in ('r','l'):
        fore=w['lowerarm_'+side].translation;hand=w['hand_'+side].translation
        # Rotate the mesh's distal palm direction with the actual hand transform.
        ref_mat=context['mat'](reference['hand_'+side]);hand_mat=w['hand_'+side]
        d_ref=Vector(side_data[side]['direction']*np.array([1.,-1.,1.]))
        d_world=hand_mat.to_3x3()@ref_mat.to_3x3().inverted()@d_ref
        fore_direction=(hand-fore).normalized()
        row['wrist'][side]={'forearm_to_palm_axis_degrees':math.degrees(fore_direction.angle(d_world.normalized())),
            'wrist_cm':list(hand),'elbow_cm':list(fore),'hand_centroid_cm':list(points[side_data[side]['ids']].mean(axis=0)*np.array([1.,-1.,1.]))}
    rows.append(row)
summary={key:sorted([{'time':r['time'],'triangle_pairs':r['intersections'][key]['triangle_pairs']} for r in rows],key=lambda a:-a['triangle_pairs'])[:10] for key in rows[0]['intersections']}
report={'state':'diagnostic','source_blend':bpy.data.filepath,'source_pose':str(pose_path),
    'material_triangles':material_groups,'triangle_set_sizes':{k:len(v) for k,v in tri_sets.items()},
    'hand_vertex_materials':{s:{str(m):sum(m in vmat[int(i)] for i in side_data[s]['ids']) for m in (0,1)} for s in ('l','r')},
    'worst_intersections':summary,'max_wrist_axis_bend':{s:max(r['wrist'][s]['forearm_to_palm_axis_degrees'] for r in rows) for s in ('r','l')},
    'rows':rows,'limits':'Discrete actual triangle overlap at 60Hz. Palm region excludes first 2cm beyond wrist to omit normal shared cuff seam. Surface overlap does not detect a fully enclosed nonintersecting palm. Geometric wrist bend is forearm-to-palm distal axis, not a universal anatomical flexion angle.'}
(OUT/'HandSurfaceAudit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('HAND_AUDIT',json.dumps({k:v for k,v in report.items() if k!='rows'}),flush=True)

if '--render' in sys.argv:
    for material in mesh.data.materials:
        if material:material.use_backface_culling=True
    for obj in bpy.context.scene.objects:obj.hide_render=True
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1100;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.render.use_compositing=False;scene.render.use_sequencer=False
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0.;scene.view_settings.gamma=1.
    scene.world=bpy.data.worlds.new('HandAuditWorld');scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');output=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(bg.outputs[0],output.inputs['Surface']);bg.inputs['Color'].default_value=(.055,.055,.055,1);bg.inputs['Strength'].default_value=.65
    md=mesh.data.copy();obj=bpy.data.objects.new('HandAuditBody',md);scene.collection.objects.link(obj);obj.shape_key_clear()
    pd=weapon.data.copy();pd.transform(weapon.matrix_world);prop_obj=bpy.data.objects.new('HandAuditSword',pd);scene.collection.objects.link(prop_obj)
    bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=1.2
    for loc,power in [((-3,-3,5),900),((4,-1,4),650),((0,4,5),900)]:
        bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=5
    for t in [float(v) for v in option('--times','0,.6,.8,.9,1.03,1.2,1.3').split(',')]:
        local=evaluated(t);points,w=skin(local);md.vertices.foreach_set('co',(points*.01).ravel());md.update()
        prop_obj.matrix_world=Matrix.Scale(.01,4)@reflect@w['hand_r']@attach@reflect
        focus=Vector(np.asarray(w['hand_r'].translation)*np.array([1.,-1.,1.])*.01);focus.z+=.12
        if '--hand-close' in sys.argv:
            focus=prop_obj.matrix_world.translation.copy();camera.data.ortho_scale=.36
        for label,offset in [('Front',Vector((-1.5,-3.,1.2))),('Side',Vector((3.,0.,.4)))]:
            camera.location=focus+offset;camera.rotation_euler=(-offset).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(OUT/('Hand_%0.2f_%s.png'%(t,label)));bpy.ops.render.render(write_still=True)
    print('HAND_AUDIT_RENDERED',str(OUT),flush=True)
