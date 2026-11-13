"""Seal the focused-window, coalesced-event movement repair."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
P=Path(__file__).resolve().parents[3];O=P/'Docs/Gameplay/PlayerBackstepIntermittent1106'
read=lambda name:json.loads((O/name).read_text(encoding='utf-8-sig'))
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
before=read('BeforeAutomation/index.json');after=read('AfterAutomation/index.json')
assert before['failed']==2 and before['succeededWithWarnings']+before['succeeded']==2
assert {t['fullTestPath'] for t in before['tests'] if t['state']=='Fail'}=={
    'Nilin.Desktop.Input.FocusedSameFrameReleaseWithAttack',
    'Nilin.Desktop.Input.LatestMovementEventWinsAcrossFrameRates'}
assert after['failed']==after['notRun']==after['inProcess']==0
assert after['succeeded']+after['succeededWithWarnings']==111
runtime=read('Runtime.json');assert runtime['fixture_isolation']['state']=='restored_without_saving_map'
assert read('Status.json')['state']=='closed'
mapfile=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap';mapsha=sha(mapfile)
assert mapsha==read('../GDDOrdered1105/Delivery.json')['map_sha256']
assert runtime['fixture_isolation']['map_sha256_after']==mapsha
# The initial visible diagnostic was interrupted while its editor closed. Remove
# only its uniquely identified test files, never a production or shared profile.
interrupted=read('RuntimeInterrupted.json')['fixture_isolation']
test_id=interrupted['temporary_level_id'];assert re.fullmatch(r'Test\.Level01\.[0-9a-f]{32}',test_id)
root=P/'Saved/SaveGames';removed=[]
marker=root/'NilinLevelRuns'/(hashlib.sha1(test_id.lower().encode()).hexdigest()+'.nlrun')
assert marker==Path(interrupted['test_marker'])
targets=[marker,Path(str(marker)+'.tmp')]
for run_id in interrupted['test_run_ids']:
    assert re.fullmatch('[0-9a-f]{32}',run_id)
    for directory,suffix in [('NilinMasterRewards','.nlmr'),('NilinOrdinaryLoot','.nllo')]:
        path=root/directory/(run_id.upper()+suffix);targets.extend([path,Path(str(path)+'.tmp')])
for path in targets:
    assert path.resolve().is_relative_to(root.resolve())
    if path.exists():
        assert path.is_file();removed.append({'path':str(path),'sha256':sha(path)});path.unlink()
for key in ['removed_only_exact_test_paths','ordinary_ledger_cleanup']:
    assert all(not Path(f).exists() for f in runtime['fixture_isolation'].get(key,[]))
binary=P/'Binaries/Win64/UnrealEditor-experiment.dll'
assert (O/'AfterAutomation/index.json').stat().st_mtime>binary.stat().st_mtime
paths=['Source/experiment/Private/Player/NLDesktopPlayerCharacter.cpp',
       'Source/experiment/Private/Tests/NLDesktopMovementInputTests.cpp']
assert all((P/f).stat().st_mtime<binary.stat().st_mtime for f in paths)
report={'state':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
    'symptom':'Intermittent continuing backwards movement after desktop attack, including after tapping S again.',
    'reproduction':'In a focused native level pawn with real UEnhancedPlayerInput, held S plus another press and a final release in the same input frame leaves legacy bDown true while the latest raw value is zero. Actual attack binding and CharacterMovement reproduce continued backwards travel on the prior version without Tab or focus loss.',
    'change':'Read the last raw W/A/S/D sample instead of legacy bDown when producing keyboard locomotion; retain prior focus/cursor/pause cleanup and ordinary braking.',
    'source_changes':[{'path':f,'before_sha256':sha(O/'BackupsV1'/f),'after_sha256':sha(P/f)} for f in paths],
    'before':{'passed':2,'failed':2,'report':'BeforeAutomation/index.json'},
    'after':{'passed':111,'failed':0,'clean':after['succeeded'],'with_warnings':after['succeededWithWarnings'],
             'report':'AfterAutomation/index.json'},
    'new_coverage':['Focused same-frame release with the real attack binding, followed by continued position/velocity checks.',
                    'All four movement keys at 15/30/60/120 Hz with release-last and press-last batches.',
                    'Existing cursor, focus, fresh movement and held-W slashing regressions remain passing.'],
    'map_sha256':mapsha,'map_unchanged':True,
    'module':{'path':str(binary),'sha256':sha(binary)},
    'supplemental_trace':'TraceAnalysis.json',
    'manual_window_limit':'Window automation was interrupted/activation failed; no completed manual continuous keyboard playthrough is claimed. Native coalesced-event regressions are the primary repair evidence.',
    'interrupted_test_cleanup':removed,'entry_point':str(P/'Run_Gameplay_Demo.cmd')}
(O/'Delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'FixNotes.txt').write_text('偶发攻击后持续后退：第二次修复（2026-11-06）\n\n上一版只修了焦点／鼠标切换，未覆盖窗口一直激活时的同帧键事件。\n本轮用真实UEnhancedPlayerInput、主关卡角色、地板、移动组件和攻击绑定复现：已按住S时，同帧收到额外按下与最终松开，legacy bDown仍为true，而RawValue已经为0；旧版继续后退。\n\n改为用方向键最后输入样本生成移动，不再用可能滞留的bDown标记。保持正常刹停、按住W移动挥剑以及原焦点／暂停清理。未锁定玩家位置，也未修改敌人碰撞或动作。\n\n前后对照：上一版4项输入专项中2通过、2失败；修复后111项完整原生回归全部通过。新增覆盖四方向、15／30／60／120帧、同帧最终松开和最终按下两种顺序。主地图哈希未变。\n\n可见窗口跟踪仅是补充观测，UI输入自动化未完整执行，不作为人工连续试玩通过证据。首次诊断被中断的测试运行文件已按确切Test.Level01身份清理，未处理正式试玩存档。\n\n请关闭旧试玩窗口，再运行 D:\\game design\\experiment\\Run_Gameplay_Demo.cmd。\n',encoding='utf-8')
print(json.dumps({'state':'passed','native_tests':111,'prior_failed_cases':2,'map_sha256':mapsha}))
