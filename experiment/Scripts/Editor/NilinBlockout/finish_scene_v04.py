"""Publish launchers and concise delivery only after recorded checks pass."""
from pathlib import Path
import json,hashlib,datetime,shutil
ROOT=Path(r'D:\game design\experiment')
OUT=ROOT/'Docs/LevelDesign/Blockout_v04'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
validation=read('Validation.json');edges=read('EdgeAudit.json');pressure=read('PressureAudit.json')
walk=read('RuntimeWalk.json');scene=read('SceneBuild.json');actual=read('Readback.json')
capture=json.loads((OUT/'Screenshots/CaptureReport.json').read_text(encoding='utf-8'))
baseline=read('SourceBaseline.json')
assert validation['success'] and edges['success'] and pressure['success']
assert walk['state']=='passed' and walk['waypoints_reached']==walk['total_waypoints']
assert not capture['error'] and len(capture['captures'])>=6
assert 'Result: Succeeded' in (OUT/'Build.log').read_text(encoding='utf-8',errors='replace')
source=Path(baseline['source'])
assert hashlib.sha256(source.read_bytes()).hexdigest()==baseline['sha256'],'Source V08 changed'
for item in capture['captures']:
    path=Path(item['file']);assert path.stat().st_size>10000
backups=OUT/'Backups';backups.mkdir(exist_ok=True)
for name in ('Run_Blockout_Demo.ps1','Run_Blockout_Editor.ps1'):
    path=ROOT/name
    if not (backups/name).exists():shutil.copy2(path,backups/name)
    text=path.read_text(encoding='utf-8-sig')
    text=text.replace("ValidateSet('V06','V07','V08')","ValidateSet('V06','V07','V08','V09')").replace("$MapVersion = 'V08'","$MapVersion = 'V09'")
    path.write_text(text,encoding='utf-8-sig')
for mode in ('Demo','Editor'):
    text=(ROOT/f'Run_Blockout_V08_{mode}.cmd').read_text(encoding='utf-8').replace('V08','V09')
    (ROOT/f'Run_Blockout_V09_{mode}.cmd').write_text(text,encoding='ascii')
report={
    'version':'V09','map':'/Game/ReversedScale/Maps/L_NilinBlockoutV09',
    'completed_at':datetime.datetime.now().astimezone().isoformat(),
    'source_v08_sha256_unchanged':True,'source_sha256':baseline['sha256'],
    'map_sha256':hashlib.sha256((ROOT/'Content/ReversedScale/Maps/L_NilinBlockoutV09.umap').read_bytes()).hexdigest(),
    'changes':{'rock_meshes':scene['terrain']['mesh_count'],'architecture_parts':scene['architecture']['instance_count'],'architecture_meshes':scene['architecture']['custom_meshes'],'new_instanced_boxes':scene['new_instances'],'new_clusters':scene['new_clusters']},
    'actor_count':actual['actor_count'],'total_hism_clusters':actual['cluster_count'],'total_hism_instances':actual['instance_count'],
    'checks':{'main_route_floor_samples':validation['checks']['route_floor_samples'],'main_route_floor_pass':not validation['checks']['route_floor_failures'],'edge_audit_pass':edges['success'],'pressure_audit_pass':pressure['success'],'node_sightlines_pass':validation['checks']['node_sightlines_pass'],'actual_pie_walk_points':walk['waypoints_reached'],'actual_pie_walk_total':walk['total_waypoints'],'actual_pie_state':walk['state'],'build':'Succeeded'},
    'screenshots':capture['captures'],
    'scope':'Scene whitebox iteration. Enemy silhouettes remain static; VR combat demo stays separate. No headset comfort test performed.'
}
(OUT/'FinalReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
instructions='''逆鳞 V09｜山势与中式建筑优化

双击项目根目录 Run_Blockout_V09_Demo.cmd 试玩。
通用 Run_Blockout_Demo.cmd 现在也启动 V09。
Run_Blockout_V09_Editor.cmd 可打开此版本关卡编辑器。
V08 对照版：Run_Blockout_V08_Demo.cmd。

操作：WASD/鼠标移动观察；1–8 跳转节点；F 切换飞行；0 总览；H 隐藏 HUD；Tab 释放鼠标。
建议观察顺序：1 山门，3 演武庭，5 炼丹院，7 山顶，最后按0查看整体山势。

本轮改动：
・新增12处错落山肩、岩脊及远侧奇峰，丰富连续山墙的轮廓与空间层次。
・山门增加额枋、斜撑、门侧格栅与挂落，中轴门洞保持宽阔。
・炼丹院增加26×12米后置重檐屋面，强化丹阁辨识度；檐下补充开放式木构。
・山顶两石阙增加斜收柱头、叠涩檐口与浅浮雕，圆形战斗场仍然开敞。
・演武庭补充两侧石灯；36人敌阵的三层高差继续用于研究人数压迫感。

检查结果：主线路面861点、沿线宽度与桥头4607点通过；敌阵地面、台阶和头胸视线通过。
六个主要登山节点在坐姿/站姿眼高下可见山顶目标。
实际角色连续行走354/354点通过，包括两翼高台往返。源V08地图文件校验值保持一致。
Screenshots目录为真实UE渲染截图，可直接对照编辑器。

当前版本为场景白模。敌人仍是站位轮廓；剑气基础技能继续在独立VR战斗试玩中使用。
本轮未做头显舒适度实测。后续可基于实机反馈调整敌阵距离、掩体和战斗区域。

新增场景物件在编辑器目录 Nilin_V09/Terrain 与 Nilin_V09/Architecture 中。
所有新增实体具有碰撞；细节方块使用HISM合批。完整检查记录见FinalReport.json。
'''
(OUT/'白模试玩说明.txt').write_text(instructions,encoding='utf-8')
print(json.dumps({k:report[k] for k in ('version','actor_count','total_hism_clusters','total_hism_instances','checks')},ensure_ascii=False,indent=2))
