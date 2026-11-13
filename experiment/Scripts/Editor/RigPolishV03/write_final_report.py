"""Write delivery evidence only after saved references and real attacks pass."""
import hashlib,json
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[3]
OUT=PROJECT/'Docs/Gameplay/RigPolish_v03'
ART=PROJECT/'ArtSource/WuxiaMale/RigPolishV03/Attack'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
motion=read(OUT/'AfterMotion.json');probe=read(OUT/'CompactAttackValidation.json')
preview=read(OUT/'AttackComparison.json');assigned=read(OUT/'AttackAssignments.json')
imported=read(ART/'CompactAttackImported.json');metrics=read(ART/'CompactAttackMetrics.json')
before=read(OUT/'BeforeAssetAudit.json');after=read(OUT/'AssetAudit.json');desktop=read(OUT/'DesktopLaunch.json')
for report in (motion,probe,preview,assigned,imported):
    assert report['state']=='passed' and not report.get('failures')
assert imported['metadata_unchanged'] and imported['maximum_lower_body_error_cm']<.1
assert all(probe['checks'].values()) and len(probe['cycles'])==2
assert all(len(c['damage_events'])==1 and c['rewinds']==0 for c in probe['cycles'])
assert len(assigned['enemies'])==4 and len(after['enemies'])==8
for a,b in zip(before['enemies'],after['enemies']):
    assert a['key']==b['key'] and a['mesh']==b['mesh'] and a['timing']==b['timing']
    for prop,old in a['animations'].items():
        if prop=='attack_animation' and a['key'] in ('sword','GM01','GM04','boss'):
            assert 'Wuxia_Attack_Sword_Compact_v03' in b['animations'][prop]
        else:assert old==b['animations'][prop],(a['key'],prop)
actual_clips=sorted({f['asset'] for f in motion['frames'] if f['asset']})
assert 'Wuxia_Attack_Sword_Compact_v03' in actual_clips
assert 'Wuxia_Death_Restrained_v02' in actual_clips
assert any('SWING_ACTIVE' in f['blade_state'] for f in motion['frames'])
for entry in read(OUT/'BeforeIntegrity.json'):
    assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest().lower()==entry['sha256'].lower(),entry['path']
assert desktop['state']=='running_verified'
report={'state':'passed','date':'2026-10-24','project':str(PROJECT),'scope':'Compact sword animation on sword, GM01, GM04 and boss only.',
    'animation':'/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Compact_v03',
    'before':{k:metrics['before'][k] for k in ('peak_hand_speed_cm_s','peak_sword_tip_speed_cm_s','sword_tip_path_cm','max_chest_rotation_from_idle_deg','max_head_rotation_from_idle_deg')},
    'after':{k:metrics['after'][k] for k in ('peak_hand_speed_cm_s','peak_sword_tip_speed_cm_s','sword_tip_path_cm','max_chest_rotation_from_idle_deg','max_head_rotation_from_idle_deg')},
    'metadata_preserved':imported['source_signature'],'maximum_lower_body_error_cm':imported['maximum_lower_body_error_cm'],
    'actual_attack_validation':{'cycles':len(probe['cycles']),'target_distance_cm':probe['target_distance_cm'],
        'initial_health':probe['initial_health'],'final_health':probe['final_health'],'checks':probe['checks']},
    'runtime_clips':actual_clips,'desktop_launch':desktop,
    'integrity':'Original attack, shoulder mesh, restrained death, Gameplay/V01 map, V10 source map and DefaultEngine.ini hashes unchanged.',
    'limits':['Desktop validation only; no VR headset acceptance or complete level playthrough.',
        'Dedicated hit test uses a stationary unguarded player at normal melee distance with other enemies isolated in PIE. No synthetic resolver damage was used in that hit test.',
        'All four sword archetype defaults were checked; the actual two-cycle hit test used the standard sword disciple.'],
    'evidence':['AttackAssignments.json','CompactAttackValidation.json','AttackComparison.json','AfterMotion.json','AssetAudit.json','BeforeIntegrity.json']}
(OUT/'FinalReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
note='敌人挥剑动作优化 v03\n\n已应用于剑弟子、宗师GM01、宗师GM04和Boss的近战动画。\n重做近身蓄力、正前方斜切及收剑回位，缩小大幅后甩和扭头扭胸，调整手肘与手腕。\n保留原2.333秒动画长度、0.8–1.03秒伤害通知、所有敌人原攻击时间/范围/伤害；脚、根位置、施法与上一轮死亡和肩部修复保留。\n实际验证：125厘米处的正常玩家胶囊，两次完整AI挥剑各扣10点生命，伤害只在有效窗口内发生，恢复段完整且未重播。新动作已在正常关卡AI中加载。\n本轮完成桌面验证，未做头显验收或全关卡通关。\n原动作保留；四个蓝图修改前备份位于Backups/Assets。详细证据见FinalReport.json。\n'
(OUT/'敌人挥剑优化说明.txt').write_text(note,encoding='utf-8')
print(json.dumps({'state':report['state'],'actual_attack_validation':report['actual_attack_validation'],'after':report['after']},ensure_ascii=False,indent=2))
