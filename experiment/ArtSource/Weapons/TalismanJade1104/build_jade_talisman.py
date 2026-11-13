"""Build the gold-foil and jade seal variant of the Nilin paper talisman."""
import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
ATLAS = ROOT / "T_JadeTalisman_BaseColor.png"
WIDTH = 0.065
HEIGHT = 0.160
THICKNESS = 0.00032
NX, NZ = 10, 30
SHEET_VERTS = (NX + 1) * (NZ + 1)
NAME = "SM_Nilin_JadeTalisman"


def index(i, j):
    return j * (NX + 1) + i


def point(u, v, side):
    # The creases taper into the sheet and the bottom corners curl independently.
    left_edge = .00044 * math.sin(v * 18) + .00019 * math.sin(v * 61) + .00012 * math.sin(v * 137)
    right_edge = .00035 * math.sin(v * 23 + .8) + .00022 * math.sin(v * 43) + .00010 * math.sin(v * 109)
    x = (u - .5) * WIDTH + (1 - u) * left_edge + u * right_edge
    notch = .0038 * max(0, 1 - abs(u - .8) * 12)
    z = (v - .5) * HEIGHT + (1 - v)**18 * (notch + .0008 * math.sin(u * 33))
    z += v**17 * (.00035 * math.sin(u * 19) - .0015 * u**7)
    y = .0045 * math.sin((v - .10) * math.tau)
    y += .006 * (u - .5)**2 + .008 * (u - .5) * (v - .5)
    y += .010 * (1 - v)**7 * (.15 + .85 * u) - .007 * v**8 * (1 - u)
    y += .0011 * math.exp(-((v - .35 - .025 * (u - .5)) / .024)**2)
    return x, y + side * THICKNESS / 2, z


def paper_mesh():
    vertices = [point(i / NX, j / NZ, side)
                for side in (-1, 1) for j in range(NZ + 1) for i in range(NX + 1)]
    faces = []
    for side in range(2):
        offset = side * SHEET_VERTS
        for j in range(NZ):
            for i in range(NX):
                quad = [offset + index(a, b) for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))]
                faces.append(quad if side == 0 else quad[::-1])
    boundary = ([index(i, 0) for i in range(NX)] + [index(NX, j) for j in range(NZ)]
                + [index(i, NZ) for i in range(NX, 0, -1)] + [index(0, j) for j in range(NZ, 0, -1)])
    for a, b in zip(boundary, boundary[1:] + boundary[:1]):
        faces.append([b, a, a + SHEET_VERTS, b + SHEET_VERTS])
    mesh = bpy.data.meshes.new(NAME)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    assert not mesh.validate(), "Generated geometry required repair"
    bm = bmesh.new()
    bm.from_mesh(mesh)
    assert all(edge.is_manifold for edge in bm.edges)
    bm.free()
    uv = mesh.uv_layers.new(name="PaperAtlas")
    for polygon in mesh.polygons:
        is_edge = polygon.index >= 2 * NX * NZ
        polygon.use_smooth = not is_edge
        for loop_index in polygon.loop_indices:
            vertex = mesh.loops[loop_index].vertex_index
            back = vertex >= SHEET_VERTS
            j, i = divmod(vertex % SHEET_VERTS, NX + 1)
            u, v = i / NX, j / NZ
            if is_edge:
                uv.data[loop_index].uv = ((1008 + 32 * int(back)) / 2048, .08 + .84 * v)
            else:
                pixel_x = 1072 + 960 * (1 - u) if back else 16 + 960 * u
                uv.data[loop_index].uv = (pixel_x / 2048, (16 + 2016 * v) / 2048)
    return mesh


def image_node(material, filename, location, noncolor=False):
    node = material.node_tree.nodes.new("ShaderNodeTexImage")
    node.label = filename
    node.location = location
    node.image = bpy.data.images.load(str(ROOT / filename))
    if noncolor:
        node.image.colorspace_settings.name = "Non-Color"
    node.image.pack()
    return node


def surface(name, color, roughness, metallic=0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = color
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return material, shader


def seal_coordinate(x, z, depth):
    return anchor + seal_right * x + seal_up * z + seal_front * depth


def seal_disk(name, profile, material, lobes=0):
    sides = 48
    vertices = []
    uv_values = []
    for radius, depth in profile:
        for side in range(sides):
            angle = math.tau * side / sides
            r = radius * (1 + lobes * math.cos(8 * angle))
            x, z = r * math.cos(angle), r * math.sin(angle)
            vertices.append(seal_coordinate(x, z, depth))
            uv_values.append((.5 + x / .016, .5 + z / .016))
    faces = [tuple(range(sides - 1, -1, -1))]
    for layer in range(len(profile) - 1):
        for side in range(sides):
            a, b = layer * sides + side, layer * sides + (side + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.append(tuple(range(len(vertices) - sides, len(vertices))))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    uv = mesh.uv_layers.new(name="PaperAtlas")
    for polygon in mesh.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
        for loop_index in polygon.loop_indices:
            uv.data[loop_index].uv = uv_values[mesh.loops[loop_index].vertex_index]
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    asset.objects.link(obj)
    return obj


def seal_cloud(material):
    curve = bpy.data.curves.new("Gold cloud relief", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 5
    curve.bevel_depth = .00016
    curve.bevel_resolution = 2
    curve.use_fill_caps = True
    paths = [
        [(-.0040, -.0010), (-.0033, .00045), (-.0021, .00055), (-.00135, .00162),
         (.00005, .0020), (.00128, .00142), (.0019, .0001), (.0032, .0001), (.0038, -.00083)],
        [(-.0033, -.00165), (-.0014, -.00140), (.0002, -.00185), (.0018, -.00148), (.00345, -.00165)],
        [(-.0007, .00055), (.00025, .0010), (.00092, .0005), (.00046, -.00012)],
    ]
    for coordinates in paths:
        spline = curve.splines.new("BEZIER")
        spline.bezier_points.add(len(coordinates) - 1)
        for control, (x, z) in zip(spline.bezier_points, coordinates):
            depth = .00260 - .00076 * (x * x + z * z) / .0065**2
            control.co = seal_coordinate(x, z, depth)
            control.handle_left_type = control.handle_right_type = "AUTO"
    obj = bpy.data.objects.new("Embossed cloud insignia", curve)
    asset.objects.link(obj)
    obj.data.materials.append(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    return bpy.context.object


def area(scene, name, position, energy, size, color):
    light = bpy.data.lights.new(name, "AREA")
    light.energy, light.shape, light.size, light.color = energy, "DISK", size, color
    obj = bpy.data.objects.new(name, light)
    studio.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (-obj.location).to_track_quat("-Z", "Y").to_euler()


def render(scene, name, position, target=(0, 0, 0), scale=.206):
    camera.location = position
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = scale
    scene.render.filepath = str(ROOT / name)
    bpy.ops.render.render(write_still=True)


assert ATLAS.is_file(), ATLAS
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
asset = bpy.data.collections.new("Talisman")
studio = bpy.data.collections.new("Studio")
scene.collection.children.link(asset)
scene.collection.children.link(studio)
mesh = paper_mesh()
model = bpy.data.objects.new(NAME, mesh)
asset.objects.link(model)
model["purpose"] = "Paper talisman for the Nilin ranged caster"
model["axis_convention"] = "Z = long axis, -Y = printed front, centered pivot"
material, principled = surface("M_JadeTalisman_PaperAndFoil", (.67, .43, .13, 1), .77)
texture = image_node(material, ATLAS.name, (-620, 340))
metal_rough = image_node(material, "T_JadeTalisman_MetalRough.png", (-620, 50), True)
emission = image_node(material, "T_JadeTalisman_Emissive.png", (-620, -270))
channels = material.node_tree.nodes.new("ShaderNodeSeparateColor")
channels.location = (-300, 50)
links = material.node_tree.links
links.new(texture.outputs["Color"], principled.inputs["Base Color"])
links.new(metal_rough.outputs["Color"], channels.inputs["Color"])
links.new(channels.outputs["Green"], principled.inputs["Roughness"])
links.new(channels.outputs["Blue"], principled.inputs["Metallic"])
links.new(emission.outputs["Color"], principled.inputs["Emission Color"])
principled.inputs["Emission Strength"].default_value = .62
mesh.materials.append(material)

gold, gold_shader = surface("M_JadeTalisman_GildedBrass", (.79, .44, .13, 1), .27, .86)
jade, jade_shader = surface("M_JadeTalisman_PolishedJade", (.10, .39, .23, 1), .25)
jade_texture = image_node(jade, "T_JadeSeal_BaseColor.png", (-400, 170))
jade.node_tree.links.new(jade_texture.outputs["Color"], jade_shader.inputs["Base Color"])
jade_shader.inputs["IOR"].default_value = 1.61
jade_shader.inputs["Coat Weight"].default_value = .33
jade_shader.inputs["Coat Roughness"].default_value = .22
jade_shader.inputs["Subsurface Weight"].default_value = .11
jade_shader.inputs["Subsurface Scale"].default_value = .0014
jade_shader.inputs["Emission Color"].default_value = (.035, .18, .09, 1)
jade_shader.inputs["Emission Strength"].default_value = .16

anchor = Vector(point(.5, .86, -1))
seal_right = (Vector(point(.56, .86, -1)) - Vector(point(.44, .86, -1))).normalized()
seal_up = (Vector(point(.5, .9, -1)) - Vector(point(.5, .82, -1))).normalized()
seal_front = seal_right.cross(seal_up).normalized()
seal_up = seal_front.cross(seal_right).normalized()
rim = seal_disk("Scalloped gold bezel",
    [(.00725, .00006), (.00765, .00022), (.00778, .00050), (.00770, .00096),
     (.00735, .00132), (.00635, .00132), (.00611, .00100)], gold, .035)
gem = seal_disk("Domed green jade",
    [(.00610, .00078), (.00649, .00128), (.00630, .00160), (.00490, .00209),
     (.00275, .00243), (.00095, .00251)], jade)
cloud = seal_cloud(gold)
bpy.ops.object.select_all(action="DESELECT")
for obj in (model, rim, gem, cloud):
    obj.select_set(True)
bpy.context.view_layer.objects.active = model
bpy.ops.object.join()
bpy.context.view_layer.update()
mesh = model.data
mesh.calc_loop_triangles()
triangles = len(mesh.loop_triangles)
dimensions = list(model.dimensions)
assert triangles < 5000 and .062 < dimensions[0] < .069 and .156 < dimensions[2] < .164
assert len(mesh.materials) == 3

bpy.ops.export_scene.gltf(filepath=str(ROOT / (NAME + ".glb")), export_format="GLB",
                          use_selection=True, export_animations=False)
bpy.ops.export_scene.fbx(filepath=str(ROOT / (NAME + ".fbx")), use_selection=True,
                         object_types={"MESH"}, axis_forward="-Y", axis_up="Z",
                         apply_unit_scale=True, path_mode="COPY", embed_textures=True)

scene.world = bpy.data.worlds.new("Studio ambience")
scene.world.use_nodes = True
scene.world.node_tree.nodes.get("Background").inputs[0].default_value = (.24, .27, .32, 1)
scene.world.node_tree.nodes.get("Background").inputs[1].default_value = .3
area(scene, "Warm paper key", (-.13, -.22, .18), 4.1, .19, (1.0, .87, .68))
area(scene, "Cool front fill", (.14, -.14, -.06), 1.65, .20, (.67, .81, 1.0))
area(scene, "Back key", (-.11, .18, .13), 4.2, .20, (1.0, .94, .83))
area(scene, "Thin edge rim", (.17, .07, .03), 2.5, .09, (1.0, .76, .40))
camera = bpy.data.objects.new("Talisman Camera", bpy.data.cameras.new("Talisman Camera"))
studio.objects.link(camera)
camera.data.type = "ORTHO"
scene.camera = camera
scene.render.engine = "CYCLES"
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 760
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.exposure = -.65
render(scene, "Render_Front.png", (.105, -.42, .06), scale=.200)
render(scene, "Render_Back.png", (.19, .35, .09), scale=.204)
scene.render.resolution_x = scene.render.resolution_y = 720
render(scene, "Render_Seal.png", (.10, -.31, .13), target=anchor, scale=.039)
scene.render.resolution_x = 760
scene.render.resolution_y = 1000
camera.data.ortho_scale = .200
camera.location = (.10, -.42, .06)
camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
for screen in bpy.data.screens:
    for viewport in screen.areas:
        if viewport.type == "VIEW_3D":
            viewport.spaces.active.region_3d.view_distance = .29
            viewport.spaces.active.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            viewport.spaces.active.shading.type = "MATERIAL"
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / (NAME + ".blend")), compress=True)

roundtrip = {}
for extension in ("glb", "fbx"):
    bpy.ops.object.select_all(action="DESELECT")
    existing = set(bpy.data.objects)
    path = str(ROOT / (NAME + "." + extension))
    if extension == "glb":
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)
    imported, = [obj for obj in bpy.data.objects if obj not in existing and obj.type == "MESH"]
    bpy.context.view_layer.update()
    imported.data.calc_loop_triangles()
    assert len(imported.data.loop_triangles) == triangles
    assert len(imported.data.uv_layers) and len(imported.data.materials) == 3
    images = [node.image for material in imported.data.materials for node in material.node_tree.nodes
              if node.type == "TEX_IMAGE" and node.image]
    assert any(list(image.size) == [2048, 2048] for image in images)
    assert max(abs(a - b) for a, b in zip(sorted(imported.dimensions), sorted(dimensions))) < .0001
    roundtrip[extension] = {"triangles": len(imported.data.loop_triangles),
                            "dimensions_m": list(imported.dimensions), "atlas_px": [2048, 2048]}
    for obj in set(bpy.data.objects) - existing:
        bpy.data.objects.remove(obj, do_unlink=True)

outputs = [ROOT / (NAME + suffix) for suffix in (".blend", ".fbx", ".glb")]
outputs += [ROOT / name for name in (ATLAS.name, "T_JadeTalisman_MetalRough.png",
                                    "T_JadeTalisman_Emissive.png", "T_JadeSeal_BaseColor.png")]
receipt = {
    "state": "validated", "mesh": NAME, "dimensions_m": dimensions, "paper_thickness_m": THICKNESS,
    "triangles": triangles, "materials": 3, "atlas_px": [2048, 2048],
    "roundtrip": roundtrip, "source": "Original Blender mesh and locally authored textures",
    "visual_reference": "https://collections.nmth.gov.tw/CollectionContent.aspx?RNO=2010.003.0185&a=132",
    "sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in outputs},
}
(ROOT / "AssetValidation.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
