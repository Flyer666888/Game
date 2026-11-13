"""Author a curved, solid two-sided talisman and its portable mesh exports."""
import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
ATLAS = ROOT / "T_Talisman_Atlas.png"
WIDTH = 0.065
HEIGHT = 0.160
THICKNESS = 0.00032
NX, NZ = 10, 30
SHEET_VERTS = (NX + 1) * (NZ + 1)
NAME = "SM_Nilin_Talisman"


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
material = bpy.data.materials.new("M_Nilin_Talisman_Paper")
material.use_nodes = True
material.diffuse_color = (.65, .32, .06, 1)
nodes = material.node_tree.nodes
principled = nodes.get("Principled BSDF")
principled.inputs["Roughness"].default_value = .81
principled.inputs["Specular IOR Level"].default_value = .29
texture = nodes.new("ShaderNodeTexImage")
texture.name = "Paper and cinnabar atlas"
texture.location = (-350, 160)
texture.image = bpy.data.images.load(str(ATLAS))
texture.image.pack()
material.node_tree.links.new(texture.outputs["Color"], principled.inputs["Base Color"])
mesh.materials.append(material)
bpy.context.view_layer.objects.active = model
model.select_set(True)
bpy.context.view_layer.update()
mesh.calc_loop_triangles()
triangles = len(mesh.loop_triangles)
dimensions = list(model.dimensions)
assert triangles == 1360 and .062 < dimensions[0] < .069 and .156 < dimensions[2] < .164

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
scene.view_settings.exposure = -.8
render(scene, "Render_Front.png", (.10, -.42, .06), scale=.200)
render(scene, "Render_Back.png", (.19, .35, .09), scale=.204)
render(scene, "Render_Edge.png", (.39, -.17, .075), scale=.198)
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
    assert len(imported.data.uv_layers) and len(imported.data.materials) == 1
    images = [node.image for node in imported.data.materials[0].node_tree.nodes
              if node.type == "TEX_IMAGE" and node.image]
    assert any(list(image.size) == [2048, 2048] for image in images)
    assert max(abs(a - b) for a, b in zip(sorted(imported.dimensions), sorted(dimensions))) < .0001
    roundtrip[extension] = {"triangles": len(imported.data.loop_triangles),
                            "dimensions_m": list(imported.dimensions), "atlas_px": [2048, 2048]}
    for obj in set(bpy.data.objects) - existing:
        bpy.data.objects.remove(obj, do_unlink=True)

outputs = [ROOT / (NAME + suffix) for suffix in (".blend", ".fbx", ".glb")] + [ATLAS]
receipt = {
    "state": "validated", "mesh": NAME, "dimensions_m": dimensions, "paper_thickness_m": THICKNESS,
    "triangles": triangles, "materials": 1, "manifold": True, "atlas_px": [2048, 2048],
    "roundtrip": roundtrip, "source": "Original Blender mesh and locally authored textures",
    "visual_reference": "https://collections.nmth.gov.tw/CollectionContent.aspx?RNO=2010.003.0185&a=132",
    "sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in outputs},
}
(ROOT / "AssetValidation.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
