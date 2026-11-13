"""Record the approved weapon and VR fix batch after asset authoring and art capture."""
import hashlib, json, shutil
from pathlib import Path

root=Path(__file__).resolve().parents[2]
docs=root/'Docs/AI'
nav=json.loads((docs/'VRNavigationEditorRepair-2026-10-16.json').read_text(encoding='utf-8'))
sword=json.loads((docs/'SelectedSwordAImported-2026-10-16.json').read_text(encoding='utf-8'))
capture=json.loads((docs/'SelectedSwordAPresentation-2026-10-16.json').read_text(encoding='utf-8'))
if not nav['success'] or not sword['success'] or not capture['visual_binding_restored']:
    raise RuntimeError('Authoring and initial presentation must finish before delivery')
if capture['held_weapon']!=sword['mesh'] or capture['melee_damage']!=10:
    raise RuntimeError('Initial held presentation does not match approved A or damage 10')
for name in ('BuildLog-VRGripNavigation-2026-10-16.txt','BuildLog-SelectedSwordA-2026-10-16.txt'):
    if 'Result: Succeeded' not in (docs/name).read_text(encoding='utf-8',errors='replace'):
        raise RuntimeError('A required source build did not succeed')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

report={
    'date':'2026-10-16','status':'Compiled_AssetsSaved_InitialHeldArtReviewed_AwaitingUserVRPlay',
    'user_selected_weapon':'A',
    'selection_source':'AssetInbox/Over 9000 Swords.zip',
    'source_zip_sha256':digest(root/'AssetInbox/Over 9000 Swords.zip'),
    'weapon':sword,
    'right_grip':{'whole_hand_controller_yaw_adjust_degrees':90,'blade_tip_axis':'+Z','forward_cutting_edge_axis':'+X in neutral controller frame'},
    'vr_entrance':{'initial_auto_start_delay_seconds':3,'requires':['HMD focus and tracking','both tracked controllers','installed input mapping','ready checkpoint','not paused or dead'],
                   'one_shot':True,'heading_aligned_at_entry_restore':True,'automatic_restart_after_cancel':False},
    'enemy_navigation':{'root_cause':'The first failed move and same-frame failed reposition previously hid/despawned the enemy, failing the encounter.',
                        'nav_data_previously_existed':True,'saved_generation_seconds':2.26,'ready_wait_seconds':10,
                        'path_recovery_attempts':3,'recovery_delay_seconds':0.75,
                        'no_nav_timeout_still_reports_failure':True,'navigation_asset_report':'Docs/AI/VRNavigationSaved-2026-10-16.json'},
    'pause_enabled_vr_reset':True,
    'initial_presentation':capture,
    'compile':'Succeeded','automated_tests_added_or_run':False,'real_hmd_acceptance':'Pending user play',
    'launcher':'Run_VR_Demo.cmd','runtime_note':'The launcher selects SteamVR only for its child. The system default OpenXR remains Meta.',
    'source_backup':'Deliveries/BeforeVRGripEncounter_20261015',
    'snapshot':'Deliveries/VRGripSwordA_20261016',
    'snapshot_requires':'Full base experiment project and local UE5.8; this is not a packaged standalone executable.',
}
(docs/'VRGripSwordADelivery-2026-10-16.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

state=docs/'State.md'
text=state.read_text(encoding='utf-8')
lines=text.splitlines()
updates={'Updated:':'Updated: 2026-10-16 Asia/Shanghai',
         'CurrentTask:':'CurrentTask: Approved sword A equipped; forward cutting edge, VR automatic entry and navigation recovery fixes compiled/saved; user VR acceptance pending',
         'TaskStatus:':'TaskStatus: VRGripSwordA_Compiled_AssetsSaved_InitialArtReviewed_AwaitingUserVRPlay'}
for i,line in enumerate(lines):
    for prefix,value in updates.items():
        if line.startswith(prefix): lines[i]=value
    if line.startswith('  CurrentAuthorization:'):
        lines[i]='  CurrentAuthorization: User requested sword-pack review, selected A, and requested forward blade grip plus visible VR encounter entry; implement, compile, save and review initial art. Real VR acceptance remains with the user.'
text='\n'.join(lines)+'\n'
section='''
VRGripSwordA_Current_20261016:
  - User reviewed real Over 9000 Swords geometry and selected A: Blade03 / Guard03 / Grip04 / Pommel03.
  - New SM_PlayerSword_A has 1594 triangles, 4 original material slots, 2 UV channels; 0.64 scale; overall 78.314cm.
  - Grip centre is authored at zero; tip +Z, edge -X in mesh frame; forward edge +X in neutral tracked controller frame.
  - Whole right-hand grip rotates +90deg around controller Z, with identical desktop basis correction before 45deg tilt.
  - Blade samples now (0,0,8.42), (0,0,36.68), (0,0,64.94) for A only; melee10 / qi15 unchanged.
  - Original Yueyao mesh/materials retained as fallback; enemy, hand and shield assets preserved.
  - VR first entry auto-starts once after 3 seconds of HMD, both hands, input mapping and checkpoint readiness.
  - Entry/explicit spatial restore aligns head yaw to saved entrance; tracking recovery preserves existing heading.
  - Cancel, failure and retry consume initial auto-start; A/menu starts again explicitly. No-HMD does not auto-start.
  - Navigation failure now waits up to10s for a matching usable tile, then attempts up to3 recoveries at0.75s intervals.
  - VR Recast already existed; rebuilt and saved completed tiles (2.26s). Bounds/radius28/height176/Dynamic retained.
  - IA_VRReset now triggers while paused. HUD exposes start/checkpoint/encounter failure reasons.
  - Build succeeded; selected weapon initial desktop Ready presentation confirms correct mesh/materials and damage10.
  - No automated tests, controller simulation, combat start or real-HMD acceptance performed.
  - Delivery: Docs/AI/VRGripSwordADelivery-2026-10-16.json; snapshot Deliveries/VRGripSwordA_20261016.
'''
if 'VRGripSwordA_Current_20261016:' not in text: text+=section
state.write_text(text,encoding='utf-8')
dev=docs/'DevelopmentStatus.md'
text=dev.read_text(encoding='utf-8')
if '2026-10-16：A武器与VR握持/入场修复' not in text:
    text+='''

## 2026-10-16：A武器与VR握持/入场修复

- 用户从真实模型组合预览选定A，已接入主角右手：03剑身、03护手、04握柄、03剑首；双刃直剑，整体78.314cm，1594三角面。
- 原材质和UV保留，握柄中心与旧手部挂点对齐；右手整体转正，锋刃朝前。命中采样已按新直剑长度更新，近战伤害仍为10。
- VR设备、映射、存档连续就绪3秒后自动进入首波；入场/恢复时对齐头部水平朝向；取消或重试后仍可用A/菜单手动开始。
- 用户日志的NavigationFailed来自第一次移动及重定位失败就隐藏敌人；现增加导航就绪等待和真正的间隔重试，并重新保存VR地图导航数据。
- 暂停时可以使用手柄重试。编译与资产保存成功，初始桌面持握呈现已检查；实际VR移动、挥剑、入场和导航仍待用户试玩。
- 报告：VRGripSwordADelivery-2026-10-16.json；试玩入口：Run_VR_Demo.cmd。旧月曜模型保留，项目仍需本机UE5.8运行。
'''
dev.write_text(text,encoding='utf-8')

guide=root/'VRDemo_操作说明.txt'
text=guide.read_text(encoding='utf-8')
if '当前主角武器：审核选定的 A' not in text:
    text+='\n当前主角武器：审核选定的 A（双刃直剑，约78.3cm）；已对齐原手部握姿。挥剑伤害10。\n'
guide.write_text(text,encoding='utf-8')

snapshot=root/'Deliveries/VRGripSwordA_20261016'
files=set()
for folder in ['Source','Config','Content/ModularWeapons','Content/ReversedScale/Weapons/SelectedSwordA','ArtSource/WeaponReview/Over9000/SelectedA']:
    files.update(p for p in (root/folder).rglob('*') if p.is_file())
for rel in ['Binaries/Win64/UnrealEditor-experiment.dll','Binaries/Win64/UnrealEditor.modules',
            'Content/ReversedScale/Maps/L_CombatLabVR.umap','Content/ReversedScale/Player/VR/Input/IA_VRReset.uasset',
            'experiment.uproject','Run_VR_Demo.cmd','Run_VR_Demo.ps1','VRDemo_操作说明.txt',
            'ArtSource/WeaponReview/Over9000/CandidateShapes.png','ArtSource/WeaponReview/Over9000/CandidateShapes.blend',
            'ArtSource/WeaponReview/Over9000/CandidateShapes.json','ArtSource/WeaponReview/Over9000/Inventory.json']:
    files.add(root/rel)
for name in ['State.md','DevelopmentStatus.md','VRGripSwordADelivery-2026-10-16.json',
             'BuildLog-VRGripNavigation-2026-10-16.txt','BuildLog-SelectedSwordA-2026-10-16.txt',
             'VRNavigationBeforeRepair-2026-10-16.json','VRNavigationSaved-2026-10-16.json','VRNavigationEditorRepair-2026-10-16.json',
             'SelectedSwordAImported-2026-10-16.json','SelectedSwordAPresentation-2026-10-16.json',
             'SelectedSwordA_Equipped.png','SelectedSwordA_BothGrip.png']:
    files.add(docs/name)
for name in ['author_vr_input_assets.py','repair_vr_navigation.py','repair_vr_navigation_editor.py',
             'import_selected_sword_a.py','capture_selected_sword_a.py','capture_player_hand_presentation.py',
             'save_vr_sword_a_delivery.py']:
    files.add(root/'Saved/Scripts'/name)
entries=[]
for src in sorted(files):
    rel=src.relative_to(root)
    dst=snapshot/rel
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
    entries.append({'path':rel.as_posix(),'bytes':src.stat().st_size,'sha256':digest(src)})
(snapshot/'Manifest.json').write_text(json.dumps({'date':'2026-10-16','requires_base_project':True,'files':entries},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'saved':True,'snapshot_files':len(entries),'report':str(docs/'VRGripSwordADelivery-2026-10-16.json')},ensure_ascii=False))
