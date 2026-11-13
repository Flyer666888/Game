"""Finalize saved batch metadata without interacting with gameplay."""
import json
import sys
from pathlib import Path

project = Path(__file__).resolve().parents[2]
docs = project / 'Docs/AI'
delivery_file = docs / 'NaturalGripDelivery-2026-10-12.json'
report = json.loads(delivery_file.read_text(encoding='utf-8'))
prefab = json.loads((docs / 'SwordDisciplePrefabSaved.json').read_text(encoding='utf-8'))
report['reusable_sword_prefab'] = prefab
report['next_task_design'] = 'Docs/AI/WaveNextTask-2026-10-12.json'
report['wave_controller_implemented'] = False
report['process_id_at_delivery'] = 52892
report['initial_scene_scope'] = 'Two live idle enemies, new mesh/Grip override/Natural death references read; temporary idle hand portrait camera restored; no combat input.'
report['recovery_snapshot'] = 'Deliveries/NaturalGrip_20261012/Manifest.json'
report['user_controls'] = {'G': 'Start/stop duel', 'LMB': 'Slash (10 damage)', 'R': 'Reset', 'E': 'Blade qi (15)', 'RMB': 'Mirror'}
if '--paused' in sys.argv:
    report['session_status'] = 'Finished at authorization deadline; heartbeat automation confirmed paused.'
delivery_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
state_file = docs / 'State.md'
state = state_file.read_text(encoding='utf-8')
state = state.replace('ProcessIdAtDelivery: 41928', 'ProcessIdAtDelivery: 52892')
state = state.replace('NextAction: Let user play this enemy slice; next dependency is WAVE-01, then SAVE-01 and ENEMY-02.',
                      'NextAction: User play natural death/grip demo. WAVE-01 design and reusable sword Blueprint are saved; Wave controller remains next, followed by SAVE-01.')
if 'SwordDisciplePrefab_Current:' not in state:
    state += '\nSwordDisciplePrefab_Current:\n  Asset: /Game/ReversedScale/Characters/WuxiaMale/BP_EnemySwordDisciple\n  Saved: True; compiled Blueprint and read CDO references; no actors spawned or gameplay tests.\n  Evidence: Docs/AI/SwordDisciplePrefabSaved.json\n  Purpose: Reusable configured enemy for next WAVE-01 batch; controller not implemented.\n  Design: Docs/AI/WaveNextTask-2026-10-12.json\n  DemoProcessIdAtDelivery: 52892\n  Snapshot: Deliveries/NaturalGrip_20261012/Manifest.json\n'
if '--paused' in sys.argv:
    state = state.replace('Automation: automation / ACTIVE / 30-minute heartbeat / 6 occurrences',
                          'Automation: automation / PAUSED / confirmed at session deadline')
    if 'OptimizationSessionFinalStatus:' not in state:
        state += '\nOptimizationSessionFinalStatus: Saved at 2026-10-12 18:35 Asia/Shanghai; automation confirmed PAUSED; user play pending.\n'
state_file.write_text(state, encoding='utf-8')
print('NATURAL_GRIP_FINAL_DELIVERY_SAVED')
