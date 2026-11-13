"""Assemble delivery evidence from actual build, map, automation and runtime reports."""
from pathlib import Path
import json,hashlib,datetime
root=Path(r'D:\game design\experiment')
out=root/'Docs/Gameplay/EncounterRecovery_v01'
read=lambda name:json.loads((out/name).read_text(encoding='utf-8-sig'))
runtime=read('RuntimeIntegration.json');tests=read('Automation/index.json')
nav=read('MapValidation.json');bake=read('StaticNavigationBake.json');desktop=read('DesktopLaunch.json')
assert runtime['success'] and runtime['state']=='passed' and not runtime['failures']
assert runtime['total_counted_spawns']==runtime['total_resolver_defeats']==109
assert len(runtime['stages'])==16 and sum(len(s['waves']) for s in runtime['stages'])==27
assert len(runtime['master_rewards'])==4 and all(r['success'] for r in runtime['master_rewards'])
assert tests['failed']==tests['notRun']==tests['inProcess']==0
assert tests['succeeded']+tests['succeededWithWarnings']==27
assert nav['success'] and len(nav['navigation_points_and_entry_paths'])==67
assert bake['state']=='passed' and bake['global_ini_unchanged']
assert desktop['responding'] and desktop['first_stage_spawned'] and not desktop['fatal_or_navigation_failure']
assert 'Result: Succeeded' in (out/'Build.log').read_text(encoding='utf-8',errors='replace')
source=root/'Content/ReversedScale/Maps/L_NilinBlockoutV10.umap'
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
assert source_hash==read('MapBuild.json')['source_map_sha256']
report={
    'completed_at':datetime.datetime.now().astimezone().isoformat(),
    'map':'/Game/ReversedScale/Maps/L_NilinGameplayV01',
    'source_v10_preserved':True,'source_v10_sha256':source_hash,
    'build':'Succeeded',
    'automation':{'passed':27,'failed':0,'passed_with_fixture_warnings':tests['succeededWithWarnings']},
    'saved_navigation_paths_passed':67,
    'cold_pie_feet_projections_passed':len(runtime['cold_pie_navigation']['checks']),
    'cold_pie_navigation_checked_at_game_seconds':runtime['cold_pie_navigation']['game_time'],
    'completed_stages':16,'completed_waves':27,'resolved_enemy_defeats':109,
    'max_alive_observed':max(w['max_alive_observed'] for s in runtime['stages'] for w in s['waves']),
    'perfect_parry_recovery':runtime['perfect_parry']['success'],
    'retry':runtime['retry']['success'],'one_shot_master_rewards_verified':4,
    'real_rock_ai':{'observed_game_seconds':runtime['rock_r01_ai']['observed_game_seconds'],
                    'projectiles':runtime['rock_r01_ai']['projectile_count'],'passed':True},
    'navigation':'Static baked; force rebuild on load disabled only in this map',
    'global_engine_config_unchanged_during_bake':True,
    'desktop_launch':desktop,
    'scope':runtime['scope'],
    'limitations':['VR headset and controller acceptance testing remains pending.',
                   'Masters and boss use existing combat templates with configured stats; unique skills/phases are not implemented.',
                   'This is not a complete manual uninterrupted playthrough or combat difficulty/performance certification.'],
    'evidence':['Build.log','Automation/index.json','MapValidation.json','RuntimeIntegration.json','StaticNavigationBake.json','DesktopLaunch.json','Screenshots/Gameplay_R01.png'],
}
(out/'FinalReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
text='''《逆鳞》玩法 V01 交付检查

已完成：
1. 关卡敌人调度：16 段、27 波、累计 109 名敌人；运行观察峰值 4 人。区域进入、前置依赖、2 秒预警、分批出生、清波推进、本段失败重试均已接入。
2. 生命反馈与恢复：每 3 次有效精准格挡回复 10 生命，普通格挡不计数，满血不积攒；四位宗师各有一份最多回复 25 生命的首杀补给，同一局防重复领取及旧存档回滚刷取。

入口：项目根目录 Run_Gameplay_Demo.cmd。独立地图 L_NilinGameplayV01；原 V10 白模未覆盖。已实际冷启动打开桌面窗口并确认第一段敌人出生、窗口响应、无崩溃或导航失败。

验证：最终编译成功；27 项自动化检查通过（0 失败，其中 3 项带测试场景预期警告）；67 条导航投影与路径通过。冷启动进入 PIE 约 1 秒后，67 个出生脚点使用 60/60/180cm 查询范围全部投影成功。真实运行完成 16 段、27 波、109 次战斗结算击杀；三次精准格挡回血、本段重试和四份一次性补给均通过。岩台两名真实 AI 在 12 秒观察中完成前摇、攻击并发射了 4 枚弹体。

验证范围：全流程检查用设置位置进入各区域，并以实际战斗结算击败敌人；除第一处岩台的实际 AI 观察外，多数 AI 在测试中局部暂停，以隔离波次与奖励规则。不是完整手动连续通关、难度平衡或帧率验收。近战物理剑刃精准格挡另有真实 sweep 自动化检查。

当前边界：宗师和 Boss 使用既有战斗模板及不同生命值，独特招式与 Boss 多阶段未完成。VR 头显、手柄和性能尚未实机验收。本次未扩展爆头奖励、随机掉落保底等后续机制。

完整证据见 FinalReport.json；操作见 试玩说明.txt；配置与规则见 GameplayDesign_v01.txt。
'''
(out/'验证报告.txt').write_text(text,encoding='utf-8')
print(json.dumps({'report':str(out/'FinalReport.json'),'state':'passed','stages':16,'waves':27,'enemies':109,'automation_tests':27},ensure_ascii=False))
