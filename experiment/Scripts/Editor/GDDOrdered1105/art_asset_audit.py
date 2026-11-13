"""Read-only UE asset and current-map audit for the later environment pass.

Does not load another level, create actors/assets, change properties or save packages.
The primary agent may dispatch this after the earlier ordered GDD tasks are verified.
"""
import hashlib
import json
from pathlib import Path
import unreal

P = Path(unreal.Paths.project_dir()).resolve()
O = P / 'Docs/Gameplay/GDDOrdered1105'
MESH_ROOT = '/Game/AsianTemple/Environment/Mesh/'
NAMES = (
    'SM_Dragon_Statue_01a', 'SM_Lamp_01a', 'SM_Temple_Door_01a',
    'SM_Temple_Pillar_01a', 'SM_Temple_Trim_01a', 'SM_Temple_Trim_01b',
    'SM_Temple_Trim_02a', 'SM_Temple_Trim_03a', 'SM_Temple_Wall_01a',
    'SM_RoofTile_Mid_01a', 'SM_RoofTile_Corner_01a', 'SM_Orn_01a',
    'SM_Cliff_01a', 'SM_Cliff_01b', 'SM_Cliff_01c', 'SM_Cliff_02a',
    'SM_Distant_Terrain', 'SM_Rock_01a', 'SM_Rock_01b', 'SM_Rock_02a',
    'SM_Tree_Big_01a', 'SM_Tree_Big_01a_Pink', 'SM_Tree_Medium_01a',
    'SM_Tree_Small_01a', 'SM_Bush_01a', 'SM_Bush_02a', 'SM_Grass_01a',
)


def xyz(v):
    return [float(v.x), float(v.y), float(v.z)]


meshes = []
for name in NAMES:
    mesh = unreal.load_asset(MESH_ROOT + name)
    assert isinstance(mesh, unreal.StaticMesh), name
    b = mesh.get_bounds()
    meshes.append({
        'path': mesh.get_path_name(), 'origin_cm': xyz(b.origin),
        'extent_cm': xyz(b.box_extent),
        'dimensions_cm': [v * 2 for v in xyz(b.box_extent)],
        'triangles_lod0': mesh.get_num_triangles(0),
        'lod_count': mesh.get_num_lods(),
        'materials': [slot.material_interface.get_path_name() if slot.material_interface else None
                      for slot in mesh.static_materials],
    })

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
scene = []
for actor in actors.get_all_level_actors():
    components = actor.get_components_by_class(unreal.StaticMeshComponent)
    if not components:
        continue
    row = {'label': actor.get_actor_label(), 'class': actor.get_class().get_name(),
           'folder': str(actor.get_folder_path()), 'position_cm': xyz(actor.get_actor_location()),
           'components': []}
    for c in components:
        mesh = c.get_editor_property('static_mesh')
        rec = {'mesh': mesh.get_path_name() if mesh else None,
               'materials': [c.get_material(i).get_path_name() if c.get_material(i) else None
                             for i in range(c.get_num_materials())],
               'collision': str(c.get_collision_enabled()),
               'navigation': c.get_editor_property('can_ever_affect_navigation')}
        if isinstance(c, unreal.InstancedStaticMeshComponent):
            rec['instance_count'] = c.get_instance_count()
        row['components'].append(rec)
    scene.append(row)

map_file = P / 'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
report = {'state': 'read_only_audit', 'world': world.get_path_name(),
          'main_map_sha256': hashlib.sha256(map_file.read_bytes()).hexdigest(),
          'mesh_assets': meshes, 'current_map_mesh_actors': scene,
          'scope': 'Loaded mesh metadata only. No level switch, property edits, actor or asset creation, compilation or package saves.'}
O.mkdir(parents=True, exist_ok=True)
(O / 'ArtAssetAudit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
