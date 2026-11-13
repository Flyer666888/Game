"""Persist deterministic meshes with Nanite disabled and real query collision."""
import unreal

def make_asset(path,vertices,triangles,collision=True):
    existing=unreal.EditorAssetLibrary.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if existing:return existing
    mesh=unreal.DynamicMesh()
    buffers=unreal.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_property('vertices',[unreal.Vector(x*100,y*100,z*100) for x,y,z in vertices])
    buffers.set_editor_property('uv0',[unreal.Vector2D(x*.1,y*.1) for x,y,z in vertices])
    buffers.set_editor_property('triangles',[unreal.IntVector(*t) for t in triangles])
    unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(mesh,buffers)
    if mesh.get_triangle_count()!=len(triangles):raise RuntimeError('Nonmanifold/rejected mesh triangles: '+path)
    options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    options.set_editor_property('enable_nanite',False)
    options.set_editor_property('enable_collision',collision)
    options.set_editor_property('collision_mode',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    options.set_editor_property('enable_recompute_normals',True)
    options.set_editor_property('enable_recompute_tangents',False)
    result=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh,path,options)
    asset=result[0] if isinstance(result,tuple) else result
    if not asset:raise RuntimeError('Static mesh asset creation failed: '+path)
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset,False):raise RuntimeError('Static mesh save failed: '+path)
    return asset
