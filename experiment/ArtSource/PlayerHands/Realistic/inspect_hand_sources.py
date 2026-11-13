import bpy, json, math
from pathlib import Path
from mathutils import Vector

OUT=Path(__file__).resolve().parent
SOURCE=OUT.parent/'Source'
report=[]
for name in ('SKM_MannyXR_right','SKM_QuinnXR_right'):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(SOURCE/(name+'.fbx')),use_anim=False,automatic_bone_orientation=False)
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    record={'source':name,'armature':arm.name,'armature_matrix':[list(r) for r in arm.matrix_world],
        'bones':[{'name':b.name,'parent':b.parent.name if b.parent else None,'head':list(b.head_local),'tail':list(b.tail_local), 'matrix':[list(r) for r in b.matrix_local]} for b in arm.data.bones], 'meshes':[]}
    for obj in meshes:
        adj=[set() for _ in obj.data.vertices]
        for e in obj.data.edges:
            a,b=e.vertices
            adj[a].add(b);adj[b].add(a)
        visited=set();parts=[]
        for i in range(len(adj)):
            if i in visited:continue
            stack=[i];part=[];visited.add(i)
            while stack:
                v=stack.pop();part.append(v)
                for n in adj[v]:
                    if n not in visited:visited.add(n);stack.append(n)
            pts=[obj.data.vertices[j].co for j in part]
            parts.append({'vertices':len(part),'bounds':[[min(p[k] for p in pts),max(p[k] for p in pts)] for k in range(3)]})
        record['meshes'].append({'name':obj.name,'vertices':len(obj.data.vertices),'polygons':len(obj.data.polygons),'matrix':[list(r) for r in obj.matrix_world], 'materials':[m.name if m else None for m in obj.data.materials], 'parts':sorted(parts,key=lambda p:-p['vertices'])})
    report.append(record)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(name+'_Reference.blend')))
    pts=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    center=sum(pts,Vector())/len(pts)
    span=max(max(p[k] for p in pts)-min(p[k] for p in pts) for k in range(3))
    scene=bpy.context.scene
    scene.render.engine='BLENDER_WORKBENCH'
    scene.display.shading.light='STUDIO'
    scene.display.shading.color_type='SINGLE'
    scene.display.shading.single_color=(0.65,0.50,0.41)
    scene.display.shading.show_shadows=True
    scene.display.shading.show_cavity=True
    scene.display.shading.cavity_type='BOTH'
    scene.world.color=(0.12,0.12,0.12)
    scene.render.resolution_x=1100;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
    for i,direction in enumerate((Vector((1,-1,1)),Vector((0,-1,0.1)),Vector((0,1,0.1)))):
        camdata=bpy.data.cameras.new('InspectionCamera');cam=bpy.data.objects.new('InspectionCamera',camdata);scene.collection.objects.link(cam)
        cam.location=center+direction.normalized()*span*2
        cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=span*1.25
        scene.camera=cam;scene.render.filepath=str(OUT/(name+'_SourceView'+str(i)+'.png'))
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(cam,do_unlink=True)
(OUT/'SourceInspection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SOURCE_INSPECTED',[(r['source'],[(m['vertices'],len(m['parts'])) for m in r['meshes']]) for r in report])
