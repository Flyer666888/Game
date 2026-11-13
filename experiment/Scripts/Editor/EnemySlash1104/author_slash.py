"""Retiming and asset assignment for the four playable sword enemies."""
import bisect
import hashlib
import json
import shutil
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUT = PROJECT / 'Docs/Gameplay/EnemySlash1104'
ASSETS = unreal.EditorAssetLibrary
ANIM = unreal.AnimationLibrary
ROOT = '/Game/ReversedScale/Characters/WuxiaMale/'
SOURCE = ROOT + 'Animations/Wuxia_Attack_Sword_Natural_v04'
DEST = ROOT + 'Animations/Wuxia_Attack_Sword_Quick_v05'
ENEMIES = '/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'
TIMINGS = ('telegraph_seconds', 'attack_seconds', 'recover_seconds')
FPS, TOTAL_FRAMES, START_FRAME, END_FRAME = 30, 45, 18, 25
START, END, DURATION = (frame / FPS for frame in (START_FRAME, END_FRAME, TOTAL_FRAMES))


def asset_file(path):
    return PROJECT / 'Content' / (path.removeprefix('/Game/') + '.uasset')


def backup(path):
    source = asset_file(path)
    target = OUT / 'Backups' / source.relative_to(PROJECT / 'Content')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source, target)


def notifications(animation):
    return [(track, event) for track in ANIM.get_animation_notify_track_names(animation)
            for event in ANIM.get_animation_notify_events_for_track(animation, track)]


def read_window(animation):
    events = notifications(animation)
    assert len(events) == 1, 'Expected exactly one attack notify'
    track, event = events[0]
    notify = event.get_editor_property('notify_state_class')
    assert notify and isinstance(notify, unreal.NLEnemyAttackWindowNotifyState)
    return track, ANIM.get_anim_notify_event_trigger_time(event), ANIM.get_anim_notify_event_duration(event)


def retime(source):
    track, old_start, old_span = read_window(source)
    old_end = old_start + old_span
    old_duration = source.get_play_length()
    # Keep the contact arc legible, compress the raised pose and long reset, and
    # interpolate the time map with shared tangents so speed never steps at impact.
    new_times = (0.0, 0.33, START, END, 1.12, DURATION)
    old_times = (0.0, 0.46, old_start, old_end, 1.57, old_duration)
    slopes = [(b - a) / (d - c) for a, b, c, d in
              zip(old_times, old_times[1:], new_times, new_times[1:])]
    tangents = [0.0] + [2 * a * b / (a + b) for a, b in zip(slopes, slopes[1:])] + [0.0]

    def source_time(t):
        i = min(bisect.bisect_right(new_times, t) - 1, len(new_times) - 2)
        width = new_times[i + 1] - new_times[i]
        u = (t - new_times[i]) / width
        u2, u3 = u * u, u * u * u
        return ((2 * u3 - 3 * u2 + 1) * old_times[i]
                + (u3 - 2 * u2 + u) * width * tangents[i]
                + (-2 * u3 + 3 * u2) * old_times[i + 1]
                + (u3 - u2) * width * tangents[i + 1])

    assert not ANIM.get_animation_curve_names(source, unreal.RawCurveTrackTypes.RCT_TRANSFORM)
    curve_names = ANIM.get_animation_curve_names(source, unreal.RawCurveTrackTypes.RCT_FLOAT)
    mesh = ASSETS.load_asset(ROOT + 'SK_WuxiaMale_Hands_v04')
    opts = unreal.AnimPoseEvaluationOptions()
    opts.evaluation_type = unreal.AnimDataEvalType.COMPRESSED
    opts.optional_skeletal_mesh = mesh
    opts.should_retarget = False
    opts.extract_root_motion = False
    times = [i / FPS for i in range(TOTAL_FRAMES + 1)]
    poses = [unreal.AnimPoseExtensions.get_anim_pose_at_time(source, source_time(t), opts) for t in times]
    assert all(unreal.AnimPoseExtensions.is_valid(pose) for pose in poses)

    candidate = ASSETS.load_asset(DEST) if ASSETS.does_asset_exist(DEST) else ASSETS.duplicate_asset(SOURCE, DEST)
    controller = candidate.controller
    model = source.controller.get_model_interface()
    settle_bones = {'spine_01', 'spine_02', 'spine_03', 'neck_01', 'head', 'clavicle_l', 'clavicle_r',
                    'upperarm_l', 'upperarm_r', 'lowerarm_l', 'lowerarm_r', 'hand_l', 'hand_r'}
    controller.open_bracket('Compact sword windup, continuous cut and eased recovery', False)
    try:
        controller.set_frame_rate(unreal.FrameRate(numerator=FPS, denominator=1), False)
        controller.set_number_of_frames(unreal.FrameNumber(value=TOTAL_FRAMES), False)
        for bone in model.get_bone_track_names():
            keys = [unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.LOCAL) for pose in poses]
            rotations = [key.rotation for key in keys]
            if str(bone) in settle_bones:
                for i, t in enumerate(times):
                    u = max(0.0, (t - 1.02) / (DURATION - 1.02))
                    alpha = 0.22 * u * u * (3.0 - 2.0 * u)
                    rotations[i] = unreal.MathLibrary.quat_slerp(rotations[i], rotations[0], alpha)
            assert controller.set_bone_track_keys(bone, [key.translation for key in keys], rotations,
                                                   [key.scale3d for key in keys], False), str(bone)
        for name in curve_names:
            identifier = unreal.AnimationCurveIdentifier()
            identifier.set_curve_identifier(name, unreal.RawCurveTrackTypes.RCT_FLOAT)
            keys = [unreal.RichCurveKey(time=t, value=unreal.AnimPoseExtensions.get_curve_weight(pose, name),
                                        interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR)
                    for t, pose in zip(times, poses)]
            assert controller.set_curve_keys(identifier, keys, False), str(name)
    finally:
        controller.close_bracket(False)
    ANIM.remove_animation_notify_events_by_track(candidate, track)
    assert ANIM.add_animation_notify_state_event(candidate, track, START, END - START, unreal.NLEnemyAttackWindowNotifyState)
    candidate.set_preview_skeletal_mesh(mesh)
    assert abs(candidate.get_play_length() - DURATION) < 0.001
    _, start, span = read_window(candidate)
    assert abs(start - START) < 0.002 and abs(span - (END - START)) < 0.002
    assert ASSETS.save_loaded_asset(candidate, False)
    return candidate


assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
source = ASSETS.load_asset(SOURCE)
source_hash = hashlib.sha256(asset_file(SOURCE).read_bytes()).hexdigest()
candidate = retime(source)
rows = []
for key, factor in (('sword', 1.0), ('GM01', 1.2), ('GM04', 1.2), ('boss', 1.2)):
    path = ENEMIES + key
    blueprint = ASSETS.load_asset(path)
    default = unreal.get_default_object(ASSETS.load_blueprint_class(path))
    assert default.get_editor_property('attack_animation') in (source, candidate), path
    assert default.get_editor_property('enemy_skeletal_mesh').get_editor_property('skeleton') == candidate.get_editor_property('skeleton')
    backup(path)
    brain = default.get_enemy_brain()
    previous = [brain.get_editor_property(prop) for prop in TIMINGS]
    desired = [phase * factor for phase in (START, END - START, DURATION - END)]
    default.set_editor_property('attack_animation', candidate)
    for prop, value in zip(TIMINGS, desired):
        brain.set_editor_property(prop, value)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    check = unreal.get_default_object(ASSETS.load_blueprint_class(path))
    assert check.get_editor_property('attack_animation') == candidate
    assert all(abs(check.get_enemy_brain().get_editor_property(prop) - value) < 0.001
               for prop, value in zip(TIMINGS, desired)), path
    assert ASSETS.save_loaded_asset(blueprint, False), path
    rows.append({'enemy': key, 'before_seconds': previous, 'after_seconds': desired})

damage_rows = []
for name, damage in (('DA_YueyaoMelee', 15.0), ('DA_PlayerBladeQi', 10.0)):
    path = '/Game/ReversedScale/Combat/' + name
    backup(path)
    definition = ASSETS.load_asset(path)
    previous = definition.get_editor_property('damage')
    definition.set_editor_property('damage', damage)
    assert ASSETS.save_loaded_asset(definition, False)
    assert definition.get_editor_property('damage') == damage
    damage_rows.append({'definition': name, 'before': previous, 'after': damage})

assert hashlib.sha256(asset_file(SOURCE).read_bytes()).hexdigest() == source_hash
(OUT / 'AssetChanges.json').write_text(json.dumps({'state': 'passed', 'clip': candidate.get_path_name(),
    'duration_seconds': DURATION, 'notify_seconds': [START, END], 'enemies': rows, 'damage': damage_rows},
    ensure_ascii=False, indent=2), encoding='utf-8')
