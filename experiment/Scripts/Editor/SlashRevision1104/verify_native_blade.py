"""Read-only compressed-pose check of the imported v07 cut and native grip.

Run in Unreal after import_native_clips.py. Writes only BladeUEVerification.json;
does not change actors, animation assets, skeletons, notifies, or editor state.
"""
import json
import math
import traceback
from pathlib import Path
import unreal

P = Path(unreal.Paths.project_dir()).resolve()
OUT = P / 'Docs/Gameplay/SlashRevision1104'
REPORT = OUT / 'BladeUEVerification.json'
report = {'state': 'starting', 'space': 'skeletal mesh component, +X forward, centimetres',
          'read_only': True, 'sample_fps': 60}


def xyz(v):
    return [float(v.x), float(v.y), float(v.z)]


def dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def unit(v):
    length = v.length()
    assert length > 1e-7, ('Degenerate vector', xyz(v))
    return v / length


def bounds(rows, key):
    return [[min(row[key][axis] for row in rows), max(row[key][axis] for row in rows)]
            for axis in range(3)]


def save():
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')


try:
    imports = json.loads((OUT / 'NativeClipsImport.json').read_text(encoding='utf-8-sig'))
    grip_spec = json.loads((OUT / 'NativeSwordGrip.json').read_text(encoding='utf-8-sig'))['unreal']
    manifest = json.loads((OUT / 'NativeSlashManifest.json').read_text(encoding='utf-8-sig'))
    mesh_path = imports.get('mesh', '/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/SK_WuxiaMale_Native_v07')
    animation_path = imports['clips']['attack']['asset']
    mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
    animation = unreal.EditorAssetLibrary.load_asset(animation_path)
    assert mesh and animation, ('Missing imported assets', mesh_path, animation_path)
    skeleton = mesh.get_editor_property('skeleton')
    assert skeleton == animation.get_editor_property('skeleton'), 'Animation and mesh skeletons differ'
    duration = animation.get_play_length()
    assert abs(duration - manifest['duration']) < .002, ('Unexpected clip duration', duration)
    start, end = map(float, manifest['notify'])
    assert 0 < start < end < duration
    report.update({'mesh': mesh.get_path_name(), 'animation': animation.get_path_name(),
                   'skeleton': skeleton.get_path_name(), 'skeleton_matches': True,
                   'duration': duration, 'contact_window': [start, end], 'grip': grip_spec})

    # Verify the imported damage notify against the interval being measured.
    library = unreal.AnimationLibrary
    events = []
    for track in library.get_animation_notify_track_names(animation):
        for event in library.get_animation_notify_events_for_track(animation, track):
            state = event.get_editor_property('notify_state_class')
            if state and isinstance(state, unreal.NLEnemyAttackWindowNotifyState):
                trigger = library.get_anim_notify_event_trigger_time(event)
                span = library.get_anim_notify_event_duration(event)
                events.append({'track': str(track), 'start': trigger, 'end': trigger + span})
    report['attack_notifies'] = events
    assert len(events) == 1, ('Expected one attack window', events)
    assert abs(events[0]['start'] - start) < .002 and abs(events[0]['end'] - end) < .002, events

    opts = unreal.AnimPoseEvaluationOptions()
    opts.evaluation_type = unreal.AnimDataEvalType.COMPRESSED
    opts.optional_skeletal_mesh = mesh
    opts.should_retarget = False
    opts.extract_root_motion = False
    grip = unreal.Transform(location=unreal.Vector(*grip_spec['translation']),
                            scale=unreal.Vector(*grip_spec['scale']))
    grip.rotation=unreal.Quat(*grip_spec['quaternion_xyzw'])
    bone = grip_spec['bone']
    cache = {}

    def evaluate(t):
        key = round(max(0.0, min(duration, float(t))), 9)
        if key in cache:
            return cache[key]
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, key, opts)
        assert unreal.AnimPoseExtensions.is_valid(pose), ('Invalid compressed pose', key)
        hand = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD)
        # Sequential point transforms unambiguously match UE's local * parent order.
        # Keep all scale: imported hand scale 100 times grip scale .01 gives unit
        # weapon scale. Normalizing the hand transform before this is incorrect.
        def point(local):
            return unreal.MathLibrary.transform_location(
                hand, unreal.MathLibrary.transform_location(grip, unreal.Vector(*local)))
        origin = point((0, 0, 0))
        basis = [(point(axis) - origin) for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
        value = {'hand': hand, 'origin': origin, 'basis': basis,
                 'blade_axis': unit(basis[2]), 'edge': unit(basis[0] * -1.0),
                 'root': point((0, 0, 8.472)), 'middle': point((.7, 0, 39)),
                 'tip': point((4.3, 0, 70.972)), 'centerline_tip': point((0, 0, 71))}
        cache[key] = value
        return value

    # Include both exact notify boundaries as well as every 60 Hz frame.
    times = sorted({round(min(duration, i / 60.0), 9)
                    for i in range(int(math.ceil(duration * 60)) + 1)} | {start, end})
    rows = []
    for t in times:
        current = evaluate(t)
        left, right = max(0.0, t - 1 / 120.0), min(duration, t + 1 / 120.0)
        before, after = evaluate(left), evaluate(right)
        row = {'time': t, 'hand_cm': xyz(current['hand'].translation),
               'hand_scale': xyz(current['hand'].scale3d),
               'weapon_scale': [axis.length() for axis in current['basis']],
               'grip_origin_cm': xyz(current['origin']),
               'blade_root_cm': xyz(current['root']), 'blade_middle_cm': xyz(current['middle']),
               'blade_tip_cm': xyz(current['tip']), 'centerline_tip_cm': xyz(current['centerline_tip']),
               'blade_axis': xyz(current['blade_axis']), 'cutting_edge': xyz(current['edge']),
               'in_contact_window': start - 1e-7 <= t <= end + 1e-7}
        for name in ('middle', 'tip'):
            velocity = (after[name] - before[name]) / (right - left)
            crossblade = velocity - current['blade_axis'] * dot(velocity, current['blade_axis'])
            row[name + '_speed_cm_s'] = velocity.length()
            row[name + '_crossblade_speed_cm_s'] = crossblade.length()
            row[name + '_edge_velocity_dot'] = (dot(current['edge'], unit(crossblade))
                                                if crossblade.length() > 1e-5 else None)
        rows.append(row)

    contact = [row for row in rows if row['in_contact_window']]
    failures = [row['time'] for row in contact if any(
        row[name + '_edge_velocity_dot'] is None or row[name + '_edge_velocity_dot'] <= 0
        for name in ('middle', 'tip'))]
    scale_error = max(abs(scale - 1) for row in rows for scale in row['weapon_scale'])
    # Independently check imported motion and coordinate reflection against the
    # authored manifest. Its tip is the 71 cm centerline, not the curved mesh tip.
    hand_error, tip_error = 0.0, 0.0
    for authored in manifest.get('rows', []):
        actual = evaluate(authored['time'])
        expected_hand = unreal.Vector(authored['hand'][0] * 100, -authored['hand'][1] * 100, authored['hand'][2] * 100)
        expected_tip = unreal.Vector(authored['tip'][0] * 100, -authored['tip'][1] * 100, authored['tip'][2] * 100)
        hand_error = max(hand_error, (actual['hand'].translation - expected_hand).length())
        tip_error = max(tip_error, (actual['centerline_tip'] - expected_tip).length())

    report.update({'samples': len(rows), 'contact_samples': len(contact), 'rows': rows,
                   'contact_edge_failures': failures,
                   'minimum_contact_middle_edge_dot': min(row['middle_edge_velocity_dot'] or 0 for row in contact),
                   'minimum_contact_tip_edge_dot': min(row['tip_edge_velocity_dot'] or 0 for row in contact),
                   'contact_tip_bounds_cm': bounds(contact, 'blade_tip_cm'),
                   'all_tip_bounds_cm': bounds(rows, 'blade_tip_cm'),
                   'maximum_weapon_scale_error': scale_error,
                   'maximum_hand_import_error_cm': hand_error,
                   'maximum_centerline_tip_import_error_cm': tip_error})
    assert not failures, ('Blade back/flat leads during active damage', failures)
    assert scale_error < .01, ('Weapon inherited incorrect skeletal scale', scale_error)
    assert hand_error < .5 and tip_error < .75, ('Imported motion/grip differs from authored motion', hand_error, tip_error)
    assert report['contact_tip_bounds_cm'][0][1] > 90.0, 'Cut does not reach the forward close-combat space'
    report['state'] = 'passed'
    save()
    unreal.log('NATIVE_BLADE_VERIFIED ' + json.dumps({key: report[key] for key in (
        'state', 'contact_samples', 'minimum_contact_middle_edge_dot', 'minimum_contact_tip_edge_dot',
        'contact_tip_bounds_cm', 'maximum_weapon_scale_error', 'maximum_hand_import_error_cm',
        'maximum_centerline_tip_import_error_cm')}))
except Exception:
    report['state'] = 'failed'
    report['error'] = traceback.format_exc()
    save()
    raise
