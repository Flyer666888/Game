import bpy,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
base=OUT/'Rejected_Radial'/'ModelRefinementAuthoring.json'
author=json.loads(base.read_text(encoding='utf-8'))
grid=json.loads((OUT/'ReliefGridCandidate.json').read_text(encoding='utf-8'))
face=next(o for o in bpy.context.scene.objects if o.name.startswith('Front face | exact dragon reference'))
author['refined_evaluated_triangles']=grid['total_triangles']
author['face'].update({'refined_vertices':grid['face_vertices'],'refined_polygons':len(face.data.polygons),'refined_triangles':grid['face_triangles'],'uv_policy':grid['uv_policy'],'max_uv_affine_mapping_error':grid['max_uv_mapping_error'],'max_added_relief_depth_cm':grid['max_added_relief_cm'],'topology':grid['topology'],'height_filter':grid['height_filter']})
author['face'].pop('mean_added_relief_depth_cm',None)
author['changes']=[s.replace('on original dual-UV face; only depth coordinates displaced.','on uniformly sampled face with the identical two analytic UV mappings; no texture re-fit.') for s in author['changes']]
author['changes'].append('Removed 12 detached visible talons left over from the original approximate dragon; preserved them in the hidden archive.')
author['excluded_old_visible_talons']=grid['excluded_old_visible_talons']
author['part_triangle_counts']=[[name,grid['face_triangles'] if name==face.name else count] for name,count in author['part_triangle_counts'] if name not in grid['excluded_old_visible_talons']]
author['refined_visible_parts']=sum(o.type in ('MESH','CURVE') and not o.hide_render for o in bpy.context.scene.objects)
author['accepted_revision']='Uniform grid relief, approved after neutral geometry review'
(OUT/'ModelRefinementAuthoring.json').write_text(json.dumps(author,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Jade_Dragon_Shield_Detailed.blend'))
exec(compile((OUT/'finalize_and_export.py').read_text(encoding='utf-8-sig'),str(OUT/'finalize_and_export.py'),'exec'),{'__name__':'__main__','__file__':str(OUT/'finalize_and_export.py')})
