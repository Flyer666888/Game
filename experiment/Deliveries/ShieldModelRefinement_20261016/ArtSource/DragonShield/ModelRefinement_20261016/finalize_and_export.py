import bpy,json,hashlib
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
scene=bpy.context.scene
bpy.context.preferences.filepaths.save_version=0
author=json.loads((OUT/'ModelRefinementAuthoring.json').read_text(encoding='utf-8'))
archive=bpy.data.collections.get('ARCHIVE | original hidden dragon and replaced parts') or bpy.data.collections.new('ARCHIVE | original hidden dragon and replaced parts')
if archive.name not in scene.collection.children:scene.collection.children.link(archive)
archive.hide_render=True
archive['purpose']='Supplied old dragon approximation and superseded construction parts; individual hide_render is true; never export.'
for o in list(scene.objects):
    if o.type in ('MESH','CURVE') and o.hide_render:
        for c in list(o.users_collection):c.objects.unlink(o)
        archive.objects.link(o)
# All required source reference textures remain packed in the derivative file.
for img in bpy.data.images:
    if img.source=='FILE' and not img.packed_file:
        try:img.pack()
        except Exception:pass

def bbox(objects):
    deps=bpy.context.evaluated_depsgraph_get();points=[]
    for o in objects:
        e=o.evaluated_get(deps);m=e.to_mesh();points.extend(e.matrix_world@v.co for v in m.vertices);e.to_mesh_clear()
    lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
    return {'min':lo,'max':hi,'center':[(lo[i]+hi[i])*.5 for i in range(3)],'dimensions':[hi[i]-lo[i] for i in range(3)]}
grip_parts=[o for o in scene.objects if o.type in ('MESH','CURVE') and not o.hide_render and (o.name.startswith('Detailed grip | rounded leather barrel') or o.name.startswith('Detailed grip | continuous leather') or o.name.startswith('Detailed grip | spiral seam') or o.name.startswith('Detailed grip stitch'))]
grip_bounds=bbox(grip_parts)
core_bounds=bbox([bpy.data.objects['Detailed grip | rounded leather barrel']])
author['grip_geometry_source_bounds']=grip_bounds;author['grip_barrel_source_bounds']=core_bounds;author['grip_fixed_center_source']=[0,.092,-.01];author['grip_geometry_dimensions_cm']=[d*46/.82 for d in grip_bounds['dimensions']];author['packed_images']=[{'name':i.name,'packed':bool(i.packed_file),'size':list(i.size)} for i in bpy.data.images if i.source=='FILE'];author['archive_collection']=archive.name
(OUT/'ModelRefinementAuthoring.json').write_text(json.dumps(author,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Jade_Dragon_Shield_Detailed.blend'))
# Invoke the existing canonical export workflow, copied into this derivative directory.
exec(compile((OUT/'prepare_dragon_shield_refined.py').read_text(encoding='utf-8-sig'),str(OUT/'prepare_dragon_shield_refined.py'),'exec'),{'__name__':'__main__','__file__':str(OUT/'prepare_dragon_shield_refined.py')})
report=json.loads((OUT/'DragonShieldRefined.json').read_text(encoding='utf-8'))
report['original_source']=author['source'];report['original_source_sha256']=author['source_sha256'];report['original_source_unchanged']=hashlib.sha256(Path(author['source']).read_bytes()).hexdigest()==author['source_sha256'];report['authoring_blend']=str(OUT/'Jade_Dragon_Shield_Detailed.blend');report['geometry_changes']=author['changes'];report['baseline_evaluated_triangles']=author['baseline_evaluated_triangles'];report['refined_evaluated_triangles']=author['refined_evaluated_triangles'];report['dragon_face_geometry']=author['face'];report['grip_geometry_source_bounds']=grip_bounds;report['grip_fixed_center_source']=[0,.092,-.01];report['grip_geometry_dimensions_cm']=author['grip_geometry_dimensions_cm'];report['packed_images']=author['packed_images'];report['archive_collection']=archive.name;report['fbx_sha256']=hashlib.sha256((OUT/'DragonShieldRefined.fbx').read_bytes()).hexdigest();report['limitations']=['Front face keeps the original photographic color texture and its baked lighting; geometry now adds restrained raised dragon volumes and shallow cloud/bronze detail.','Preview uses source materials; UE integration should preserve the existing PBR materials.','No gameplay, VR handling, performance or automated tests run in this authoring task.']
(OUT/'DragonShieldRefined.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('FINAL_REFINED_EXPORT',json.dumps({'triangles':report['triangles'],'bounds_cm':report['bounds_cm'],'grip_center_cm':report['grip_center_cm'],'grip_geometry_dimensions_cm':report['grip_geometry_dimensions_cm'],'materials':[m['ue_name'] for m in report['materials']],'fbx_sha256':report['fbx_sha256']}),flush=True)
