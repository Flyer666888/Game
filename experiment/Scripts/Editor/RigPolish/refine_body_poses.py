"""Generate separate upright enemy motion candidates; never changes BP references.

Run in the UE editor, outside PIE. The source skeleton, mesh, animation assets,
root track, clip length, curves and notifies stay unchanged. Only pelvis position
and thigh/calf/foot rotations are authored on *_Upright_v01 copies. The shared
idle stance is also present in Attack and Cast, so this is a stance correction,
not a claim that the original attack alone introduced the bent knees.

The pure Python IK functions can be imported without Unreal for numerical QA.
"""
import copy
import json
import math
from pathlib import Path

PARENTS = {
    'root': None, 'pelvis': 'root', 'spine_01': 'pelvis', 'spine_02': 'spine_01',
    'spine_03': 'spine_02', 'neck_01': 'spine_03', 'head': 'neck_01',
    'clavicle_l': 'spine_03', 'upperarm_l': 'clavicle_l',
    'lowerarm_l': 'upperarm_l', 'hand_l': 'lowerarm_l',
    'clavicle_r': 'spine_03', 'upperarm_r': 'clavicle_r',
    'lowerarm_r': 'upperarm_r', 'hand_r': 'lowerarm_r',
    'thigh_l': 'pelvis', 'calf_l': 'thigh_l', 'foot_l': 'calf_l', 'ball_l': 'foot_l',
    'thigh_r': 'pelvis', 'calf_r': 'thigh_r', 'foot_r': 'calf_r', 'ball_r': 'foot_r',
}
CHANGED = ('pelvis', 'thigh_l', 'calf_l', 'foot_l', 'thigh_r', 'calf_r', 'foot_r')
CLIPS = ('Wuxia_Idle_Planted', 'Wuxia_Attack_Sword', 'Wuxia_Cast_Talisman',
         'Wuxia_Walk_Sword', 'Wuxia_Hit_Sword')
LIFT_CM = 4.5
MIN_KNEE_BEND_DEGREES = 12.0


def add(a, b): return [x + y for x, y in zip(a, b)]
def sub(a, b): return [x - y for x, y in zip(a, b)]
def mul(a, v): return [x * v for x in a]
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def length(v): return math.sqrt(dot(v, v))
def normalize(v):
    n = length(v)
    if n < 1e-10:
        raise RuntimeError('Degenerate IK direction')
    return mul(v, 1.0 / n)
def qmul(a, b):
    return add(add(mul(b[:3], a[3]), mul(a[:3], b[3])), cross(a[:3], b[:3])) + [a[3]*b[3]-dot(a[:3], b[:3])]
def qinverse(q): return [-q[0], -q[1], -q[2], q[3]]
def qrotate(q, v): return qmul(qmul(q, list(v) + [0.0]), qinverse(q))[:3]
def qbetween(a, b):
    a, b = normalize(a), normalize(b)
    cosine = max(-1.0, min(1.0, dot(a, b)))
    if cosine < -0.999999:
        axis = normalize(cross(a, [1., 0., 0.] if abs(a[0]) < .9 else [0., 1., 0.]))
        return axis + [0.0]
    return normalize(cross(a, b) + [1.0 + cosine])
def qangle(a, b):
    return math.degrees(2.0 * math.acos(min(1.0, abs(dot(normalize(a), normalize(b))))))


def world_from_local(local):
    world = {}
    for bone, parent in PARENTS.items():
        t = local[bone]
        if parent is None:
            world[bone] = copy.deepcopy(t)
        else:
            p = world[parent]
            world[bone] = {
                'p': add(p['p'], qrotate(p['q'], [x*y for x, y in zip(t['p'], p['s'])])),
                'q': normalize(qmul(p['q'], t['q'])),
                's': [x*y for x, y in zip(t['s'], p['s'])],
            }
    return world


def knee_bend(world, side):
    hip, knee, ankle = [world[b+'_'+side]['p'] for b in ('thigh', 'calf', 'foot')]
    return math.degrees(math.acos(max(-1., min(1., dot(normalize(sub(knee, hip)), normalize(sub(ankle, knee)))))))


def allowed_lift(world, desired=LIFT_CM):
    """Keep both legs reachable with a small knee bend, never stretching bones."""
    result = desired
    for side in ('l', 'r'):
        h, k, f = [world[b+'_'+side]['p'] for b in ('thigh', 'calf', 'foot')]
        a, b = length(sub(k, h)), length(sub(f, k))
        reach_sq = a*a + b*b + 2*a*b*math.cos(math.radians(MIN_KNEE_BEND_DEGREES))
        horizontal_sq = (h[0]-f[0])**2 + (h[1]-f[1])**2
        if reach_sq <= horizontal_sq:
            return 0.0
        max_height = math.sqrt(reach_sq-horizontal_sq)
        result = min(result, max(0.0, max_height - (h[2]-f[2])))
    return result


def refine(local, lift):
    """Two-bone IK with original bend plane, fixed ankle position/orientation."""
    original = world_from_local(local)
    revised = copy.deepcopy(local)
    root = original['root']
    local_delta = qrotate(qinverse(root['q']), [0., 0., lift])
    revised['pelvis']['p'] = add(revised['pelvis']['p'], [a/b for a, b in zip(local_delta, root['s'])])
    lifted = world_from_local(revised)
    for side in ('l', 'r'):
        thigh, calf, foot = (b+'_'+side for b in ('thigh', 'calf', 'foot'))
        old_h, old_k, fixed_f = [original[b]['p'] for b in (thigh, calf, foot)]
        new_h = lifted[thigh]['p']
        upper, lower = length(sub(old_k, old_h)), length(sub(fixed_f, old_k))
        axis = normalize(sub(fixed_f, new_h))
        d = length(sub(fixed_f, new_h))
        if d >= upper+lower-1e-5 or d <= abs(upper-lower)+1e-5:
            raise RuntimeError('Requested lift exceeds leg reach')
        # Preserve the side of the original knee, avoiding an inverted joint.
        hint = sub(old_k, old_h)
        bend = sub(hint, mul(axis, dot(hint, axis)))
        if length(bend) < 1e-6:
            bend = sub([0., 1., 0.], mul(axis, axis[1]))
        bend = normalize(bend)
        along = (upper*upper-lower*lower+d*d)/(2*d)
        height = math.sqrt(max(0.0, upper*upper-along*along))
        new_k = add(add(new_h, mul(axis, along)), mul(bend, height))
        thigh_q = normalize(qmul(qbetween(sub(old_k, old_h), sub(new_k, new_h)), original[thigh]['q']))
        calf_q = normalize(qmul(qbetween(sub(fixed_f, old_k), sub(fixed_f, new_k)), original[calf]['q']))
        revised[thigh]['q'] = normalize(qmul(qinverse(lifted['pelvis']['q']), thigh_q))
        revised[calf]['q'] = normalize(qmul(qinverse(thigh_q), calf_q))
        revised[foot]['q'] = normalize(qmul(qinverse(calf_q), original[foot]['q']))
    return revised


def sample_metrics(before, after):
    result = {'foot_position_error_cm': 0., 'foot_rotation_error_degrees': 0.,
              'leg_length_error_cm': 0., 'root_position_error_cm': 0.,
              'root_rotation_error_degrees': 0.,
              'pelvis_lift_cm': after['pelvis']['p'][2]-before['pelvis']['p'][2],
              'knee_bend_before_degrees': {}, 'knee_bend_after_degrees': {}}
    for side in ('l', 'r'):
        for name in ('foot_', 'ball_'):
            b = name+side
            result['foot_position_error_cm'] = max(result['foot_position_error_cm'], length(sub(after[b]['p'], before[b]['p'])))
            result['foot_rotation_error_degrees'] = max(result['foot_rotation_error_degrees'], qangle(after[b]['q'], before[b]['q']))
        for p, b in (('thigh_', 'calf_'), ('calf_', 'foot_')):
            x = abs(length(sub(after[b+side]['p'], after[p+side]['p'])) - length(sub(before[b+side]['p'], before[p+side]['p'])))
            result['leg_length_error_cm'] = max(result['leg_length_error_cm'], x)
        result['knee_bend_before_degrees'][side] = knee_bend(before, side)
        result['knee_bend_after_degrees'][side] = knee_bend(after, side)
    result['root_position_error_cm'] = length(sub(before['root']['p'], after['root']['p']))
    result['root_rotation_error_degrees'] = qangle(before['root']['q'], after['root']['q'])
    return result


def aggregate(rows):
    max_keys = ('foot_position_error_cm', 'foot_rotation_error_degrees', 'leg_length_error_cm',
                'root_position_error_cm', 'root_rotation_error_degrees')
    out = {'max_'+k: max(row[k] for row in rows) for k in max_keys}
    out['pelvis_lift_range_cm'] = [min(row['pelvis_lift_cm'] for row in rows), max(row['pelvis_lift_cm'] for row in rows)]
    for key in ('knee_bend_before_degrees', 'knee_bend_after_degrees'):
        out[key] = {side: [min(row[key][side] for row in rows), max(row[key][side] for row in rows)] for side in ('l', 'r')}
    return out


def loop_seam_metrics(before_first, before_last, after_first, after_last):
    """Compare each bone's loop boundary so aggregate maxima cannot hide a seam."""
    rows = []
    for bone in PARENTS:
        rows.append({
            'before_position_cm': length(sub(before_first[bone]['p'], before_last[bone]['p'])),
            'after_position_cm': length(sub(after_first[bone]['p'], after_last[bone]['p'])),
            'before_rotation_degrees': qangle(before_first[bone]['q'], before_last[bone]['q']),
            'after_rotation_degrees': qangle(after_first[bone]['q'], after_last[bone]['q']),
        })
    result = {'max_'+key: max(row[key] for row in rows) for key in rows[0]}
    result['max_added_position_cm'] = max(0., max(row['after_position_cm']-row['before_position_cm'] for row in rows))
    result['max_added_rotation_degrees'] = max(0., max(row['after_rotation_degrees']-row['before_rotation_degrees'] for row in rows))
    return result


def smooth_lifts(caps, looping=False):
    """Conservative reach smoothing; looping clips include a repeated last key."""
    if looping:
        period = len(caps)-1
        if period < 1 or abs(caps[0]-caps[-1]) > 1e-5:
            raise RuntimeError('Loop reach limits must agree at the repeated endpoint')
        values = [min(caps[i], sum(caps[(i+j) % period] for j in (-2, -1, 0, 1, 2))/5.)
                  for i in range(period)]
        return values + [values[0]]
    return [min(caps[i], sum(caps[max(0, i-2):min(len(caps), i+3)])/len(caps[max(0, i-2):min(len(caps), i+3)]))
            for i in range(len(caps))]


def transform_record(t):
    return {'p': [t.translation.x, t.translation.y, t.translation.z],
            'q': [t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w],
            's': [t.scale3d.x, t.scale3d.y, t.scale3d.z]}


def run():
    import unreal
    project = Path(unreal.Paths.project_dir())
    output = project/'Docs/Gameplay/RigPolish_v01'
    output.mkdir(parents=True, exist_ok=True)
    assets = unreal.EditorAssetLibrary
    root = '/Game/ReversedScale/Characters/WuxiaMale'
    mesh = assets.load_asset(root+'/SK_WuxiaMale_Combat')
    skeleton = mesh.get_editor_property('skeleton')
    if unreal.EditorLevelLibrary.get_game_world():
        raise RuntimeError('Stop PIE before creating animation candidates')
    reference = json.loads((project/'ArtSource/WuxiaMale/SwordCombat/SwordCandidatePoses.json').read_text(encoding='utf-8'))
    if set(reference['reference']) != set(PARENTS) or reference['skeleton'] != skeleton.get_path_name():
        raise RuntimeError('Expected the original unchanged 23-bone enemy skeleton')
    report = {'status': 'running', 'blueprint_references_changed': False,
              'method': '4.5 cm component-space pelvis lift, reach limited, two-bone IK, fixed feet',
              'changed_tracks': list(CHANGED), 'bone_count': len(PARENTS), 'clips': []}
    poses = {'mesh': mesh.get_path_name(), 'skeleton': skeleton.get_path_name(), 'fps': 30,
             'reference': reference['reference'], 'clips': []}

    def write_report():
        (output/'UprightCandidatesReport.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    def pose_at(clip, time, evaluation_type):
        options = unreal.AnimPoseEvaluationOptions()
        options.set_editor_property('evaluation_type', evaluation_type)
        options.set_editor_property('optional_skeletal_mesh', mesh)
        options.set_editor_property('should_retarget', False)
        options.set_editor_property('extract_root_motion', False)
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, time, options)
        if not unreal.AnimPoseExtensions.is_valid(pose):
            raise RuntimeError('Invalid source or candidate pose')
        if set(map(str, unreal.AnimPoseExtensions.get_bone_names(pose))) != set(PARENTS):
            raise RuntimeError('A pose no longer contains exactly the original 23 bones')
        local = {bone: transform_record(unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.LOCAL)) for bone in PARENTS}
        world = {bone: transform_record(unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD)) for bone in PARENTS}
        return local, world

    def signature(clip):
        model = clip.controller.get_model_interface()
        fps = model.get_frame_rate()
        notifies = []
        for track in unreal.AnimationLibrary.get_animation_notify_track_names(clip):
            for event in unreal.AnimationLibrary.get_animation_notify_events_for_track(clip, track):
                state = event.get_editor_property('notify_state_class')
                notify = event.get_editor_property('notify')
                notifies.append({'track': str(track), 'name': str(event.get_editor_property('notify_name')),
                    'start': unreal.AnimationLibrary.get_anim_notify_event_trigger_time(event),
                    'duration': unreal.AnimationLibrary.get_anim_notify_event_duration(event),
                    'state_class': state.get_class().get_path_name() if state else None,
                    'notify_class': notify.get_class().get_path_name() if notify else None})
        return {'duration': clip.get_play_length(), 'frame_rate': [fps.numerator, fps.denominator],
                'frames': model.get_number_of_frames(), 'keys': model.get_number_of_keys(),
                'bone_track_names': sorted(map(str, model.get_bone_track_names())),
                'root_motion': clip.get_editor_property('enable_root_motion'),
                'rate_scale': clip.get_editor_property('rate_scale'),
                'notify_tracks': list(map(str, unreal.AnimationLibrary.get_animation_notify_track_names(clip))),
                'notifies': notifies, 'skeleton': clip.get_editor_property('skeleton').get_path_name()}

    try:
        # Prepare and numerically verify every candidate before creating assets.
        pending = []
        for name in CLIPS:
            source = assets.load_asset(root+'/Animations/'+name)
            if not source or source.get_editor_property('skeleton') != skeleton:
                raise RuntimeError('Missing or incompatible source '+name)
            meta = signature(source)
            frames, duration = meta['frames'], meta['duration']
            if meta['keys'] != frames+1:
                raise RuntimeError('Unexpected source key count')
            samples = []
            for i in range(frames+1):
                t = duration*i/frames
                local, evaluated_world = pose_at(source, t, unreal.AnimDataEvalType.SOURCE)
                reconstructed = world_from_local(local)
                if max(length(sub(evaluated_world[b]['p'], reconstructed[b]['p'])) for b in PARENTS) > .01:
                    raise RuntimeError('FK conventions do not match UE source evaluation')
                samples.append({'time': t, 'local': local, 'world': reconstructed})
            caps = [allowed_lift(s['world']) for s in samples]
            # The Walk has one repeated endpoint. Use periodic neighbours so the
            # IK correction cannot introduce a new seam into that exact loop.
            lifts = smooth_lifts(caps, looping=name == 'Wuxia_Walk_Sword')
            candidate_samples, metrics = [], []
            for sample, lift in zip(samples, lifts):
                local = refine(sample['local'], lift)
                world = world_from_local(local)
                metrics.append(sample_metrics(sample['world'], world))
                candidate_samples.append({'time': sample['time'], 'local': local, 'world': world})
            stats = aggregate(metrics)
            if stats['max_foot_position_error_cm'] > .01 or stats['max_foot_rotation_error_degrees'] > .01 or stats['max_leg_length_error_cm'] > .001:
                raise RuntimeError('Offline IK invariant failed: '+name)
            destination = root+'/Animations/'+name+'_Upright_v01'
            row = {'source': source.get_path_name(), 'destination': destination, 'source_signature': meta,
                   'offline_metrics': stats, 'status': 'offline_passed'}
            if name == 'Wuxia_Walk_Sword':
                seam = loop_seam_metrics(samples[0]['world'], samples[-1]['world'],
                                         candidate_samples[0]['world'], candidate_samples[-1]['world'])
                row['offline_loop_seam'] = seam
                if seam['max_added_position_cm'] > 1e-5 or seam['max_added_rotation_degrees'] > 1e-4:
                    raise RuntimeError('Candidate introduces a new Walk loop seam')
            report['clips'].append(row)
            pending.append((source, destination, candidate_samples, row))
            poses['clips'].append({'name': name+'_Before', 'asset': source.get_path_name(), 'duration': duration, 'frames': frames, 'samples': samples})
            poses['clips'].append({'name': name+'_Upright_v01', 'asset': destination, 'duration': duration, 'frames': frames, 'samples': candidate_samples})
        write_report()
        (output/'UprightCandidatePoses.json').write_text(json.dumps(poses, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        for source, destination, samples, row in pending:
            animation = assets.load_asset(destination) if assets.does_asset_exist(destination) else assets.duplicate_asset(source.get_path_name().split('.')[0], destination)
            if not animation or animation.get_editor_property('skeleton') != skeleton:
                raise RuntimeError('Could not create isolated candidate '+destination)
            controller = animation.controller
            controller.open_bracket('Upright stance with original foot contacts', False)
            try:
                for bone in CHANGED:
                    keys = [sample['local'][bone] for sample in samples]
                    if not controller.set_bone_track_keys(bone, [unreal.Vector(*v['p']) for v in keys],
                                                         [unreal.Quat(*v['q']) for v in keys],
                                                         [unreal.Vector(*v['s']) for v in keys], False):
                        raise RuntimeError('Cannot author candidate track '+bone)
            finally:
                controller.close_bracket(False)
            if signature(animation) != row['source_signature']:
                raise RuntimeError('Duration, frame count, skeleton, root-motion or notifies changed')
            if not assets.save_loaded_asset(animation, False):
                raise RuntimeError('Candidate save failed')
            # Evaluate frame keys and midpoints through UE, including compression.
            validations = {}
            frames, duration = row['source_signature']['frames'], row['source_signature']['duration']
            for label, kind in (('source', unreal.AnimDataEvalType.SOURCE), ('compressed', unreal.AnimDataEvalType.COMPRESSED)):
                results = []
                for i in range(frames*2+1):
                    t = duration*i/(frames*2)
                    _, before = pose_at(source, t, kind)
                    _, after = pose_at(animation, t, kind)
                    results.append(sample_metrics(before, after))
                    if i == 0:
                        first_before, first_after = before, after
                validations[label] = aggregate(results)
                m = validations[label]
                if source.get_name() == 'Wuxia_Walk_Sword':
                    seam = loop_seam_metrics(first_before, before, first_after, after)
                    m['loop_seam'] = seam
                    tolerance = .01 if label == 'compressed' else .001
                    if seam['max_added_position_cm'] > tolerance or seam['max_added_rotation_degrees'] > tolerance:
                        row['runtime_metrics'] = validations
                        raise RuntimeError('UE candidate introduces a new Walk loop seam: '+label)
                # Compression can differ slightly even though the root track is untouched.
                if m['max_foot_position_error_cm'] > .25 or m['max_foot_rotation_error_degrees'] > .35 or m['max_leg_length_error_cm'] > .02 or m['max_root_position_error_cm'] > .01 or m['max_root_rotation_error_degrees'] > .01:
                    row['runtime_metrics'] = validations
                    raise RuntimeError('UE sampled pose invariant failed: '+destination+' '+label)
            row.update({'status': 'passed', 'runtime_metrics': validations, 'metadata_unchanged': True, 'saved': True})
            write_report()
        report['status'] = 'passed'
        report['next_step'] = 'Inspect actual-mesh candidates before deliberately changing enemy BP references.'
        write_report()
        unreal.log('UPRIGHT_CANDIDATES_PASSED '+str(len(pending)))
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        write_report()
        raise


if __name__ == '__main__':
    run()
