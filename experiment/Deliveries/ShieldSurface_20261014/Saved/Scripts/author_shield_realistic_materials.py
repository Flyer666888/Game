"""Author shield-only PBR materials from prepared tile images; no mesh changes.

Run with UnrealEditor.exe -ExecutePythonScript after the asset folder is backed up.
World-to-local projection keeps colour and ORM attached to the moving shield.
The dragon front retains its original base-image and UV1 normal connections.
"""
import hashlib
import json
import re
from pathlib import Path

import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
ART = PROJECT / 'ArtSource/DragonShield'
SURFACE = ART / 'RealisticSurface'
MANIFEST = SURFACE / 'RealisticSurface.json'
PREPARED = ART / 'DragonShieldPrepared.json'
ROOT = '/Game/ReversedScale/Weapons/DragonShield'
TEX_ROOT = ROOT + '/Textures/RealisticSurface'
REPORT = PROJECT / 'Docs/AI/ShieldRealisticMaterials-2026-10-14.json'
PREFIX = 'NL_ShieldRealistic: '
A = unreal.EditorAssetLibrary
LIB = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
if not unreal.get_editor_subsystem(unreal.AssetEditorSubsystem):
    # UE5.8 MaterialEditingLibrary's editor-notification and recompile paths
    # dereference this subsystem. Do not substitute a transient instance.
    raise RuntimeError('Run shield material authoring in the full Unreal Editor: AssetEditorSubsystem is unavailable.')

DATA = json.loads(MANIFEST.read_text(encoding='utf-8-sig'))
ORIGINAL = json.loads(PREPARED.read_text(encoding='utf-8-sig'))
ENTRIES = {entry['ue_name']: entry for entry in ORIGINAL['materials']}
EXPECTED = ['M_DragonShield_%02d' % index for index in range(8)]
MAPPING = dict(DATA['material_profile_by_ue_name'])
PROFILES = DATA['profiles']
MAPPING.setdefault('M_DragonShield_07', 'bronze')
if set(MAPPING) != set(EXPECTED) or set(ENTRIES) != set(EXPECTED):
    raise RuntimeError('Exactly the existing eight Dragon Shield materials are required.')
if any(name not in PROFILES for name in MAPPING.values()):
    raise RuntimeError('Every shield material must reference a prepared surface profile.')


def save(asset):
    if not A.save_loaded_asset(asset, False):
        raise RuntimeError('Could not save shield asset: ' + asset.get_path_name())


def source_file(value):
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (SURFACE / path).resolve()
    if not path.is_file() or not path.is_relative_to(SURFACE.resolve()):
        raise RuntimeError('Surface images must exist inside RealisticSurface: ' + str(path))
    return path


def enum_value(enum, spelling):
    # UE Python preserves the enum token's upper-case spelling.
    value = getattr(enum, spelling, None)
    if value is None:
        raise RuntimeError('Required UE5.8 enum token is unavailable: ' + enum.__name__ + '.' + spelling)
    return value


def connect(ref, node, pin):
    source, output = ref
    # MaterialEditingLibrary compares shortened graph labels, not raw reflected
    # member names. UE5.8 UMaterialGraphNode::GetShortenPinName maps Input to
    # NAME_None, Coordinates to UVs and Exponent to Exp. Empty input names select
    # GetInput(0), which is the required input for our unary/transform nodes.
    actual_pin = {'Input': '', 'Coordinates': 'UVs',
                  'Exponent': 'Exp', 'TextureObject': 'Tex'}.get(pin, pin)
    if not LIB.connect_material_expressions(source, output, node, actual_pin):
        names = [str(value) for value in LIB.get_material_expression_input_names(node)]
        raise RuntimeError('Could not connect ' + node.get_class().get_name() +
                           '.' + repr(actual_pin) + '; available graph inputs: ' + repr(names))


def property_connect(ref, prop):
    if not LIB.connect_material_property(ref[0], ref[1], prop):
        raise RuntimeError('Could not connect shield material property ' + str(prop))


class Graph:
    def __init__(self, material):
        self.material = material
        self.count = 0
        self.texture_fetches = 0

    def node(self, cls, desc='', **properties):
        value = LIB.create_material_expression(self.material, cls)
        if not value:
            raise RuntimeError('Could not create material expression ' + cls.__name__)
        value.set_editor_property('desc', PREFIX + desc)
        for key, setting in properties.items():
            value.set_editor_property(key, setting)
        self.count += 1
        return value

    def scalar(self, value):
        return (self.node(unreal.MaterialExpressionConstant, 'scalar', r=float(value)), '')

    def color(self, value):
        return (self.node(unreal.MaterialExpressionConstant3Vector, 'linear colour',
                          constant=unreal.LinearColor(*value[:3], 1.0)), '')

    def binary(self, cls, left, right, left_pin='A', right_pin='B'):
        value = self.node(cls)
        connect(left, value, left_pin)
        connect(right, value, right_pin)
        return value, ''

    def add(self, left, right):
        return self.binary(unreal.MaterialExpressionAdd, left, right)

    def subtract(self, left, right):
        return self.binary(unreal.MaterialExpressionSubtract, left, right)

    def multiply(self, left, right):
        return self.binary(unreal.MaterialExpressionMultiply, left, right)

    def divide(self, left, right):
        return self.binary(unreal.MaterialExpressionDivide, left, right)

    def unary(self, cls, ref, pin='Input'):
        value = self.node(cls)
        connect(ref, value, pin)
        return value, ''

    def saturate(self, ref):
        return self.unary(unreal.MaterialExpressionSaturate, ref)

    def mask(self, ref, channels):
        value = self.node(unreal.MaterialExpressionComponentMask, 'component ' + channels,
                          r='R' in channels, g='G' in channels,
                          b='B' in channels, a='A' in channels)
        connect(ref, value, 'Input')
        return value, ''

    def lerp(self, left, right, amount):
        value = self.node(unreal.MaterialExpressionLinearInterpolate)
        connect(left, value, 'A')
        connect(right, value, 'B')
        connect(amount, value, 'Alpha')
        return value, ''

    def sample(self, texture, uv, role):
        sampler_type = {'base_color': unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                        'orm': unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                        'normal': unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL}[role]
        value = self.node(unreal.MaterialExpressionTextureSample, role + ' tile',
                          texture=texture, sampler_type=sampler_type,
                          sampler_source=enum_value(unreal.SamplerSourceMode,
                                                    'SSM_WRAP_WORLD_GROUP_SETTINGS'))
        connect(uv, value, 'UVs')
        self.texture_fetches += 1
        return value, 'RGB'

    def projection(self, tile_size):
        world = self.node(unreal.MaterialExpressionWorldPosition, 'absolute world position')
        position = self.node(unreal.MaterialExpressionTransformPosition, 'world to object position',
            transform_source_type=enum_value(unreal.MaterialPositionTransformSource, 'TRANSFORMPOSSOURCE_WORLD'),
            transform_type=enum_value(unreal.MaterialPositionTransformSource, 'TRANSFORMPOSSOURCE_LOCAL'))
        connect((world, ''), position, 'Input')
        local_position = position, ''
        uv_position = self.multiply(local_position, self.scalar(1.0 / tile_size))
        normal = self.node(unreal.MaterialExpressionVertexNormalWS, 'geometric vertex normal')
        local_normal = self.node(unreal.MaterialExpressionTransform, 'world to object normal',
            transform_source_type=enum_value(unreal.MaterialVectorCoordTransformSource, 'TRANSFORMSOURCE_WORLD'),
            transform_type=enum_value(unreal.MaterialVectorCoordTransform, 'TRANSFORM_LOCAL'))
        connect((normal, ''), local_normal, 'Input')
        absolute = self.unary(unreal.MaterialExpressionAbs, (local_normal, ''))
        squared = self.multiply(absolute, absolute)
        sharp = self.multiply(squared, squared)
        weight_components = [self.mask(sharp, channel) for channel in 'RGB']
        total = self.add(self.add(weight_components[0], weight_components[1]), weight_components[2])
        total = self.add(total, self.scalar(0.00001))
        weights = [self.divide(component, total) for component in weight_components]
        # X normal uses the YZ plane; Y normal uses XZ; Z normal uses XY.
        uvs = [self.mask(uv_position, channels) for channels in ('GB', 'RB', 'RG')]
        return local_position, uvs, weights

    def triplanar(self, texture, role, uvs, weights):
        terms = [self.multiply(self.sample(texture, uv, role), weight)
                 for uv, weight in zip(uvs, weights)]
        return self.add(self.add(terms[0], terms[1]), terms[2])


textures, texture_records = {}, []
for profile_name, profile in PROFILES.items():
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', profile_name):
        raise RuntimeError('Profile names must be safe ASCII asset names.')
    profile_textures = {}
    tile_size = float(profile.get('tile_size_cm', 12.0))
    if not 1.0 <= tile_size <= 100.0:
        raise RuntimeError('Surface tile_size_cm must be between 1 and 100.')
    for role in ('base_color', 'orm', 'normal'):
        path = source_file(profile[role])
        suffix = {'base_color': 'BaseColor', 'orm': 'ORM', 'normal': 'Normal'}[role]
        name = 'T_DragonShield_' + profile_name.capitalize() + '_' + suffix
        destination = TEX_ROOT + '/' + name
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', str(path))
        task.set_editor_property('destination_path', TEX_ROOT)
        task.set_editor_property('destination_name', name)
        task.set_editor_property('automated', True)
        task.set_editor_property('replace_existing', True)
        task.set_editor_property('save', False)
        TOOLS.import_asset_tasks([task])
        image = A.load_asset(destination)
        if not isinstance(image, unreal.Texture2D):
            raise RuntimeError('Surface texture import failed: ' + str(path))
        image.set_editor_property('srgb', role == 'base_color')
        image.set_editor_property('compression_settings',
            unreal.TextureCompressionSettings.TC_NORMALMAP if role == 'normal' else
            unreal.TextureCompressionSettings.TC_MASKS if role == 'orm' else
            unreal.TextureCompressionSettings.TC_DEFAULT)
        convention = str(profile.get('normal_convention', 'OpenGL')).lower()
        if convention not in ('opengl', 'directx'):
            raise RuntimeError('Normal convention must be OpenGL or DirectX.')
        image.set_editor_property('flip_green_channel', role == 'normal' and convention == 'opengl')
        image.set_editor_property('address_x', unreal.TextureAddress.TA_WRAP)
        image.set_editor_property('address_y', unreal.TextureAddress.TA_WRAP)
        save(image)
        profile_textures[role] = image
        texture_records.append({'profile': profile_name, 'role': role,
            'source': str(path), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'asset': destination, 'srgb': role == 'base_color',
            'packed_channels': 'R=AO, G=roughness, B=metallic' if role == 'orm' else None,
            'normal_convention': convention if role == 'normal' else None,
            'flip_green_channel': role == 'normal' and convention == 'opengl'})
    textures[profile_name] = profile_textures

material_records = []
reference_colors = {'bronze': (.23309, .16618, .07098),
                    'jade': (.05458, .12901, .10420),
                    'leather': (.11952, .05478, .02789)}
for name in EXPECTED:
    material = A.load_asset(ROOT + '/Materials/' + name)
    if not isinstance(material, unreal.Material):
        raise RuntimeError('Existing shield material is missing: ' + name)
    entry = ENTRIES[name]
    profile_name = MAPPING[name]
    profile = PROFILES[profile_name]
    images = textures[profile_name]
    is_face = name == 'M_DragonShield_07'
    original_base = original_normal = None
    if is_face:
        original_base = LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
        original_normal = LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_NORMAL)
        if not isinstance(original_base, unreal.MaterialExpressionTextureSample) or not original_normal:
            raise RuntimeError('The original dragon face base/normal graph must be present.')
        if original_base.get_editor_property('texture').get_path_name() != ROOT + '/Textures/T_DragonShield_07_BaseColor.T_DragonShield_07_BaseColor':
            raise RuntimeError('Refusing to modify a dragon face with an unexpected original base texture.')
        # Remove only this author's previous generated nodes on repeat execution.
        for old_node in list(LIB.get_material_expressions(material)):
            if str(old_node.get_editor_property('desc')).startswith(PREFIX):
                LIB.delete_material_expression(material, old_node)
    else:
        LIB.delete_all_material_expressions(material)
    graph = Graph(material)
    local_position, uvs, weights = graph.projection(float(profile.get('tile_size_cm', 12.0)))
    orm = graph.triplanar(images['orm'], 'orm', uvs, weights)
    ao = graph.lerp(graph.scalar(.93), graph.scalar(1.0), graph.mask(orm, 'R'))
    property_connect(ao, unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    if is_face:
        # Bronze/gold parts of the retained image reflect more than green oxide.
        original_output = LIB.get_material_property_input_node_output_name(material, unreal.MaterialProperty.MP_BASE_COLOR)
        base = original_base, original_output
        gold = graph.subtract(graph.mask(base, 'R'), graph.mask(base, 'G'))
        gold = graph.saturate(graph.add(graph.multiply(gold, graph.scalar(4.0)), graph.scalar(.30)))
        image_metal = graph.lerp(graph.scalar(.06), graph.scalar(.82), gold)
        # The retained face image distinguishes raised bronze from green oxide.
        # Its metal identity is independent of the supplementary tile profile.
        metallic = image_metal
        roughness = graph.lerp(graph.scalar(.74), graph.scalar(.43), gold)
        micro_variation = graph.multiply(graph.subtract(graph.mask(orm, 'G'), graph.scalar(.5)), graph.scalar(.10))
        roughness = graph.saturate(graph.add(roughness, micro_variation))
        normal_strength = float(entry.get('normal_strength', .18))
    else:
        base = graph.triplanar(images['base_color'], 'base_color', uvs, weights)
        # A dedicated profile copies this slot's original palette; it needs no
        # second tint. A shared neutral profile can opt into relative tinting.
        reference = profile.get('reference_color_linear', reference_colors.get(profile_name, entry['color'][:3]))
        tint = ([1.0, 1.0, 1.0] if profile.get('source_material') else
                [max(.35, min(1.9, entry['color'][i] / max(.01, float(reference[i])))) for i in range(3)])
        base = graph.multiply(base, graph.color(tint))
        roughness = graph.mask(orm, 'G')
        is_metal_profile = float(profile.get('base_metallic', 1.0 if 'bronze' in profile_name or profile_name == 'brass' else 0.0)) > .5
        metallic = graph.mask(orm, 'B') if is_metal_profile else graph.scalar(0.0)
        rim_wear = name in ('M_DragonShield_00', 'M_DragonShield_01', 'M_DragonShield_06')
        if rim_wear:
            radial = graph.unary(unreal.MaterialExpressionLength, graph.mask(local_position, 'GB'))
            rim = graph.saturate(graph.divide(graph.subtract(radial, graph.scalar(20.7)), graph.scalar(1.9)))
            base = graph.multiply(base, graph.add(graph.scalar(1.0), graph.multiply(rim, graph.scalar(.12))))
            roughness = graph.subtract(roughness, graph.multiply(rim, graph.scalar(.06)))
        roughness = graph.saturate(roughness)
        property_connect(base, unreal.MaterialProperty.MP_BASE_COLOR)
        uv = graph.node(unreal.MaterialExpressionTextureCoordinate, 'UV0 fine normal only',
                        coordinate_index=0,
                        u_tiling=float(profile.get('normal_uv_tiling', 3.0)),
                        v_tiling=float(profile.get('normal_uv_tiling', 3.0)))
        normal = graph.sample(images['normal'], (uv, ''), 'normal')
        normal_strength = float(profile.get('normal_strength',
                               {'bronze': .12, 'jade': .07, 'leather': .20}.get(profile_name, .10)))
        normal_strength = max(0.0, min(.35, normal_strength))
        normal = graph.lerp(graph.color((0.0, 0.0, 1.0)), normal, graph.scalar(normal_strength))
        normal = graph.unary(unreal.MaterialExpressionNormalize, normal, 'VectorInput')
        property_connect(normal, unreal.MaterialProperty.MP_NORMAL)
    property_connect(metallic, unreal.MaterialProperty.MP_METALLIC)
    property_connect(roughness, unreal.MaterialProperty.MP_ROUGHNESS)
    property_connect(graph.scalar(.35 if profile_name == 'leather' else .5), unreal.MaterialProperty.MP_SPECULAR)
    if is_face:
        if (LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR) != original_base or
            LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_NORMAL) != original_normal):
            raise RuntimeError('The retained dragon base/normal graph changed unexpectedly.')
    LIB.layout_material_expressions(material)
    compile_errors = [str(error) for error in LIB.recompile_material(material)]
    if compile_errors:
        raise RuntimeError('Shield material compilation failed for ' + name + ': ' + '; '.join(compile_errors))
    save(material)
    material_records.append({'asset': material.get_path_name(), 'profile': profile_name,
        'object_local_triplanar': True,
        'tile_size_cm': float(profile.get('tile_size_cm', 12.0)),
        'blend_weights': 'abs(local vertex normal)^4 / sum(weights)',
        'normal_mapping': 'Original face UV1 retained' if is_face else 'Fine tile in existing UV0',
        'normal_strength': normal_strength,
        'dragon_image_graph_preserved': is_face,
        'texture_fetch_count': graph.texture_fetches + (2 if is_face else 0),
        'new_expression_count': graph.count,
        'material_recompile_errors': compile_errors,
        'rim_position_wear': name in ('M_DragonShield_00', 'M_DragonShield_01', 'M_DragonShield_06'),
        'metallic_policy': 'Original-image gold vs green oxide mask' if is_face else
                           'Packed ORM exposed bronze/brass and oxide mask' if is_metal_profile else 'Dielectric 0'})
    unreal.log('SHIELD_REALISTIC_MATERIAL_SAVED ' + name)

report = {'module': 'ART-SHIELD-REALISTIC', 'manifest': str(MANIFEST),
    'textures': texture_records, 'materials': material_records,
    'changed_assets': [record['asset'] for record in texture_records] +
                      [record['asset'] for record in material_records],
    'limits': ['Surface colour and packed masks use object-local triplanar projection; fine normals use existing UV0.',
               'The dragon front retains the supplied image and 0.18-strength UV1 normal; no new sculpted relief.',
               'Position-based outer rim wear is an approximation; no baked curvature or new mesh geometry.',
               'Texture sample counts are graph counts, not a measured GPU timing.',
               'Visual lighting and actual VR performance remain pending user review.'],
    'scope': 'Only shield materials and new surface textures saved. No mesh, transforms, damage, source blend, maps, gameplay or tests changed.',
    'source_notes': DATA.get('notes', [])}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('SHIELD_REALISTIC_MATERIALS_COMPLETE ' + str(REPORT))
