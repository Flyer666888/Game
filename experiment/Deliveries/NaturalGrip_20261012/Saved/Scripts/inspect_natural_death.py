"""Offline review of full source motion and weighted floor contacts; never saves blend."""
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

PROJECT = Path(__file__).resolve().parents[2]
OUT = PROJECT / 'ArtSource/WuxiaMale/NaturalDeath'
OUT.mkdir(parents=True, exist_ok=True)
PARENTS = {'root':None, 'pelvis':'root', 'spine_01':'pelvis', 'spine_02':'spine_01',
 'spine_03':'spine_02','neck_01':'spine_03','head':'neck_01',
 'clavicle_l':'spine_03','upperarm_l':'clavicle_l','lowerarm_l':'upperarm_l','hand_l':'lowerarm_l',
 'clavicle_r':'spine_03','upperarm_r':'clavicle_r','lowerarm_r':'upperarm_r','hand_r':'lowerarm_r',
 'thigh_l':'pelvis','calf_l':'thigh_l','foot_l':'calf_l','ball_l':'foot_l',
 'thigh_r':'pelvis','calf_r':'thigh_r','foot_r':'calf_r','ball_r':'foot_r'}
def mat(t):
 q=t['q']; return Matrix.LocRotScale(Vector(t['p']),Quaternion((q[3],*q[:3])),Vector(t['s']))
mesh=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
n=len(mesh.data.vertices); coords=np.ones((n,4)); flat=np.empty(n*3)
mesh.data.vertices.foreach_get('co',flat); coords[:,:3]=flat.reshape((-1,3))
groups={}; sums=np.zeros(n)
for v in mesh.data.vertices:
 for g in v.groups:
  if g.weight>0:
   name=mesh.vertex_groups[g.group].name; ids,weights=groups.setdefault(name,([],[]))
   ids.append(v.index);weights.append(g.weight);sums[v.index]+=g.weight
groups={name:(np.asarray(ids),np.asarray(ws)) for name,(ids,ws) in groups.items()}
pelvis_weights=np.zeros(n)
if 'pelvis' in groups:pelvis_weights[groups['pelvis'][0]]=groups['pelvis'][1]
# Low, nearly rigid pelvis-weighted garment vertices are long robe hem, not
# physical support points. Their binding cannot represent kneeling cloth.
body_ids=np.flatnonzero(~((coords[:,2]<65.) & (pelvis_weights>.90)))
reflect=Matrix.Diagonal((1.,-1.,1.,1.))
datasets=[]
old=json.loads((PROJECT/'ArtSource/WuxiaMale/CombatReactions/CandidatePoses.json').read_text(encoding='utf-8'))
old['clips']=[c for c in old['clips'] if 'dEAh' in c['name']]
datasets.append(old)
extra=OUT/'NaturalCandidatePoses.json'
if extra.exists(): datasets.append(json.loads(extra.read_text(encoding='utf-8')))
report={'source_blend':bpy.data.filepath,'mesh':mesh.name,'weighted_bones':len(groups),'clips':[]}
for data in datasets:
 invref={b:mat(data['reference'][b]).inverted() for b in groups}
 for clip in data['clips']:
  rows=[]; max_reconstruction=0.
  for sample in clip['samples']:
   rec={}
   for b,p in PARENTS.items():rec[b]=rec[p]@mat(sample['local'][b]) if p else mat(sample['local'][b])
   max_reconstruction=max(max_reconstruction,max((rec[b].translation-Vector(sample['world'][b]['p'])).length for b in PARENTS))
   z=np.zeros(n)
   for b,(ids,ws) in groups.items():
    deform=reflect@mat(sample['world'][b])@invref[b]@reflect
    z[ids]+=(coords[ids]@np.asarray(tuple(deform[2])))*ws
   z[sums==0]=coords[sums==0,2]
   rows.append({'time':sample['time'],'minimum_cm':float(z.min()),'lowest_vertex':int(z.argmin()),
    'body_minimum_cm':float(z[body_ids].min()),'body_lowest_vertex':int(body_ids[z[body_ids].argmin()]),
    'body_lowest_rest_xyz':list(coords[body_ids[z[body_ids].argmin()],:3]),
    'body_lowest_groups':[(mesh.vertex_groups[g.group].name,g.weight) for g in mesh.data.vertices[int(body_ids[z[body_ids].argmin()])].groups],
    'lowest_group_names':[(mesh.vertex_groups[g.group].name,g.weight) for g in mesh.data.vertices[int(z.argmin())].groups],
    'pelvis_cm':sample['world']['pelvis']['p'],'head_cm':sample['world']['head']['p'],
    'ankle_l_cm':sample['world']['foot_l']['p'],'ankle_r_cm':sample['world']['foot_r']['p']})
  c={'name':clip['name'],'asset':clip['asset'],'duration':clip['duration'],
     'max_reconstructed_world_translation_error_cm':max_reconstruction,
     'raw_skin_minimum_range_cm':[min(r['minimum_cm'] for r in rows),max(r['minimum_cm'] for r in rows)],
     'rows':rows}
  report['clips'].append(c)
  print('NATURAL_CANDIDATE',json.dumps({k:v for k,v in c.items() if k!='rows'}),flush=True)
(OUT/'NaturalCandidateContactReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if '--preview' in sys.argv:
 data=datasets[-1]
 renderer=(PROJECT/'Saved/Scripts/render_reaction_candidates.py').read_text(encoding='utf-8')
 renderer=renderer.replace("OUTPUT = CACHE_ROOT / 'EnemyReactionRevision'",'OUTPUT = Path('+repr(str(OUT))+')')
 renderer=renderer.replace('floor.location.z = min(0.0, min(pose_box[0].z for pose_box in pose_bounds)) - 0.015','floor.location.z = -0.015')
 source=extra if extra.exists() else PROJECT/'ArtSource/WuxiaMale/CombatReactions/CandidatePoses.json'
 sys.argv=['render_reaction_candidates.py','--',str(source)]
 exec(compile(renderer,'natural_candidate_renderer','exec'),{'__name__':'__main__'})
