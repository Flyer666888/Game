"""External delivery packager; refuses to publish launchers without real UE checks."""
from pathlib import Path
import json,hashlib,datetime
ROOT=Path(r'D:\game design\experiment')
OUT=ROOT/'Docs/LevelDesign/Blockout_v03'
def load(name):return json.loads((OUT/name).read_text(encoding='utf-8-sig'))
def main():
    build=load('BuildPressure.json');geom=load('Validation.json');edges=load('EdgeAudit.json');pressure=load('PressureAudit.json');walk=load('RuntimeWalk.json');readback=load('Readback.json')
    capture=load('Screenshots/CaptureReport.json');source=load('SourcePreservation.json');comparison=load('SourceComparison.json')
    assert build['saved'] and build['enemy_count']==36
    assert geom['success'] and edges['success'] and pressure['success']
    assert walk['state']=='passed' and walk['waypoints_reached']==walk['total_waypoints'] and not walk['failures']
    assert not capture['error'] and len(capture['captures'])==5
    assert source['restored_actor_count']==657 and source['restored_pressure_actors']==0
    assert comparison['success'] and comparison['unchanged_base_actors']==645
    map_file=ROOT/'Content/ReversedScale/Maps/L_NilinBlockoutV08.umap'
    for shot in capture['captures']:
        assert Path(shot['file']).stat().st_size>10000
        assert Path(shot['file']).stat().st_mtime>=map_file.stat().st_mtime, 'Capture predates latest map save'
    assert 'Result: Succeeded' in (OUT/'BuildFinal.log').read_text(encoding='utf-8',errors='replace')
    for mode in ('Demo','Editor'):
        path=ROOT/('Run_Blockout_'+mode+'.ps1')
        txt=path.read_text(encoding='utf-8-sig')
        txt=txt.replace("ValidateSet('V06','V07')","ValidateSet('V06','V07','V08')").replace("$MapVersion = 'V07'","$MapVersion = 'V08'")
        path.write_text(txt,encoding='utf-8-sig')
        for version in ('V07','V08'):
            cmd='@echo off\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run_Blockout_'+mode+'.ps1" -MapVersion '+version+'\nexit /b %errorlevel%\n'
            (ROOT/('Run_Blockout_'+version+'_'+mode+'.cmd')).write_text(cmd,encoding='ascii')
    digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    final={'version':'V08','map':build['map'],'completed_at':datetime.datetime.now().isoformat(),'scope':'B martial court elevation pressure prototype. C alchemy and D summit layout retained from V07. Static crowd only; no combat AI, wave scheduler or VR validation.',
      'display_enemies':36,'ground_enemies':6,'terrace_enemies':30,'heights_m':[1.6,3.2,4.8],
      'checks':{'main_route_floors':geom['checks']['route_floor_samples'],'main_route_floors_pass':geom['success'],
        'route_width_samples':edges['samples'],'pressure_floor_samples':pressure['floor_samples'],
        'landing_capsules_clear':all(c['clear'] for c in pressure['landing_capsules']),
        'entry_heads_architecture_clear':[{k:v[k] for k in ('eye_height_m','count','heads_clear','chests_clear')} for v in pressure['entry_sightlines']],
        'actual_pie_walk_points':walk['waypoints_reached'],'actual_pie_walk_total':walk['total_waypoints'],'actual_pie_state':walk['state'],
        'peak_node_sightlines':geom['checks']['node_sightlines_pass']},
      'actor_count':build['actor_count'],'cluster_count':readback['cluster_count'],'instance_count':readback['instance_count'],'additional_instanced_actors':len(build['new_clusters']),
      'source_original_restored':source,'source_comparison_passed':comparison['success'],'screenshots':capture['captures'],
      'map_sha256':digest(ROOT/'Content/ReversedScale/Maps/L_NilinBlockoutV08.umap')}
    (OUT/'FinalReport.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
    readme='''逆鳞 V08：演武庭高低差敌阵样段

双击项目根目录 Run_Blockout_V08_Demo.cmd 试玩，按 3 直接到演武庭。
1–8 跳转；WASD/鼠标移动观察；F 切换飞行；0 总览；H 隐藏 HUD；Tab 释放鼠标。
Run_Blockout_V08_Editor.cmd 打开此版本编辑器。V07 可用 Run_Blockout_V07_Demo.cmd 对照。
项目默认地图未改变。通用 Run_Blockout_Demo.cmd/Editor.cmd 现在启动 V08。

这次只强化 B 演武庭：6 个地面近敌＋30 个高台敌人轮廓，三层石台分别高出庭院 1.6/3.2/4.8m。
两翼外侧各有 2.4m 宽石阶，中间保留 28m 直径平地战斗区与 8m 上山主通道。
三根阻挡石阶的武器架已在 V08 副本中移入廊侧，原 V07 的布置已从无新敌阵的副本恢复并核对。
新增物件位于 Nilin_V08/EnemyPressure；36 个落点 TargetPoint 带 NLPressure.Enemy.* 标签。
新轮廓与新增几何使用 5 个 native HISM Actor。它们不是可战斗敌人，不具备 AI、攻击或波次控制。
C 友方—丹炉关系、D 山顶 Boss 场景沿用 V07。后续分批下台接敌只是设计建议。

实际 UE 检查：主线路面 861 点、沿线宽度和桥头 4607 点、新敌阵地面 216 点通过；
6 处新阶梯平台的角色胶囊净空通过，中央战斗盘抽样保持原高；
入场处 1.10m 和 1.62m 眼高对 36 个敌人头/胸的建筑遮挡查询均通过；
此查询不包含人形彼此遮挡，轮廓重叠应结合实际游戏截图判断。
六个主要节点的坐姿/站姿山顶目标视线通过，不表示所有任意位置均可见。
实际 PIE CharacterMovement 完整行走含两侧石阶往返：{points}/{points} 点通过。

Screenshots 为真实 Unreal 渲染；Plan 中平面与剖面为按布局参数绘制的设计图。
当前为桌面白模检查，未整合敌人战斗或 VR 寻路/舒适度验证。
'''.format(points=walk['total_waypoints'])
    (OUT/'白模试玩说明.txt').write_text(readme,encoding='utf-8')
    note_path=OUT/'敌阵高低差设计说明.md'
    note=note_path.read_text(encoding='utf-8-sig')
    before='## 可玩性边界与待验证事项'
    if before in note:
        start=note.index(before);end=note.index('## 后续波次建议',start)
        checked='''## 已检查的空间与当前边界

- 静态敌阵共36个；尚未实现分批进攻、下台寻路、远程攻击或波次控制。
- V08 中三根负 X 武器架已移入廊侧，迁移记录保存在 BuildPressure.json；V07 对照图的原布置已核对。
- 新敌阵216处支撑地面查询、6处石阶平台角色胶囊净空查询通过；中央R14m战斗盘抽样保持原高度。
- 入场1.10m、1.62m眼高对36个头部及胸部的建筑遮挡查询均通过；人形彼此的遮挡与压迫感以真实渲染图为准。
- 角色沿主线及两侧高台往返的实际 PIE 行走 {points}/{points} 点通过，六个主要节点的坐姿/站姿山顶目标视线通过。
- 本轮为桌面白模空间验证，当前未进行战斗和VR舒适度测试。

'''.format(points=walk['total_waypoints'])
        note_path.write_text(note[:start]+checked+note[end:],encoding='utf-8')
    print(json.dumps({'completed':True,'walk_points':walk['total_waypoints'],'enemy_count':36,'screenshots':len(capture['captures'])}))
if __name__=='__main__':main()
