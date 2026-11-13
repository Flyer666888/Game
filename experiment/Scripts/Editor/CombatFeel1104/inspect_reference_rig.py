"""Read FBX structure without changing source files or enabling automatic bone orientation."""
import bpy, json, math, hashlib
from pathlib import Path
P=Path(r'D:/game design/experiment')
OUT=P/'Docs/Gameplay/RigReference1104'
OUT.mkdir(parents=True,exist_ok=True)
FILES={
 'provided':Path(r'C:/Users/21475/Desktop/Game model/古代男青年走路动画.fbx'),
 'current':P/'ArtSource/WuxiaMale/RigPolishV04/HandsReplacement/WuxiaMaleRealGrip_v04.fbx'
}
def vec(v):return [round(float(x),6) for x in v]
def matrix(m):return [vec(row) for row in m]
def curves(action):
    if hasattr(action,'fcurves'): return list(action.fcurves)
    return [fc for layer in action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
report={}
for label,path in FILES.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path),automatic_bone_orientation=False,use_anim=True,ignore_leaf_bones=False)
    arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    data={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
          'unit_scale':bpy.context.scene.unit_settings.scale_length,'fps':bpy.context.scene.render.fps,
          'armatures':[],'meshes':[],'actions':[]}
    for arm in arms:
        bones=[]
        for b in arm.data.bones:
            local=b.parent.matrix_local.inverted()@b.matrix_local if b.parent else b.matrix_local
            bones.append({'name':b.name,'parent':b.parent.name if b.parent else None,'head':vec(b.head_local),
                'tail':vec(b.tail_local),'length':b.length,'deform':b.use_deform,'rest_matrix':matrix(b.matrix_local),
                'local_euler_degrees':vec(math.degrees(v) for v in local.to_euler())})
        data['armatures'].append({'name':arm.name,'world_matrix':matrix(arm.matrix_world),'bones':bones,
            'constraints':{p.name:[c.type for c in p.constraints] for p in arm.pose.bones if p.constraints},
            'action':arm.animation_data.action.name if arm.animation_data and arm.animation_data.action else None})
    for mesh in meshes:
        totals={g.name:{'vertices':0,'weight_sum':0.0} for g in mesh.vertex_groups}
        unweighted=0;max_influences=0;sum_error=0.0
        for v in mesh.data.vertices:
            groups=[g for g in v.groups if g.weight>1e-6]
            if not groups:unweighted+=1
            max_influences=max(max_influences,len(groups));sum_error=max(sum_error,abs(sum(g.weight for g in groups)-1))
            for g in groups:
                entry=totals[mesh.vertex_groups[g.group].name];entry['vertices']+=1;entry['weight_sum']+=g.weight
        data['meshes'].append({'name':mesh.name,'vertices':len(mesh.data.vertices),'polygons':len(mesh.data.polygons),
            'dimensions':vec(mesh.dimensions),'groups':totals,'unweighted_vertices':unweighted,
            'maximum_influences':max_influences,'max_weight_sum_error':sum_error,
            'shape_keys':list(mesh.data.shape_keys.key_blocks.keys()) if mesh.data.shape_keys else [],
            'armature_modifiers':[(m.name,m.object.name if m.object else None) for m in mesh.modifiers if m.type=='ARMATURE']})
    for action in bpy.data.actions:
        fcs=curves(action)
        data['actions'].append({'name':action.name,'range':vec(action.frame_range),'curves':len(fcs),
            'animated_paths':sorted(set(f.data_path for f in fcs))})
    if arms and bpy.data.actions:
        arm=arms[0];action=arm.animation_data.action if arm.animation_data else None
        if action:
            first,last=map(float,action.frame_range);data['samples']=[]
            for i in range(25):
                frame=first+(last-first)*i/24;bpy.context.scene.frame_set(int(frame),subframe=frame-int(frame))
                data['samples'].append({'frame':frame,'bones':{b.name:{'head_world':vec(arm.matrix_world@b.head),
                    'pose_matrix':matrix(b.matrix),'basis_quat':vec(b.matrix_basis.to_quaternion())} for b in arm.pose.bones}})
    report[label]=data
    (OUT/(label+'_rig.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
summary={k:{'armatures':len(v['armatures']),'bone_counts':[len(a['bones']) for a in v['armatures']],
    'roots':[[b['name'] for b in a['bones'] if b['parent'] is None] for a in v['armatures']],
    'meshes':[(m['name'],m['vertices'],len(m['groups'])) for m in v['meshes']],
    'actions':[(a['name'],a['range'],a['curves']) for a in v['actions']]} for k,v in report.items()}
(OUT/'Summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print('RIG_AUDIT_SUMMARY '+json.dumps(summary,ensure_ascii=True))
