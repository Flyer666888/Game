"""Consolidate owned V07 Cube actors into native, serialized HISM clusters.

Run main() in the normal UE editor after backing up L_NilinBlockoutV07.
No custom meshes, nodes, markers, attached actors or gameplay actors are touched.
audit_only=True writes the complete recovery snapshot without changing the map.
restore(recovery_path) recreates source StaticMeshActors and removes this run's
clusters. Both operations refuse every map other than the independent V07 map.

All transforms/recovery data use UE centimetres; source Cube size remains 100 cm.
Negative world determinant is absorbed by a mirrored cluster actor. Each local
instance is canonicalized to strictly positive scale and verified at all 8 Cube
corners before the source actors may be removed.
"""
import datetime
import hashlib
import json
import math
import os
import re
import traceback
from collections import Counter, defaultdict

import unreal

ROOT = r'D:\game design\experiment'
OUT = os.path.join(ROOT, 'Docs', 'LevelDesign', 'Blockout_v02')
MAP = '/Game/ReversedScale/Maps/L_NilinBlockoutV07'
CUBE = '/Engine/BasicShapes/Cube.Cube'
CLUSTER_TAG = 'NLBlockout.ClusterV02'
MIN_INSTANCES = 3
POINT_TOLERANCE_CM = 0.1
EXCLUDE = re.compile(r'^NB_Node_\d+_|marker|targeteye|friend|boss|victory|player|ritual|'
                     r'triangle|breaker|combat|spawn|suspendedsword|seal|pine|'
                     r'banner|lantern', re.I)
RENDER_PROPERTIES = ('cast_shadow', 'visible', 'hidden_in_game', 'receives_decals',
                     'reverse_culling', 'render_custom_depth',
                     'custom_depth_stencil_value', 'visible_in_ray_tracing',
                     'bounds_scale', 'translucency_sort_priority',
                     'can_ever_affect_navigation')
SAMPLES = [(0, 0, 0)] + [(x, y, z) for x in (-50, 50)
                         for y in (-50, 50) for z in (-50, 50)]


def _subsystems():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if not editor.get_editor_world().get_path_name().startswith(MAP + '.'):
        raise RuntimeError('Refusing HISM operation outside independent V07 map')
    return actors, levels


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + '.tmp', 'w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
    os.replace(path + '.tmp', path)


def _xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def _transform_data(transform):
    q = transform.get_editor_property('rotation')
    return {'translation_cm': _xyz(transform.get_editor_property('translation')),
            'rotation_quat_xyzw': [float(q.x), float(q.y), float(q.z), float(q.w)],
            'scale': _xyz(transform.get_editor_property('scale3d'))}


def _transform(data):
    value = unreal.Transform()
    value.set_editor_property('translation', unreal.Vector(*data['translation_cm']))
    value.set_editor_property('rotation', unreal.Quat(*data['rotation_quat_xyzw']))
    value.set_editor_property('scale3d', unreal.Vector(*data['scale']))
    return value


def _enum_name(enum_class, value):
    # UE 5.8 exposes some renamed enums (e.g. CollisionResponseType).
    # The returned value's actual type is authoritative over a legacy alias.
    for candidate in (type(value), enum_class):
        for name in dir(candidate):
            if name.isupper() and getattr(candidate, name) == value:
                return name
    raise RuntimeError('Cannot serialize enum %s: %s' % (enum_class, value))


def _response_enum():
    return getattr(unreal, 'CollisionResponseType', None) or unreal.CollisionResponse


def _enum_value(name, class_name, fallback):
    enum_class = getattr(unreal, class_name, None) if class_name else None
    for candidate in (enum_class, fallback):
        if candidate is not None and hasattr(candidate, name):
            return getattr(candidate, name)
    raise RuntimeError('Cannot restore enum %s.%s' % (class_name, name))


def _channels():
    for name in dir(unreal.CollisionChannel):
        if name.isupper() and 'MAX' not in name:
            channel = getattr(unreal.CollisionChannel, name)
            if isinstance(channel, unreal.CollisionChannel):
                yield name, channel


def _collision(actor, component):
    enabled = component.get_collision_enabled()
    object_type = component.get_collision_object_type()
    responses = {name: component.get_collision_response_to_channel(channel)
                 for name, channel in _channels()}
    return {'actor_enabled': bool(actor.get_actor_enable_collision()),
            'profile': str(component.get_collision_profile_name()),
            'enabled': _enum_name(unreal.CollisionEnabled, enabled),
            'object_type': _enum_name(unreal.CollisionChannel, object_type),
            'enum_classes': {'enabled': type(enabled).__name__,
                             'object_type': type(object_type).__name__,
                             'response': type(next(iter(responses.values()))).__name__},
            'generate_overlap_events': bool(component.get_editor_property('generate_overlap_events')),
            'responses': {name: _enum_name(_response_enum(), response)
                          for name, response in responses.items()}}


def _flags(component):
    result = {}
    for name in RENDER_PROPERTIES:
        try:
            value = component.get_editor_property(name)
        except Exception:
            continue  # Not all optional rendering properties exist in every UE build.
        if isinstance(value, (bool, int, float, str)):
            result[name] = value
    return result


def _configure(actor, component, data, activate=True):
    mesh = unreal.load_asset(data['mesh'])
    if not mesh:
        raise RuntimeError('Missing source mesh: ' + data['mesh'])
    component.set_static_mesh(mesh)
    component.set_mobility(unreal.ComponentMobility.STATIC)
    for index, material_path in enumerate(data['materials']):
        material = unreal.load_asset(material_path) if material_path else None
        if material_path and not material:
            raise RuntimeError('Missing source material: ' + material_path)
        component.set_material(index, material)
    for name, value in data['component_flags'].items():
        component.set_editor_property(name, value)
    config = data['collision']
    enum_classes = config.get('enum_classes', {})
    component.set_collision_profile_name(config['profile'])
    component.set_collision_object_type(_enum_value(config['object_type'],
                                       enum_classes.get('object_type'), unreal.CollisionChannel))
    for name, response in config['responses'].items():
        component.set_collision_response_to_channel(getattr(unreal.CollisionChannel, name),
                  _enum_value(response, enum_classes.get('response'), _response_enum()))
    component.set_collision_enabled(_enum_value(config['enabled'], enum_classes.get('enabled'),
                                                unreal.CollisionEnabled))
    component.set_editor_property('generate_overlap_events', config['generate_overlap_events'])
    # Individual response setters rename an otherwise identical preset to Custom.
    # Restore named presets last, then verify every effective response below.
    if config['profile']!='Custom':component.set_collision_profile_name(config['profile'])
    actor.set_actor_enable_collision(config['actor_enabled'] if activate else False)


def _positive_local(world, cluster_world):
    # Mirror is its own inverse; identity handles original positive determinants.
    local = unreal.MathLibrary.compose_transforms(world, cluster_world)
    scale = local.get_editor_property('scale3d')
    scales = [float(scale.x), float(scale.y), float(scale.z)]
    if min(abs(s) for s in scales) < 1e-7 or math.prod(scales) <= 0:
        raise RuntimeError('Degenerate or still-reflected local instance transform')
    if min(scales) < 0:
        origin = unreal.MathLibrary.transform_location(local, unreal.Vector())
        axes = []
        for axis, length in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), scales):
            endpoint = unreal.MathLibrary.transform_location(local, unreal.Vector(*axis))
            axes.append(unreal.Vector((endpoint.x-origin.x)/abs(length),
                                      (endpoint.y-origin.y)/abs(length),
                                      (endpoint.z-origin.z)/abs(length)))
        rotation = unreal.MathLibrary.make_rotation_from_axes(*axes)
        local = unreal.MathLibrary.make_transform(origin, rotation,
                                                  unreal.Vector(*[abs(s) for s in scales]))
    if min(_transform_data(local)['scale']) <= 0:
        raise RuntimeError('Instance must have strictly positive local scale')
    rebuilt = unreal.MathLibrary.compose_transforms(local, cluster_world)
    error = _point_error(world, rebuilt)
    if error > POINT_TOLERANCE_CM:
        raise RuntimeError('Mirror/canonicalization changed Cube corners by %.6f cm' % error)
    return local, error


def _point_error(first, second):
    error = 0.0
    for point in SAMPLES:
        a = unreal.MathLibrary.transform_location(first, unreal.Vector(*point))
        b = unreal.MathLibrary.transform_location(second, unreal.Vector(*point))
        error = max(error, math.dist(_xyz(a), _xyz(b)))
    return error


def _read_instance(component, index):
    value = component.get_instance_transform(index, world_space=True)
    if isinstance(value, tuple):
        value = next((item for item in value if isinstance(item, unreal.Transform)), None)
    if not isinstance(value, unreal.Transform):
        raise RuntimeError('Could not read back HISM instance %d' % index)
    return value


def _source_record(actor, component):
    transform = actor.get_actor_transform()
    data = _transform_data(transform)
    materials = [component.get_material(index) for index in range(component.get_num_materials())]
    return {'label': actor.get_actor_label(), 'object_path': actor.get_path_name(),
            'actor_class': actor.get_class().get_path_name(),
            'folder': str(actor.get_folder_path()),
            'tags': sorted(str(tag) for tag in actor.get_editor_property('tags')),
            'actor_transform': data, 'mesh': component.get_editor_property('static_mesh').get_path_name(),
            'materials': [material.get_path_name() if material else None for material in materials],
            'collision': _collision(actor, component), 'component_flags': _flags(component),
            'mobility': 'STATIC', 'determinant_sign': -1 if math.prod(data['scale']) < 0 else 1}


def _restore_sources(records, actor_subsystem):
    labels = {actor.get_actor_label() for actor in actor_subsystem.get_all_level_actors()}
    restored = []
    for data in records:
        if data['label'] in labels:
            continue
        actor = actor_subsystem.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
        actor.set_actor_label(data['label'])
        actor.set_folder_path(unreal.Name(data['folder']))
        actor.set_editor_property('tags', [unreal.Name(tag) for tag in data['tags']])
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        _configure(actor, component, data)
        if not actor_subsystem.set_actor_transform(actor, _transform(data['actor_transform'])):
            raise RuntimeError('Cannot restore source transform: ' + data['label'])
        labels.add(data['label'])
        restored.append(data['label'])
    return restored


def restore(recovery_path, save=True):
    """Restore an explicitly chosen conversion run. Unrelated actors are preserved."""
    actors, levels = _subsystems()
    with open(recovery_path, encoding='utf-8') as stream:
        recovery = json.load(stream)
    if recovery.get('map') != MAP or recovery.get('schema') != 'NilinHISMRecoveryV1':
        raise RuntimeError('Recovery snapshot does not belong to V07')
    restored = _restore_sources(recovery['sources'], actors)
    expected = set(data['label'] for data in recovery['sources'])
    existing = {actor.get_actor_label() for actor in actors.get_all_level_actors()}
    if not expected.issubset(existing):
        raise RuntimeError('Source recovery incomplete; retained clusters for safety')
    cluster_labels = {group['cluster_label'] for group in recovery['groups']}
    removed = 0
    for actor in actors.get_all_level_actors():
        if actor.actor_has_tag(CLUSTER_TAG) and actor.get_actor_label() in cluster_labels:
            if not actors.destroy_actor(actor):
                raise RuntimeError('Cannot remove restored cluster: ' + actor.get_actor_label())
            removed += 1
    if save and not levels.save_current_level():
        raise RuntimeError('Restored actors but could not save map')
    result = {'map': MAP, 'restored_sources': len(restored), 'removed_clusters': removed,
              'recovery_path': os.path.abspath(recovery_path), 'saved': save}
    _write(os.path.join(OUT, 'ClusterRestore.json'), result)
    unreal.log('NILIN_HISM_RESTORE_OK ' + json.dumps(result))
    return result


def main(audit_only=False):
    actors, levels = _subsystems()
    cluster_class = unreal.load_class(None, '/Script/experiment.NLBlockoutMeshCluster')
    if not cluster_class:
        raise RuntimeError('Compile ANLBlockoutMeshCluster before running conversion')
    run_id = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    recovery_path = os.path.join(OUT, 'HISMRecovery_' + run_id + '.json')
    grouped = defaultdict(list)
    source_refs = {}
    skipped = Counter()
    all_actors = actors.get_all_level_actors()
    for actor in all_actors:
        if actor.get_class().get_path_name() != '/Script/Engine.StaticMeshActor':
            skipped['non_native_StaticMeshActor'] += 1
            continue
        if not (actor.actor_has_tag('NLBlockoutV06') or actor.actor_has_tag('NBOptV02')):
            skipped['not_owned'] += 1
            continue
        if EXCLUDE.search(actor.get_actor_label()) or any('Node.' in str(tag) for tag in actor.get_editor_property('tags')):
            skipped['node_marker_landmark'] += 1
            continue
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if not component or component != actor.get_editor_property('root_component') or actor.get_attach_parent_actor():
            skipped['non_root_or_attached'] += 1
            continue
        mesh = component.get_editor_property('static_mesh')
        if not mesh or mesh.get_path_name() != CUBE:
            skipped['not_engine_Cube'] += 1
            continue
        if component.get_editor_property('mobility') != unreal.ComponentMobility.STATIC or component.is_simulating_physics():
            skipped['non_static_or_simulated'] += 1
            continue
        data = _source_record(actor, component)
        if any(not math.isfinite(s) or abs(s) < 1e-7 for s in data['actor_transform']['scale']):
            skipped['degenerate_scale'] += 1
            continue
        key = json.dumps({name: data[name] for name in ('mesh', 'materials', 'collision',
                         'folder', 'determinant_sign', 'component_flags', 'tags')}, sort_keys=True)
        grouped[key].append(data)
        source_refs[data['object_path']] = actor

    groups, sources = [], []
    locals_by_group = []
    max_preflight_error = 0.0
    for key, records in sorted(grouped.items()):
        if len(records) < MIN_INSTANCES:
            skipped['group_below_3_instances'] += len(records)
            continue
        digest = hashlib.sha256(key.encode('utf-8')).hexdigest()[:10]
        index = len(groups)
        prefix = re.sub(r'[^A-Za-z0-9_]', '_', records[0]['folder'].split('/')[-1])
        cluster_label = 'NB2_HISM_%s_%03d_%s_%s' % (prefix, index, digest, run_id)
        cluster_transform = unreal.Transform(scale=unreal.Vector(-1, 1, 1)) if records[0]['determinant_sign'] < 0 else unreal.Transform()
        local_transforms = []
        for instance_index, record in enumerate(records):
            local, error = _positive_local(_transform(record['actor_transform']), cluster_transform)
            max_preflight_error = max(max_preflight_error, error)
            record['local_instance_transform'] = _transform_data(local)
            record['cluster_label'] = cluster_label
            record['instance_index'] = instance_index
            local_transforms.append(local)
        group = {name: records[0][name] for name in ('mesh', 'materials', 'collision',
                 'folder', 'determinant_sign', 'component_flags', 'tags')}
        group.update(cluster_label=cluster_label, cluster_transform=_transform_data(cluster_transform),
                     count=len(records), source_labels=[record['label'] for record in records])
        groups.append(group)
        sources.extend(records)
        locals_by_group.append(local_transforms)

    recovery = {'schema': 'NilinHISMRecoveryV1', 'map': MAP, 'units': 'UE centimetres',
                'run_id': run_id, 'stage': 'pre_mutation_snapshot', 'min_instances': MIN_INSTANCES,
                'groups': groups, 'sources': sources, 'skipped': dict(skipped),
                'preflight_max_corner_error_cm': max_preflight_error,
                'actor_count_before': len(all_actors)}
    # This durable file is written before even the first cluster actor is created.
    _write(recovery_path, recovery)
    summary = {'map': MAP, 'run_id': run_id, 'audit_only': audit_only,
               'recovery_path': recovery_path, 'source_actors': len(sources),
               'clusters': len(groups), 'skipped': dict(skipped),
               'preflight_max_corner_error_cm': max_preflight_error}
    if audit_only or not groups:
        summary['status'] = 'audited_only' if audit_only else 'nothing_to_merge'
        _write(os.path.join(OUT, 'ClusterAudit.json'), summary)
        return summary

    created = []
    commit_started = False
    try:
        for group, local_transforms in zip(groups, locals_by_group):
            actor = actors.spawn_actor_from_class(cluster_class, unreal.Vector())
            created.append(actor)
            actor.set_actor_enable_collision(False)
            actor.set_actor_label(group['cluster_label'])
            actor.set_folder_path(unreal.Name(group['folder']))
            actor.set_editor_property('tags', [unreal.Name(tag) for tag in
                                      sorted(set(group['tags'] + [CLUSTER_TAG]))])
            component = actor.get_editor_property('instances')
            if not component:
                raise RuntimeError('Native HISM component missing')
            _configure(actor, component, group, activate=False)
            if not actors.set_actor_transform(actor, _transform(group['cluster_transform'])):
                raise RuntimeError('Cannot set HISM cluster mirror transform')
            indices = component.add_instances(local_transforms, True, False, True)
            if component.get_instance_count() != group['count'] or len(indices) != group['count']:
                raise RuntimeError('HISM instance count mismatch')
            records = [sources_record for sources_record in sources
                       if sources_record['cluster_label'] == group['cluster_label']]
            max_error = 0.0
            for record in records:
                actual = _read_instance(component, record['instance_index'])
                max_error = max(max_error, _point_error(_transform(record['actor_transform']), actual))
            if max_error > POINT_TOLERANCE_CM:
                raise RuntimeError('HISM world readback changed Cube corners by %.6f cm' % max_error)
            actor.set_actor_enable_collision(group['collision']['actor_enabled'])
            actual_config=_collision(actor, component)
            actor.set_actor_enable_collision(False)
            expected_config=group['collision']
            if actual_config != expected_config:
                recovery['collision_difference']={'actual':actual_config,'expected':expected_config}
                raise RuntimeError('HISM component collision configuration differs from source: '+json.dumps(recovery['collision_difference']))
            group['readback_max_corner_error_cm'] = max_error
        recovery['stage'] = 'clusters_verified_before_source_removal'
        _write(recovery_path, recovery)
        commit_started = True
        for actor, group in zip(created, groups):
            actor.set_actor_enable_collision(group['collision']['actor_enabled'])
        for record in sources:
            if not actors.destroy_actor(source_refs[record['object_path']]):
                raise RuntimeError('Cannot remove source actor: ' + record['label'])
        if not levels.save_current_level():
            raise RuntimeError('Could not save consolidated V07 map')
        recovery['stage'] = 'committed_and_saved'
        _write(recovery_path, recovery)
        summary.update(status='committed_and_saved',
                       actor_count_before=len(all_actors),
                       actor_count_after=len(actors.get_all_level_actors()),
                       removed_actor_count=len(sources)-len(groups),
                       negative_mirror_clusters=sum(g['determinant_sign'] < 0 for g in groups),
                       readback_max_corner_error_cm=max(g['readback_max_corner_error_cm'] for g in groups),
                       actual_collision_and_PIE_validation='required_after_conversion')
        _write(os.path.join(OUT, 'ClusterAudit.json'), summary)
        unreal.log('NILIN_HISM_CONSOLIDATION_OK ' + json.dumps(summary))
        return summary
    except Exception:
        recovery['failure'] = traceback.format_exc()
        if commit_started:
            recovery['rollback_restored_sources'] = _restore_sources(sources, actors)
        for actor in created:
            actors.destroy_actor(actor)
        recovery['stage'] = 'rolled_back_in_memory' if commit_started else 'pre_commit_cancelled'
        _write(recovery_path, recovery)
        summary.update(status=recovery['stage'], failure=recovery['failure'])
        _write(os.path.join(OUT, 'ClusterAudit.json'), summary)
        raise


if __name__ == '__main__':
    main()
