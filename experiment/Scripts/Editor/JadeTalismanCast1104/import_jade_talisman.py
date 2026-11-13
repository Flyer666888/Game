"""Import the validated jade talisman and author its UE material package."""

import hashlib
import json
from pathlib import Path
import traceback

import unreal


PROJECT = Path(unreal.Paths.project_dir()).resolve()
SOURCE = PROJECT / "ArtSource/Weapons/TalismanJade1104"
OUTPUT = PROJECT / "Docs/Gameplay/JadeTalismanCast1104/Import.json"
DEST = "/Game/ReversedScale/Weapons/TalismanJade1104"
MESH_NAME = "SM_Nilin_JadeTalisman"
PAPER_NAME = "M_JadeTalisman_PaperAndFoil"
BRASS_NAME = "M_JadeTalisman_GildedBrass"
JADE_NAME = "M_JadeTalisman_PolishedJade"
ORB_NAME = "M_TalismanGoldenOrb"
TEXTURES = {
    "paper": ("T_JadeTalisman_BaseColor", True),
    "metal_rough": ("T_JadeTalisman_MetalRough", False),
    "emissive": ("T_JadeTalisman_Emissive", True),
    "jade": ("T_JadeSeal_BaseColor", True),
}
EDITOR_ASSETS = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
GRAPH = unreal.MaterialEditingLibrary
PROPS = unreal.MaterialProperty


def import_task(path, name, folder=DEST):
    task = unreal.AssetImportTask()
    task.filename = str(path)
    task.destination_path = folder
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.replace_existing_settings = True
    task.save = False
    return task


def save(asset):
    assert EDITOR_ASSETS.save_loaded_asset(asset, False), asset.get_path_name()
    asset_path = asset.get_path_name().split(".", 1)[0]
    disk_path = PROJECT / "Content" / (asset_path.removeprefix("/Game/") + ".uasset")
    assert disk_path.is_file() and disk_path.stat().st_size > 0, str(disk_path)


def make_material(name, unlit=False):
    path = DEST + "/" + name
    material = EDITOR_ASSETS.load_asset(path) if EDITOR_ASSETS.does_asset_exist(path) else (
        TOOLS.create_asset(name, DEST, unreal.Material, unreal.MaterialFactoryNew())
    )
    assert isinstance(material, unreal.Material), path
    GRAPH.delete_all_material_expressions(material)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT if unlit
                                 else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("two_sided", False)
    return material


def node(material, expression, **properties):
    expression = GRAPH.create_material_expression(material, expression)
    assert expression is not None
    for key, value in properties.items():
        expression.set_editor_property(key, value)
    return expression


def link(source, output, target, pin):
    assert GRAPH.connect_material_expressions(source, output, target, pin), (source, output, target, pin)


def output(expression, property_name, channel=""):
    assert GRAPH.connect_material_property(expression, channel, property_name), (expression, property_name)


def scalar(material, value):
    return node(material, unreal.MaterialExpressionConstant, r=value)


def rgb(material, color):
    return node(material, unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*color, 1))


def texture_sample(material, texture, srgb=True):
    return node(material, unreal.MaterialExpressionTextureSample, texture=texture,
                sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if srgb else
                unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)


def finish_material(material):
    GRAPH.layout_material_expressions(material)
    GRAPH.recompile_material(material)
    save(material)
    return material


def load_textures():
    tasks = [import_task(SOURCE / (name + ".png"), name, DEST + "/Textures")
             for name, _ in TEXTURES.values()]
    TOOLS.import_asset_tasks(tasks)
    textures = {}
    for (role, (name, srgb)), task in zip(TEXTURES.items(), tasks):
        assert task.imported_object_paths, str(task.filename)
        texture = EDITOR_ASSETS.load_asset(DEST + "/Textures/" + name)
        assert isinstance(texture, unreal.Texture2D), task.imported_object_paths
        texture.set_editor_property("srgb", srgb)
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT if srgb
                                    else unreal.TextureCompressionSettings.TC_MASKS)
        texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
        texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
        save(texture)
        textures[role] = texture
    return textures


def build_paper(textures):
    material = make_material(PAPER_NAME)
    surface = texture_sample(material, textures["paper"])
    masks = texture_sample(material, textures["metal_rough"], srgb=False)
    emit = texture_sample(material, textures["emissive"])
    glow = node(material, unreal.MaterialExpressionMultiply, const_b=.2)
    link(emit, "RGB", glow, "A")
    output(surface, PROPS.MP_BASE_COLOR, "RGB")
    output(masks, PROPS.MP_METALLIC, "B")
    output(masks, PROPS.MP_ROUGHNESS, "G")
    output(glow, PROPS.MP_EMISSIVE_COLOR)
    return finish_material(material)


def build_brass():
    material = make_material(BRASS_NAME)
    output(rgb(material, (.79, .44, .13)), PROPS.MP_BASE_COLOR)
    output(scalar(material, .86), PROPS.MP_METALLIC)
    output(scalar(material, .27), PROPS.MP_ROUGHNESS)
    return finish_material(material)


def build_jade(textures):
    material = make_material(JADE_NAME)
    output(texture_sample(material, textures["jade"]), PROPS.MP_BASE_COLOR, "RGB")
    output(scalar(material, .25), PROPS.MP_ROUGHNESS)
    output(scalar(material, .49), PROPS.MP_SPECULAR)
    output(rgb(material, (.007, .029, .014)), PROPS.MP_EMISSIVE_COLOR)
    return finish_material(material)


def build_orb():
    material = make_material(ORB_NAME, unlit=True)
    tint = node(material, unreal.MaterialExpressionVectorParameter, parameter_name="Color",
                default_value=unreal.LinearColor(1.0, .61, .13, 1.0))
    intensity = node(material, unreal.MaterialExpressionScalarParameter, parameter_name="GlowStrength",
                     default_value=1.1)
    bounded_intensity = node(material, unreal.MaterialExpressionClamp, min_default=.25, max_default=1.8)
    link(intensity, "", bounded_intensity, "")
    core = node(material, unreal.MaterialExpressionMultiply, const_b=1.36)
    link(tint, "RGB", core, "A")
    edge = node(material, unreal.MaterialExpressionMultiply)
    link(tint, "RGB", edge, "A")
    link(rgb(material, (.80, .48, .35)), "", edge, "B")
    fresnel = node(material, unreal.MaterialExpressionFresnel, exponent=2.35, base_reflect_fraction=0.0)
    profile = node(material, unreal.MaterialExpressionLinearInterpolate)
    link(core, "", profile, "A")
    link(edge, "", profile, "B")
    link(fresnel, "", profile, "Alpha")
    emissive = node(material, unreal.MaterialExpressionMultiply)
    link(profile, "", emissive, "A")
    link(bounded_intensity, "", emissive, "B")
    output(emissive, PROPS.MP_EMISSIVE_COLOR)
    return finish_material(material)


def import_mesh(fbx):
    unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    task = import_task(fbx, MESH_NAME)
    options = unreal.FbxImportUI()
    options.automated_import_should_detect_type = False
    options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    options.import_as_skeletal = False
    options.import_mesh = True
    options.import_animations = False
    options.import_materials = False
    options.import_textures = False
    data = options.static_mesh_import_data
    data.combine_meshes = True
    data.convert_scene = True
    data.convert_scene_unit = True
    data.force_front_x_axis = True
    data.import_uniform_scale = 1.0
    data.auto_generate_collision = False
    data.build_nanite = False
    data.generate_lightmap_u_vs = False
    data.remove_degenerates = False
    data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    data.normal_generation_method = unreal.FBXNormalGenerationMethod.MIKK_T_SPACE
    task.options = options
    TOOLS.import_asset_tasks([task])
    assert task.imported_object_paths, str(fbx)
    mesh = EDITOR_ASSETS.load_asset(DEST + "/" + MESH_NAME)
    assert isinstance(mesh, unreal.StaticMesh), task.imported_object_paths
    return mesh


def vector_values(value):
    return [value.x, value.y, value.z]


def validate_mesh(mesh, reference):
    bounds = mesh.get_bounds()
    dimensions = [2 * size for size in vector_values(bounds.box_extent)]
    expected = [meters * 100 for meters in reference["dimensions_m"]]
    assert abs(dimensions[2] - expected[2]) < .08, (dimensions, expected)
    assert all(abs(a - b) < .08 for a, b in zip(sorted(dimensions), sorted(expected))), (dimensions, expected)
    triangles = mesh.get_num_triangles(0)
    source_triangles = reference["triangles"]
    assert triangles in (source_triangles, source_triangles - 4), (triangles, source_triangles)
    assert mesh.get_num_tex_coords(0) >= 1
    return {"bounds_origin_cm": vector_values(bounds.origin), "dimensions_cm": dimensions,
            "triangles": triangles, "source_triangles": source_triangles,
            "source_triangle_difference": source_triangles - triangles,
            "uv_channels": mesh.get_num_tex_coords(0),
            "thin_axis": ["X", "Y", "Z"][dimensions.index(min(dimensions))],
            "force_front_x_axis": True}


def measure_front(mesh, dimensions):
    """Measure the seal protrusion relative to the nearby paper in UE coordinates."""
    try:
        description = mesh.get_static_mesh_description(0)
        regions = []
        for index in range(description.get_polygon_group_count()):
            group_id = unreal.PolygonGroupID(id_value=index)
            positions = set()
            for polygon in description.get_polygon_group_polygons(group_id):
                for vertex_id in description.get_polygon_vertices(polygon):
                    positions.add(tuple(vector_values(description.get_vertex_position(vertex_id))))
            if positions:
                regions.append(positions)
        assert len(regions) == 3, len(regions)
        def height(region):
            return max(point[2] for point in region) - min(point[2] for point in region)

        sheets = [region for region in regions if height(region) >= dimensions[2] * .9]
        assert len(sheets) == 1, "Expected exactly one full-height paper group"
        paper = sheets[0]
        thin_axis = dimensions.index(min(dimensions))
        wide_axis = 1 - thin_axis
        seal = [point for region in regions if region is not paper for point in region]
        center = [sum(point[axis] for point in seal) / len(seal) for axis in range(3)]
        nearby = [point for point in paper if abs(point[wide_axis] - center[wide_axis]) < .45
                  and abs(point[2] - center[2]) < .55]
        assert nearby
        delta = center[thin_axis] - sum(point[thin_axis] for point in nearby) / len(nearby)
        return {"seal_center_cm": center, "signed_seal_offset_cm": delta,
                "front_axis": ("+" if delta > 0 else "-") + ["X", "Y"][thin_axis]}
    except Exception as error:
        # Bounds are verified separately. An editor build can omit mesh-description bindings.
        return {"unavailable": str(error)}


def bind_materials(mesh, materials):
    bindings = []
    for index, slot in enumerate(mesh.static_materials):
        imported_name = str(slot.get_editor_property("imported_material_slot_name"))
        slot_name = str(slot.material_slot_name)
        key = imported_name if imported_name in materials else slot_name
        assert key in materials, (index, imported_name, slot_name)
        mesh.set_material(index, materials[key])
        bindings.append({"index": index, "slot": slot_name, "imported_slot": imported_name,
                         "material": materials[key].get_path_name()})
    assert len(bindings) == len(materials) == len({item["material"] for item in bindings})
    for binding in bindings:
        assert mesh.get_material(binding["index"]).get_path_name() == binding["material"], binding
    return bindings


def source_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
    reference = json.loads((SOURCE / "AssetValidation.json").read_text(encoding="utf-8"))
    assert reference["state"] == "validated"
    fbx = SOURCE / (MESH_NAME + ".fbx")
    paths = [fbx] + [SOURCE / (name + ".png") for name, _ in TEXTURES.values()]
    hashes = {path.name: source_hash(path) for path in paths}
    assert hashes == {path.name: reference["sha256"][path.name] for path in paths}
    mesh = import_mesh(fbx)
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    settings = subsystem.get_lod_build_settings(mesh, 0)
    settings.remove_degenerates = False
    subsystem.set_lod_build_settings(mesh, 0, settings)
    mesh_report = validate_mesh(mesh, reference)
    mesh_report["remove_degenerates"] = subsystem.get_lod_build_settings(mesh, 0).remove_degenerates
    mesh_report["front_probe"] = measure_front(mesh, mesh_report["dimensions_cm"])
    textures = load_textures()
    materials = {
        PAPER_NAME: build_paper(textures),
        BRASS_NAME: build_brass(),
        JADE_NAME: build_jade(textures),
    }
    orb = build_orb()
    bindings = bind_materials(mesh, materials)
    subsystem.remove_collisions(mesh)
    mesh.set_editor_property("bHasNavigationData", False)
    save(mesh)
    assert hashes == {path.name: source_hash(path) for path in paths}
    return {"state": "passed", "asset": mesh.get_path_name(), "mesh": mesh_report, "materials": bindings,
            "textures": {role: texture.get_path_name() for role, texture in textures.items()},
            "orb": {"material": orb.get_path_name(), "color_parameter": "Color",
                    "color_default_linear": [1.0, .61, .13, 1.0], "glow_parameter": "GlowStrength",
                    "glow_default": 1.1, "glow_clamp": [.25, 1.8]},
            "sha256": hashes, "validated_in_unreal": True}


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
try:
    result = main()
except Exception:
    OUTPUT.write_text(json.dumps({"state": "failed", "traceback": traceback.format_exc()}, indent=2),
                      encoding="utf-8")
    raise
OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
unreal.log("Validated jade talisman package: " + result["asset"])
