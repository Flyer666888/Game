"""Package verified local sword-qi code and practical player/developer notes."""
from pathlib import Path
import json,hashlib,datetime
ROOT=Path(r'D:\game design\experiment')
OUT=ROOT/'Docs/Combat/SwordQiTemplate'
def main():
    inspection=json.loads((OUT/'AssetInspection.json').read_text(encoding='utf-8'))
    tests=json.loads((OUT/'Automation/index.json').read_text(encoding='utf-8-sig'))
    assert inspection['success'] and tests['failed']==0 and tests['notRun']==0 and tests['inProcess']==0
    assert tests['succeeded']+tests['succeededWithWarnings']==15
    assert 'Result: Succeeded' in (OUT/'BuildFinal.log').read_text(encoding='utf-8',errors='replace')
    source_paths=[
      'Source/experiment/Public/Combat/NLBladeComponent.h',
      'Source/experiment/Private/Combat/NLBladeComponent.cpp',
      'Source/experiment/Public/Combat/NLBladeQiGesture.h',
      'Source/experiment/Public/Player/NLDesktopPlayerCharacter.h',
      'Source/experiment/Private/Player/NLDesktopPlayerCharacter.cpp',
      'Source/experiment/Public/Player/NLVRPlayerCharacter.h',
      'Source/experiment/Private/Player/NLVRPlayerCharacter.cpp',
      'Source/experiment/Private/Tests/NLBladeQiGestureTests.cpp',
      'Source/experiment/Private/Tests/NLBladeQiMotionTests.cpp',
      'Source/experiment/Private/Tests/NLBladeQiProjectileTests.cpp']
    report={'feature':'VR sword qi gesture template','completed_at':datetime.datetime.now().isoformat(),
      'interaction':'Press the existing right trigger while performing a valid tracked right-hand swing; each press and swing emits at most one projectile.',
      'defaults':dict(inspection['native_defaults'],damage=inspection['attack']['damage'],cooldown_seconds=inspection['attack']['cooldown_seconds']),
      'verification':{'build':'Succeeded','automated_tests':15,'tests_succeeded_without_warnings':tests['succeeded'],'tests_succeeded_with_fixture_warnings':tests['succeededWithWarnings'],'failed':tests['failed'],
        'warning_reason':'Two deferred-spawn player fixtures intentionally do not load their skeletal hand assets; the engine reports missing hand_r sockets during fixture component registration. Their assertions all pass.',
        'input_asset_inspection':True,'headset_controller_hardware_playtest':False},
      'tests':[{'name':t['fullTestPath'],'state':t['state'],'errors':t['errors'],'warnings':t['warnings']} for t in tests['tests']],
      'scope':'Native VR combat adapter and shared projectile launcher. Uses existing placeholder projectile and combat damage path; no new VFX. Whitebox maps and static formations are not converted to combat actors.',
      'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths},
      'module_sha256':hashlib.sha256((ROOT/'Binaries/Win64/UnrealEditor-experiment.dll').read_bytes()).hexdigest()}
    (OUT/'FinalReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    player_note='''《逆鳞》VR 剑气基础模板（2026-10-22）

启动项目根目录 Run_VR_Demo.cmd，连接 SteamVR 头显和左右手柄。
沿用当前 L_CombatLabVR 战斗试玩入口；本轮没有把 V08 静态人形改成敌人。

使用：右手持剑朝向远处目标，挥剑的同时扣下右扳机。
可在挥剑前最多约0.25秒扣住扳机；发出一道后松开，再配合下一次挥剑按下。
仅按扳机、仅挥剑、低速移动均不会发出剑气。按住过早或一直不松开也不会连续发射。
发射方向为扣键与挥动配合成功时手柄的正前方，未加入自动锁敌。
场景使用已有的简单蓝色占位投射物观察飞行与命中，本轮未增加特效。

默认参数：
单次伤害15；成功发射后冷却0.35秒；飞行速度12米/秒；最大飞行距离约48米；命中半径5厘米。
有效刀刃采样速度阈值2.2米/秒，包含转腕带来的刀刃运动。
一发在首个有效伤害/格挡或墙体处消失，不是贯穿型或范围型攻击。
已有阵营、护甲/格挡、伤害保护和死亡反馈继续由原战斗系统处理。

暂停、死亡、重试、重新居中、瞬时转向、追踪中断或追踪跳变都会取消未发出的请求。
恢复操作后先松开右扳机，再重新配合挥剑。已按下的旧请求不会补发。
局内文字提示 READY / SWING NOW / RELEASE / COOLDOWN / FIRED。
手柄或发射点被墙体隔住时拒绝发射，失败不会启动伤害冷却；仍需松键重试。

工程编译通过，15项自动化用例均通过，覆盖真实刀刃采样与输入门控、真实物理查询和伤害结算。
其中两项无手模型的隔离测试有预期缺少hand_r插槽的日志警告，断言均通过。
自动化通过不等同于真实头显手感验证；本轮未戴设备试玩，挥动阈值可在实际使用时继续调节。
'''
    (OUT/'试玩说明.txt').write_text(player_note,encoding='utf-8')
    developer_note='''VR 剑气模板接入与可调项

已有 VR 输入：/Game/ReversedScale/Player/VR/Input/IA_VRBladeQi
已有映射：IMC_NilinVR，已读回确认六组右扳机映射。Started提交请求；Completed/Canceled清除请求。
ANLVRGameMode 的默认 Pawn 为 ANLVRPlayerCharacter，因此原 VR Demo 直接使用新代码。

逻辑链：
ANLVRPlayerCharacter::FireBladeQi → FNLBladeQiGestureGate::Press
→ UNLBladeComponent完成本帧追踪空间采样 → OnTrackedMotionSample
→ Gate.TryConsume（当前有效挥剑ID、速度阈值、短按键缓冲）
→ 头部到手柄遮挡查询 → TryLaunchBladeQi出口扫掠与冷却
→ ANLCombatProjectile沿通道NLProjectile连续扫掠 → 原NLCombatResolverSubsystem处理伤害。
Blade.OnHistoryReset和VR状态复位都取消请求；使用追踪空间相对速度，角色移动本身不会算作挥剑。
FireBladeQi是虚函数，VR对象的蓝图调用也要走门控；共享发射函数为protected、非蓝图入口。

在原生VR Pawn/派生蓝图的默认值或实例详情中可调整：
Player|VR|SwordQi：BladeQiInputBufferSeconds、BladeQiMinimumSwingSpeedCmPerSec。
Player|SwordQi：BladeQiSpeedCmPerSec、BladeQiRangeCm、BladeQiRadiusCm、BladeQiMuzzleOffsetCm、BladeQiProjectileClass。
刀刃本身的追踪挥动起步阈值在Blade组件SpeedThresholdCmPerSec；剑气阈值低于它不会绕过有效挥剑状态。
伤害与冷却在 /Game/ReversedScale/Combat/DA_PlayerBladeQi 中的 Damage / CooldownSeconds。
本轮保留现有DA：15伤害、0.35秒冷却。

后续美术接入：将BladeQiProjectileClass替换为ANLCombatProjectile派生蓝图，装饰Visual即可。
OnBladeQiLaunched蓝图事件可挂接声音、震动或起手效果；当前未设置这些效果。
保留原投射物显式扫掠和resolver处理，不需靠特效碰撞额外扣血。
默认使用共享阵营规则（玩家可伤Enemy与Objective，忽略Player/Neutral），未改任务物件规则。
本轮没有修改白模关卡、输入资产、DA攻击资产或OpenXR全局设置。

验证文件：BuildFinal.log、Automation/index.json、AssetInspection.json、FinalReport.json。
测试前缀：Nilin.Combat.BladeQi，15用例（Gesture5、Motion4、Projectile6）。
Automation日志启动期的引擎自测文本不属于本用例结果；以Automation/index.json各项结果为准。
修改前原生源代码备份位于 Backups/BeforeGesture_20261022。
'''
    (OUT/'接入与参数说明.txt').write_text(developer_note,encoding='utf-8')
    old=ROOT/'VRDemo_操作说明.txt'
    text=old.read_text(encoding='utf-8-sig')
    text=text.replace('（2026-10-16）','（2026-10-22）').replace('刀气','剑气')
    text=text.replace('右扳机：发射剑气，伤害 15。',
      '右扳机：挥动右手持剑时扣下，发出一道剑气，伤害15、冷却0.35秒。\n'
      '可提前约0.25秒扣住；成功后松开再按。静止按键或一直长按不会连发。\n'
      '剑气按手柄正前方飞行，使用已有简单蓝色占位体；追踪恢复后先松键再试。')
    old.write_text(text,encoding='utf-8')
    print(json.dumps({'complete':True,'tests':15,'damage':inspection['attack']['damage'],'hardware_playtest':False}))
if __name__=='__main__':main()
