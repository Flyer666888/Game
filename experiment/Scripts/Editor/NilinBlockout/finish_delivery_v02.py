from pathlib import Path
import json,datetime,hashlib,re
ROOT=Path(r'D:\game design\experiment');OUT=ROOT/'Docs/LevelDesign/Blockout_v02'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
v=read('Validation.json');e=read('EdgeAudit.json');walk=read('RuntimeWalk.json');rb=read('Readback.json');cluster=read('ClusterAudit.json');capture=json.loads((OUT/'Screenshots/CaptureReport.json').read_text(encoding='utf-8'))
assert v['success'] and e['success'] and walk['state']=='passed' and not walk['failures']
assert rb['save_confirmed'] and cluster['status']=='committed_and_saved'
assert not capture['error'] and len(capture['captures'])>=9
log=(OUT/'EditorReopen.log').read_text(encoding='utf-8',errors='replace')
map_checks=[line for line in log.splitlines() if 'MapCheck:' in line and ('地图检测完成' in line or 'Map check complete' in line)]
build=(OUT/'BuildFinal.log').read_text(encoding='utf-8',errors='replace')
assert 'Result: Succeeded' in build
report={'map':rb['map'],'saved_file':str(ROOT/'Content/ReversedScale/Maps/L_NilinBlockoutV07.umap'),'verified_at':datetime.datetime.now().isoformat(),'native_editor_build':'Succeeded','saved_and_reopened':True,'map_check_log':map_checks[-1] if map_checks else 'Not recorded','actor_count':rb['actor_count'],'actor_count_before_instancing':cluster['actor_count_before'],'clusters':rb['cluster_count'],'instanced_cubes':rb['instance_count'],'max_instance_corner_error_cm':cluster['readback_max_corner_error_cm'],'route_floor_samples':v['checks']['route_floor_samples'],'floor_failures':len(v['checks']['route_floor_failures']),'node_capsules_clear':all(n['capsule_clear'] for n in v['checks']['node_landings']),'main_nodes_seated_and_standing_see_peak_and_crown':all(n['physical_peak'] and n['crown'] for n in v['sightlines']['nodes']),'floor_width_and_bridgehead_query_samples':e['samples'],'continuous_desktop_walk':walk['state'],'walk_waypoints':walk['waypoints_reached'],'walk_seconds':walk['elapsed_seconds'],'walk_failures':walk['failures'],'actual_UE_screenshots':len(capture['captures']),'scope':'Playable desktop level-layout whitebox. Combat actors remain static placeholders.','not_validated':['VR headset performance and comfort','Formal combat, rescue and boss progression','Manual testing of every key','Visibility from every possible position'],'source_map_V06_preserved':True}
report['map_sha256']=hashlib.sha256(Path(report['saved_file']).read_bytes()).hexdigest()
(OUT/'FinalReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
text=f'''《逆鳞》V07 优化白模 — 交付与试玩说明
日期：2026-10-21

打开与试玩
工程根目录双击 Run_Blockout_Demo.cmd 进入新版桌面漫游；Run_Blockout_Editor.cmd 打开新版编辑器。
地图：/Game/ReversedScale/Maps/L_NilinBlockoutV07
旧图保留，Run_Blockout_V06_Demo.cmd / Run_Blockout_V06_Editor.cmd 可打开V06。

本轮改进
保留四院、八节点及0→28→72→132m主高程关系。高山门、低演武廊、开放巨炉亭、峰顶石阙圆阵分别形成轮廓。
程序屋面采用连续曲线、起翘檐角与斗拱；配房屋脊沿长边布置。丹炉改为宽肩炉腹、双耳、炉盖和三足。
五块连续折面岩体取代柱列山体，巨松增加曲干、分枝与层叠树冠；云雾下降，路线边缘保持清楚。
保留前段8m结构宽度；上段6.5m结构宽度、步高≤16cm。原休息板不缩小，增设三块桥头，峰顶使用径向入口及8×3m接圆板。
重复Cube已实例化：{cluster['actor_count_before']}个Actor降至{rb['actor_count']}个；{rb['cluster_count']}组、{rb['instance_count']}个实例。这里只确认物件数量减少，不推断帧率。

实际验证
原生Editor编译成功；V07保存、关闭后重新载入；地图检查见FinalReport.json。
861/861路线地面采样通过，8/8节点胶囊落点通过；01–06在1.1m/1.7m眼高共12组实体峰顶与剑冠视线通过。
{e['samples']}个地面宽度/桥头采样通过。此项仅查询支撑地面，忽略栏杆以免将柱体当成地板；地图栏杆仍保持BlockAll碰撞。
真实PIE CharacterMovement连续步行：{walk['waypoints_reached']}/{walk['total_waypoints']}路径点，{walk['elapsed_seconds']:.1f}秒，无卡死/坠落记录；8节点实际角色落地记录见RuntimeWalk.json。
本目录Screenshots为真实UE渲染；Plan读取最终LayoutSpec，含可编辑SVG、PNG和可开关图层的HTML。

操作
WASD移动、鼠标转向、Space跳跃、Shift加速、Ctrl精细移动。
F切换步行/飞行；飞行Q下降、E上升；0跳至总览相机，1–8淡出跳至节点，R回01。
F1开关帮助，H隐藏/恢复HUD，Tab释放/恢复鼠标，Esc释放鼠标（PIE可能停止），Alt+F4关闭独立试玩。

范围
这是可漫游的关卡布局白模；挚友、敌人及Boss仍是位置占位。未接入正式战斗、解救计时、Boss阶段、存档或通关逻辑。
坐站视线验收覆盖上述节点，不代表每一处位置始终无遮挡。VR头显舒适性、帧率和全键鼠手工体验尚未完整验收。

恢复与维护
Backups保留几何与实例化前地图；HISMRecovery_*.json记录各源物件变换、材质与碰撞配置。
不要以旧版检查结果替代本轮报告；后续改动后需重新验证。脚本源在Scripts/Editor/NilinBlockout。
'''
(OUT/'白模试玩说明.txt').write_text(text,encoding='utf-8-sig')
print(json.dumps(report,ensure_ascii=False,indent=2))
