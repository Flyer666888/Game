"""Import the prepared Dragon Shield copy; preserve source art and combat assets."""
import json
import re
from pathlib import Path
import unreal

OUT = Path(unreal.Paths.project_dir()) / 'ArtSource/DragonShield'
DATA = json.loads((OUT / 'DragonShieldPrepared.json').read_text(encoding='utf-8'))
ROOT = '/Game/ReversedScale/Weapons/DragonShield'
MESH_PATH = ROOT + '/SM_DragonShield'
A = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LIB = unreal.MaterialEditingLibrary
STATIC = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
STATIC_MODE = 'registered_editor_subsystem'
if not unreal.get_editor_subsystem(unreal.AssetEditorSubsystem):
    # SetLods/RemoveCollisions dereference this real editor service internally.
    # A transient substitute for that initialized, stateful service is unsafe.
    raise RuntimeError('Run shield authoring in the full Unreal Editor: AssetEditorSubsystem is unavailable.')
if not STATIC:
    # UE5.8 UStaticMeshEditorSubsystem has no fields or Initialize override.
    # Its selected methods operate on mesh arguments and the real GEditor
    # services checked above, so a retained temporary utility instance is safe.
    STATIC = unreal.new_object(unreal.StaticMeshEditorSubsystem)
    STATIC_MODE = 'temporary_stateless_editor_utility'
    if not STATIC:
        raise RuntimeError('Could not instantiate the static mesh authoring utility.')


def source_path(value):
    candidate = Path(value)
    return candidate if candidate.is_absolute() else OUT / candidate


def save(value):
    if not A.save_loaded_asset(value, False):
        raise RuntimeError('Could not save shield asset: ' + value.get_path_name())


def expression(material, cls):
    value = LIB.create_material_expression(material, cls)
    if not value:
        raise RuntimeError('Could not create shield material expression: ' + cls.__name__)
    return value


def scalar(material, value):
    node = expression(material, unreal.MaterialExpressionConstant)
    node.set_editor_property('r', float(value))
    return node


def color(material, value):
    node = expression(material, unreal.MaterialExpressionConstant3Vector)
    node.set_editor_property('constant', unreal.LinearColor(*value[:3], 1.0))
    return node


def property_connection(node, output, destination):
    if not LIB.connect_material_property(node, output, destination):
        raise RuntimeError('Could not connect shield material property: ' + str(destination))


def node_connection(source, output, destination, pin):
    if not LIB.connect_material_expressions(source, output, destination, pin):
        raise RuntimeError('Could not connect shield material input: ' + pin)


texture_cache, texture_records = {}, []


def texture(value, material_name, normal=False):
    filename = source_path(value)
    if not filename.is_file():
        raise RuntimeError('Prepared shield texture is missing: ' + str(filename))
    key = (str(filename.resolve()).casefold(), normal)
    if key in texture_cache:
        return texture_cache[key]
    name = 'T_' + material_name.removeprefix('M_') + ('_Normal' if normal else '_BaseColor')
    task = unreal.AssetImportTask()
    task.filename = str(filename)
    task.destination_path = ROOT + '/Textures'
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = False
    TOOLS.import_asset_tasks([task])
    result = A.load_asset(ROOT + '/Textures/' + name)
    if not isinstance(result, unreal.Texture2D):
        raise RuntimeError('Shield texture import failed: ' + str(filename))
    result.set_editor_property('compression_settings',
        unreal.TextureCompressionSettings.TC_NORMALMAP if normal else unreal.TextureCompressionSettings.TC_DEFAULT)
    result.set_editor_property('srgb', not normal)
    result.set_editor_property('flip_green_channel', normal)
    save(result)
    texture_cache[key] = result
    texture_records.append({'source': str(filename), 'asset': result.get_path_name(),
                            'role': 'normal' if normal else 'base_color',
                            'srgb': not normal, 'flip_green_channel': normal,
                            'normal_convention': 'Blender OpenGL to Unreal DirectX' if normal else None})
    return result


def texture_sample(material, image, uv_index, normal=False):
    uv = expression(material, unreal.MaterialExpressionTextureCoordinate)
    uv.set_editor_property('coordinate_index', int(uv_index))
    sample = expression(material, unreal.MaterialExpressionTextureSample)
    sample.set_editor_property('texture', image)
    sample.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
                               if normal else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    node_connection(uv, '', sample, 'UVs')
    return sample


entries = DATA['materials']
if not entries:
    raise RuntimeError('Prepared shield materials are required.')
names = [entry['ue_name'] for entry in entries]
if len(set(names)) != len(names) or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) for name in names):
    raise RuntimeError('Prepared shield material names must be unique ASCII asset names.')
materials, material_records = {}, []
for entry in entries:
    name = entry['ue_name']
    destination = ROOT + '/Materials/' + name
    material = A.load_asset(destination) if A.does_asset_exist(destination) else None
    if not material:
        material = TOOLS.create_asset(name, ROOT + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
    if not isinstance(material, unreal.Material):
        raise RuntimeError('Could not create shield material: ' + destination)
    LIB.delete_all_material_expressions(material)
    base_file = entry.get('base_color_texture')
    if base_file:
        base = texture_sample(material, texture(base_file, name), 0)
        property_connection(base, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        property_connection(color(material, entry['color']), '', unreal.MaterialProperty.MP_BASE_COLOR)
    for value, prop in ((entry['metallic'], unreal.MaterialProperty.MP_METALLIC),
                        (entry['roughness'], unreal.MaterialProperty.MP_ROUGHNESS)):
        property_connection(scalar(material, value), '', prop)
    normal_file = entry.get('normal_texture')
    normal_uv_index = int(entry.get('normal_uv_index', 1))
    normal_strength = float(entry.get('normal_strength', .18))
    if normal_file:
        normal = texture_sample(material, texture(normal_file, name, True), normal_uv_index, True)
        attenuated = expression(material, unreal.MaterialExpressionMultiply)
        node_connection(normal, 'RGB', attenuated, 'A')
        node_connection(color(material, (normal_strength, normal_strength, 1.0)), '', attenuated, 'B')
        property_connection(attenuated, '', unreal.MaterialProperty.MP_NORMAL)
    LIB.recompile_material(material)
    save(material)
    materials[name] = material
    material_records.append({'asset': material.get_path_name(), 'ue_name': name,
        'source_name': entry.get('name'), 'base_color_linear': entry['color'],
        'base_color_texture': str(source_path(base_file)) if base_file else None,
        'base_color_uv_index': 0, 'metallic': entry['metallic'], 'roughness': entry['roughness'],
        'normal_texture': str(source_path(normal_file)) if normal_file else None,
        'normal_uv_index': normal_uv_index if normal_file else None,
        'normal_strength': normal_strength if normal_file else None,
        'procedural_approximation': None if base_file else
            'Original procedural Blender nodes use supplied constant linear PBR color, metallic and roughness.'})

fbx = source_path(DATA.get('fbx_path') or 'DragonShieldPrepared.fbx')
if not fbx.is_file():
    raise RuntimeError('Prepared shield FBX is missing: ' + str(fbx))
unreal.SystemLibrary.execute_console_command(None, 'Interchange.FeatureFlags.Import.FBX 0')
task = unreal.AssetImportTask()
task.filename = str(fbx)
task.destination_path = ROOT
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
TOOLS.import_asset_tasks([task])
mesh = A.load_asset(MESH_PATH)
if not isinstance(mesh, unreal.StaticMesh):
    raise RuntimeError('Prepared Dragon Shield static mesh import failed.')
mesh.set_editor_property('bHasNavigationData', False)
if not STATIC.remove_collisions(mesh):
    raise RuntimeError('Could not remove shield mesh collision.')
slots = []
for index, slot in enumerate(mesh.get_editor_property('static_materials')):
    visible_name = str(slot.get_editor_property('material_slot_name'))
    imported_name = str(slot.get_editor_property('imported_material_slot_name'))
    name = imported_name if imported_name in materials else visible_name
    if name not in materials:
        raise RuntimeError('Unrecognized shield FBX material slot: ' + imported_name + ' / ' + visible_name)
    mesh.set_material(index, materials[name])
    slots.append({'index': index, 'slot_name': visible_name, 'imported_name': imported_name,
                  'material': materials[name].get_path_name()})
if not slots:
    raise RuntimeError('The shield mesh must retain material slots.')
uv_count = STATIC.get_num_uv_channels(mesh, 0)
for entry in entries:
    if entry.get('normal_texture') and int(entry.get('normal_uv_index', 1)) >= uv_count:
        raise RuntimeError('Shield FBX must preserve its separate normal UV channel.')

# These native editor APIs are verified in the local UE5.8 StaticMeshEditorSubsystem headers.
reduction = unreal.StaticMeshReductionOptions()
reduction.set_editor_property('auto_compute_lod_screen_size', True)
lod_settings = []
for fraction, screen_size in ((1.0, 1.0), (.5, .6), (.25, .3), (.1, .12)):
    setting = unreal.StaticMeshReductionSettings()
    setting.set_editor_property('percent_triangles', fraction)
    setting.set_editor_property('screen_size', screen_size)
    lod_settings.append(setting)
reduction.set_editor_property('reduction_settings', lod_settings)
if STATIC.set_lods(mesh, reduction) != 4:
    raise RuntimeError('Could not generate four Dragon Shield LODs.')
lod_count = STATIC.get_lod_count(mesh)
for lod in range(lod_count):
    for section in range(mesh.get_num_sections(lod)):
        STATIC.enable_section_collision(mesh, False, lod, section)
save(mesh)
bounds = mesh.get_bounds()
report = {'mesh': mesh.get_path_name(), 'prepared_metadata': str(OUT / 'DragonShieldPrepared.json'),
    'static_mesh_authoring_service': STATIC_MODE,
    'source_fbx': str(fbx), 'material_slots': slots, 'materials': material_records, 'textures': texture_records,
    'bounds_cm': {'origin': [bounds.origin.x, bounds.origin.y, bounds.origin.z],
                  'box_extent': [bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z],
                  'sphere_radius': bounds.sphere_radius},
    'uv_count_lod0': uv_count, 'generated_lightmap_uvs': False,
    'lod_count': lod_count, 'requested_lod_triangle_fractions': [1.0, .5, .25, .1],
    'lod_triangle_counts': [mesh.get_num_triangles(lod) for lod in range(lod_count)],
    'nanite': False, 'auto_generate_collision': False, 'simple_collision_count': STATIC.get_simple_collision_count(mesh),
    'navigation_data': mesh.get_editor_property('bHasNavigationData'),
    'collision_owner': 'Existing player shield BoxComponent; imported visual has no collision sections.',
    'procedural_material_note': 'Seven original procedural Blender materials are represented by supplied constant PBR approximations; front color and normal textures are preserved.',
    'scope': 'Imported prepared model copy, textures and shield-only materials. Original blend, combat definitions and maps are unchanged. No gameplay or tests executed.'}
(OUT / 'DragonShieldImported.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('DRAGON_SHIELD_IMPORTED ' + MESH_PATH)
