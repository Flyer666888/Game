"""Retarget six unedited 3583 sword clips to the confirmed NativeRigV07 mesh.

Run in the review worker, never in the user's live editing session. This creates
isolated IK assets and review clips. It does not bind gameplay, author a strike,
change a skeleton/mesh, crop a clip, change playback speed, or add attack events.

The imported target has a 100x scale on Hips. UE's retarget processor bakes all
reference scales into translations and uses scale 1 internally; after native
retargeting we restore the *existing* target local bind offsets and
scales, retaining every retargeted rotation and the complete global pelvis path.
The only other conversion is a constant -90 degree root yaw, from source +Y to
the unchanged target +X coordinate convention.
"""
import hashlib
import json
import math
from pathlib import Path
import unreal

P = Path(unreal.Paths.project_dir()).resolve()
OUT = P / 'Docs/Gameplay/PackSlashReview1104'
OUT.mkdir(parents=True, exist_ok=True)
A = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
BASE = '/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07'
DEST = BASE + '/PackSlashCandidates/V3'
RIGS = DEST + '/RetargetSetup'
SOURCE_MESH = '/Game/Character/Mesh/SK_Mannequin'
TARGET_MESH = BASE + '/SK_WuxiaMale_Native_v07'
CLIPS = ['Anim_CSATLI_01', 'Anim_CSATLI_02', 'Anim_CSATLI_03',
         'Anim_CSATLI_04', 'Anim_CSAT_heavy_01', 'Anim_CSAT_heavy_02']
SOURCE = unreal.RetargetSourceOrTarget.SOURCE
TARGET = unreal.RetargetSourceOrTarget.TARGET
WORLD = unreal.AnimPoseSpaces.WORLD
LOCAL = unreal.AnimPoseSpaces.LOCAL


def record(t):
    return {'p': [t.translation.x, t.translation.y, t.translation.z],
            'q': [t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w],
            's': [t.scale3d.x, t.scale3d.y, t.scale3d.z]}


def quat_values(q):
    return (q.x, q.y, q.z, q.w)


def qmul(a, b):
    x, y, z, w = a
    X, Y, Z, W = b
    return (w*X+x*W+y*Z-z*Y, w*Y-x*Z+y*W+z*X,
            w*Z+x*Y-y*X+z*W, w*W-x*X-y*Y-z*Z)


def qinv(q):
    return (-q[0], -q[1], -q[2], q[3])


def rotation(q):
    return unreal.Quat(x=q[0], y=q[1], z=q[2], w=q[3])


def hashes(assets):
    result = {}
    for asset in assets:
        package = asset.get_path_name().split('.')[0]
        path = P / 'Content' / (package.removeprefix('/Game/') + '.uasset')
        if not path.is_file():
            raise RuntimeError('Cannot fingerprint protected asset: ' + str(path))
        result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def create(name, kind, factory):
    path = RIGS + '/' + name
    return A.load_asset(path) if A.does_asset_exist(path) else TOOLS.create_asset(name, RIGS, kind, factory)


source_mesh = A.load_asset(SOURCE_MESH)
target_mesh = A.load_asset(TARGET_MESH)
assert source_mesh and target_mesh
target_skeleton = target_mesh.get_editor_property('skeleton')
source_skeleton = source_mesh.get_editor_property('skeleton')
protected = [target_mesh, target_skeleton, source_mesh, source_skeleton]
protected += [A.load_asset('/Game/Animations/Sword/' + n) for n in CLIPS]
assert all(protected)
before_hashes = hashes(protected)
ref = unreal.AnimPoseExtensions.get_reference_pose(target_skeleton)
names = list(unreal.AnimPoseExtensions.get_bone_names(ref))
assert len(names) == 41, 'Expected the unchanged supplied 41-bone native skeleton'
local_ref = {str(b): unreal.AnimPoseExtensions.get_bone_pose(ref, b, LOCAL) for b in names}
world_ref = {str(b): unreal.AnimPoseExtensions.get_bone_pose(ref, b, WORLD) for b in names}
assert abs(local_ref['Hips'].scale3d.x - 100.0) < .01

# Explicit homologous chains avoid accidentally mapping UE auxiliary IK/twist
# bones to Mixamo anatomical bones. Chain matching itself is exact automatic.
source_chains = [('Spine', 'spine_01', 'spine_03'), ('Head', 'neck_01', 'head')]
target_chains = [('Spine', 'Spine', 'Spine2'), ('Head', 'Neck', 'Head')]
for side, suffix in [('Left', 'l'), ('Right', 'r')]:
    source_chains += [(side+'Clavicle', 'clavicle_'+suffix, 'clavicle_'+suffix),
                      (side+'Arm', 'upperarm_'+suffix, 'hand_'+suffix),
                      (side+'Leg', 'thigh_'+suffix, 'foot_'+suffix),
                      (side+'Toe', 'ball_'+suffix, 'ball_'+suffix),
                      (side+'Thumb', 'thumb_01_'+suffix, 'thumb_03_'+suffix),
                      (side+'Index', 'index_01_'+suffix, 'index_03_'+suffix)]
    target_chains += [(side+'Clavicle', side+'Shoulder', side+'Shoulder'),
                      (side+'Arm', side+'Arm', side+'Hand'),
                      (side+'Leg', side+'UpLeg', side+'Foot'),
                      (side+'Toe', side+'ToeBase', side+'ToeBase'),
                      (side+'Thumb', side+'HandThumb1', side+'HandThumb3'),
                      (side+'Index', side+'HandIndex1', side+'HandIndex3')]


def make_rig(name, mesh, pelvis, chains):
    rig = create(name, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(rig)
    assert c.set_skeletal_mesh(mesh)
    assert c.set_retarget_root(pelvis)
    for chain in list(c.get_retarget_chains()):
        c.remove_retarget_chain(chain.chain_name)
    for chain, start, end in chains:
        assert str(c.add_retarget_chain(chain, start, end, '')) == chain
    # No hand-authored IK solver: preserve the original full FK performance.
    for i in reversed(range(c.get_num_solvers())):
        assert c.remove_solver(i)
    assert A.save_loaded_asset(rig, False)
    return rig


source_rig = make_rig('IK_PackSource_1104', source_mesh, 'pelvis', source_chains)
target_rig = make_rig('IK_Native41_1104', target_mesh, 'Hips', target_chains)
retargeter = create('RTG_Pack_Native41_1104', unreal.IKRetargeter, unreal.IKRetargetFactory())
rc = unreal.IKRetargeterController.get_controller(retargeter)
rc.set_ik_rig(SOURCE, source_rig)
rc.set_ik_rig(TARGET, target_rig)
rc.set_preview_mesh(SOURCE, source_mesh)
rc.set_preview_mesh(TARGET, target_mesh)
rc.remove_all_ops()
# Hips is the topmost target bone. A separate root-motion-generation op would
# overwrite its pelvis performance; the pelvis op already carries source motion.
for op in ['IKRetargetPelvisMotionOp', 'IKRetargetFKChainsOp', 'IKRetargetCurveRemapOp']:
    assert rc.add_retarget_op('/Script/IKRig.' + op) >= 0
rc.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
for chain, _, _ in target_chains:
    assert str(rc.get_source_chain(chain)) == chain
# Every homologous chain here has the same anatomical joint count. Interpolated
# mode samples by limb length and mixes the elbow/knee with adjacent joints when
# the two characters have different segment proportions. Keep joint identity.
fk_controller = rc.get_op_controller(1)
fk_settings = fk_controller.get_settings()
fk_chains = list(fk_settings.chains_to_retarget)
for chain in fk_chains:
    chain.rotation_mode = unreal.FKChainRotationMode.ONE_TO_ONE
fk_settings.chains_to_retarget = fk_chains
fk_controller.set_settings(fk_settings)
for side in [SOURCE, TARGET]:
    rc.reset_retarget_pose(rc.get_current_retarget_pose_name(side), [], side)

# Root rotation offsets in IK retarget poses are BONE local, not world local.
half = math.sqrt(.5)
yaw_plus_90 = (0.0, 0.0, half, half)
yaw_minus_90 = (0.0, 0.0, -half, half)
hip_ref_q = quat_values(local_ref['Hips'].rotation)
hip_pose_offset = qmul(qmul(qinv(hip_ref_q), yaw_plus_90), hip_ref_q)
rc.set_rotation_offset_for_retarget_pose_bone('Hips', rotation(hip_pose_offset), TARGET)
# Align SOURCE to the existing native A pose. AutoAlignAllBones first resets the
# pose on the chosen side; choosing SOURCE preserves the TARGET +90 degree yaw.
rc.auto_align_all_bones(SOURCE, unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN)
assert A.save_loaded_asset(retargeter, False)

inputs = unreal.IKRetargetBatchOperationInputs()
inputs.assets_to_retarget = [A.find_asset_data('/Game/Animations/Sword/' + n) for n in CLIPS]
inputs.source_mesh = source_mesh
inputs.target_mesh = target_mesh
inputs.ik_retarget_asset = retargeter
inputs.target_path = DEST
inputs.prefix = 'Pack_'
inputs.include_referenced_assets = False
inputs.overwrite_existing_files = True  # Only this isolated review directory.
result = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
anims = [d.get_asset() for d in result if isinstance(d.get_asset(), unreal.AnimSequence)]
assert len(anims) == len(CLIPS), 'Expected all six original package clips'

options = unreal.AnimPoseEvaluationOptions()
options.evaluation_type = unreal.AnimDataEvalType.RAW
options.optional_skeletal_mesh = target_mesh
options.should_retarget = False
options.extract_root_motion = False
report = {'state': 'preparing', 'source_mesh': SOURCE_MESH, 'target_mesh': TARGET_MESH,
          'target_skeleton': target_skeleton.get_path_name(), 'source_rig': source_rig.get_path_name(),
          'target_rig': target_rig.get_path_name(), 'retargeter': retargeter.get_path_name(),
          'chain_mapping': {c: str(rc.get_source_chain(c)) for c, _, _ in target_chains},
          'retarget_pose_offsets': {str(b): list(quat_values(rc.get_rotation_offset_for_retarget_pose_bone(b, TARGET))) for b in names},
          'auto_align_side': 'SOURCE (unit-scale source to native target A-pose)',
          'fk_rotation_mode': 'ONE_TO_ONE (equal anatomical joint counts)',
          'coordinate_conversion': 'constant root yaw -90 degrees, source +Y to native +X',
          'unit_repair': 'existing target local bind scale and fixed bone offsets; all retargeted rotations and complete pelvis displacement retained',
          'clips': []}
poses_report = {'fps': 30, 'mesh': TARGET_MESH, 'reference': {b: record(t) for b, t in world_ref.items()}, 'clips': []}
source_options = unreal.AnimPoseEvaluationOptions()
source_options.evaluation_type = unreal.AnimDataEvalType.RAW
source_options.optional_skeletal_mesh = source_mesh
source_options.should_retarget = False
source_options.extract_root_motion = False
source_reference_pose = unreal.AnimPoseExtensions.get_reference_pose(source_skeleton)
source_pelvis_height = unreal.AnimPoseExtensions.get_bone_pose(source_reference_pose, 'pelvis', WORLD).translation.z
height_ratio = world_ref['Hips'].translation.z / source_pelvis_height
direction_pairs = [('upperarm_r', 'lowerarm_r', 'RightArm', 'RightForeArm'),
                   ('lowerarm_r', 'hand_r', 'RightForeArm', 'RightHand'),
                   ('thigh_r', 'calf_r', 'RightUpLeg', 'RightLeg'),
                   ('calf_r', 'foot_r', 'RightLeg', 'RightFoot'),
                   ('thigh_l', 'calf_l', 'LeftUpLeg', 'LeftLeg'),
                   ('calf_l', 'foot_l', 'LeftLeg', 'LeftFoot')]
audit = {'target_to_source_pelvis_height_ratio': height_ratio, 'clips': []}


def angle_degrees(a, b):
    denominator = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    assert denominator > 1e-8
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x*y for x, y in zip(a, b))/denominator))))


for anim in anims:
    assert anim.get_path_name().startswith(DEST + '/')
    assert anim.get_editor_property('skeleton') == target_skeleton
    source_name = anim.get_name().removeprefix('Pack_')
    assert source_name in CLIPS
    original = A.load_asset('/Game/Animations/Sword/' + source_name)
    duration = anim.get_play_length()
    assert abs(duration-original.get_play_length()) < .0001
    frames = unreal.AnimationLibrary.get_num_frames(anim)
    assert frames > 0
    keys = {str(b): [] for b in names}
    for i in range(frames+1):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(anim, duration*i/frames, options)
        assert unreal.AnimPoseExtensions.is_valid(pose)
        for b in names:
            keys[str(b)].append(unreal.AnimPoseExtensions.get_bone_pose(pose, b, LOCAL))
    uncorrected_root_scales = [record(t)['s'] for t in keys['Hips']]
    controller = anim.controller
    controller.open_bracket('Restore existing native rig units and forward coordinates', False)
    try:
        for b in names:
            name = str(b)
            values = keys[name]
            if name == 'Hips':
                positions = [unreal.Vector(t.translation.y, -t.translation.x, t.translation.z) for t in values]
                rotations = [rotation(qmul(yaw_minus_90, quat_values(t.rotation))) for t in values]
            else:
                positions = [local_ref[name].translation for _ in values]
                rotations = [t.rotation for t in values]
            scales = [local_ref[name].scale3d for _ in values]
            controller.add_bone_curve(b, False)
            assert controller.set_bone_track_keys(b, positions, rotations, scales, False), name
    finally:
        controller.close_bracket(False)
    anim.set_preview_skeletal_mesh(target_mesh)
    assert A.save_loaded_asset(anim, False)
    assert abs(anim.get_play_length()-duration) < .0001
    samples = []
    count = max(1, round(duration*30))
    for i in range(count+1):
        t = duration*i/count
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(anim, t, options)
        world = {str(b): record(unreal.AnimPoseExtensions.get_bone_pose(pose, b, WORLD)) for b in names}
        assert all(math.isfinite(v) for bone in world.values() for group in bone.values() for v in group)
        assert max(abs(v-100) for v in world['Hips']['s']) < .01
        samples.append({'t': t, 'bones': world})
    root_points = [f['bones']['Hips']['p'] for f in samples]
    pelvis_errors = []
    direction_errors = {t1+'_'+t2: [] for _, _, t1, t2 in direction_pairs}
    for sample in samples:
        source_pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(original, sample['t'], source_options)
        source_bones = {n: record(unreal.AnimPoseExtensions.get_bone_pose(source_pose, n, WORLD))
                        for n in {'pelvis'} | {n for pair in direction_pairs for n in pair[:2]}}
        sp = source_bones['pelvis']['p']
        expected_pelvis = [sp[1]*height_ratio, -sp[0]*height_ratio, sp[2]*height_ratio]
        pelvis_errors.append(math.dist(expected_pelvis, sample['bones']['Hips']['p']))
        for s1, s2, t1, t2 in direction_pairs:
            sv = [source_bones[s2]['p'][j]-source_bones[s1]['p'][j] for j in range(3)]
            expected = [sv[1], -sv[0], sv[2]]
            actual = [sample['bones'][t2]['p'][j]-sample['bones'][t1]['p'][j] for j in range(3)]
            direction_errors[t1+'_'+t2].append(angle_degrees(expected, actual))
    audit_row = {'name': anim.get_name(), 'pelvis_path_max_error_cm': max(pelvis_errors),
                 'bone_direction_error_degrees': {n: {'first': v[0], 'mean': sum(v)/len(v), 'max': max(v)} for n, v in direction_errors.items()}}
    audit['clips'].append(audit_row)
    assert max(pelvis_errors) < .1, 'Original global pelvis displacement was not preserved'
    row = {'name': anim.get_name(), 'source': original.get_path_name(), 'asset': anim.get_path_name(),
           'duration': duration, 'source_duration': original.get_play_length(), 'frames': frames,
           'root_scale_before_repair': uncorrected_root_scales[0],
           'root_scale_after_repair': samples[0]['bones']['Hips']['s'],
           'pelvis_range_cm': [max(p[j] for p in root_points)-min(p[j] for p in root_points) for j in range(3)]}
    report['clips'].append(row)
    poses_report['clips'].append(dict(row, frames=samples))
    unreal.log('PACK_SLASH_CANDIDATE ' + anim.get_path_name())

after_hashes = hashes(protected)
report['protected_assets_sha256_before'] = before_hashes
report['protected_assets_sha256_after'] = after_hashes
assert before_hashes == after_hashes, 'A protected original asset changed on disk'
report['state'] = 'retargeted_review_only'
(OUT/'CandidateManifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT/'CandidateMotion.json').write_text(json.dumps(poses_report, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
(OUT/'RetargetDirectionAuditV3.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('PACK_SLASH_CANDIDATES_READY ' + str(OUT/'CandidateManifest.json'))
