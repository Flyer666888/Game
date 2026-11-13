"""Import refined shield geometry only, reusing the saved realistic materials.

Run in the full Unreal Editor. Does not enter PIE, start combat or author shaders.
"""
import hashlib
import json
import math
import time
import traceback
from pathlib import Path
import unreal


_shield_root = Path(unreal.Paths.project_dir()).resolve()
_shield_art = _shield_root / 'ArtSource/DragonShield/ModelRefinement_20261016'
_shield_destination = '/Game/ReversedScale/Weapons/DragonShield'
_shield_mesh_path = _shield_destination + '/SM_DragonShield'
_shield_report_path = _shield_root / 'Docs/AI/ShieldModelImported-2026-10-16.json'
_shield_material_names = ['M_DragonShield_%02d' % index for index in range(8)]
_shield_expected_grip = [-5.160975456237793, 0.0, -0.5609756112098694]
_shield_started = time.monotonic()
_shield_done = None
_shield_running = False
_shield_handle = None
_shield_report = {'date': '2026-10-16', 'success': False, 'mesh_saved': False,
                  'mesh': _shield_mesh_path, 'tests_added_or_run': False,
                  'scope': 'Refined shield static mesh import, original PBR material binding, LOD authoring and save only.'}


def _shield_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shield_material_hashes():
    result = {}
    base = _shield_root / 'Content/ReversedScale/Weapons/DragonShield/Materials'
    for name in _shield_material_names:
        package = base / (name + '.uasset')
        if not package.is_file():
            raise RuntimeError('An existing shield material package is missing: ' + str(package))
        for extension in ('.uasset', '.uexp', '.ubulk'):
            path = base / (name + extension)
            if path.is_file():
                result[path.relative_to(_shield_root).as_posix()] = _shield_sha256(path)
    return result


def _shield_metadata_fields(data, names, prefix='', depth=0):
    """Allow the modelling manifest's nesting to evolve without guessing values."""
    rows = []
    if not isinstance(data, dict) or depth > 4:
        return rows
    for name, value in data.items():
        key = prefix + name
        if name in names:
            rows.append({'field': key, 'value': value})
        if isinstance(value, dict):
            rows.extend(_shield_metadata_fields(value, names, key + '.', depth + 1))
    return rows


def _shield_check_metadata(data, original):
    expected = original.get('grip_center_cm')
    if not isinstance(expected, list) or len(expected) != 3 or any(
            not math.isfinite(float(value)) or abs(float(value) - target) > .002
            for value, target in zip(expected, _shield_expected_grip)):
        raise RuntimeError('Original shield metadata no longer matches the current left-hand grip anchor.')
    rows = _shield_metadata_fields(data, {'grip_center_cm', 'canonical_grip_center_cm', 'grip_center_ue_cm'})
    for row in rows:
        value = row['value']
        if isinstance(value, dict) and all(axis in value for axis in ('x', 'y', 'z')):
            value = [value[axis] for axis in ('x', 'y', 'z')]
        if not isinstance(value, (list, tuple)) or len(value) != 3 or any(
                not math.isfinite(float(item)) or abs(float(item) - target) > .05
                for item, target in zip(value, _shield_expected_grip)):
            raise RuntimeError('Refined shield grip metadata moved the original rear handle: ' + str(row))
    directions = _shield_metadata_fields(data, {'direction', 'canonical_direction'})
    for row in directions:
        direction = row['value']
        if isinstance(direction, dict):
            for key, required in (('front', '+X'), ('up', '+Z'), ('horizontal', '+Y')):
                if key in direction and str(direction[key]).replace(' ', '').upper() != required:
                    raise RuntimeError('Refined shield metadata has an incompatible orientation: ' + str(row))
    _shield_report['grip_metadata'] = {'original_grip_center_cm': expected,
                                     'refined_recognized_fields': rows,
                                     'refined_field_present': bool(rows),
                                     'tolerance_cm': .05,
                                     'note': 'Metadata consistency only; imported mesh bounds do not locate a hidden grip feature.'}
    _shield_report['direction_metadata'] = directions


def _shield_author():
    fbx = _shield_art / 'DragonShieldRefined.fbx'
    manifest = _shield_art / 'DragonShieldRefined.json'
    if not fbx.is_file() or not manifest.is_file():
        raise RuntimeError('Refined shield FBX and JSON must both be prepared before import.')
    data = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise RuntimeError('Refined shield JSON must contain a metadata object.')
    original = json.loads((_shield_root / 'ArtSource/DragonShield/DragonShieldPrepared.json').read_text(encoding='utf-8-sig'))
    _shield_check_metadata(data, original)
    _shield_report.update({'source_fbx': str(fbx), 'fbx_sha256': _shield_sha256(fbx),
                           'source_metadata': str(manifest), 'metadata_sha256': _shield_sha256(manifest),
                           'metadata_keys': sorted(data),
                           'source_mesh_summary': _shield_metadata_fields(data, {'vertices', 'triangles', 'vertex_count', 'triangle_count', 'nominal_diameter_cm'})})
    _shield_report['material_package_hashes_before'] = _shield_material_hashes()
    materials = {}
    for name in _shield_material_names:
        material = unreal.load_asset(_shield_destination + '/Materials/' + name)
        if not isinstance(material, unreal.MaterialInterface):
            raise RuntimeError('Existing shield PBR material is unavailable: ' + name)
        materials[name] = material
    if not unreal.get_editor_subsystem(unreal.AssetEditorSubsystem):
        raise RuntimeError('Full editor AssetEditorSubsystem is required for static mesh authoring.')
    static = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if not static:
        # This subsystem is a stateless authoring utility in local UE5.8.
        static = unreal.new_object(unreal.StaticMeshEditorSubsystem)
    if not static:
        raise RuntimeError('Static mesh authoring service is unavailable.')

    unreal.SystemLibrary.execute_console_command(None, 'Interchange.FeatureFlags.Import.FBX 0')
    task = unreal.AssetImportTask()
    task.filename = str(fbx)
    task.destination_path = _shield_destination
    task.destination_name = 'SM_DragonShield'
    task.automated = True
    task.replace_existing = True
    task.save = False
    options = unreal.FbxImportUI()
    options.automated_import_should_detect_type = False
    options.set_editor_property('reset_to_fbx_on_material_conflict', True)
    options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    options.import_as_skeletal = False
    options.import_mesh = True
    options.import_animations = False
    options.import_materials = False
    options.import_textures = False
    mesh_options = options.static_mesh_import_data
    mesh_options.combine_meshes = True
    mesh_options.convert_scene = True
    mesh_options.convert_scene_unit = True
    mesh_options.auto_generate_collision = False
    mesh_options.generate_lightmap_u_vs = False
    mesh_options.build_nanite = False
    mesh_options.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    mesh_options.normal_generation_method = unreal.FBXNormalGenerationMethod.BUILT_IN
    task.options = options
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported_paths = [str(path) for path in task.get_editor_property('imported_object_paths')]
    _shield_report['imported_object_paths'] = imported_paths
    if not any(path.split('.')[0] == _shield_mesh_path for path in imported_paths):
        raise RuntimeError('FBX import did not report the target mesh; refusing to deliver a stale pre-existing asset.')
    mesh = unreal.load_asset(_shield_mesh_path)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError('Refined shield mesh import failed.')
    bounds = mesh.get_bounds()
    extent = [bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z]
    origin = [bounds.origin.x, bounds.origin.y, bounds.origin.z]
    dimensions = [2.0 * value for value in extent]
    _shield_report['bounds_cm'] = {'origin': origin, 'box_extent': extent,
                                  'dimensions': dimensions, 'sphere_radius': bounds.sphere_radius}
    if not all(math.isfinite(value) for value in extent + origin) or any(value <= 0 for value in extent):
        raise RuntimeError('Refined shield has invalid import bounds.')
    if any(abs(dimensions[index] - 46.0) > 2.5 for index in (1, 2)):
        raise RuntimeError('Refined shield must remain close to the authored 46 cm diameter: ' + str(dimensions))
    if extent[0] >= min(extent[1], extent[2]) * .5:
        raise RuntimeError('Shield thickness must remain the X axis; FBX axis conversion appears incorrect.')
    if abs(origin[1]) > 1.0 or abs(origin[2]) > 1.0:
        raise RuntimeError('Shield centre moved away from its existing Y/Z pivot.')

    slots = []
    used_names = []
    for index, slot in enumerate(mesh.get_editor_property('static_materials')):
        imported = str(slot.get_editor_property('imported_material_slot_name'))
        visible = str(slot.get_editor_property('material_slot_name'))
        name = imported if imported in materials else visible
        if name not in materials:
            raise RuntimeError('Unexpected shield material slot: ' + imported + ' / ' + visible)
        mesh.set_material(index, materials[name])
        used_names.append(name)
        slots.append({'index': index, 'imported_name': imported, 'slot_name': visible,
                      'bound_name': name, 'material': materials[name].get_path_name()})
    expected = set(_shield_material_names)
    if len(used_names) != len(set(used_names)) or set(used_names) not in (expected, expected - {'M_DragonShield_04'}):
        raise RuntimeError('Retain the eight named materials or the existing seven-slot layout without unused patina.')
    _shield_report['material_slots'] = slots
    if static.get_num_uv_channels(mesh, 0) != 2:
        raise RuntimeError('The shield must retain UV0 colour and UV1 dragon normal channels.')

    mesh.set_editor_property('bHasNavigationData', False)
    nanite = static.get_nanite_settings(mesh)
    if nanite.get_editor_property('enabled'):
        nanite.set_editor_property('enabled', False)
        static.set_nanite_settings(mesh, nanite, True)
    if not static.remove_collisions(mesh):
        raise RuntimeError('Could not remove shield visual collision.')
    reduction = unreal.StaticMeshReductionOptions()
    reduction.set_editor_property('auto_compute_lod_screen_size', True)
    settings = []
    for fraction, screen_size in ((1.0, 1.0), (.5, .6), (.25, .3), (.1, .12)):
        setting = unreal.StaticMeshReductionSettings()
        setting.set_editor_property('percent_triangles', fraction)
        setting.set_editor_property('screen_size', screen_size)
        settings.append(setting)
    reduction.set_editor_property('reduction_settings', settings)
    if static.set_lods(mesh, reduction) != 4:
        raise RuntimeError('Refined shield must have four LODs.')
    lods = []
    for lod in range(static.get_lod_count(mesh)):
        build = static.get_lod_build_settings(mesh, lod)
        if build.get_editor_property('generate_lightmap_u_vs'):
            build.set_editor_property('generate_lightmap_u_vs', False)
            static.set_lod_build_settings(mesh, lod, build)
        sections = []
        for section in range(mesh.get_num_sections(lod)):
            static.enable_section_collision(mesh, False, lod, section)
            enabled = static.is_section_collision_enabled(mesh, lod, section)
            if enabled:
                raise RuntimeError('Shield visual section collision remained enabled.')
            sections.append({'section': section, 'collision_enabled': enabled})
        # GetNumUVChannels reads only source MeshDescription. UE-generated LODs
        # normally have none and return zero even when their render UVs survive.
        # GetNumTexCoords reads the actual render vertex buffer for this LOD.
        source_uv_count = static.get_num_uv_channels(mesh, lod)
        render_uv_count = mesh.get_num_tex_coords(lod)
        if lod == 0 and source_uv_count != 2:
            raise RuntimeError('Shield LOD0 source mesh did not preserve both UV channels.')
        if render_uv_count != 2:
            raise RuntimeError('Shield LOD %d render vertex buffer has %d UV channels, expected two.' % (lod, render_uv_count))
        triangles = mesh.get_num_triangles(lod)
        if triangles <= 0:
            raise RuntimeError('Refined shield LOD contains no triangles.')
        lods.append({'lod': lod, 'triangles': triangles, 'uv_count': render_uv_count,
                     'render_uv_count': render_uv_count,
                     'source_uv_count': source_uv_count if source_uv_count else None,
                     'source_uv_status': 'available' if source_uv_count else 'unavailable_generated_lod',
                     'generate_lightmap_uvs': static.get_lod_build_settings(mesh, lod).get_editor_property('generate_lightmap_u_vs'),
                     'recompute_normals': build.get_editor_property('recompute_normals'),
                     'recompute_tangents': build.get_editor_property('recompute_tangents'),
                     'use_mikk_t_space': build.get_editor_property('bUseMikkTSpace'),
                     'sections': sections})
    _shield_report.update({'lod_count': len(lods), 'lods': lods,
                           'requested_lod_triangle_fractions': [1.0, .5, .25, .1],
                           'lod_triangle_counts': [row['triangles'] for row in lods],
                           'uv_count_lod0': static.get_num_uv_channels(mesh, 0),
                           'render_uv_count_lod0': mesh.get_num_tex_coords(0),
                           'nanite': static.get_nanite_settings(mesh).get_editor_property('enabled'),
                           'simple_collision_count': static.get_simple_collision_count(mesh),
                           'navigation_data': mesh.get_editor_property('bHasNavigationData'),
                           'collision_owner': 'Existing GuardCollision BoxComponent; imported visual remains collision-free.',
                           'front_axis_check': 'Imported X is the thin axis; front sign follows the preserved source metadata.'})
    if _shield_report['nanite'] or _shield_report['simple_collision_count'] != 0 or _shield_report['navigation_data']:
        raise RuntimeError('Refined shield has unexpected Nanite, collision or navigation settings.')
    if _shield_material_hashes() != _shield_report['material_package_hashes_before']:
        raise RuntimeError('Existing PBR material package content changed during mesh-only import.')
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh, False):
        raise RuntimeError('Could not save the refined shield mesh.')
    _shield_report['mesh_saved'] = True
    _shield_report['mesh'] = mesh.get_path_name()
    package = _shield_root / 'Content/ReversedScale/Weapons/DragonShield/SM_DragonShield.uasset'
    _shield_report['mesh_uasset_sha256'] = _shield_sha256(package)
    _shield_report['success'] = True
    unreal.log('REFINED_SHIELD_MODEL_IMPORTED')


def _shield_tick(delta):
    global _shield_running, _shield_done
    if _shield_running or time.monotonic() - _shield_started < 6.0:
        return
    if _shield_done is not None:
        if time.monotonic() - _shield_done >= 2.0:
            unreal.unregister_slate_post_tick_callback(_shield_handle)
            unreal.SystemLibrary.quit_editor()
        return
    _shield_running = True
    try:
        _shield_author()
    except Exception:
        _shield_report['success'] = False
        _shield_report['error'] = traceback.format_exc()
        unreal.log_error(_shield_report['error'])
    finally:
        try:
            _shield_report['material_package_hashes_after'] = _shield_material_hashes()
            _shield_report['materials_unchanged'] = (
                _shield_report.get('material_package_hashes_before') == _shield_report['material_package_hashes_after'])
            if not _shield_report['materials_unchanged']:
                _shield_report['success'] = False
        except Exception:
            _shield_report['success'] = False
            _shield_report['material_hash_error'] = traceback.format_exc()
        _shield_report_path.parent.mkdir(parents=True, exist_ok=True)
        _shield_report_path.write_text(json.dumps(_shield_report, ensure_ascii=False, indent=2), encoding='utf-8')
        _shield_done = time.monotonic()
        _shield_running = False


_shield_handle = unreal.register_slate_post_tick_callback(_shield_tick)
unreal.log('REFINED_SHIELD_MODEL_IMPORT_REGISTERED')
