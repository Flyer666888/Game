"""Save the completed VR/hands batch and a content-addressed delivery snapshot."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'Docs/AI'
DELIVERY = ROOT / 'Deliveries/VRHands_20261015'

def read_report(name):
    return json.loads((DOCS / name).read_text(encoding='utf-8-sig'))

def manifest(folder, label):
    entries = []
    for path in sorted(folder.rglob('*')):
        if path.is_file() and path.name != 'Manifest.json':
            entries.append({'path': path.relative_to(folder).as_posix(), 'bytes': path.stat().st_size,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    data = {'date': '2026-10-15', 'scope': label, 'file_count': len(entries), 'files': entries}
    (folder / 'Manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data

vr = read_report('VRLabSaved-2026-10-15.json')
inputs = read_report('VRInputAssets-2026-10-15.json')
hands = read_report('PlayerHandsImported-2026-10-15.json')
presentation = read_report('PlayerHandsInitialPresentation-2026-10-15.json')
if not hands.get('success') or not hands.get('mesh_saved') or not presentation.get('visual_binding_restored'):
    raise RuntimeError('Finish mesh/material save and initial art presentation before recording this delivery.')
if not hands.get('mesh_uasset_sha256') or hands['mesh_uasset_sha256'] != presentation.get('hand_mesh_uasset_sha256'):
    raise RuntimeError('Capture the current saved hand mesh before delivery.')
report = {
    'date': '2026-10-15', 'generated_utc': datetime.now(timezone.utc).isoformat(),
    'project': 'ReversedScale / 逆鳞',
    'task': 'SteamVR controller movement and tracked sword swings, followed by realistic player hands',
    'status': 'Compiled_AssetsSaved_InitialArtReviewed_AwaitingUserVRPlay',
    'demo': {'launcher': 'Run_VR_Demo.cmd', 'map': vr['map'], 'pawn': vr['pawn'],
             'game_mode': vr['game_mode'], 'local_ue58_and_base_assets_required': True,
             'packaged_standalone_exe': False,
             'runtime_manifest': r'D:\steam\steamapps\common\SteamVR\steamxr_win64.json',
             'runtime_selection': 'XR_RUNTIME_JSON in the UE child process only; global runtime registry unchanged',
             'command_flags': '-game -vr; no -nohmd',
             'default_project_map': vr['map']},
    'vr': {'left_stick': 'HMD-yaw-relative movement, 180 cm/s',
           'right_stick': '30 degree snap turn, rearm after release',
           'vive_wmr_trackpad': 'Press trackpad to move/turn',
           'left_trigger': 'Held shield guard', 'right_hand_motion': 'Tracked blade sweep, melee damage 10',
           'right_trigger': 'Blade qi, damage 15',
           'start': 'Right A (Index/Touch/PICO/HP) or right menu (Vive/WMR); keyboard G fallback',
           'retry': 'Right B (Index/Touch/PICO/HP) or right grip (Vive/WMR); keyboard R fallback',
           'pause': 'Left B (Index), left Y (Touch/PICO/HP) or left menu (Vive/WMR); P/Esc fallback',
           'height': 'Real HMD floor-relative pose; desktop eye-height matching bypassed',
           'tracking_loss': 'Combat gated by active HMD/controller tracking; fresh settled sample required',
           'sample_basis': 'VROrigin; locomotion and snap turns excluded from damaging swing motion',
           'minimum_swing_speed_cm_s': 220, 'settle_speed_cm_s': 70,
           'input_mapping_count': inputs['mapping_count'], 'optional_keys_skipped': inputs['optional_keys_skipped'],
           'checkpoint_context': vr['checkpoint_ids'], 'wave_count': vr['wave_count'],
           'hardware_acceptance': 'Pending user SteamVR play; no controller poses or inputs were simulated'},
    'hands': {'mesh': hands['mesh'], 'skeleton': hands['skeleton'],
              'bind_pose': hands['reference_pose_comparison'], 'material_slots': hands['material_slots'],
              'lods': hands['lods'], 'materials': hands['materials'], 'textures': hands['textures'],
              'left_hand': 'Same authored mesh and grip animation, mirrored by the existing calibrated left-hand transform',
              'grip_and_hilt': 'Original hand_r, grip animation and weapon attachment transforms retained',
              'source': 'ArtSource/PlayerHands/Realistic',
              'original_assets_unchanged_on_disk': hands.get('original_source_assets_unchanged_on_disk'),
              'presentation': presentation},
    'compile': {'target': 'experimentEditor Win64 Development', 'result': 'Succeeded', 'exit_code': 0,
                'log': 'Docs/AI/BuildLog-VRInputHands-2026-10-15.txt'},
    'preserved': ['Player melee 10 and blade qi 15', 'Enemy face, feet, grounded death and sword grip',
                  'User weapon hilt and shield PBR assets', 'Original desktop lab maps and launchers'],
    'validation_scope': 'Native compilation, asset import/save and initial art presentation only. No tests added or run; no combat, locomotion or save/load exercise by the agent.',
    'remaining_user_review': ['SteamVR headset and both controller tracking', 'Movement and snap turn',
                              'Real sword swing contacts and guard timing', 'Hand appearance and controller grip offsets'],
    'automation': 'Existing automation remains PAUSED',
    'snapshot': 'Deliveries/VRHands_20261015/Manifest.json',
    'before_source': 'Deliveries/BeforeVRInput_20261015/Manifest.json',
}
(DOCS / 'VRHandsDelivery-2026-10-15.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
state_path = DOCS / 'State.md'
state = state_path.read_text(encoding='utf-8-sig')
state = state.replace('CurrentTask: SteamVR movement and tracked swings compiled/map saved; realistic hands imported with unchanged bind pose; initial held-art capture in progress',
                      'CurrentTask: SteamVR movement and tracked swings plus realistic hands saved; initial held-art reviewed; user VR play pending')
state = state.replace('TaskStatus: VRCompiled_HandsAssetsSaved_InitialPresentationInProgress',
                      'TaskStatus: VRCompiled_HandsAssetsSaved_InitialPresentationReviewed_AwaitingUserVRPlay')
section = '''
VRHands_Current_20261015:
  Authorization: SteamVR controller movement and physical sword swings, then realistic left/right hands.
  Map: /Game/ReversedScale/Maps/L_CombatLabVR; native NLVRGameMode / NLVRPlayerCharacter.
  Demo: Run_VR_Demo.cmd; local UE5.8 and full base project required; not a packaged standalone EXE.
  Runtime: SteamVR OpenXR manifest specified for UE child process only; system default registry unchanged.
  Controls: Left stick move180cm/s; right stick snap30deg; pressed Vive/WMR pads; left trigger guard; physical right swing10; right trigger bladeqi15.
  Encounter: Separate VR checkpoint IDs and two mixed waves; Ready does not auto-spawn; start A/menu, retry B/grip, pause leftY/IndexB/menu.
  Tracking: Real HMD floor-relative camera; left/right controller grip poses; origin follows room-scale head; snap/recenter/lost-focus reset blade history.
  Swing: Settled<=70 then speed>=220cm/s; max1sec active; recovery0.22sec; sweeps exclude artificial locomotion and rotation.
  Hands: Continuous human skin derivative; palm/thenar/knuckles/tendons/short nails; mirrored left mesh with existing calibrated grip.
  HandGeometry: 15497 source vertices / 30720 triangles per hand; 17851 UE render vertices / two sections / one LOD.
  HandMaterials: Linear vertex skin color,1024 micro normal + roughness, two skin texture samples; separate nail material.
  HandRig: Complete47-bone original hierarchy/reference pose retained; original mesh/skeleton/grip asset hashes unchanged.
  SurfaceReview: Three Blender shape iterations and local wrist-back polish; actual equipped and both-grip Ready screenshots reviewed.
  Preserved: Enemy face, feet, grounded death, weapon hilt/grip and shield PBR; player melee10/qi15; previous desktop maps/launchers.
  Build: Editor Development succeeded exit0; Docs/AI/BuildLog-VRInputHands-2026-10-15.txt.
  AssetSave: Input/map authoring exit0; full-editor hand mesh/materials saved, no shader compile errors; editor and initial art preview exited normally.
  InitialPresentation: Health100/guard100, Ready, alive0; both hand mesh/material references recorded; temporary visual visibility restored.
  Scope: No tests added or run; no synthetic VR poses, movement, attacks, guard activation or save/load exercise.
  Acceptance: Real SteamVR headset/controller tracking, locomotion, grip offsets and combat timing await user play; GPU timing unmeasured.
  Delivery: Docs/AI/VRHandsDelivery-2026-10-15.json; Deliveries/VRHands_20261015/Manifest.json.
  BeforeSource: Deliveries/BeforeVRInput_20261015/Manifest.json.
  Automation: Existing automation remains PAUSED.
  Next: User VR feedback before further combat content.
'''
if 'VRHands_Current_20261015:' not in state:
    state += '\n' + section
state_path.write_text(state, encoding='utf-8')
dev_path = DOCS / 'DevelopmentStatus.md'
dev = dev_path.read_text(encoding='utf-8-sig')
if '## 2026-10-15 SteamVR 手柄输入与真实皮肤手部' not in dev:
    dev += '''

## 2026-10-15 SteamVR 手柄输入与真实皮肤手部

- 新增 NLVRPlayerCharacter / NLVRGameMode 和独立 L_CombatLabVR。左摇杆按头部朝向移动，右摇杆每次转向30度，左右手柄追踪手部和武器。真实挥刀沿用统一结算器，每刀10伤害；刀气15、左扳机护心镜格挡。
- 使用 OpenXR Enhanced Input，13个动作与53条有效映射覆盖 Index、Touch、Vive、WMR、PICO、HP；Vive/WMR 触控板按下后移动/转向。运行时状态与按钮说明改为立体文字。实际 HMD 高度直接取设备地面坐标。
- 新启动器 Run_VR_Demo.cmd 通过本次 UE 子进程环境变量指定 SteamVR OpenXR，不修改系统默认运行时。专用地图沿用两波混合敌人，使用独立检查点上下文；桌面入口保留。
- 将机械手表面改为连续皮肤，补掌丘、指节、肌腱、低幅掌纹与短指甲，三轮调整指甲贴合后再平滑手腕局部折痕。每手30720三角、两材质槽；皮肤有线性顶点肤色及1024微法线/粗糙度贴图。左手沿用镜像握镜姿态。
- 完整47骨父级和参考姿态保持兼容；原手部网格、骨架与握持动画文件哈希不变。新模型保留自身皮肤/指甲材质，旧手套仅作为旧模型回退。
- Editor Development 编译成功；输入、地图、网格及材质已保存，着色器无编译错误。已查看 Blender 三视图和实际局内 Ready 初始握持截图；生命/护势100，敌人0，临时外观呈现已恢复。
- 未添加或运行测试，也没有发送移动/攻击/格挡输入或合成控制器姿态。真实 SteamVR 手柄、挥剑命中、握持偏移及帧率仍需用户试玩。交付记录 VRHandsDelivery-2026-10-15.json，快照 Deliveries/VRHands_20261015/Manifest.json。
'''
    dev_path.write_text(dev, encoding='utf-8')
DELIVERY.mkdir(parents=True, exist_ok=True)
paths = ['Source', 'Config', 'experiment.uproject', 'Run_VR_Demo.ps1', 'Run_VR_Demo.cmd', 'VRDemo_操作说明.txt',
         'Content/ReversedScale/Maps/L_CombatLabVR.umap', 'Content/ReversedScale/Player/VR',
         'Content/ReversedScale/Player/Hands', 'Content/ReversedScale/Player/Materials/M_PlayerSkin.uasset',
         'Content/ReversedScale/Player/Materials/M_PlayerNails.uasset', 'ArtSource/PlayerHands',
         'Saved/Scripts/create_vr_lab.py', 'Saved/Scripts/author_vr_input_assets.py',
         'Saved/Scripts/export_player_hand_sources.py', 'Saved/Scripts/export_hands_editor.py',
         'Saved/Scripts/import_realistic_player_hands.py', 'Saved/Scripts/author_player_hands_editor.py',
         'Saved/Scripts/capture_player_hand_presentation.py', 'Saved/Scripts/save_vr_hands_delivery.py',
         'Binaries/Win64/UnrealEditor-experiment.dll', 'Binaries/Win64/UnrealEditor.modules']
paths += [path.relative_to(ROOT).as_posix() for path in DOCS.glob('*2026-10-15*') if path.is_file()]
paths += ['Docs/AI/State.md', 'Docs/AI/DevelopmentStatus.md', 'Docs/AI/PlayerHands_Equipped.png', 'Docs/AI/PlayerHands_BothGrip.png']
for relative in paths:
    source, target = ROOT / relative, DELIVERY / relative
    if not source.exists():
        raise RuntimeError('Missing delivery source: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)
before = manifest(ROOT / 'Deliveries/BeforeVRInput_20261015', 'Source, config and State.md before the VR input batch')
saved = manifest(DELIVERY, 'VR/hands batch snapshot; run the launcher from the complete project with local UE5.8 and SteamVR')
print(json.dumps({'delivery': str(DELIVERY), 'files': saved['file_count'], 'before_files': before['file_count']}, ensure_ascii=False))
