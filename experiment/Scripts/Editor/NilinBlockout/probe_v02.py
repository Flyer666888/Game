import unreal,json,os
out=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v02'
os.makedirs(out,exist_ok=True)
report={'engine':unreal.SystemLibrary.get_engine_version()}
classes=['DynamicMesh','DynamicMeshActor','StaticMeshDescription','StaticMesh','AssetImportTask','StaticMeshEditorSubsystem','GeometryScript_MeshEdits','GeometryScript_AssetUtils','GeometryScript_NewAssetUtils','GeometryScript_Collision','GeometryScriptSimpleMeshBuffers','GeometryScriptCreateNewStaticMeshAssetOptions','GeometryScriptCopyMeshToAssetOptions','MeshMergingSettings','EditorPerformanceSettings','MaterialExpressionNoise']
for name in classes:
    obj=getattr(unreal,name,None)
    report[name]={'available':obj is not None,'methods':[x for x in dir(obj) if not x.startswith('_')]} if obj else None
for cls,methods in [('GeometryScript_MeshEdits',['append_buffers_to_mesh','append_triangles','append_vertex','append_vertices','append_triangle']),('GeometryScript_AssetUtils',['copy_mesh_to_static_mesh']),('GeometryScript_NewAssetUtils',['create_new_static_mesh_asset_from_mesh']),('GeometryScript_Collision',['set_static_mesh_collision_from_mesh']),('StaticMesh',['build_from_static_mesh_descriptions']),('StaticMeshEditorSubsystem',['merge_static_mesh_actors','add_simple_collisions','set_collision_complexity'])]:
    obj=getattr(unreal,cls,None)
    if obj:
        for method in methods:report[cls+'.'+method]=getattr(getattr(obj,method,None),'__doc__',None)
json.dump(report,open(os.path.join(out,'EditorAPIProbe.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
unreal.log('NILIN_V02_PROBE_OK')
