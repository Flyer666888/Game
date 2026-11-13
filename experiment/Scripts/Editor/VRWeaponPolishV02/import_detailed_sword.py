"""Import a new detailed A sword package, preserving all original project assets."""
import hashlib, json, traceback
from pathlib import Path
import unreal
P = Path(unreal.Paths.project_dir()).resolve()
OUT = P / 'Docs/Gameplay/VRWeaponPolish_v02'
SRC = P / 'ArtSource/WeaponReview/SelectedA_DetailV02'
DEST = '/Game/ReversedScale/Weapons/SelectedSwordA_DetailV01'
NAME = 'SM_PlayerSword_A_DetailV01'
report = {'state': 'starting', 'source': str(SRC), 'destination': DEST, 'stable_runtime_asset_updated': True, 'backup':str(OUT/'Backups/Content/ReversedScale/Weapons/SelectedSwordA_DetailV01')}
EL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
ML = unreal.MaterialEditingLibrary

def make_metal(name, color, roughness, metallic=1.0):
    path = DEST + '/Materials/V02/' + name
    material = unreal.load_asset(path) if EL.does_asset_exist(path) else AT.create_asset(name, DEST + '/Materials/V02', unreal.Material, unreal.MaterialFactoryNew())
    assert material
    ML.delete_all_material_expressions(material)
    c = ML.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -400, 0)
    c.set_editor_property('constant', unreal.LinearColor(*color, 1))
    assert ML.connect_material_property(c, '', unreal.MaterialProperty.MP_BASE_COLOR)
    for prop, value, ypos in [(unreal.MaterialProperty.MP_METALLIC, metallic, 150), (unreal.MaterialProperty.MP_ROUGHNESS, roughness, 250)]:
        e = ML.create_material_expression(material, unreal.MaterialExpressionConstant, -200, ypos)
        e.set_editor_property('r', value)
        assert ML.connect_material_property(e, '', prop)
    ML.recompile_material(material)
    assert EL.save_loaded_asset(material, False)
    return material

try:
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
    fbx = SRC / 'SM_PlayerSword_A_DetailV02.fbx'
    assert (OUT/'Backups/Content/ReversedScale/Weapons/SelectedSwordA_DetailV01/SM_PlayerSword_A_DetailV01.uasset').is_file()
    assert fbx.is_file(), str(fbx)
    report['source_sha256'] = hashlib.sha256(fbx.read_bytes()).hexdigest()
    contract = json.loads((SRC/'AssetGeometryReport.json').read_text(encoding='utf-8'))['material_contract']
    report['runtime_material_contract'] = contract
    mats = {}
    for key in ('BladeSteel','BladeEdge','BladeFuller','Guard03','Grip04','Pommel03','GoldDetail'):
        spec = contract[key]
        mats[key] = unreal.load_asset(spec['existing_ue_material']) if 'existing_ue_material' in spec else make_metal(
            'M_'+key, spec['base_color_linear'], spec['roughness'], spec['metallic'])
    assert all(mats.values())
    unreal.SystemLibrary.execute_console_command(None, 'Interchange.FeatureFlags.Import.FBX 0')
    task = unreal.AssetImportTask()
    task.filename = str(fbx)
    task.destination_path = DEST
    task.destination_name = NAME
    task.automated = True
    task.replace_existing = True
    task.replace_existing_settings = True
    task.save = False
    opts = unreal.FbxImportUI()
    opts.automated_import_should_detect_type = False
    opts.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    opts.import_as_skeletal = False
    opts.import_mesh = True
    opts.import_animations = opts.import_materials = opts.import_textures = False
    data = opts.static_mesh_import_data
    data.combine_meshes = True
    data.convert_scene = data.convert_scene_unit = True
    data.auto_generate_collision = data.generate_lightmap_u_vs = data.build_nanite = False
    # Preserve authored split normals; compute tangents against UE's final triangles and UVs.
    data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    data.normal_generation_method = unreal.FBXNormalGenerationMethod.MIKK_T_SPACE
    task.options = opts
    AT.import_asset_tasks([task])
    mesh = unreal.load_asset(DEST + '/' + NAME)
    assert isinstance(mesh, unreal.StaticMesh), str(task.imported_object_paths)
    b = mesh.get_bounds()
    report['bounds_cm'] = {'origin': [b.origin.x,b.origin.y,b.origin.z], 'extent': [b.box_extent.x,b.box_extent.y,b.box_extent.z],
                           'tip_z': b.origin.z+b.box_extent.z, 'bottom_z': b.origin.z-b.box_extent.z}
    assert abs(report['bounds_cm']['tip_z'] - 64.9391) < .12, report['bounds_cm']
    assert abs(b.box_extent.z * 2 - 78.3143) < .25, report['bounds_cm']
    assert 4 < b.box_extent.x < 8.2 and .5 < b.box_extent.y < 2.5, report['bounds_cm']
    report['materials'] = []
    for i, slot in enumerate(mesh.get_editor_property('static_materials')):
        slot_name = str(slot.get_editor_property('imported_material_slot_name'))
        if slot_name not in mats:
            slot_name = str(slot.get_editor_property('material_slot_name'))
        assert slot_name in mats, slot_name
        mesh.set_material(i, mats[slot_name])
        report['materials'].append({'slot': slot_name, 'path': mats[slot_name].get_path_name()})
    assert len(report['materials']) == len(mats)
    mesh.set_editor_property('bHasNavigationData', False)
    stored_import = mesh.get_editor_property('asset_import_data')
    stored_import.set_editor_property('normal_import_method', unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    stored_import.set_editor_property('normal_generation_method', unreal.FBXNormalGenerationMethod.MIKK_T_SPACE)
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    subsystem.remove_collisions(mesh)
    build = subsystem.get_lod_build_settings(mesh,0)
    build.set_editor_property('recompute_normals',False)
    build.set_editor_property('recompute_tangents',True)
    build.set_editor_property('use_mikk_t_space',True)
    build.set_editor_property('use_high_precision_tangent_basis',True)
    build.set_editor_property('use_full_precision_u_vs',True)
    subsystem.set_lod_build_settings(mesh,0,build)
    assert EL.save_loaded_asset(mesh, False)
    # Reload the package and check the stored mesh and bindings, not just import task success.
    package = mesh.get_outer()
    reload_result = unreal.EditorLoadingAndSavingUtils.reload_packages([package], unreal.ReloadPackagesInteractionMode.ASSUME_NEGATIVE)
    assert reload_result[0] and not str(reload_result[1]), 'Reload failed: ' + str(reload_result)
    mesh = unreal.load_asset(DEST + '/' + NAME)
    saved_build = subsystem.get_lod_build_settings(mesh,0)
    assert saved_build.recompute_tangents and saved_build.use_mikk_t_space and not saved_build.recompute_normals
    report['saved_build_settings'] = str(saved_build)
    assert mesh and mesh.get_num_sections(0) == 7
    assert 2000 < mesh.get_num_triangles(0) < 20000
    assert mesh.get_num_tex_coords(0) >= 2
    report.update({'state':'passed', 'mesh':mesh.get_path_name(), 'lod0_sections':mesh.get_num_sections(0), 'lod0_triangles':mesh.get_num_triangles(0), 'lod0_vertices':mesh.get_num_vertices(0), 'uv_channels':mesh.get_num_tex_coords(0),
                   'blade_samples_cm':[[0,0,8.42],[0,0,36.68],[0,0,64.94]],
                   'collision':'Native sampled blade sweep; no mesh-body collision or navigation',
                   'readback_materials':[mesh.get_material(i).get_path_name() for i in range(7)]})
except Exception:
    report.update({'state':'failed', 'error':traceback.format_exc()})
    unreal.log_error(report['error'])
finally:
    (OUT/'ImportReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
