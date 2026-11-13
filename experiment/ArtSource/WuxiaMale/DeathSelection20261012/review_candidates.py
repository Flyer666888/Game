"""Read-only animation source comparison on the final Combat skin.

Writes preview poses, contact measurements and nine-frame contact sheets only.
Source .blend, weights, materials and all original animation JSON remain intact.
"""
import copy
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

PROJECT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WUXIA = PROJECT / 'ArtSource/WuxiaMale'
old = json.loads((WUXIA/'CombatReactions/CandidatePoses.json').read_text(encoding='utf-8'))
extra = json.loads((WUXIA/'NaturalDeath/NaturalCandidatePoses.json').read_text(encoding='utf-8'))
natural = json.loads((WUXIA/'NaturalDeath/NaturalDeathAuthoredPoses.json').read_text(encoding='utf-8'))
source = max((o for o in bpy.context.scene.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
n = len(source.data.vertices)
coords = np.ones((n,4))
flat = np.empty(n*3)
source.data.vertices.foreach_get('co', flat)
coords[:,:3] = flat.reshape((-1,3))
groups = {}
for vertex in source.data.vertices:
    for weight in vertex.groups:
        if weight.weight > 0:
            name = source.vertex_groups[weight.group].name
            ids, values = groups.setdefault(name, ([],[]))
            ids.append(vertex.index)
            values.append(weight.weight)
groups = {b: (np.asarray(ids,dtype=np.int64), np.asarray(values)) for b,(ids,values) in groups.items()}
arms = {b: ids[values > .5] for b,(ids,values) in groups.items() if b.startswith(('lowerarm_', 'hand_'))}

def mat(tr):
    q = tr['q']
    return Matrix.LocRotScale(Vector(tr['p']),Quaternion((q[3],*q[:3])),Vector(tr['s']))

reflect = Matrix.Diagonal((1.,-1.,1.,1.))
inv = {b: mat(old['reference'][b]).inverted() for b in groups}

def skin_z(sample, morph_deltas=None):
    adjusted = coords.copy()
    for name, weight in sample.get('morph_weights', {}).items():
        for change in (morph_deltas or {}).get(name, []):
            adjusted[change['index'],:3] += np.asarray(change['delta'])*weight
    z = np.zeros(n)
    for bone,(ids,values) in groups.items():
        deform = reflect @ mat(sample['world'][bone]) @ inv[bone] @ reflect
        z[ids] += (adjusted[ids] @ np.asarray(tuple(deform[2]))) * values
    return z

clips = [c for c in old['clips'] if 'dEAh_F_' in c['name']] + extra['clips']
preview_clips = []
report = {'source_blend':bpy.data.filepath,'mesh':source.name,'vertices':n,
          'scope':'Actual final Combat skin; source candidates unchanged. Preview only compensates penetration, retaining airborne phases.',
          'clips':[]}
for clip in clips:
    pose = copy.deepcopy(clip)
    rows=[]
    for sample in pose['samples']:
        z = skin_z(sample)
        offset = max(0.,.15-float(z.min()))
        for transform in sample['world'].values():
            transform['p'][2] += offset
        sample['local']['root']['p'][2] += offset
        grounded = z+offset
        rows.append({'time':sample['time'],'penetration_compensation_cm':offset,
                     'skin_min_cm':float(grounded.min()),'head_z_cm':sample['world']['head']['p'][2],
                     'pelvis_z_cm':sample['world']['pelvis']['p'][2],
                     'forearm_hand_min_cm':{b:float(grounded[ids].min()) for b,ids in arms.items()}})
    root = np.asarray([s['world']['root']['p'] for s in clip['samples']])
    report['clips'].append({'name':clip['name'],'duration':clip['duration'],
       'source_root_xy_displacement_cm':float(np.linalg.norm(root[-1,:2]-root[0,:2])),
       'max_penetration_compensation_cm':max(r['penetration_compensation_cm'] for r in rows),
       'final_contact':rows[-1], 'rows':rows})
    pose['samples'] = [pose['samples'][round(i*(len(pose['samples'])-1)/8)] for i in range(9)]
    preview_clips.append(pose)
    print('DEATH_CANDIDATE_CONTACT',clip['name'],rows[-1],flush=True)

current = copy.deepcopy(natural['clips'][0])
current['name'] = 'Current_Natural_DeathPL'
rows=[]
for sample in current['samples']:
    z = skin_z(sample,natural.get('morph_deltas',{}))
    rows.append({'time':sample['time'],'skin_min_cm':float(z.min()),
                 'head_z_cm':sample['world']['head']['p'][2],
                 'pelvis_z_cm':sample['world']['pelvis']['p'][2],
                 'forearm_hand_min_cm':{b:float(z[ids].min()) for b,ids in arms.items()}})
report['clips'].append({'name':current['name'],'duration':current['duration'],
                       'final_contact':rows[-1],'rows':rows})
current['samples'] = [current['samples'][round(i*(len(current['samples'])-1)/8)] for i in range(9)]
preview_clips.append(current)
data={'mesh':old['mesh'],'reference':old['reference'],'clips':preview_clips,
      'morph_deltas':natural.get('morph_deltas',{})}
(OUT/'CandidateFinalSkinPoses.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
(OUT/'CandidateFinalSkinContact.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

renderer=(PROJECT/'Saved/Scripts/render_reaction_candidates.py').read_text(encoding='utf-8')
renderer=renderer.replace("OUTPUT = CACHE_ROOT / 'EnemyReactionRevision'",'OUTPUT = Path('+repr(str(OUT))+')')
renderer=renderer.replace('WIDTH, HEIGHT = 1800, 500','WIDTH, HEIGHT = 3200, 600')
renderer=renderer.replace('indices = [round(index * (len(samples) - 1) / 4) for index in range(5)]','indices = list(range(len(samples)))')
renderer=renderer.replace('floor.location.z = min(0.0, min(pose_box[0].z for pose_box in pose_bounds)) - 0.015','floor.location.z = -0.015')
renderer=renderer.replace('        for coord, vertex_weights in zip(coords, weights):',
    "        current_coords = [v.copy() for v in coords]\n"
    "        for morph_name, morph_weight in sample.get('morph_weights', {}).items():\n"
    "            for change in data.get('morph_deltas', {}).get(morph_name, []):\n"
    "                current_coords[change['index']] += Vector(change['delta']) * morph_weight\n"
    "        for coord, vertex_weights in zip(current_coords, weights):")
renderer=renderer.replace("        mesh_data.vertices.foreach_set('co', [value for point in posed for value in point])",'        # Pose vertices are written after removing copied shape keys.')
renderer=renderer.replace("        obj = bpy.data.objects.new(PREFIX + 'Pose' + str(index), mesh_data)",
    "        obj = bpy.data.objects.new(PREFIX + 'Pose' + str(index), mesh_data)\n"
    "        if obj.data.shape_keys: obj.shape_key_clear()\n"
    "        mesh_data.vertices.foreach_set('co', [value for point in posed for value in point])\n"
    "        mesh_data.update()")
saved_argv=sys.argv[:]
try:
    sys.argv=['render_reaction_candidates.py','--',str(OUT/'CandidateFinalSkinPoses.json')]
    exec(compile(renderer,'render_reaction_candidates.py','exec'),{'__name__':'__main__'})
finally:
    sys.argv=saved_argv
print('DEATH_CANDIDATE_FINAL_SKIN_REVIEW_COMPLETE',str(OUT),flush=True)
