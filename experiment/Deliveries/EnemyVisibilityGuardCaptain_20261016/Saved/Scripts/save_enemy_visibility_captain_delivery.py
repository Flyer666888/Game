"""Record the authored batch and copy an incremental delivery after initial art review."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'Docs/AI'


def read(name):
    return json.loads((DOCS / name).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    build = DOCS / 'BuildLog-EnemyVisibilityCaptain-2026-10-16.txt'
    if 'Result: Succeeded' not in build.read_text(encoding='utf-8-sig', errors='replace'):
        raise RuntimeError('The current native build has not succeeded.')
    author = read('GuardCaptainAuthoringSession-2026-10-16.json')
    if not author.get('success') or not author.get('navigation_saved'):
        raise RuntimeError('The independent captain scene/navigation has not been saved.')
    scene_names = ('VREnemyReady-2026-10-16.json', 'GuardCaptainReady-2026-10-16.json')
    scenes = [read(name) for name in scene_names]
    for scene_name, scene in zip(scene_names, scenes):
        if not scene.get('success') or not scene.get('ready_previews') or scene.get('melee_damage') != 10:
            raise RuntimeError('The initial presentation record is missing its waiting enemies or preserved damage.')
        shot = DOCS / Path(scene['screenshot']).name
        if not shot.is_file():
            raise RuntimeError('The initial screenshot is missing.')
        scene['screenshot'] = str(shot)
        (DOCS / scene_name).write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding='utf-8')
    lab = read('GuardCaptainLabSaved-2026-10-16.json')
    for name in ('State.md', 'DevelopmentStatus.md'):
        dest = ROOT / 'Deliveries/BeforeEnemyVisibility_20261016/Docs/AI' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(DOCS / name, dest)
    user_log = ROOT / 'Saved/Logs/experiment.log'
    user_copy = DOCS / 'EnemyVisibilityUserRun-2026-10-16.log'
    if user_log.exists() and not user_copy.exists():
        shutil.copy2(user_log, user_copy)
    report = {
        'date': '2026-10-16',
        'status': 'NativeCompiled_AssetsAndNavigationSaved_InitialPresentationReviewed_UserPlayPending',
        'request': '敌人还是没有出现在我的视野里；修复完这个bug就继续工作',
        'diagnosis': {
            'user_entry': 'Editor PIE on L_CombatLabVR; last saved PlayMode_Simulate; empty command line.',
            'runtime': 'Latest user log initialized Oculus runtime 1.208.0; SteamVR launcher was not evidenced.',
            'inference': 'Simulation uses a spectator rather than the controlled VR pawn; the pawn-owned auto-start cannot run. This is strongly supported by saved mode and local engine source, not a direct pawn enumeration in that old log.',
            'navigation': 'Recast warnings in that user run followed world teardown, not evidence of a new startup navigation failure.',
        },
        'fixes': [
            'Ready/Cancelled presents noncombat idle enemies at deterministic planned entry positions, grounded and using preserved mesh/grip.',
            'Presentation actors have no AI, damage, collision or progression identity; removed before real combat and on reset/end.',
            'VR enables waiting enemies by default; older desktop maps unchanged; captain lab opts in.',
            'SteamVR demo/editor entry uses process-local XR_RUNTIME_JSON; global runtime untouched.',
            'Editor last play mode corrected to VR Preview while UE was closed; spectator entry and readiness blockers are visible and logged.',
        ],
        'next_module': 'ENEMY-02B Guard Captain',
        'guard_captain': lab,
        'preserved': 'Player melee10; Sword A and grip; refined dragon shield; existing enemy mesh/face/feet/grip/hit/death assets.',
        'build_log': build.relative_to(ROOT).as_posix(),
        'initial_compile_repair': 'UE_LOG macro needed braces in an if/else; fixed and subsequent compilation succeeded.',
        'authoring': author, 'initial_presentations': scenes,
        'tests_added_or_run': False,
        'user_acceptance_pending': ['Actual SteamVR headset view and both-hand input', 'Ready-to-combat transition and retry', 'Guard Captain block/break/heavy attack, navigation and checkpoint flow'],
        'launchers': ['Run_VR_Demo.cmd', 'Run_VR_Editor.cmd', 'Run_GuardCaptain_Demo.cmd'],
        'snapshot': 'Deliveries/EnemyVisibilityGuardCaptain_20261016',
        'delivery_requires': 'Full existing experiment project and local UE5.8; incremental snapshot and local demo entry, not packaged EXE.',
    }
    report_path = DOCS / 'EnemyVisibilityGuardCaptainDelivery-2026-10-16.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    state = (DOCS / 'State.md').read_text(encoding='utf-8')
    replacements = {
        'Milestone:': 'Milestone: VR input adapter + COMBAT-04 + ENEMY-01 + DIR-01 + WAVE-01 + SAVE-01 + ENEMY-02A + ENEMY-02B + Dragon Shield PBR',
        'CurrentTask:': 'CurrentTask: Enemy Ready visibility and SteamVR entry corrected; independent Guard Captain module saved for user play',
        'TaskStatus:': 'TaskStatus: EnemyVisibilityGuardCaptain_Compiled_AssetsSaved_InitialPresentationReviewed_UserPlayPending',
        '  CurrentAuthorization:': '  CurrentAuthorization: User requested fixing enemy visibility and then continuing the next development task. Compile and initial presentation only; no new tests authorized.',
        'NextAction:': 'NextAction: User review of VR start and Guard Captain combat; LEVEL-01 is the next dependency batch.',
    }
    lines = state.splitlines()
    for i, line in enumerate(lines):
        for prefix, value in replacements.items():
            if line.startswith(prefix):
                lines[i] = value
                break
    state = '\n'.join(lines) + '\n'
    state = state.replace('  Log: Docs/AI/BuildLog-VRInputHands-2026-10-15.txt',
                          '  Log: Docs/AI/BuildLog-EnemyVisibilityCaptain-2026-10-16.txt', 1)
    state = state.replace('  AssetSave: Mixed map commandlet exit0; shield full-editor import/LOD author success',
                          '  AssetSave: Guard Captain full-editor assets and completed navigation saved; previous shield refinement retained', 1)
    state = state.replace('Talisman caster is implemented in the separate mixed scene; ENEMY-02B Guard Captain/high-threat content and final enemy balance remain pending.',
                          'Talisman caster and ENEMY-02B Guard Captain have independent scenes; final enemy balance/high-threat content and gameplay acceptance remain pending.')
    section = '''
EnemyVisibilityGuardCaptain_Current_20261016:
  - Latest user entry was editor PIE with saved Simulate mode and Oculus runtime; no controlled VR entry evidence.
  - Ready waiting enemies now appear at planned spawn points, without collision/AI/damage/progression. They retire before combat.
  - VR Preview default and explicit SteamVR Demo/Editor launchers; process-local runtime only, no registry change.
  - Added readiness/entry/spawn diagnostics. Actual headset tracking and view acceptance remains with user.
  - ENEMY-02B independent map L_CombatLabGuardCaptain: 1 captain, then 1 captain + 1 caster; total3, maxalive2.
  - Captain 30HP / 40guard / 20guard per frontal block; heavy20damage; 1.2s break opening. Player melee remains10.
  - Shared Resolver guards synchronous reentry; local guard pause and reaction duration preserved.
  - Existing meshes/face/feet/grip/hit/death, Sword A and refined dragon shield retained.
  - Native compilation succeeded; new assets/navigation saved; VR and captain initial Ready art reviewed.
  - No tests or agent gameplay inputs. Actual combat and checkpoint behavior awaits user play.
  - Delivery: Docs/AI/EnemyVisibilityGuardCaptainDelivery-2026-10-16.json.
  - Launchers: Run_VR_Demo.cmd; Run_VR_Editor.cmd; Run_GuardCaptain_Demo.cmd.
'''
    if 'EnemyVisibilityGuardCaptain_Current_20261016:' not in state:
        state += section
    (DOCS / 'State.md').write_text(state, encoding='utf-8')
    dev = (DOCS / 'DevelopmentStatus.md').read_text(encoding='utf-8')
    heading = '## 2026-10-16：开场敌人显示与护阵执事'
    if heading not in dev:
        dev += '\n' + heading + '''

最近用户运行使用编辑器模拟入口，配置记录为 PlayMode_Simulate，日志初始化 Oculus OpenXR。根据 UE 本地源码，模拟入口以旁观者启动，无法依赖受控 VR Pawn 的自动开场；这是设置与源码支持的推断，旧日志没有直接枚举 Pawn。销毁阶段的 Recast 警告未作为开场导航故障依据。

准备阶段现在呈现同一计划出生点的待战角色，保持地面、模型、待机和握持。呈现对象不参与碰撞、伤害、AI、存档或击败统计，开始战斗前清理。VR 默认开启，旧桌面场景不变。新增 SteamVR 编辑器入口，与 Demo 共用子进程运行时；修改关闭时的默认播放为 VR 预览，并补足状态提示和日志。

按资料包继续完成 ENEMY-02B 护阵执事最小模块：正面护阵40、每次近战格挡耗20、重击20伤害、破防后1.2秒反击窗口；玩家挥剑仍为10。独立场景两波共3名敌人，沿用当前修正过的角色/动画，护阵用示意美术。编译成功，资产及导航保存，初始画面已查看；真实VR与实际攻防/检查点仍待用户试玩，没有添加或运行测试。

入口和说明：`Run_VR_Demo.cmd`、`Run_VR_Editor.cmd`、`Run_GuardCaptain_Demo.cmd`、`EnemyVisibilityAndCaptainQuickstart.md`。完整记录见 `EnemyVisibilityGuardCaptainDelivery-2026-10-16.json`。
'''
    (DOCS / 'DevelopmentStatus.md').write_text(dev, encoding='utf-8')
    files = set(p for p in (ROOT / 'Source').rglob('*') if p.is_file())
    files.update(p for p in (ROOT / 'Config').rglob('*') if p.is_file())
    for pattern in ('*GuardCaptain*.uasset', '*GuardCaptain*.umap'):
        files.update((ROOT / 'Content').rglob(pattern))
    for pattern in ('*EnemyVisibility*', '*GuardCaptain*', '*EnemyReady*'):
        files.update(p for p in DOCS.glob(pattern) if p.is_file())
    for relative in [
        'experiment.uproject', 'Binaries/Win64/UnrealEditor-experiment.dll', 'Binaries/Win64/UnrealEditor.modules',
        'Docs/AI/State.md', 'Docs/AI/DevelopmentStatus.md',
        'Run_VR_Demo.ps1', 'Run_VR_Demo.cmd', 'Run_VR_Editor.ps1', 'Run_VR_Editor.cmd',
        'Run_GuardCaptain_Demo.ps1', 'Run_GuardCaptain_Demo.cmd',
        'Saved/Scripts/create_guard_captain_lab.py', 'Saved/Scripts/author_guard_captain_editor.py',
        'Saved/Scripts/capture_enemy_ready_presentation.py', 'Saved/Scripts/save_enemy_visibility_captain_delivery.py',
    ]:
        path = ROOT / relative
        if path.is_file():
            files.add(path)
    destination = ROOT / 'Deliveries/EnemyVisibilityGuardCaptain_20261016'
    rows = []
    for source in sorted(files):
        relative = source.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rows.append({'path': relative.as_posix(), 'bytes': source.stat().st_size, 'sha256': sha(source)})
    (destination / 'Manifest.json').write_text(json.dumps({
        'date': '2026-10-16', 'requires_base_project_and_ue': True,
        'tests_added_or_run': False, 'files': rows,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'saved': True, 'files': len(rows), 'delivery': str(destination)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
