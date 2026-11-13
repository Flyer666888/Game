"""Author one new planted talisman gesture from the existing exported idle pose.

Run in Unreal Editor before create_mixed_lab.py. This creates only
Wuxia_Cast_Talisman, never a mesh, skeleton, source motion or blade notify.
"""
import copy
import json
import math
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir())
ROOT = '/Game/ReversedScale/Characters/WuxiaMale'
SOURCE = ROOT + '/Animations/Wuxia_Idle_Planted'
DESTINATION = ROOT + '/Animations/Wuxia_Cast_Talisman'
OUT = PROJECT / 'ArtSource/WuxiaMale/TalismanCast'
POSE_SOURCE = PROJECT / 'ArtSource/WuxiaMale/SwordCombat/SwordCandidatePoses.json'
A = unreal.EditorAssetLibrary
FPS = 30
DURATION = 2.0
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
CHANGED_BONES = ('upperarm_l', 'lowerarm_l', 'hand_l')


def add(a, b): return [x + y for x, y in zip(a, b)]
def sub(a, b): return [x - y for x, y in zip(a, b)]
def mul(a, value): return [x * value for x in a]
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def length(value): return math.sqrt(dot(value, value))
def normalize(value):
    magnitude = length(value)
    if magnitude < 1e-8:
        raise RuntimeError('Cannot normalize a degenerate pose direction.')
    return mul(value, 1.0 / magnitude)
def qmul(a, b):
    xyz = add(add(mul(b[:3], a[3]), mul(a[:3], b[3])), cross(a[:3], b[:3]))
    return xyz + [a[3]*b[3] - dot(a[:3], b[:3])]
def qinverse(q): return [-q[0], -q[1], -q[2], q[3]]
def qrotate(q, value):
    return qmul(qmul(q, value + [0.0]), qinverse(q))[:3]
def qbetween(a, b):
    a, b = normalize(a), normalize(b)
    cosine = max(-1.0, min(1.0, dot(a, b)))
    if cosine < -0.9999:
        axis = normalize(cross(a, [1.0, 0.0, 0.0] if abs(a[0]) < .9 else [0.0, 1.0, 0.0]))
        return axis + [0.0]
    return normalize(cross(a, b) + [1.0 + cosine])
def qblend(a, b, weight):
    if dot(a, b) < 0.0:
        b = mul(b, -1.0)
    cosine = max(-1.0, min(1.0, dot(a, b)))
    if cosine > .9995:
        return normalize(add(mul(a, 1.0-weight), mul(b, weight)))
    angle = math.acos(cosine)
    return add(mul(a, math.sin((1.0-weight)*angle)/math.sin(angle)),
               mul(b, math.sin(weight*angle)/math.sin(angle)))
def smooth(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def world_from_local(local):
    world = {}
    for bone, parent in PARENTS.items():
        transform = local[bone]
        if not parent:
            world[bone] = copy.deepcopy(transform)
        else:
            base = world[parent]
            scaled = [value * scale for value, scale in zip(transform['p'], base['s'])]
            world[bone] = {'p': add(base['p'], qrotate(base['q'], scaled)),
                           'q': normalize(qmul(base['q'], transform['q'])),
                           's': [a*b for a, b in zip(base['s'], transform['s'])]}
    return world


data = json.loads(POSE_SOURCE.read_text(encoding='utf-8'))
idle_local = data['idle_local']
if set(idle_local) != set(PARENTS):
    raise RuntimeError('The cast requires the existing unchanged 23-bone exported idle pose.')
mesh = A.load_asset(ROOT + '/SK_WuxiaMale_Combat')
idle = A.load_asset(SOURCE)
if not mesh or not idle:
    raise RuntimeError('The current Combat mesh and planted idle must exist.')
skeleton = mesh.get_editor_property('skeleton')
if data['skeleton'] != skeleton.get_path_name() or idle.get_editor_property('skeleton') != skeleton:
    raise RuntimeError('The exported pose, current mesh and idle must share the existing skeleton.')
baseline = world_from_local(idle_local)


def left_arm_pose(forward_cm):
    """Keep the shoulder/body fixed and raise the hand to chest height.

    Mesh +Y faces forward (the native mesh is yaw -90). The elbow pole points
    out to the left arm's own side, keeping the gesture clear of the face.
    """
    shoulder = baseline['upperarm_l']['p']
    elbow = baseline['lowerarm_l']['p']
    hand = baseline['hand_l']['p']
    target = add(shoulder, [7.0, forward_cm, -9.0])
    upper_length, lower_length = length(sub(elbow, shoulder)), length(sub(hand, elbow))
    delta = sub(target, shoulder)
    distance, axis = length(delta), normalize(delta)
    if distance >= upper_length + lower_length - .5:
        raise RuntimeError('The restrained talisman hand target exceeds arm reach.')
    pole = [1.0, 0.0, -0.1]
    pole = normalize(sub(pole, mul(axis, dot(pole, axis))))
    projection = (upper_length**2-lower_length**2+distance**2)/(2.0*distance)
    bend = math.sqrt(max(0.0, upper_length**2-projection**2))
    raised_elbow = add(add(shoulder, mul(axis, projection)), mul(pole, bend))
    upper_q = normalize(qmul(qbetween(sub(elbow, shoulder), sub(raised_elbow, shoulder)),
                             baseline['upperarm_l']['q']))
    lower_q = normalize(qmul(qbetween(sub(hand, elbow), sub(target, raised_elbow)),
                             baseline['lowerarm_l']['q']))
    pose = copy.deepcopy(idle_local)
    pose['upperarm_l']['q'] = normalize(qmul(qinverse(baseline['clavicle_l']['q']), upper_q))
    pose['lowerarm_l']['q'] = normalize(qmul(qinverse(upper_q), lower_q))
    # A small wrist opening gives the plane attached to hand_l a readable face.
    wrist_angle = math.radians(12.0)
    pose['hand_l']['q'] = normalize(qmul(idle_local['hand_l']['q'],
                                        [0.0, math.sin(wrist_angle/2.0), 0.0, math.cos(wrist_angle/2.0)]))
    return pose


raised, released = left_arm_pose(38.0), left_arm_pose(43.0)
frames = round(DURATION * FPS)
samples = []
for frame in range(frames + 1):
    time = frame / FPS
    local = copy.deepcopy(idle_local)
    if time < .6:
        first, second, weight = idle_local, raised, smooth(time/.6)
    elif time <= 1.1:
        first, second, weight = raised, raised, 0.0
    elif time <= 1.25:
        first, second, weight = raised, released, smooth((time-1.1)/.15)
    else:
        first, second, weight = released, idle_local, smooth((time-1.25)/.75)
    for bone in CHANGED_BONES:
        local[bone]['q'] = qblend(first[bone]['q'], second[bone]['q'], weight)
    samples.append({'time': time, 'local': local, 'world': world_from_local(local)})

animation = A.load_asset(DESTINATION) if A.does_asset_exist(DESTINATION) else A.duplicate_asset(SOURCE, DESTINATION)
if not animation or animation.get_editor_property('skeleton') != skeleton:
    raise RuntimeError('Could not create the separate talisman animation on the existing skeleton.')
animation.set_editor_property('enable_root_motion', False)
animation.set_editor_property('rate_scale', 1.0)
controller = animation.controller
controller.open_bracket('Author planted left-hand talisman casting gesture', False)
try:
    controller.set_frame_rate(unreal.FrameRate(numerator=FPS, denominator=1), False)
    controller.set_number_of_frames(unreal.FrameNumber(value=frames), False)
    for bone in PARENTS:
        keys = [sample['local'][bone] for sample in samples]
        if not controller.set_bone_track_keys(bone, [unreal.Vector(*key['p']) for key in keys],
                                              [unreal.Quat(*key['q']) for key in keys],
                                              [unreal.Vector(*key['s']) for key in keys], False):
            raise RuntimeError('Cannot author the cast track: ' + bone)
finally:
    controller.close_bracket(False)
for track in unreal.AnimationLibrary.get_animation_notify_track_names(animation):
    unreal.AnimationLibrary.remove_animation_notify_events_by_track(animation, track)
if not A.save_loaded_asset(animation, False):
    raise RuntimeError('Could not save the separate cast animation.')
OUT.mkdir(parents=True, exist_ok=True)
clip = {'name': 'Wuxia_Cast_Talisman', 'asset': animation.get_path_name(),
        'source_asset': SOURCE, 'role': 'cast', 'duration': DURATION,
        'frames': frames, 'samples': samples}
(OUT / 'TalismanCastPoses.json').write_text(json.dumps({
    'mesh': mesh.get_path_name(), 'skeleton': skeleton.get_path_name(),
    'fps': FPS, 'reference': data['reference'], 'clips': [clip]},
    ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
(OUT / 'TalismanCastAuthoring.json').write_text(json.dumps({
    'asset': animation.get_path_name(), 'source_asset_preserved': SOURCE,
    'pose_source': str(POSE_SOURCE), 'mesh_preserved': mesh.get_path_name(),
    'skeleton': skeleton.get_path_name(), 'duration_seconds': animation.get_play_length(),
    'changed_bones': list(CHANGED_BONES), 'translation_and_scale_tracks_preserved': True,
    'lower_body_and_root': 'Exact exported planted idle local transforms at every key.',
    'raise_end_seconds': .6, 'release_start_seconds': 1.1,
    'release_end_seconds': 1.25, 'settled_seconds': 2.0,
    'hand_l_at_raise_end_cm': samples[18]['world']['hand_l']['p'],
    'hand_l_at_release_end_cm': samples[38]['world']['hand_l']['p'],
    'root_motion_enabled': False, 'damage_notify_count': 0,
    'scope': 'Only a new animation and its pose report. Mesh, face, feet, morphs, hilt and source clips are preserved.'
}, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('TALISMAN_CAST_AUTHORED ' + DESTINATION)
