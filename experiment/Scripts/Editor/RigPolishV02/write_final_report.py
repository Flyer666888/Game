"""Collect completed, saved evidence for the shoulder and restrained-death pass."""
import hashlib,json
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[3]
OUT=PROJECT/'Docs/Gameplay/RigPolish_v02'
ART=PROJECT/'ArtSource/WuxiaMale/RigPolishV02'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
motion=read(OUT/'AfterMotion.json');ranged=read(OUT/'RangedValidation.json')
assignments=read(OUT/'EnemyAssignments.json');audit=read(OUT/'AssetAudit.json');before=read(OUT/'BeforeAssetAudit.json')
shoulder=read(ART/'Shoulder/ShoulderRepairSummary.json')
death=read(ART/'Death/RestrainedDeathContacts.json');runtime_death=read(ART/'Death/RestrainedDeathRuntimeContacts.json')
imported_death=read(ART/'Death/RestrainedDeathImported.json')
automation=read(OUT/'Automation/index.json');desktop=read(OUT/'DesktopLaunch.json')
assert desktop['state']=='running_verified','Desktop window/level did not finish launching'
for report in (motion,ranged,assignments,runtime_death,read(OUT/'ShoulderImport.json'),read(OUT/'ShoulderComparison.json'),read(OUT/'DeathComparison.json')):
    assert report['state']=='passed' and not report.get('failures'),report.get('state')
assert len(assignments['enemies'])==len(audit['enemies'])==8
for enemy,original in zip(audit['enemies'],before['enemies']):
    assert enemy['key']==original['key']
    assert 'SK_WuxiaMale_Shoulder_v02' in enemy['mesh']
    assert 'Wuxia_Death_Restrained_v02' in enemy['animations']['death_animation']
    for key,value in original['animations'].items():
        if key!='death_animation':assert enemy['animations'][key]==value,key
assert all('SK_WuxiaMale_Shoulder_v02' in f['mesh_asset'] for f in motion['frames'])
actual_clips=sorted({f['asset'] for f in motion['frames'] if f['asset']})
assert 'Wuxia_Death_Restrained_v02' in actual_clips
assert 'Wuxia_Hit_Sword_Upright_v01' in actual_clips
blade_frames=sum('SWING_ACTIVE' in f['blade_state'] for f in motion['frames'])
assert blade_frames>0
assert all(ranged['checks'].values())
assert automation['failed']==automation['notRun']==automation['inProcess']==0
assert automation['succeeded']+automation['succeededWithWarnings']==28
source_v10=hashlib.sha256((PROJECT/'Content/ReversedScale/Maps/L_NilinBlockoutV10.umap').read_bytes()).hexdigest()
assert source_v10=='701a12f8a896e938ad76cb5ab68e7cf65d635a5c9d6b2699375bdc9a3538e248'
for name in ('SK_WuxiaMale_Combat','SK_WuxiaMale_Demo_Skeleton'):
    suffix=Path('ReversedScale/Characters/WuxiaMale')/(name+'.uasset')
    assert (PROJECT/'Content'/suffix).read_bytes()==(OUT/'Backups/Assets'/suffix).read_bytes()
report={'date':'2026-10-24','state':'passed','project':str(PROJECT),
    'scope':'Shoulder weights and death presentation on the eight current Gameplay/V01 enemy archetypes.',
    'shoulder':{'source_vertices':shoulder['unchanged_invariants']['vertices'],'changed_weight_vertices':shoulder['changed_vertices'],
        'basis_uv_topology_skeleton_morphs_materials_unchanged':True,'max_bone_influences':shoulder['max_influences'],
        'grip_weight_overlap':shoulder['grip_overlap'],'robe_weight_overlap':shoulder['robe_overlap'],'metrics':shoulder['metrics']},
    'death':{'duration_seconds':death['duration_seconds'],'final_hold_seconds':death['final_hold_seconds'],
        'root_travel_before_cm':death['before']['root_xy_travel_cm'],'root_travel_after_cm':death['after']['root_xy_travel_cm'],
        'maximum_imported_bone_error_cm':imported_death['maximum_bone_position_error_cm'],
        'runtime_minimum_skin_height_cm':runtime_death['minimum_skin_height_cm'],
        'runtime_minimum_sword_height_cm':runtime_death['minimum_sword_height_cm']},
    'runtime':{'motion_frames':len(motion['frames']),'actual_clips':actual_clips,'active_blade_frames':blade_frames,
        'ranged_checks':ranged['checks'],'ranged_projectiles':ranged['rock_r01_ai']['projectile_count'],
        'ranged_cleanup':ranged['cleanup']['state']},
    'automation':{k:automation[k] for k in ('succeeded','succeededWithWarnings','failed','notRun','inProcess')},
    'desktop_launch':desktop,'source_blockout_v10_sha256':source_v10,
    'limits':['Desktop presentation checks only; no headset acceptance or full manual level playthrough.',
        'Contact checks use the flat local floor and the real skinned mesh; no all-terrain corpse physics or cloth simulation.',
        'Motion probe uses health assistance and real resolver test contacts; it is not a manual combat acceptance test.'],
    'evidence':['ShoulderImport.json','ShoulderComparison.json','DeathComparison.json','AfterMotion.json','RangedValidation.json','EnemyAssignments.json','AssetAudit.json','Automation/index.json']}
(OUT/'FinalReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
text='敌人肩部与死亡动作优化 v02\n\n已应用到8类当前关卡敌人。\n肩部：修复颈肩上胸误绑头骨和邻近权重突变，消除待机、挥剑、施法中的肩颈尖角。保留原模型外形、材质、握剑手形和攻击动作轨迹。\n死亡：改为屈膝失力、手臂撑地、身体下沉；动作2.6秒，最后0.5秒静止。根位移约71.4厘米缩至35厘米。\n验证：UE并排预览、实际AI行走/攻击/受击/死亡、两名岩台施法敌人的真实投射物，以及28项现有自动化测试通过。UE压缩后的79帧实际蒙皮及剑网格无局部平面穿地。\n限制：本轮为桌面验证，未做头显验收或全地形尸体物理验证。\n原资产保留，蓝图修改前副本在同目录Backups/Assets。详见FinalReport.json。\n'
(OUT/'敌人肩部与死亡动作优化说明.txt').write_text(text,encoding='utf-8')
print(json.dumps({'state':report['state'],'automation':report['automation'],'death':report['death']},ensure_ascii=False,indent=2))
