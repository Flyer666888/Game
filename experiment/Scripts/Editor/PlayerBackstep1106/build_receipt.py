"""Verify and record the player backstep repair, without changing game assets."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
P=Path(__file__).resolve().parents[3]; O=P/'Docs/Gameplay/PlayerBackstep1106'
read=lambda name:json.loads((O/name).read_text(encoding='utf-8-sig'))
sha=lambda file:hashlib.sha256(file.read_bytes()).hexdigest()
before=read('BeforeAutomation/index.json');after=read('AfterAutomation/index.json')
assert before['failed']==2 and before['notRun']==before['inProcess']==0
assert all(any('cache' in e['event']['message'].lower() or 'cached' in e['event']['message'].lower()
               for e in t['entries'] if e['event']['type']=='Error') for t in before['tests'])
assert after['failed']==after['notRun']==after['inProcess']==0
assert after['succeeded']+after['succeededWithWarnings']==109
runtime=read('Runtime.json');assert runtime['state']=='passed' and runtime['success'] and not runtime['failures']
assert len(runtime['cases'])==8 and all(runtime['checks'].values())
binary=P/'Binaries/Win64/UnrealEditor-experiment.dll'
assert (O/'Runtime.json').stat().st_mtime>binary.stat().st_mtime
assert (O/'AfterAutomation/index.json').stat().st_mtime>binary.stat().st_mtime
mapfile=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
mapsha=sha(mapfile)
assert runtime['fixture_isolation']['state']=='restored_without_saving_map'
assert runtime['fixture_isolation']['map_sha256_after']==mapsha
assert mapsha==read('../GDDOrdered1105/Delivery.json')['map_sha256']
for key in ['removed_only_exact_test_paths','ordinary_ledger_cleanup']:
    assert all(not Path(file).exists() for file in runtime['fixture_isolation'].get(key,[]))
assert read('Status.json')['state']=='closed'
sources=[]
for relative in ['Source/experiment/Private/Player/NLDesktopPlayerCharacter.cpp',
                 'Source/experiment/Public/Player/NLDesktopPlayerCharacter.h',
                 'Source/experiment/Private/Player/NLLevelCombatPlayer.cpp']:
    file=P/relative;assert file.read_bytes()==(O/'FixCandidate'/relative).read_bytes()
    assert file.stat().st_mtime<binary.stat().st_mtime
    sources.append({'path':relative,'before_sha256':sha(O/'Backups'/relative),'after_sha256':sha(file)})
report={'state':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
    'symptom':'Desktop gameplay keeps walking backwards after attacks even after movement keys are released.',
    'reproduced_cause':'A missed key-up leaves S cached down. The main combat pawn continued polling it across cursor release/recapture; the old two native regressions fail on cache, momentum, pending input and real world position.',
    'changes':['Flush cached keys, consume queued movement and stop momentum at cursor and pause transitions.',
               'Gate keyboard movement while the viewport is unfocused/background or the pointer is released; clear old keys when focus returns.',
               'Keep normal held movement active during attacks; preserve combat collision and animation.'],
    'source_changes':sources,'new_regression_source':'Source/experiment/Private/Tests/NLDesktopMovementInputTests.cpp',
    'old_version_regression':{'failed':2,'report':'BeforeAutomation/index.json'},
    'final_regression':{'passed':109,'failed':0,'clean':after['succeeded'],
                        'with_warnings':after['succeededWithWarnings'],'report':'AfterAutomation/index.json'},
    'saved_map_native_melee_cases':[{'name':r['name'],'max_xy_drift_cm':r['max_xy_drift_cm']} for r in runtime['cases']],
    'runtime_scope':runtime['scope'], 'map_sha256':mapsha, 'map_assets_unchanged':True,
    'module':{'path':str(binary),'sha256':sha(binary)},
    'entry_point':str(P/'Run_Gameplay_Demo.cmd'),
    'limits':['Key-up loss is delivered to real UPlayerInput in an isolated native test, not a physical OS Alt+Tab playtest.',
              'The saved-map probe uses explicit positions, normal player movement and native swings; six stationary-AI cases and two live-AI cases. No physical headset input is claimed.'],
    'fixture_note':'InitialFixtureFailure.json preserves a test setup failure before ULocalPlayer initialization was corrected; BeforeAutomation is the subsequent valid old-product regression.'}
(O/'Delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'FixNotes.txt').write_text('键鼠攻击后持续后退修复（2026-11-06）\n\n已复现：S键漏掉松键事件后，主关卡在释放／收回鼠标后仍轮询旧按键状态，持续后退。\n修复：窗口失焦、鼠标释放／收回、暂停切换时清除按键缓存、待处理移动和速度；鼠标释放或窗口未激活时不接受键鼠移动。正常按住W移动时仍能挥剑。\n\n验证：旧版两项输入回归失败；修复后109项全部通过。最终保存的主地图另跑8组正常剑击／活跃敌人测试，无输入时XY位移均小于0.1厘米。原主地图与资产未改。\n\n请关闭旧试玩窗口，再双击 D:\\game design\\experiment\\Run_Gameplay_Demo.cmd 使用新模块。\n\n详细证据见 Delivery.json、BeforeAutomation/index.json、AfterAutomation/index.json、Runtime.json。键盘丢失松键采用原生输入缓存夹具；未声称进行了物理Alt+Tab或PICO设备验收。\n',encoding='utf-8')
print(json.dumps({'state':'passed','native_tests':109,'melee_cases':8,'map_sha256':mapsha}))
