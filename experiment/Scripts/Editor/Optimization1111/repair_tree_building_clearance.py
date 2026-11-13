"""Translate only the six cosmetic GDD1105 tree instances clear of architecture.

Run main(apply=False) in the editor to review the proposed translations. After
review run main(apply=True); that path backs up the saved map before any edit,
keeps mesh/scale/rotation/material/collision/navigation unchanged, and refuses
to save if source geometry or any encounter configuration changed.

Bounds tests use conservative height-sliced LOD0 triangle envelopes, not one
wide canopy box stretched down to ground level. Actual floor traces keep each
relocated trunk on its original terrace. Original landmark pine is preserved.
"""
import hashlib
import json
import math
import shutil
import time
from pathlib import Path

import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = PROJECT / 'Docs/Gameplay/Optimization1111/TreeClearance'
MAP = '/Game/ReversedScale/Maps/L_NilinGameplayV01'
MAP_FILE = PROJECT / 'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
TREE_LABELS = {'NL1105_Art_SM_Tree_Big_01a', 'NL1105_Art_SM_Tree_Medium_01a'}
CLEARANCE_CM = 120.0
MAX_TRANSLATION_CM = 2400
ENVELOPE_HEIGHT_CM = 150.0
GEOMETRY_CACHE = {}


def xyz(v):
    return [float(v.x), float(v.y), float(v.z)]


def transform_record(t):
    q = t.rotation
    return {'location': xyz(t.translation), 'scale': xyz(t.scale3d), 'quat': [q.x, q.y, q.z, q.w]}


def world_bounds(mesh, transform):
    bounds = mesh.get_bounds()
    center, extent = xyz(bounds.origin), xyz(bounds.box_extent)
    points = [xyz(unreal.MathLibrary.transform_location(transform, unreal.Vector(
        center[0] + sx * extent[0], center[1] + sy * extent[1], center[2] + sz * extent[2])))
        for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    return ([min(p[k] for p in points) for k in range(3)], [max(p[k] for p in points) for k in range(3)])


def shifted(bounds, offset):
    return ([bounds[0][k] + offset[k] for k in range(3)], [bounds[1][k] + offset[k] for k in range(3)])


def intersects(a, b, margin=0):
    return all(a[0][k] < b[1][k] + margin and a[1][k] > b[0][k] - margin for k in range(3))


def mesh_geometry(mesh):
    key = mesh.get_path_name()
    if key not in GEOMETRY_CACHE:
        description = mesh.get_static_mesh_description(0)
        assert description, f'No readable LOD0 mesh description: {key}'
        positions, triangles = {}, []
        count = description.get_vertex_count()
        for index in range(count * 4 + 100):
            vertex = unreal.VertexID(id_value=index)
            if description.is_vertex_valid(vertex):
                positions[index] = description.get_vertex_position(vertex)
                if len(positions) == count:
                    break
        assert len(positions) == count
        count = description.get_triangle_count()
        for index in range(count * 4 + 100):
            triangle = unreal.TriangleID(id_value=index)
            if description.is_triangle_valid(triangle):
                vertices = list(description.get_triangle_vertices(triangle))
                # This UE5.8 wrapper preallocates 3 and then Algo::Copy appends
                # 3 (MeshDescriptionBase.cpp:748). Only the last three IDs are
                # initialized source vertices; future corrected wrappers return 3.
                if len(vertices) == 6:
                    vertices = vertices[-3:]
                assert len(vertices) == 3
                ids = [int(v.id_value) for v in vertices]
                assert all(i in positions for i in ids)
                if len(triangles) < 8:
                    direct = [int(description.get_vertex_instance_vertex(
                        description.get_triangle_vertex_instance(triangle, corner)).id_value) for corner in range(3)]
                    assert ids == direct, 'Triangle array wrapper disagrees with direct corner access'
                triangles.append(ids)
                if len(triangles) == count:
                    break
        assert len(triangles) == count
        GEOMETRY_CACHE[key] = positions, triangles
    return GEOMETRY_CACHE[key]


def tree_envelopes(mesh, transform, bounds):
    positions, triangles = mesh_geometry(mesh)
    vertices = {i: xyz(unreal.MathLibrary.transform_location(transform, p)) for i, p in positions.items()}
    bottom = bounds[0][2]
    count = max(1, int(math.ceil((bounds[1][2] - bottom) / ENVELOPE_HEIGHT_CM)))
    slices = [[[float('inf')] * 3, [float('-inf')] * 3] for _ in range(count)]
    for triangle in triangles:
        points = [vertices[i] for i in triangle]
        lo, hi = [min(p[k] for p in points) for k in range(3)], [max(p[k] for p in points) for k in range(3)]
        first = max(0, min(count - 1, int(math.floor((lo[2] - bottom) / ENVELOPE_HEIGHT_CM))))
        last = max(0, min(count - 1, int(math.floor((hi[2] - bottom) / ENVELOPE_HEIGHT_CM))))
        # Assign the whole triangle's XY envelope to every height slab it crosses.
        # This covers long triangles even when a slab contains no source vertex.
        for index in range(first, last + 1):
            slab = slices[index]
            for axis in (0, 1):
                slab[0][axis] = min(slab[0][axis], lo[axis])
                slab[1][axis] = max(slab[1][axis], hi[axis])
            slab[0][2] = min(slab[0][2], max(lo[2], bottom + index * ENVELOPE_HEIGHT_CM))
            slab[1][2] = max(slab[1][2], min(hi[2], bottom + (index + 1) * ENVELOPE_HEIGHT_CM))
    result = [s for s in slices if all(math.isfinite(v) for side in s for v in side)]
    assert result and all(s[0][2] <= s[1][2] for s in result)
    return result


def blocking_architecture(envelopes, foot_z, architecture):
    contacts = []
    for item in architecture:
        lo, hi = item['bounds']
        # Actual diagnosis found 1.2cm StoneJoint floor strips mistaken for walls
        # because their parent HISM label contains Shanmen/Architecture. Ignore
        # only those strips at this candidate's ground plane, never thin roofs.
        if item.get('ground_joint') and foot_z - 20 <= lo[2] <= foot_z + 5 and hi[2] <= foot_z + 5:
            continue
        for bounds in envelopes:
            # Horizontal safety clearance must not grow a supporting floor up
            # into the tree's roots or grow a low rail up into high foliage.
            if bounds[0][2] >= hi[2] or bounds[1][2] <= lo[2]:
                continue
            if all(bounds[0][k] < hi[k] + CLEARANCE_CM and bounds[1][k] > lo[k] - CLEARANCE_CM for k in (0, 1)):
                contacts.append(item['id'])
                break
    return contacts


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def geometry_snapshot(actors):
    rows, stages = [], []
    for actor in actors:
        if actor.get_actor_label() in TREE_LABELS:
            continue
        for c in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = c.static_mesh
            row = {'actor': actor.get_name(), 'component': c.get_name(), 'mesh': mesh.get_path_name() if mesh else None,
                   'transform': transform_record(c.get_world_transform()), 'collision': str(c.get_collision_enabled()),
                   'navigation': bool(c.get_editor_property('can_ever_affect_navigation')),
                   'materials': [c.get_material(i).get_path_name() if c.get_material(i) else None
                                 for i in range(c.get_num_materials())]}
            if isinstance(c, unreal.InstancedStaticMeshComponent):
                row['instances'] = [transform_record(c.get_instance_transform(i, world_space=True))
                                    for i in range(c.get_instance_count())]
            rows.append(row)
        if isinstance(actor, unreal.NLLevelEncounterDirector):
            for s in actor.stages:
                stages.append({'id': str(s.stage_id), 'entry': transform_record(s.entry_transform),
                               'center': xyz(s.trigger_center), 'extent': xyz(s.trigger_extent), 'seed': s.seed,
                               'points': [(str(p.spawn_point_id), transform_record(p.spawn_transform)) for p in s.spawn_points],
                               'waves': [w.get_path_name() for w in s.waves]})
    return {'geometry': sorted(rows, key=lambda r: (r['actor'], r['component'])), 'stages': stages}


def architecture_records(actors):
    records = []
    for actor in actors:
        label = actor.get_actor_label()
        if actor.actor_has_tag('NL.GDD1105.Art'):
            continue
        # Repeated columns/beams live in Architecture HISM groups. Test every
        # individual instance, never their map-wide aggregate actor bounds.
        architectural = ('Architecture' in label or any(word in label for word in
            ('Roof', 'Eave', 'Column', 'Wall', 'Beam', 'Shanmen', 'GateSide', 'MartialGallery', 'AlchemyWorkshop', 'Pavilion')))
        if not architectural or any(word in label for word in ('Floor', 'Landing', 'Spine', 'Pine', 'CAM_', 'Camera')):
            continue
        for c in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = c.static_mesh
            if not mesh:
                continue
            transforms = [(i, c.get_instance_transform(i, world_space=True)) for i in range(c.get_instance_count())] \
                if isinstance(c, unreal.InstancedStaticMeshComponent) else [(None, c.get_world_transform())]
            for index, transform in transforms:
                bounds = world_bounds(mesh, transform)
                materials = [c.get_material(i).get_name() for i in range(c.get_num_materials()) if c.get_material(i)]
                records.append({'id': label + (f':{index}' if index is not None else ''), 'bounds': bounds,
                    'ground_joint': bounds[1][2] - bounds[0][2] <= 5 and any('StoneJoint' in m for m in materials)})
    assert records, 'No architecture bounds found; refuse an empty clearance audit'
    return records


def collect_trees(actors):
    trees = []
    for actor in actors:
        if actor.get_actor_label() not in TREE_LABELS:
            continue
        c = actor.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
        assert c and c.static_mesh and 'NO_COLLISION' in str(c.get_collision_enabled()), actor.get_actor_label()
        assert not c.get_editor_property('can_ever_affect_navigation')
        for index in range(c.get_instance_count()):
            t = c.get_instance_transform(index, world_space=True)
            bounds = world_bounds(c.static_mesh, t)
            trees.append({'actor': actor, 'component': c, 'index': index, 'transform': t, 'bounds': bounds,
                          'envelopes': tree_envelopes(c.static_mesh, t, bounds),
                          'foot': [(bounds[0][0] + bounds[1][0]) * .5, (bounds[0][1] + bounds[1][1]) * .5, bounds[0][2]]})
    assert len(trees) == 6, f'Expected the six authored cosmetic trees, found {len(trees)}'
    return trees


def floor_at(world, foot):
    hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(foot[0], foot[1], foot[2] + 120),
        unreal.Vector(foot[0], foot[1], foot[2] - 180), unreal.TraceTypeQuery.ECC_VISIBILITY,
        False, [], unreal.DrawDebugTrace.NONE)
    if not hit:
        return None
    value = hit.to_tuple()
    p, normal = value[5], value[7]
    if normal.z < .7 or abs(p.z - foot[2]) > 80:
        return None
    return float(p.z)


def route_clear(foot, routes):
    for start, end in routes:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = dx * dx + dy * dy
        t = max(0, min(1, ((foot[0] - start[0]) * dx + (foot[1] - start[1]) * dy) / length)) if length else 0
        nearest = [start[k] + (end[k] - start[k]) * t for k in range(3)]
        if math.hypot(foot[0] - nearest[0], foot[1] - nearest[1]) < 250 and abs(foot[2] - nearest[2]) < 350:
            return False
    return True


def find_translation(tree, architecture, reserved, spawn_boxes, routes, world):
    for radius in range(100, MAX_TRANSLATION_CM + 1, 100):
        offsets = [[radius * math.cos(i * math.tau / 24), radius * math.sin(i * math.tau / 24), 0] for i in range(24)]
        # Stable ordering favors outward framing when distances are equal.
        offsets.sort(key=lambda d: (-d[0] * (1 if tree['foot'][0] >= 0 else -1), abs(d[1])))
        for offset in offsets:
            foot = [tree['foot'][k] + offset[k] for k in range(3)]
            if not route_clear(foot, routes):
                continue
            bounds = shifted(tree['bounds'], offset)
            envelopes = [shifted(b, offset) for b in tree['envelopes']]
            if blocking_architecture(envelopes, foot[2], architecture):
                continue
            if any(intersects(bounds, b, 50) for b in reserved) or any(intersects(e, b) for e in envelopes for b in spawn_boxes):
                continue
            z = floor_at(world, foot)
            if z is None:
                continue
            offset[2] = z - tree['foot'][2]
            bounds = shifted(tree['bounds'], offset)
            envelopes = [shifted(b, offset) for b in tree['envelopes']]
            if blocking_architecture(envelopes, z, architecture):
                continue
            if any(intersects(bounds, b, 50) for b in reserved) or any(intersects(e, b) for e in envelopes for b in spawn_boxes):
                continue
            return offset, bounds
    return None, None


def main(apply=False):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert editor.get_game_world() is None, 'End PIE before the tree patch'
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Save existing map changes before this patch'
    if not editor.get_editor_world().get_path_name().startswith(MAP + '.'):
        assert level.load_level(MAP)
    world = editor.get_editor_world()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    before = geometry_snapshot(actors)
    assert len(before['stages']) == 16
    architecture = architecture_records(actors)
    trees = collect_trees(actors)
    director = next(a for a in actors if isinstance(a, unreal.NLLevelEncounterDirector))
    spawn_boxes, routes = [], []
    for stage in director.stages:
        entry, center = xyz(stage.entry_transform.translation), xyz(stage.trigger_center)
        routes.append((entry, center))
        for point in stage.spawn_points:
            p = xyz(point.spawn_transform.translation)
            spawn_boxes.append(([p[0] - 140, p[1] - 140, p[2] - 100], [p[0] + 140, p[1] + 140, p[2] + 180]))
    changes, rows = [], []
    reserved = [t['bounds'] for t in trees]
    for tree in trees:
        contacts = blocking_architecture(tree['envelopes'], tree['foot'][2], architecture)
        row = {'actor': tree['actor'].get_actor_label(), 'instance': tree['index'], 'before': transform_record(tree['transform']),
               'bounds_before': tree['bounds'], 'height_envelopes_before': tree['envelopes'],
               'architecture_conflicts_before': contacts, 'translation_cm': [0, 0, 0]}
        if contacts:
            other_trees = [b for b in reserved if b is not tree['bounds']]
            offset, bounds = find_translation(tree, architecture, other_trees, spawn_boxes, routes, world)
            assert offset is not None, f'No supported local placement for {row["actor"]}:{row["instance"]}; nothing has been edited'
            row['translation_cm'] = offset
            row['bounds_after'] = bounds
            changes.append((tree, offset))
            reserved[reserved.index(tree['bounds'])] = bounds
        else:
            row['bounds_after'] = tree['bounds']
        row['height_envelopes_after'] = [shifted(b, row['translation_cm']) for b in tree['envelopes']]
        row['architecture_conflicts_after'] = blocking_architecture(row['height_envelopes_after'],
            tree['foot'][2] + row['translation_cm'][2], architecture)
        rows.append(row)
    report = {'state': 'planned', 'apply': apply, 'map': MAP, 'created_utc': time.time(), 'clearance_cm': CLEARANCE_CM,
              'architecture_instance_count': len(architecture), 'tree_count': len(trees), 'moved_count': len(changes),
              'geometry_test': '150cm height slabs conservatively covering every LOD0 triangle; XY clearance only; ground-plane StoneJoint strips excluded',
              'scope': 'Six cosmetic GDD1105 tree instances; original landmark pine, architecture, gameplay, collision and navigation are preserved.',
              'map_sha256_before': hashlib.sha256(MAP_FILE.read_bytes()).hexdigest(), 'trees': rows,
              'source_geometry_and_gameplay_digest_before': digest(before)}
    (OUTPUT / 'Plan.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if not apply:
        unreal.log(f'OPT1111_TREE_PLAN_READY {len(changes)} tree translations')
        return report
    backup = OUTPUT / 'Backups' / time.strftime('%Y%m%d_%H%M%S') / MAP_FILE.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MAP_FILE, backup)
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == report['map_sha256_before']
    report['backup'] = str(backup)
    applied = []
    try:
        for tree, offset in changes:
            transform = tree['component'].get_instance_transform(tree['index'], world_space=True)
            transform.translation += unreal.Vector(*offset)
            assert tree['component'].update_instance_transform(tree['index'], transform, world_space=True,
                mark_render_state_dirty=True, teleport=True)
            applied.append(tree)
        after = geometry_snapshot(actors)
        assert before == after, 'A non-tree component, original landmark pine, navigation or encounter configuration changed'
        for tree in trees:
            actual_transform = tree['component'].get_instance_transform(tree['index'], world_space=True)
            actual = world_bounds(tree['component'].static_mesh, actual_transform)
            envelopes = tree_envelopes(tree['component'].static_mesh, actual_transform, actual)
            assert not blocking_architecture(envelopes, actual[0][2], architecture)
        assert level.save_current_level(), 'Failed to save the tree-only map patch'
    except Exception:
        for tree in applied:
            tree['component'].update_instance_transform(tree['index'], tree['transform'], world_space=True,
                mark_render_state_dirty=True, teleport=True)
        raise
    report.update({'state': 'passed', 'map_sha256_after': hashlib.sha256(MAP_FILE.read_bytes()).hexdigest(),
                   'source_geometry_and_gameplay_unchanged': before == after,
                   'source_geometry_and_gameplay_digest_after': digest(after), 'remaining_architecture_conflicts': 0})
    (OUTPUT / 'Applied.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('OPT1111_TREE_PATCH_SAVED ' + report['map_sha256_after'])
    return report


if __name__ == '__main__':
    main(apply=False)
