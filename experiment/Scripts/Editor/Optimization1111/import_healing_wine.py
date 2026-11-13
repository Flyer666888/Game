"""Import the original wine-flask source into a new, isolated UE asset package."""
import unreal, json, traceback, hashlib
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
SRC=ROOT/'ArtSource/Pickups/HealingWine1111'
OUT=ROOT/'Docs/Gameplay/Optimization1111'
DEST='/Game/ReversedScale/Pickups/HealingWine1111'
NAME='SM_HealingWineV01'
EL=unreal.EditorAssetLibrary
AT=unreal.AssetToolsHelpers.get_asset_tools()
ML=unreal.MaterialEditingLibrary
report={'state':'starting','destination':DEST}
try:
    source=json.loads((SRC/'AssetReport.json').read_text(encoding='utf-8'))
    assert source['state']=='passed'
    fbx=SRC/(NAME+'.fbx')
    assert hashlib.sha256(fbx.read_bytes()).hexdigest()==source['fbx_sha256']
    mats={}
    for slot,params in source['materials'].items():
        material_name='M_HealingWine_'+slot
        mat=unreal.load_asset(DEST+'/'+material_name)
        if not mat:mat=AT.create_asset(material_name,DEST,unreal.Material,unreal.MaterialFactoryNew())
        assert mat
        ML.delete_all_material_expressions(mat)
        rgb=ML.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-350,0)
        rgb.set_editor_property('constant',unreal.LinearColor(*params['color'],1))
        ML.connect_material_property(rgb,'',unreal.MaterialProperty.MP_BASE_COLOR)
        for prop,val,y in [('MP_ROUGHNESS',params['roughness'],160),('MP_METALLIC',params['metallic'],260)]:
            scalar=ML.create_material_expression(mat,unreal.MaterialExpressionConstant,-350,y)
            scalar.set_editor_property('r',val)
            ML.connect_material_property(scalar,'',getattr(unreal.MaterialProperty,prop))
        ML.recompile_material(mat)
        assert EL.save_loaded_asset(mat,False)
        mats[slot]=mat
    unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
    task=unreal.AssetImportTask()
    task.filename=str(fbx);task.destination_path=DEST;task.destination_name=NAME
    task.automated=True;task.replace_existing=False;task.save=False
    opts=unreal.FbxImportUI();opts.automated_import_should_detect_type=False
    opts.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
    opts.import_as_skeletal=False;opts.import_mesh=True
    opts.import_materials=opts.import_textures=opts.import_animations=False
    data=opts.static_mesh_import_data
    data.combine_meshes=True;data.convert_scene=True;data.convert_scene_unit=True
    data.auto_generate_collision=False;data.generate_lightmap_u_vs=False;data.build_nanite=False
    data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    task.options=opts
    if not EL.does_asset_exist(DEST+'/'+NAME):AT.import_asset_tasks([task])
    mesh=unreal.load_asset(DEST+'/'+NAME)
    assert isinstance(mesh,unreal.StaticMesh),str(task.imported_object_paths)
    slots=mesh.get_editor_property('static_materials')
    bindings=[]
    for i,slot in enumerate(slots):
        key=str(slot.get_editor_property('imported_material_slot_name'))
        if key not in mats:key=str(slot.get_editor_property('material_slot_name'))
        assert key in mats,key
        mesh.set_material(i,mats[key]);bindings.append(key)
    assert len(bindings)==4,bindings
    bounds=mesh.get_bounds()
    height=bounds.box_extent.z*2
    assert 28<height<30,height
    assert 500<mesh.get_num_triangles(0)<10000
    assert mesh.get_num_tex_coords(0)>=2
    mesh.set_editor_property('bHasNavigationData',False)
    # The commandlet does not instantiate editor subsystems. Collision generation
    # was disabled on import; the runtime visual also uses NoCollision.
    assert EL.save_loaded_asset(mesh,False)
    report.update(state='passed',mesh=mesh.get_path_name(),height_cm=height,
        triangles=mesh.get_num_triangles(0),material_slots=bindings,uv_channels=mesh.get_num_tex_coords(0),
        source_sha256=source['fbx_sha256'],license=source['license'],collision='Pickup overlap sphere; mesh has no blocking body')
except Exception:
    report.update(state='failed',error=traceback.format_exc());unreal.log_error(report['error'])
finally:
    (OUT/'WineImport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if report['state']!='passed':raise RuntimeError('Healing wine import failed; inspect WineImport.json')
