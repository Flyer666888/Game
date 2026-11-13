"""Author full genuine death motion plus a derived robe-only weight repair.

Uses an unsaved copy of the current Feet blend. Original geometry, UVs, face,
boots, hands and the 23-bone hierarchy are preserved. Outputs a patch to merge
into the separate derived combat mesh, and full local/world animation tracks.
"""
import copy
import json
import math
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

PROJECT=Path(__file__).resolve().parents[2]
OUT=PROJECT/'ArtSource/WuxiaMale/NaturalDeath'; OUT.mkdir(parents=True,exist_ok=True)
data=json.loads((OUT/'NaturalCandidatePoses.json').read_text(encoding='utf-8'))
sword=json.loads((PROJECT/'ArtSource/WuxiaMale/SwordCombat/SwordCandidatePoses.json').read_text(encoding='utf-8'))
source=next(c for c in data['clips'] if c['name']=='NaturalCandidate_Anim_DeathPL')
idle=sword['idle_local']
FPS=30; SOURCE_DURATION=float(source['duration']); HOLD=.60; DURATION=SOURCE_DURATION+HOLD
CLEARANCE=.15; ROOT_XY_SCALE=.27
PARENTS={'root':None,'pelvis':'root','spine_01':'pelvis','spine_02':'spine_01',
 'spine_03':'spine_02','neck_01':'spine_03','head':'neck_01',
 'clavicle_l':'spine_03','upperarm_l':'clavicle_l','lowerarm_l':'upperarm_l','hand_l':'lowerarm_l',
 'clavicle_r':'spine_03','upperarm_r':'clavicle_r','lowerarm_r':'upperarm_r','hand_r':'lowerarm_r',
 'thigh_l':'pelvis','calf_l':'thigh_l','foot_l':'calf_l','ball_l':'foot_l',
 'thigh_r':'pelvis','calf_r':'thigh_r','foot_r':'calf_r','ball_r':'foot_r'}
def smooth(x):
 x=max(0.,min(1.,x));return x*x*(3.-2.*x)
def mat(t):
 q=t['q'];return Matrix.LocRotScale(Vector(t['p']),Quaternion((q[3],*q[:3])),Vector(t['s']))
def record(m):
 p,q,s=m.decompose();return {'p':list(p),'q':[q.x,q.y,q.z,q.w],'s':list(s)}
def blend(a,b,w):
 q=Quaternion((a['q'][3],*a['q'][:3])).slerp(Quaternion((b['q'][3],*b['q'][:3])),w)
 return {'p':list(Vector(a['p']).lerp(Vector(b['p']),w)),
         'q':[q.x,q.y,q.z,q.w],'s':list(Vector(a['s']).lerp(Vector(b['s']),w))}
def world(local):
 out={}
 for b,p in PARENTS.items():out[b]=out[p]@mat(local[b]) if p else mat(local[b])
 return out
mesh=max((o for o in bpy.context.scene.objects if o.type=='MESH' and not o.name.startswith('ReactionCandidateReview_')),key=lambda o:len(o.data.vertices))
n=len(mesh.data.vertices); coords=np.ones((n,4));flat=np.empty(n*3)
mesh.data.vertices.foreach_get('co',flat);coords[:,:3]=flat.reshape((-1,3))
original_weights=[{mesh.vertex_groups[g.group].name:float(g.weight) for g in v.groups if g.weight>0.} for v in mesh.data.vertices]
repair=json.loads((PROJECT/'ArtSource/WuxiaMale/FootCorrection/FeetWeightRepair.json').read_text(encoding='utf-8'))
sole_ids={int(v['index']) for v in repair['sole_vertices']}
sole_side={side:np.asarray([int(v['index']) for v in repair['sole_vertices'] if v['side']==side]) for side in ('l','r')}
patch=[]
for v in mesh.data.vertices:
 x,y,z=coords[v.index,:3]; w=original_weights[v.index]; pelvis=w.get('pelvis',0.)
 if (pelvis<=.50 or z<=18.0 or z>=82.0 or v.index in sole_ids
     or any(w.get(b,0.)>.05 for b in ('foot_l','foot_r','ball_l','ball_r'))):continue
 # Waist remains on pelvis. The garment gradually follows thigh, then calf,
 # using existing bones, allowing a knee fold instead of a rigid vertical tube.
 retain=smooth((z-65.)/17.)
 calf=smooth((58.-z)/23.)
 side=smooth((x+8.)/16.)
 transfer=pelvis*(1.-retain)
 new=dict(w);new['pelvis']=pelvis-transfer
 for b,value in {'thigh_l':transfer*side*(1.-calf),'calf_l':transfer*side*calf,
                 'thigh_r':transfer*(1.-side)*(1.-calf),'calf_r':transfer*(1.-side)*calf}.items():
  new[b]=new.get(b,0.)+value
 total=sum(new.values());new={b:value/total for b,value in new.items() if value>1e-7}
 patch.append({'index':v.index,'weights':new})
 for g in list(v.groups):mesh.vertex_groups[g.group].remove([v.index])
 for b,value in new.items():
  group=mesh.vertex_groups.get(b) or mesh.vertex_groups.new(name=b)
  group.add([v.index],value,'REPLACE')
patch_report={'schema':'vertex-index full replacement weights', 'base_blend':bpy.data.filepath,
 'base_vertices':n,'geometry_changed':False,'uv_changed':False,'material_slots_changed':False,
 'bones_added':False,'protected_sole_vertex_count':len(sole_ids),'vertices':patch,
 'authoring':{'eligible':'pelvis > 0.5, rest Z 18..82 cm, excludes feet/ball and all recorded sole verts',
 'waist_pelvis_transition_z_cm':[65.,82.],'calf_transition_z_cm':[35.,58.],
 'left_right_seam_width_cm':16.}}
(OUT/'RobeWeightPatch.json').write_text(json.dumps(patch_report,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

weights=[{mesh.vertex_groups[g.group].name:float(g.weight) for g in v.groups if g.weight>0.} for v in mesh.data.vertices]
groups={};sums=np.zeros(n)
for i,w in enumerate(weights):
 for b,value in w.items():
  ids,ws=groups.setdefault(b,([],[]));ids.append(i);ws.append(value);sums[i]+=value
groups={b:(np.asarray(ids),np.asarray(ws)) for b,(ids,ws) in groups.items()}
reflect=Matrix.Diagonal((1.,-1.,1.,1.));inverse_ref={b:mat(data['reference'][b]).inverted() for b in groups}
def skin_z(w):
 z=np.zeros(n)
 for b,(ids,values) in groups.items():
  deform=reflect@w[b]@inverse_ref[b]@reflect;z[ids]+=(coords[ids]@np.asarray(tuple(deform[2])))*values
 z[sums==0]=coords[sums==0,2];return z
def calf_contact(local,time):
 # A prone bare-mannequin ankle can be lower than this character's thick boot.
 # Slightly flex the existing calf (max 18 degrees) instead of lifting the head
 # and trunk to accommodate that boot. Counter-rotate foot so its source world
 # orientation is preserved. This never changes weights or limb lengths.
 result=copy.deepcopy(local); phase=smooth((time-1.50)/.35)
 for side in ('l','r'):
  w=world(result); z=skin_z(w); need=max(0.,CLEARANCE-float(z[sole_side[side]].min()))*phase
  if need<.001:continue
  calf='calf_'+side;foot='foot_'+side
  old=w[foot].translation-w[calf].translation;target=old.copy();target.z+=need
  if old.length<1e-5 or target.length<1e-5:continue
  rotate=old.normalized().rotation_difference(target.normalized())
  if rotate.angle>math.radians(18.):rotate=Quaternion().slerp(rotate,math.radians(18.)/rotate.angle)
  p,q,s=w[calf].decompose();new=Matrix.LocRotScale(p,rotate@q,s)
  result[calf]=record(w[PARENTS[calf]].inverted()@new)
  updated=world(result)
  # Preserve the child's source translation and its complete world orientation.
  p2,q2,s2=w[foot].decompose();desired=Matrix.LocRotScale(updated[foot].translation,q2,s2)
  result[foot]=record(new.inverted()@desired)
 return result
def source_pose(t):
 phase=min(len(source['samples'])-1,t/SOURCE_DURATION*source['frames'])
 lo=int(phase);hi=min(lo+1,len(source['samples'])-1);f=phase-lo
 return {b:blend(source['samples'][lo]['local'][b],source['samples'][hi]['local'][b],f) for b in PARENTS}
samples=[];bounds=[];raw_offsets=[]
garment_ids=np.asarray([p['index'] for p in patch],dtype=np.int64)
body_ids=np.asarray(sorted(set(range(n)).difference(garment_ids)),dtype=np.int64)
root_first=source['samples'][0]['local']['root']['p']
for i in range(round(DURATION*FPS)+1):
 t=i/FPS;local=source_pose(min(t,SOURCE_DURATION))
 for axis in (0,1):local['root']['p'][axis]=idle['root']['p'][axis]+(local['root']['p'][axis]-root_first[axis])*ROOT_XY_SCALE
 # Small entry transition only. Every complete source phase remains present.
 entry=smooth(t/.20)
 for b in PARENTS:local[b]=blend(idle[b],local[b],entry)
 # Keep every genuine source leg and foot pose. A candidate calf-contact
 # correction was rejected after the actual skin preview showed floating boots.
 w=world(local);z=skin_z(w);offset=CLEARANCE-float(z[body_ids].min())
 # Contact repair only; preserve genuine source pelvis/knee/torso rotation.
 raw_offsets.append(offset);samples.append({'time':t,'local':local})
filtered=np.convolve(np.pad(raw_offsets,(2,2),mode='edge'),np.asarray([1,2,3,2,1])/9.,mode='valid')
offsets=np.maximum(filtered,np.asarray(raw_offsets))
offsets[round(SOURCE_DURATION*FPS):]=offsets[round(SOURCE_DURATION*FPS)]
for sample,offset in zip(samples,offsets):
 sample['local']['root']['p'][2]+=float(offset)
 w=world(sample['local']);z=skin_z(w)
 bounds.append({'time':sample['time'],'root_floor_offset_cm':float(offset),'minimum_cm':float(z.min()),
  'pelvis_z_cm':float(w['pelvis'].translation.z),'head_z_cm':float(w['head'].translation.z),
  'sole_min_cm':float(z[list(sole_ids)].min()),'lowest_vertex':int(z.argmin()),
  'lowest_rest_xyz':list(coords[int(z.argmin()),:3]),'lowest_weights':weights[int(z.argmin())]})
 sample['world']={b:record(m) for b,m in w.items()}

# A few phase-specific cloth corrections absorb garment contact without moving
# the body's true support points. The shared combat mesh receives these keys;
# their basis stays exactly equal to the original mesh and curves are death-only.
morph_times=[.27,.67,1.10,1.43,1.70,1.80,2.13,2.70]
morph_names=['EnemyDeathRobe_'+str(i+1) for i in range(len(morph_times))]
morph_deltas={};morphs=[]
for name,t in zip(morph_names,morph_times):
 sample=samples[round(t*FPS)];w={b:mat(value) for b,value in sample['world'].items()}
 transforms={b:np.asarray(reflect@w[b]@inverse_ref[b]@reflect) for b in groups}
 z=skin_z(w);changes=[];deltas={}
 for i in garment_ids:
  need=max(0.,CLEARANCE+.50-float(z[i]))
  if need<.02:continue
  deform=sum(transforms[b][:3,:3]*value for b,value in weights[int(i)].items())
  delta=np.linalg.pinv(deform)@np.asarray([0.,0.,need])
  deltas[int(i)]=delta
  changes.append({'index':int(i),'co':list(coords[i,:3]+delta)})
 morph_deltas[name]=deltas;morphs.append({'name':name,'time':t,'vertices':changes})

def morph_weights(t):
 if t<=0:return {}
 if t<morph_times[0]:return {morph_names[0]:smooth(t/morph_times[0])}
 for i,(a,b) in enumerate(zip(morph_times,morph_times[1:])):
  if t<=b:
   weight=(t-a)/(b-a);return {morph_names[i]:1.-weight,morph_names[i+1]:weight}
 return {morph_names[-1]:1.}

def corrected_z(w,mw):
 adjusted=coords.copy()
 for name,value in mw.items():
  if value:
   for i,delta in morph_deltas[name].items():adjusted[i,:3]+=delta*value
 z=np.zeros(n)
 for b,(ids,values) in groups.items():
  deform=reflect@w[b]@inverse_ref[b]@reflect
  z[ids]+=(adjusted[ids]@np.asarray(tuple(deform[2])))*values
 return z

for sample,row in zip(samples,bounds):
 mw=morph_weights(sample['time']);sample['morph_weights']=mw
 w={b:mat(value) for b,value in sample['world'].items()}
 z=corrected_z(w,mw);row['corrected_mesh_minimum_cm']=float(z.min())
curves={name:[{'time':s['time'],'value':s['morph_weights'].get(name,0.)} for s in samples] for name in morph_names}
(OUT/'RobeMorphPatch.json').write_text(json.dumps({'base_vertices':n,'basis_changed':False,'morphs':morphs,
 'animation_asset':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Natural',
 'curve_keys':curves},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
clip={'name':'Wuxia_Death_Natural','asset':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Natural',
 'source_asset':source['asset'],'role':'death','duration':DURATION,'frames':round(DURATION*FPS),'samples':samples,
 'timing':{'source_motion_seconds':SOURCE_DURATION,'final_hold_seconds':HOLD,'loop':False},
 'authoring':{'full_source_sequence':True,'source_time_scale':1.,'entry_blend_seconds':.20,'root_xy_scale':ROOT_XY_SCALE,
              'invented_root_fall_rotation':False,'lower_body_idle_lock':False,'grounding':'body/boots plus garment-only corrective morphs',
              'prone_calf_contact_applied':False},'morph_curves':curves}
result={'mesh':'/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Combat',
 'skeleton':sword['skeleton'],'fps':FPS,'reference':data['reference'],'clips':[clip],
 'morph_deltas':{name:[{'index':i,'delta':list(delta)} for i,delta in changes.items()] for name,changes in morph_deltas.items()}}
(OUT/'NaturalDeathAuthoredPoses.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
summary={'source_blend':bpy.data.filepath,'source_clip':source['name'],'source_asset':source['asset'],
 'source_duration_seconds':SOURCE_DURATION,'authored_duration_seconds':DURATION,'final_hold_seconds':HOLD,
 'robe_patched_vertices':len(patch),'base_vertices':n,'foot_sole_weights_unchanged':all(original_weights[i]==weights[i] for i in sole_ids),
 'full_source_motion_retained':True,'root_floor_offset_range_cm':[float(min(offsets)),float(max(offsets))],
 'max_root_floor_offset_frame_step_cm':float(np.abs(np.diff(offsets)).max()),
 'mesh_minimum_z_range_cm':[min(r['minimum_cm'] for r in bounds),max(r['minimum_cm'] for r in bounds)],
 'corrected_mesh_minimum_z_range_cm':[min(r['corrected_mesh_minimum_cm'] for r in bounds),max(r['corrected_mesh_minimum_cm'] for r in bounds)],
 'death_only_corrective_morphs':len(morphs),
 'final_contact':bounds[-1],'grounding':bounds,
 'rejected_candidates':{'KD_F_and_DU_E_GR':'backward launch with airborne feet',
                       'Death_1':'airborne sideways flip, not ordinary sword death',
                       'dEAh_F_01_to_04':'long theatrical kneeling sequence and severe rigid-robe support correction'},
 'scope':'Derived robe weights only; original blend, geometry, UVs, face, boots and fingers remain unchanged.'}
(OUT/'NaturalDeathBakeSummary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print('NATURAL_DEATH_AUTHORED',json.dumps({k:v for k,v in summary.items() if k!='grounding'}),flush=True)
if '--preview' in sys.argv:
 renderer=(PROJECT/'Saved/Scripts/render_reaction_candidates.py').read_text(encoding='utf-8')
 renderer=renderer.replace("OUTPUT = CACHE_ROOT / 'EnemyReactionRevision'",'OUTPUT = Path('+repr(str(OUT))+')')
 renderer=renderer.replace('floor.location.z = min(0.0, min(pose_box[0].z for pose_box in pose_bounds)) - 0.015','floor.location.z = -0.015')
 renderer=renderer.replace('CandidateVisualSummary.json','NaturalDeathVisualSummary.json')
 renderer=renderer.replace("deform = {name: reflection @ pose_matrix(sample['world'][name])", "pose_coords = [coord.copy() for coord in coords]\n        for morph_name, morph_weight in sample.get('morph_weights', {}).items():\n            for change in data.get('morph_deltas', {}).get(morph_name, []):\n                pose_coords[change['index']] += Vector(change['delta']) * morph_weight\n        deform = {name: reflection @ pose_matrix(sample['world'][name])")
 renderer=renderer.replace('zip(coords, weights)','zip(pose_coords, weights)')
 render_data=copy.deepcopy(result)
 # Dense authoring review keeps the entire frame series in the delivered clip.
 render_data['clips']=[]
 times=[0.,.27,.53,.80,1.07,1.33,1.60,1.87,2.13,2.40,2.70,3.30]
 for label,group_times in [('Early',times[:6]),('Late',times[6:])]:
  item={k:v for k,v in clip.items() if k!='samples'};item['name']=clip['name']+'_'+label
  item['samples']=[samples[round(t*FPS)] for t in group_times];render_data['clips'].append(item)
 # Also inspect unchanged idle and established locomotion/sword motion on robe patch.
 review=json.loads((PROJECT/'ArtSource/WuxiaMale/SwordCombat/SwordAuthoredPoses.json').read_text(encoding='utf-8'))
 render_data['clips'].extend(review['clips'])
 idle_world=world(idle)
 render_data['clips'].append({'name':'RobePatch_Idle','duration':0.,'samples':[{'time':0.,'local':idle,
  'world':{b:record(m) for b,m in idle_world.items()}}]*6})
 preview_path=OUT/'NaturalDeathDenseReviewPoses.json'
 preview_path.write_text(json.dumps(render_data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 renderer=renderer.replace('WIDTH, HEIGHT = 1800, 500','WIDTH, HEIGHT = 2400, 600')
 renderer=renderer.replace('indices = [round(index * (len(samples) - 1) / 4) for index in range(5)]',
 'indices = list(range(len(samples))) if len(samples) <= 6 else [round(i * (len(samples)-1)/5) for i in range(6)]')
 renderer=renderer.replace('(index - 2) * cell_width','(index - 2.5) * cell_width')
 sys.argv=['render_reaction_candidates.py','--',str(preview_path)]
 exec(compile(renderer,'natural_death_author_preview','exec'),{'__name__':'__main__'})
