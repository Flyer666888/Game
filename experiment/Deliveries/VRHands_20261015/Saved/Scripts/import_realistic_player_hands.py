"""Import the derivative right hand and author inexpensive VR skin materials.

Run through author_player_hands_editor.py in the full editor. No level, player
class, existing Manny asset, original skeleton or animation is authored here.
Optional HandsAuthoring.json textures may be nested under textures.skin/nails
or flat under textures for skin. All source files must stay in Realistic.
"""
import hashlib
import json
import math
import traceback
from pathlib import Path

import unreal


PROJECT = Path(unreal.Paths.project_dir()).resolve()
ART = PROJECT / 'ArtSource/PlayerHands/Realistic'
MANIFEST = ART / 'HandsAuthoring.json'
SOURCE_MESH = '/Game/XRMannequins/Meshes/SKM_MannyXR_right'
GRIP_ANIMATION = '/Game/ReversedScale/Player/Animations/A_Yueyao_Grip_Right'
MESH_ROOT = '/Game/ReversedScale/Player/Hands'
MESH_PATH = MESH_ROOT + '/SK_PlayerHand_Realistic_R'
MATERIAL_ROOT = '/Game/ReversedScale/Player/Materials'
TEXTURE_ROOT = '/Game/ReversedScale/Player/Hands/Textures'
REPORT = PROJECT / 'Docs/AI/PlayerHandsImported-2026-10-15.json'
A = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LIB = unreal.MaterialEditingLibrary


def asset_path(value):
    return value.get_path_name() if value else None


def save(value):
    result = bool(A.save_loaded_asset(value, False))
    if not result:
        raise RuntimeError('Could not save player hand asset: ' + value.get_path_name())
    return result


def source_file(value):
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (ART / path).resolve()
    if not path.is_file() or not path.is_relative_to(ART.resolve()):
        raise RuntimeError('Player hand sources must exist inside ArtSource/PlayerHands/Realistic: ' + str(path))
    return path


def reference_pose(mesh):
    # GetRefBonePose reads the optional mesh's reference skeleton in UE5.8.
    # The shared animation only supplies an evaluation container: this is an
    # offline asset query and never places a component or starts gameplay.
    animation = A.load_asset(GRIP_ANIMATION)
    if not animation:
        raise RuntimeError('The existing right-hand grip animation is required.')
    options = unreal.AnimPoseEvaluationOptions()
    options.optional_skeletal_mesh = mesh
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, 0.0, options)
    result = []
    for name in unreal.AnimPoseExtensions.get_bone_names(pose):
        entry = {'name': str(name),
                 'parent': str(unreal.SkeletalMeshEditorSubsystem.get_bone_parent(mesh, name))}
        for label, space in (('local', unreal.AnimPoseSpaces.LOCAL), ('world', unreal.AnimPoseSpaces.WORLD)):
            transform = unreal.AnimPoseExtensions.get_ref_bone_pose(pose, name, space)
            entry[label] = {
                'p': [transform.translation.x, transform.translation.y, transform.translation.z],
                'q': [transform.rotation.x, transform.rotation.y, transform.rotation.z, transform.rotation.w],
                's': [transform.scale3d.x, transform.scale3d.y, transform.scale3d.z],
            }
        result.append(entry)
    return result


def compare_reference_pose(expected, actual):
    violations, differences = [], []
    if len(expected) != 47 or len(actual) != len(expected):
        violations.append('The complete original 47-bone Manny hand hierarchy is required.')
    maximum = {space: {'translation_cm': 0.0, 'rotation_deg': 0.0, 'scale_component': 0.0,
                      'quaternion_component_sign_invariant': 0.0} for space in ('local', 'world')}
    for source, target in zip(expected, actual):
        entry = {'bone': source['name']}
        if source['name'] != target['name'] or source['parent'] != target['parent']:
            violations.append('Bone name, order or parent mismatch: ' + source['name'])
        for space in ('local', 'world'):
            source_transform, target_transform = source[space], target[space]
            position_error = math.sqrt(sum((a - b) ** 2 for a, b in zip(source_transform['p'], target_transform['p'])))
            scale_error = max(abs(a - b) for a, b in zip(source_transform['s'], target_transform['s']))
            source_q, target_q = source_transform['q'], target_transform['q']
            quaternion_error = min(max(abs(a - b) for a, b in zip(source_q, target_q)),
                                   max(abs(a + b) for a, b in zip(source_q, target_q)))
            norm_product = math.sqrt(sum(a * a for a in source_q) * sum(b * b for b in target_q))
            if not math.isfinite(norm_product) or norm_product < 0.00001:
                rotation_error = 360.0
            else:
                dot = max(0.0, min(1.0, abs(sum(a * b for a, b in zip(source_q, target_q))) / norm_product))
                rotation_error = math.degrees(2.0 * math.acos(dot))
            errors = {'translation_cm': position_error, 'rotation_deg': rotation_error,
                      'scale_component': scale_error, 'quaternion_component_sign_invariant': quaternion_error}
            entry[space] = errors
            for key, value in errors.items():
                maximum[space][key] = max(maximum[space][key], value)
            if (not all(math.isfinite(value) for value in errors.values()) or
                    position_error > 0.03 or rotation_error > 0.1 or scale_error > 0.001):
                violations.append(source['name'] + ' ' + space + ' reference transform exceeds tolerance: ' + str(errors))
        differences.append(entry)
    return {'matches_original_hierarchy_and_bind_pose': not violations,
            'expected_bone_count': len(expected), 'actual_bone_count': len(actual),
            'tolerances': {'translation_cm': 0.03, 'rotation_deg': 0.1, 'scale_component': 0.001},
            'maximum_errors': maximum, 'per_bone_differences': differences, 'violations': violations}


def source_asset_hashes(asset_paths):
    result = {}
    for path in asset_paths:
        package = path.split('.')[0]
        if not package.startswith('/Game/'):
            raise RuntimeError('Original hand sources must be project assets: ' + package)
        file_base = PROJECT / 'Content' / package.removeprefix('/Game/')
        files = {}
        for extension in ('.uasset', '.uexp', '.ubulk'):
            filename = file_base.with_suffix(extension)
            if filename.is_file():
                files[str(filename)] = hashlib.sha256(filename.read_bytes()).hexdigest()
        if not files:
            raise RuntimeError('Could not locate original hand asset files: ' + package)
        result[path] = files
    return result


def connect(source, output, target, pin):
    # UE5.8 shortens unary Input to NAME_None and Coordinates to UVs.
    pin = {'Input': '', 'Coordinates': 'UVs'}.get(pin, pin)
    if not LIB.connect_material_expressions(source, output, target, pin):
        raise RuntimeError('Could not connect hand material pin: ' + target.get_class().get_name() + '.' + repr(pin))


def property_connect(source, output, prop):
    if not LIB.connect_material_property(source, output, prop):
        raise RuntimeError('Could not connect player hand material property: ' + str(prop))


def node(material, cls, **properties):
    result = LIB.create_material_expression(material, cls)
    if not result:
        raise RuntimeError('Could not create hand material expression: ' + cls.__name__)
    for key, value in properties.items():
        result.set_editor_property(key, value)
    return result


def scalar(material, value):
    return node(material, unreal.MaterialExpressionConstant, r=float(value))


def color(material, value):
    return node(material, unreal.MaterialExpressionConstant3Vector,
                constant=unreal.LinearColor(*value[:3], 1.0))


def texture_profile(data, profile_name):
    textures = data.get('textures') or {}
    if not isinstance(textures, dict):
        raise RuntimeError('HandsAuthoring textures must be an object.')
    if profile_name in textures:
        profile = textures[profile_name]
    elif profile_name == 'skin' and any(role in textures for role in ('base_color', 'normal', 'roughness')):
        profile = textures
    else:
        profile = {}
    if not isinstance(profile, dict):
        raise RuntimeError('Hand texture profile must be an object: ' + profile_name)
    return profile


def import_texture(filename, profile_name, role, profile):
    filename = source_file(filename)
    suffix = {'base_color': 'BaseColor', 'normal': 'Normal', 'roughness': 'Roughness'}[role]
    name = 'T_Player' + profile_name.capitalize() + '_' + suffix
    task = unreal.AssetImportTask()
    task.filename = str(filename)
    task.destination_path = TEXTURE_ROOT
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = False
    TOOLS.import_asset_tasks([task])
    image = A.load_asset(TEXTURE_ROOT + '/' + name)
    if not isinstance(image, unreal.Texture2D):
        raise RuntimeError('Hand texture import failed: ' + str(filename))
    convention = str(profile.get('normal_convention', 'OpenGL')).lower()
    if convention not in ('opengl', 'directx'):
        raise RuntimeError('Hand normal convention must be OpenGL or DirectX.')
    image.set_editor_property('srgb', role == 'base_color')
    image.set_editor_property('compression_settings',
        unreal.TextureCompressionSettings.TC_NORMALMAP if role == 'normal' else
        unreal.TextureCompressionSettings.TC_MASKS if role == 'roughness' else
        unreal.TextureCompressionSettings.TC_DEFAULT)
    image.set_editor_property('flip_green_channel', role == 'normal' and convention == 'opengl')
    image.set_editor_property('address_x', unreal.TextureAddress.TA_WRAP)
    image.set_editor_property('address_y', unreal.TextureAddress.TA_WRAP)
    saved = save(image)
    return image, {'asset': asset_path(image), 'source': str(filename), 'role': role,
                   'sha256': hashlib.sha256(filename.read_bytes()).hexdigest(),
                   'srgb': role == 'base_color', 'saved': saved,
                   'normal_convention': convention if role == 'normal' else None}


def author_material(profile_name, profile, texture_records):
    name = 'M_PlayerSkin' if profile_name == 'skin' else 'M_PlayerNails'
    destination = MATERIAL_ROOT + '/' + name
    material = A.load_asset(destination) if A.does_asset_exist(destination) else None
    if not material:
        material = TOOLS.create_asset(name, MATERIAL_ROOT, unreal.Material, unreal.MaterialFactoryNew())
    if not isinstance(material, unreal.Material):
        raise RuntimeError('Unexpected existing asset class at ' + destination)
    LIB.delete_all_material_expressions(material)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property('two_sided', False)
    LIB.set_base_material_usage(material, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH, True)

    vertex = node(material, unreal.MaterialExpressionVertexColor)
    # VertexColor's RGB output has NAME_None in UE5.8; an empty name selects it.
    base, base_output = vertex, ''
    images = {}
    tiling = float(profile.get('uv_tiling', 1.0))
    if not math.isfinite(tiling) or not 0.125 <= tiling <= 64.0:
        raise RuntimeError('Hand UV tiling must be finite and between 0.125 and 64.')
    coordinates = None
    for role in ('base_color', 'normal', 'roughness'):
        filename = profile.get(role)
        if not filename:
            continue
        image, record = import_texture(filename, profile_name, role, profile)
        texture_records.append(record)
        sampler_type = {'base_color': unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                        'normal': unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
                        'roughness': unreal.MaterialSamplerType.SAMPLERTYPE_MASKS}[role]
        sample = node(material, unreal.MaterialExpressionTextureSample,
                      texture=image, sampler_type=sampler_type)
        if coordinates is None:
            coordinates = node(material, unreal.MaterialExpressionTextureCoordinate,
                               coordinate_index=0, u_tiling=tiling, v_tiling=tiling)
        connect(coordinates, '', sample, 'UVs')
        images[role] = sample
    if 'base_color' in images:
        # Optional neutral detail albedo multiplies the authored skin tones.
        # An absolute albedo can opt into replacement instead.
        mode = str(profile.get('base_color_mode', 'multiply')).lower()
        if mode == 'multiply':
            base = node(material, unreal.MaterialExpressionMultiply)
            connect(vertex, '', base, 'A')
            connect(images['base_color'], 'RGB', base, 'B')
            base_output = ''
        elif mode == 'replace':
            base, base_output = images['base_color'], 'RGB'
        else:
            raise RuntimeError('base_color_mode must be multiply or replace.')
    property_connect(base, base_output, unreal.MaterialProperty.MP_BASE_COLOR)
    property_connect(scalar(material, 0.0), '', unreal.MaterialProperty.MP_METALLIC)
    property_connect(scalar(material, 0.28), '', unreal.MaterialProperty.MP_SPECULAR)
    roughness = 0.48 if profile_name == 'skin' else 0.30
    if 'roughness' in images:
        property_connect(images['roughness'], 'R', unreal.MaterialProperty.MP_ROUGHNESS)
    else:
        property_connect(scalar(material, roughness), '', unreal.MaterialProperty.MP_ROUGHNESS)
    if 'normal' in images:
        strength = float(profile.get('normal_strength', 0.12 if profile_name == 'skin' else 0.06))
        if not 0.0 <= strength <= 1.0:
            raise RuntimeError('Hand normal strength must be between zero and one.')
        normal = node(material, unreal.MaterialExpressionMultiply)
        connect(images['normal'], 'RGB', normal, 'A')
        connect(color(material, (strength, strength, 1.0)), '', normal, 'B')
        property_connect(normal, '', unreal.MaterialProperty.MP_NORMAL)

    # Legacy Default Lit inputs are supported by the project's Substrate
    # conversion. Avoid subsurface profiles/screen-space passes for forward VR.
    errors = [str(value) for value in LIB.recompile_material(material)]
    if errors:
        raise RuntimeError('Player hand shader compilation failed for ' + name + ': ' + '; '.join(errors))
    saved = save(material)
    return material, {'asset': asset_path(material), 'profile': profile_name,
                       'base_color': 'Imported linear vertex colors' if 'base_color' not in images else
                                     'Optional UV0 albedo: ' + str(profile.get('base_color_mode', 'multiply')),
                       'roughness': roughness if 'roughness' not in images else 'UV0 roughness red channel',
                       'specular': 0.28, 'metallic': 0.0, 'shading_model': 'Default Lit',
                       'subsurface_profile': None, 'two_sided': False,
                       'texture_samples': len(images), 'uv_tiling': tiling,
                       'normal_strength': profile.get('normal_strength') if 'normal' in images else None,
                       'compile_errors': errors, 'saved': saved}


def main():
    report = {'date': '2026-10-15', 'success': False,
              'scope': 'Derivative player hand mesh and material authoring only; no gameplay or tests.',
              'source_mesh': SOURCE_MESH, 'mesh': MESH_PATH,
              'materials': [], 'textures': []}
    try:
        if not unreal.get_editor_subsystem(unreal.AssetEditorSubsystem):
            raise RuntimeError('Run hand import in the full initialized Unreal Editor, not a commandlet.')
        data = json.loads(MANIFEST.read_text(encoding='utf-8-sig')) if MANIFEST.is_file() else {}
        fbx = source_file(data.get('fbx_path') or data.get('fbx') or 'PlayerHandRealistic_R.fbx')
        original = A.load_asset(SOURCE_MESH)
        if not isinstance(original, unreal.SkeletalMesh):
            raise RuntimeError('The original Manny right hand asset is missing.')
        skeleton = original.get_editor_property('skeleton')
        if not skeleton:
            raise RuntimeError('The original Manny right hand skeleton is missing.')
        original_reference = reference_pose(original)
        if len(original_reference) != 47:
            raise RuntimeError('Unexpected original Manny right hand bone count: ' + str(len(original_reference)))
        source_paths = [SOURCE_MESH, asset_path(skeleton), GRIP_ANIMATION]
        original_hashes = source_asset_hashes(source_paths)
        report['original_source_asset_hashes_before'] = original_hashes
        report['original_reference_pose'] = original_reference
        report['original_mesh_skeleton_before'] = asset_path(skeleton)

        unreal.SystemLibrary.execute_console_command(None, 'Interchange.FeatureFlags.Import.FBX 0')
        task = unreal.AssetImportTask()
        task.filename = str(fbx)
        task.destination_path = MESH_ROOT
        task.destination_name = 'SK_PlayerHand_Realistic_R'
        task.automated = True
        task.replace_existing = True
        task.save = False
        options = unreal.FbxImportUI()
        options.automated_import_should_detect_type = False
        options.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
        options.import_as_skeletal = True
        options.import_mesh = True
        options.import_animations = False
        options.import_materials = False
        options.import_textures = False
        options.create_physics_asset = False
        options.skeleton = skeleton
        options.set_editor_property('reset_to_fbx_on_material_conflict', True)
        import_data = options.skeletal_mesh_import_data
        import_data.set_editor_property('vertex_color_import_option', unreal.VertexColorImportOption.REPLACE)
        import_data.set_editor_property('update_skeleton_reference_pose', False)
        import_data.set_editor_property('use_t0_as_ref_pose', False)
        import_data.set_editor_property('import_morph_targets', False)
        import_data.set_editor_property('preserve_smoothing_groups', True)
        import_data.set_editor_property('import_meshes_in_bone_hierarchy', True)
        import_data.set_editor_property('convert_scene', True)
        import_data.set_editor_property('convert_scene_unit', True)
        import_data.set_editor_property('normal_import_method', unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
        options.anim_sequence_import_data.set_editor_property('add_curve_metadata_to_skeleton', False)
        task.options = options
        TOOLS.import_asset_tasks([task])
        mesh = A.load_asset(MESH_PATH)
        if not isinstance(mesh, unreal.SkeletalMesh) or mesh.get_editor_property('skeleton') != skeleton:
            raise RuntimeError('Realistic player hand must use the unchanged original Manny right hand skeleton.')
        report['original_mesh_skeleton_after'] = asset_path(original.get_editor_property('skeleton'))
        report['imported_mesh_skeleton'] = asset_path(mesh.get_editor_property('skeleton'))
        imported_reference = reference_pose(mesh)
        report['imported_reference_pose'] = imported_reference
        pose_comparison = compare_reference_pose(original_reference, imported_reference)
        report['reference_pose_comparison'] = pose_comparison
        if not pose_comparison['matches_original_hierarchy_and_bind_pose']:
            raise RuntimeError('The imported hand is not bind-pose compatible: ' + '; '.join(pose_comparison['violations'][:8]))
        original_after = reference_pose(original)
        original_pose_comparison = compare_reference_pose(original_reference, original_after)
        report['original_reference_pose_after_import'] = original_after
        report['original_reference_pose_comparison'] = original_pose_comparison
        if not original_pose_comparison['matches_original_hierarchy_and_bind_pose']:
            raise RuntimeError('The original Manny hand reference pose changed unexpectedly.')

        materials = {}
        for profile_name in ('skin', 'nails'):
            material, record = author_material(profile_name, texture_profile(data, profile_name), report['textures'])
            materials[profile_name] = material
            report['materials'].append(record)
        slots = list(mesh.get_editor_property('materials'))
        slot_records = []
        found = []
        for slot in slots:
            slot_name = str(slot.get_editor_property('material_slot_name'))
            imported_name = str(slot.get_editor_property('imported_material_slot_name'))
            name = imported_name if imported_name in ('M_Skin', 'M_Nails') else slot_name
            if name not in ('M_Skin', 'M_Nails'):
                raise RuntimeError('Unexpected player hand material slot: ' + repr(slot_name) + ' / ' + repr(imported_name))
            profile_name = 'skin' if name == 'M_Skin' else 'nails'
            slot.set_editor_property('material_interface', materials[profile_name])
            # Keep the imported slot names stable for repeat import and sections.
            slot.set_editor_property('material_slot_name', name)
            # ImportedMaterialSlotName is read-only; the FBX already supplied it.
            found.append(name)
            slot_records.append({'material_slot_name': name, 'imported_material_slot_name': name,
                                 'material': asset_path(materials[profile_name])})
        if len(slots) != 2 or set(found) != {'M_Skin', 'M_Nails'}:
            raise RuntimeError('Exactly the original M_Skin and M_Nails FBX slots must import separately.')
        mesh.set_editor_property('materials', slots)
        mesh_saved = save(mesh)

        subsystem = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
        subsystem_mode = 'registered_editor_subsystem'
        if not subsystem:
            # GetNumVerts/GetNumSections are stateless, read-only utility calls
            # that inspect the supplied mesh's render resources and GEditor.
            subsystem = unreal.new_object(unreal.SkeletalMeshEditorSubsystem)
            subsystem_mode = 'temporary_stateless_editor_utility'
        if not subsystem:
            raise RuntimeError('Skeletal mesh statistics utility is unavailable.')
        lod_count = int(subsystem.get_lod_count(mesh))
        lods = [{'index': index, 'render_vertices': int(subsystem.get_num_verts(mesh, index)),
                 'sections': int(subsystem.get_num_sections(mesh, index))}
                for index in range(lod_count)]
        if not lods or lods[0]['render_vertices'] <= 0 or lods[0]['sections'] != 2:
            raise RuntimeError('The imported hand must render nonempty geometry in exactly two LOD0 sections.')

        after_hashes = source_asset_hashes(source_paths)
        report['original_source_asset_hashes_after'] = after_hashes
        report['original_source_assets_unchanged_on_disk'] = after_hashes == original_hashes
        if after_hashes != original_hashes:
            raise RuntimeError('An original hand mesh, skeleton or grip animation file changed unexpectedly.')

        report.update({
            'success': True, 'mesh': asset_path(mesh), 'mesh_saved': mesh_saved,
            'mesh_uasset_sha256': hashlib.sha256((PROJECT / 'Content/ReversedScale/Player/Hands/SK_PlayerHand_Realistic_R.uasset').read_bytes()).hexdigest(),
            'skeleton': asset_path(skeleton), 'skeleton_reference_pose_updated': False,
            'reference_pose_comparison': pose_comparison,
            'reference_pose_query_animation': GRIP_ANIMATION,
            'physics_asset': asset_path(mesh.get_editor_property('physics_asset')),
            'material_slots': slot_records, 'lods': lods,
            'statistics_subsystem': subsystem_mode,
            'source_mesh_stats': data.get('source_mesh_stats') or {},
            'authored_mesh_stats': data.get('mesh_stats') or {},
            'source_fbx': str(fbx), 'source_fbx_sha256': hashlib.sha256(fbx.read_bytes()).hexdigest(),
            'manifest': str(MANIFEST) if MANIFEST.is_file() else None,
            'vertex_colors': {'import_option': 'REPLACE with FBX colors', 'channel': 'SkinTint',
                              'shader_interpretation': 'Linear RGB authored skin and nail color, alpha ignored',
                              'source_manifest': data.get('vertex_color') or {}},
            'imported_object_paths': [str(value) for value in task.imported_object_paths],
            'legacy_fbx_importer': True, 'import_animations': False,
            'import_materials': False, 'import_textures_from_fbx': False,
            'create_physics_asset': False,
            'runtime_acceptance': 'Pending user VR play; no character class or map was modified by this script.',
        })
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        if 'original_source_asset_hashes_before' in report:
            try:
                final_hashes = source_asset_hashes(source_paths)
                report['original_source_asset_hashes_after'] = final_hashes
                report['original_source_assets_unchanged_on_disk'] = final_hashes == original_hashes
            except Exception:
                report['original_source_asset_hash_error'] = traceback.format_exc()
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('PLAYER_HAND_REALISTIC_IMPORT_SAVED ' + MESH_PATH)


main()
