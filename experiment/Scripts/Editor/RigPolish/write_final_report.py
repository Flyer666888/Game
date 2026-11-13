"""Collect completed evidence without manufacturing pass states."""
import hashlib,json
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[3]
OUT=PROJECT/'Docs/Gameplay/RigPolish_v01'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8-sig'))
automation=read('AutomationFinal/index.json')
motion=read('AfterMotion.json');facing=read('FacingValidation.json');ranged=read('RangedValidation.json')
candidates=read('UprightCandidatesReport.json');assignments=read('BodyAssignments.json');audit=read('AssetAudit.json')
desktop=read('DesktopLaunch.json')
assert automation['failed']==0 and automation['notRun']==0 and automation['inProcess']==0
assert automation['succeeded']+automation['succeededWithWarnings']==28
assert all(r['state']=='passed' and not r.get('failures') for r in (motion,facing,ranged,assignments))
assert candidates['status']=='passed' and len(candidates['clips'])==5
assert len(audit['enemies'])==8 and all('_Upright_v01' in e['animations']['walk_animation'] for e in audit['enemies'])
walk=next(c for c in candidates['clips'] if '/Wuxia_Walk_' in c['source'])
assert walk['runtime_metrics']['compressed']['loop_seam']['max_added_position_cm']<.001
report={
    'date':'2026-10-24','state':'passed','project':str(PROJECT),'map':'/Game/ReversedScale/Maps/L_NilinGameplayV01',
    'scope':'Enemy bodies and animation in the current desktop gameplay level.',
    'changes':['Five new upright clips assigned to all eight gameplay enemy archetypes.',
               'Pose transitions: locomotion 0.16 s, attack 0.12 s, hit 0.10 s; death retains 0.18 s.',
               'Velocity-scaled walk rate and 8/3 cm/s start/stop hysteresis.',
               '150 degrees/s waiting turn, attack reservation after facing error <=3 degrees.',
               'World-height smoothing and cyclic walk pose closure.'],
    'automation':{k:automation[k] for k in ('succeeded','succeededWithWarnings','failed','notRun','inProcess')},
    'runtime':{'motion_frames':len(motion['frames']),'motion_states':sorted(set(f['state'] for f in motion['frames'])),
               'actual_clips':sorted(set(f['asset'] for f in motion['frames'])),
               'blade_active_frames':sum('SWING_ACTIVE' in f['blade_state'] for f in motion['frames']),
               'facing_checks':facing['checks'],'turn_rate_observed_max':facing['max_observed_turn_rate_deg_s'],
               'ranged_checks':ranged['checks'],'ranged_projectiles':ranged['rock_r01_ai']['projectile_count'],
               'ranged_observation_seconds':ranged['rock_r01_ai']['observed_game_seconds'],
               'test_cleanup':ranged['cleanup']['state']},
    'pose_validation':{'clips':len(candidates['clips']),'bones':candidates['bone_count'],
                       'max_sampled_foot_error_cm':max(c['runtime_metrics']['compressed']['max_foot_position_error_cm'] for c in candidates['clips']),
                       'walk_loop':walk['runtime_metrics']['compressed']['loop_seam'],
                       'clip_metadata_unchanged':all(c['metadata_unchanged'] for c in candidates['clips'])},
    'desktop_launch':desktop,
    'source_blockout_v10_sha256':hashlib.sha256((PROJECT/'Content/ReversedScale/Maps/L_NilinBlockoutV10.umap').read_bytes()).hexdigest(),
    'limits':['Desktop only; no headset acceptance or full manual playthrough.',
              'First-stage motion probe uses a fixed target with health assistance; hit/death are resolver-driven test contacts.',
              'The first-stage motion observations did not record actual enemy damage to the player; attack/notify validation is based on active blade windows. Ranged probe independently observed real projectiles.',
              'Existing 23-bone mesh and simplified garment weights retained; no cloth simulation.',
              'Terrain-height smoothing was implemented; no full stair-route traversal was performed in this pass.'],
    'evidence':['Build.log','AutomationFinal/index.json','AfterMotion.json','FacingValidation.json','RangedValidation.json',
                'UprightCandidatesReport.json','AssetAudit.json','BodyAssignments.json','BodyPreview.json','MotionComparison.json'],
}
assert report['source_blockout_v10_sha256']=='701a12f8a896e938ad76cb5ab68e7cf65d635a5c9d6b2699375bdc9a3538e248'
(OUT/'FinalReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ('state','automation','pose_validation')},ensure_ascii=False,indent=2))
