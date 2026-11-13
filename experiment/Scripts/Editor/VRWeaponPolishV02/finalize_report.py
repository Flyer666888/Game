"""Collect final asset and supplied-pose evidence without starting Unreal."""
import hashlib, json
from pathlib import Path

P = Path(__file__).resolve().parents[3]
OUT = P/'Docs/Gameplay/VRWeaponPolish_v02'
SRC = P/'ArtSource/WeaponReview/SelectedA_DetailV02'
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

imp = read(OUT/'ImportReport.json')
run = read(OUT/'RuntimeGripReport.json')
geo = read(SRC/'AssetReadbackReport.json')
protected = [dict(path=x['Path'], before=x['Hash'].lower(), after=digest(Path(x['Path'])))
             for x in read(OUT/'ProtectedBaselineHashes.json')]
assert all(x['before']==x['after'] for x in protected)
assert imp['state']==run['state']==geo['state']=='passed'
assert len(run['poses'])==7 and not run['failures']
assert run['map_unchanged'] and run['checkpoint_settings_restored']
assert read(OUT/'Status.json')['state']=='closed'
fbx = SRC/'SM_PlayerSword_A_DetailV02.fbx'
mesh = P/'Content/ReversedScale/Weapons/SelectedSwordA_DetailV01/SM_PlayerSword_A_DetailV01.uasset'
assert digest(fbx)==imp['source_sha256']==geo['fbx_sha256']
assert digest(mesh)==run['mesh_sha256']
excerpt = (OUT/'FinalImportExcerpt.log').read_text(encoding='utf-8-sig')
assert not any(x in excerpt for x in ('FBXImport: Warning','近零的切线','近零的副法线','Traceback'))
report = {
    'state':'passed', 'revision':'V02',
    'runtime_asset':run['equipped_mesh'],
    'runtime_asset_sha256':digest(mesh), 'source_fbx_sha256':digest(fbx),
    'source_triangles':geo['triangles'], 'ue_render_triangles':run['lod0_triangles'],
    'triangle_counts_note':'Source and UE render counts are recorded separately; they differ by 16 triangles.',
    'uv_channels':geo['uv_channels'], 'material_slots':geo['slots'],
    'final_import_warning_check':'No FBX warning or near-zero tangent/binormal message in the final reimport excerpt.',
    'saved_build_settings':imp['saved_build_settings'],
    'synthetic_equipped_grip_poses_passed':len(run['poses']),
    'map_unchanged':run['map_unchanged'], 'checkpoint_settings_restored':run['checkpoint_settings_restored'],
    'protected_files':protected,
    'visual_review':'Final UE Forte_Closeup and Blade_Oblique screenshots visually inspected after tangent rebuild.',
    'review_editor_closed':True,
    'launcher_preflight':'Run_VR_Demo.ps1 -CheckOnly: Passed; no application started.',
    'physical_pico_acceptance':False, 'performance_benchmark_run':False,
    'cpp_changed_or_rebuilt_this_revision':False,
    'evidence':['ImportReport.json','FinalImportExcerpt.log','ReimportSettingsRepair.json',
                'AssetReadbackReport.json','AssetUVRepairReport.json','RuntimeGripReport.json'],
    'backup':'Backups/Content/ReversedScale/Weapons/SelectedSwordA_DetailV01'
}
(OUT/'FinalReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
notes = '''主角剑模型 V02：修改与验证说明

完成内容
1. 护手改成纤薄的单片如意云肩曲线，连续圆角，保留中心剑根套箍。
2. 剑身宽度和厚度连续收向剑尖，整理菱形刃面；短浅槽在剑身前段逐渐淡出。
3. 云纹嵌线贴合刃面，突出量约0.03毫米，减少浮雕悬浮感。
4. 剑首增加青玉镶饰和青铜叶形包边。
5. 总长约78.314厘米；握持部位、模型原点和攻击采样位置保持原状。

落地方式
源文件：ArtSource/WeaponReview/SelectedA_DetailV02，包含.blend、.fbx及细节预览。
运行时保留 SelectedSwordA_DetailV01/SM_PlayerSword_A_DetailV01 的稳定路径，内容已更新为V02。
新材质存于该目录 Materials/V02；旧版材料保留。未改C++或重新编译。

验证结果
独立FBX读回通过：13,580三角面、7材质槽、2UV通道。UE渲染网格为13,564三角面，两者分别记录。
源几何无零面积三角面；两套UV均无零/近零面积三角面。只修复原握柄各通道16个退化UV面，其余握柄UV不变。
解决了重导入沿用旧“导入法线和切线”设置的问题；保留模型法线，使用MikkTSpace重算切线。
最终重导入日志不再出现近零切线/副法线警告。日志保存在FinalImportExcerpt.log。
实际VR角色在PIE中装备新网格，通过7个合成Grip方向检查，并保存3张游戏内截图。
9个保护文件哈希全部不变，包括手模型、动作、关卡、持剑代码及DLL。
PIE结束、临时检查点设置恢复、隐藏UE验证进程退出。VR入口CheckOnly检查通过。
本轮未进行真人PICO头显验收、完整战斗回归或性能基准测试。

预览区别
Screenshots下是最终UE游戏内截图；ArtSource中的Detail预览采用Blender棚拍灯光，反光与场景中不同。

试玩
退出旧试玩后，双击工程根目录Run_VR_Demo.cmd，进入现有L_CombatLabVR。

回滚
关闭UE后，将本目录Backups/Content/ReversedScale/Weapons/SelectedSwordA_DetailV01中的原文件覆盖回工程同名目录。
V02材料可保留，不影响旧网格。操作说明的原件也保存在Backups中。
'''
(OUT/'修改与验证说明.txt').write_text(notes,encoding='utf-8')
print(json.dumps({'state':report['state'],'protected_files':len(protected),'synthetic_grip_poses':len(run['poses']),'report':str(OUT/'FinalReport.json')},ensure_ascii=False))
