"""Read-only placement diagnostics for the six cosmetic tree instances.

The current saved gameplay map must already be open outside PIE. This captures
the exact architecture instances rejecting tree zero, plus independent ground
traces for candidate positions. No map, actor, component or asset is changed.
"""
import collections
import hashlib
import importlib.util
import json
import math
import time
from pathlib import Path

import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUT = PROJECT / 'Docs/Gameplay/Optimization1111/TreeClearance'
SOURCE = PROJECT / 'Scripts/Editor/Optimization1111/repair_tree_building_clearance.py'
spec = importlib.util.spec_from_file_location('opt1111_tree_repair_diagnostic', SOURCE)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def architecture_metadata(actors, records):
    wanted = {r['id'] for r in records}
    metadata = {}
    for actor in actors:
        label = actor.get_actor_label()
        for c in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = c.static_mesh
            if not mesh:
                continue
            instances = [(i, c.get_instance_transform(i, world_space=True)) for i in range(c.get_instance_count())] \
                if isinstance(c, unreal.InstancedStaticMeshComponent) else [(None, c.get_world_transform())]
            for index, transform in instances:
                key = label + (f':{index}' if index is not None else '')
                if key not in wanted:
                    continue
                lo, hi = repair.world_bounds(mesh, transform)
                size = [hi[k] - lo[k] for k in range(3)]
                metadata[key] = {
                    'id': key, 'actor': label, 'component': c.get_name(), 'instance': index,
                    'mesh': mesh.get_path_name(), 'materials': [c.get_material(i).get_path_name() if c.get_material(i) else None
                        for i in range(c.get_num_materials())], 'collision': str(c.get_collision_enabled()),
                    'affects_navigation': bool(c.get_editor_property('can_ever_affect_navigation')),
                    'transform': repair.transform_record(transform), 'bounds': [lo, hi], 'size_cm': size,
                    'flat_box_candidate': size[2] < min(size[0], size[1]) * .2,
                }
    return metadata


def inspect_floor(world, foot):
    hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(foot[0], foot[1], foot[2] + 120),
        unreal.Vector(foot[0], foot[1], foot[2] - 180), unreal.TraceTypeQuery.ECC_VISIBILITY,
        False, [], unreal.DrawDebugTrace.NONE)
    if not hit:
        return {'hit': False, 'supported': False}
    value = hit.to_tuple()
    point, normal = value[5], value[7]
    objects = []
    for index, item in enumerate(value):
        if hasattr(item, 'get_path_name'):
            objects.append({'tuple_index': index, 'type': type(item).__name__, 'path': item.get_path_name()})
    return {'hit': True, 'supported': normal.z >= .7 and abs(point.z - foot[2]) <= 80,
            'impact_cm': repair.xyz(point), 'normal': repair.xyz(normal), 'objects': objects}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert editor.get_game_world() is None
    assert editor.get_editor_world().get_path_name().startswith(repair.MAP + '.')
    original_hash = hashlib.sha256(repair.MAP_FILE.read_bytes()).hexdigest()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    architecture = repair.architecture_records(actors)
    metadata = architecture_metadata(actors, architecture)
    trees = repair.collect_trees(actors)
    target = next(t for t in trees if t['actor'].get_actor_label() == 'NL1105_Art_SM_Tree_Big_01a' and t['index'] == 0)
    director = next(a for a in actors if isinstance(a, unreal.NLLevelEncounterDirector))
    routes, spawn_boxes = [], []
    for stage in director.stages:
        routes.append((repair.xyz(stage.entry_transform.translation), repair.xyz(stage.trigger_center)))
        for point in stage.spawn_points:
            p = repair.xyz(point.spawn_transform.translation)
            spawn_boxes.append(([p[0] - 140, p[1] - 140, p[2] - 100], [p[0] + 140, p[1] + 140, p[2] + 180]))
    original_contacts = [r['id'] for r in architecture if repair.intersects(target['bounds'], r['bounds'], repair.CLEARANCE_CM)]
    actual_contacts = [r['id'] for r in architecture if repair.intersects(target['bounds'], r['bounds'], 0)]
    counts = collections.Counter()
    blocker_counts = collections.Counter()
    candidates = []
    other_trees = [t['bounds'] for t in trees if t is not target]
    for radius in range(0, repair.MAX_TRANSLATION_CM + 1, 100):
        for angle in range(1 if radius == 0 else 24):
            offset = [radius * math.cos(angle * math.tau / 24), radius * math.sin(angle * math.tau / 24), 0]
            foot = [target['foot'][k] + offset[k] for k in range(3)]
            bounds = repair.shifted(target['bounds'], offset)
            blockers = [a['id'] for a in architecture if repair.intersects(bounds, a['bounds'], repair.CLEARANCE_CM)]
            blockers_without_padding = [a['id'] for a in architecture if repair.intersects(bounds, a['bounds'], 0)]
            flat_blockers = [key for key in blockers if metadata.get(key, {}).get('flat_box_candidate')]
            blocker_counts.update(blockers)
            route_ok = repair.route_clear(foot, routes)
            tree_clear = not any(repair.intersects(bounds, b, 50) for b in other_trees)
            spawn_clear = not any(repair.intersects(bounds, b) for b in spawn_boxes)
            floor = inspect_floor(editor.get_editor_world(), foot)
            if not route_ok: counts['route_rejected'] += 1
            if blockers: counts['architecture_rejected'] += 1
            if not tree_clear: counts['other_tree_rejected'] += 1
            if not spawn_clear: counts['spawn_rejected'] += 1
            if not floor['supported']: counts['ground_rejected'] += 1
            if floor['supported'] and blockers: counts['ground_supported_but_architecture_rejected'] += 1
            if floor['supported'] and blockers and len(flat_blockers) == len(blockers): counts['supported_rejected_only_flat_boxes'] += 1
            if floor['supported'] and blockers and not blockers_without_padding: counts['supported_rejected_only_padding'] += 1
            eligible = route_ok and not blockers and tree_clear and spawn_clear and floor['supported']
            if eligible: counts['eligible'] += 1
            candidates.append({'offset_cm': offset, 'foot_cm': foot, 'architecture_blockers': blockers,
                'architecture_blockers_without_padding': blockers_without_padding, 'flat_blockers': flat_blockers,
                'route_clear': route_ok, 'other_tree_clear': tree_clear, 'spawn_clear': spawn_clear,
                'ground': floor, 'eligible': eligible})
    interesting = set(original_contacts) | {name for name, _ in blocker_counts.most_common(50)}
    report = {
        'state': 'read_only_diagnostic', 'created_utc': time.time(), 'map': repair.MAP,
        'target': {'actor': target['actor'].get_actor_label(), 'instance': target['index'], 'bounds': target['bounds'],
                   'foot_cm': target['foot'], 'transform': repair.transform_record(target['transform']),
                   'original_ground': inspect_floor(editor.get_editor_world(), target['foot'])},
        'clearance_cm': repair.CLEARANCE_CM, 'original_padded_contacts': original_contacts,
        'original_actual_aabb_contacts': actual_contacts, 'candidate_count': len(candidates),
        'rejection_counts': dict(counts), 'blocker_frequencies': blocker_counts.most_common(50),
        'architecture_contact_details': [metadata[key] for key in sorted(interesting) if key in metadata],
        'candidates': candidates, 'map_sha256_before': original_hash,
        'map_sha256_after': hashlib.sha256(repair.MAP_FILE.read_bytes()).hexdigest(),
    }
    assert report['map_sha256_before'] == report['map_sha256_after']
    (OUT / 'Diagnostic.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('OPT1111_TREE_DIAGNOSTIC_READY ' + json.dumps(report['rejection_counts']))
    return report


if __name__ == '__main__':
    main()
