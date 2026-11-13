"""Verify UE compressed poses against the actual final shoulder skin and sword.

Run with Blender -b WuxiaMaleShoulder_v02.blend --python this_script.
Reads the UE export. Writes evidence only; no blend or UE asset edits.
"""
import hashlib,json
from pathlib import Path
import bpy
import numpy as np
PROJECT=Path(r'D:\game design\experiment')
OUT=PROJECT/'ArtSource/WuxiaMale/RigPolishV02/Death'
SETUP=PROJECT/'Saved/Scripts/bake_selected_death.py'
context={'__name__':'runtime_skin_setup','__file__':str(SETUP)}
exec(compile(SETUP.read_text(encoding='utf-8').split('raw=[];locals=[];support=[]')[0],str(SETUP),'exec'),context)
authored=json.loads((OUT/'RestrainedDeathContacts.json').read_text(encoding='utf-8'))
runtime=json.loads((OUT/'RestrainedDeathRuntimePoses.json').read_text(encoding='utf-8'))
hash_value=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
if hash_value!=authored['source_blend_sha256']:raise RuntimeError('Runtime verification must use the exact skin used for authoring')
rows=[]
for sample in runtime['clips'][0]['samples']:
    points,w=context['skin'](sample['local'],sample.get('morph_weights',{}));prop=context['prop_world'](sample['local'])
    rows.append({'time':sample['time'],'skin_min_cm':float(points[:,2].min()),'sword_min_cm':float(prop[:,2].min()),
                 'palm_l_min_cm':float(points[context['hand_ids']['l'],2].min()),'palm_r_min_cm':float(points[context['hand_ids']['r'],2].min()),
                 'boot_l_min_cm':float(points[context['boot_ids']['l'],2].min()),'boot_r_min_cm':float(points[context['boot_ids']['r'],2].min())})
minimum_skin=min(r['skin_min_cm'] for r in rows);minimum_sword=min(r['sword_min_cm'] for r in rows)
report={'state':'passed' if min(minimum_skin,minimum_sword)>=-.25 else 'failed','source_blend':bpy.data.filepath,
        'source_blend_sha256':hash_value,'runtime_mesh':runtime['mesh'],'evaluated_frames':len(rows),
        'vertex_count':len(context['mesh'].data.vertices),'minimum_skin_height_cm':minimum_skin,'minimum_sword_height_cm':minimum_sword,
        'compression_tolerance_cm':.25,'frames':rows,'scope':'Read-only actual skin and held-sword verification from UE compressed local poses.'}
(OUT/'RestrainedDeathRuntimeContacts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('RESTRAINED_DEATH_RUNTIME_CONTACTS',json.dumps({k:v for k,v in report.items() if k!='frames'}),flush=True)
if report['state']!='passed':raise RuntimeError('Runtime contact penetration exceeds animation compression tolerance')
