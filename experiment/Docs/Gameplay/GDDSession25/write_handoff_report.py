"""Aggregate existing validation evidence; never edits source/assets or save games."""
import datetime
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[2]
GAMEPLAY = OUT.parent

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

hand = read(GAMEPLAY / 'RigPolish_v04/FinalReport.json')
seals = read(GAMEPLAY / 'FourSeals_v01/RuntimeIntegration.json')
isolation = read(GAMEPLAY / 'FourSeals_v01/FixtureIsolation.json')
abilities = read(GAMEPLAY / 'CombatSkills_v01/AbilityGameplayProbe.json')
inputs = read(GAMEPLAY / 'CombatSkills_v01/AbilityInputAssets.json')
lab = read(GAMEPLAY / 'RitualObjective_v01/LabAuthored.json')
ritual = read(GAMEPLAY / 'RitualObjective_v01/RuntimeProbe.json')
automation = read(OUT / 'Automation_01/index.json')
assert hand['state'] == 'complete'
assert seals['state'] == 'passed' and seals['success'] and not seals['failures']
assert abilities['state'] == 'passed' and all(abilities['checks'].values())
assert inputs['state'] == 'passed'
assert lab['state'] == 'authored' and lab['source_unchanged']
assert ritual['state'] == 'passed' and all(ritual['checks'].values())
assert automation['failed'] == automation['notRun'] == automation['inProcess'] == 0
assert (OUT / 'Build_02.exitcode').read_text().strip() == '0'
map_path = PROJECT / 'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
map_hash = hashlib.sha256(map_path.read_bytes()).hexdigest()
assert isolation['state'] == 'restored_without_saving_map'
assert map_hash == isolation['map_sha256_before'] == isolation['map_sha256_after']
assert not Path(isolation['test_marker']).exists()

report = {
    'state': 'implemented_scope_saved_and_verified',
    'date': '2026-10-26',
    'generated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'Close the authorized work window and its interrupted validation; not completion of the entire GDD.',
    'hand_v04': {'state': hand['state'], 'report': '../RigPolish_v04/FinalReport.json'},
    'four_seals': {
        'state': seals['state'], 'stages': len(seals['stages']),
        'waves': sum(len(stage['waves']) for stage in seals['stages']),
        'spawned': seals['total_counted_spawns'],
        'resolver_defeats': seals['total_resolver_defeats'],
        'spawn_attempt_retries': sum(stage['runtime_totals']['failed_spawns'] for stage in seals['stages']),
        'fixture_restored': True, 'main_map_sha256': map_hash,
        'report': '../FourSeals_v01/RuntimeIntegration.json',
        'scope': 'Scripted isolated integration, real resolver contacts; not a manual continuous playthrough.'
    },
    'combat05': {
        'state': abilities['state'], 'checks': abilities['checks'],
        'inputs_saved': True, 'report': '../CombatSkills_v01/AbilityGameplayProbe.json',
        'scope': 'Real sword AI interrupted by actual abilities. Burst energy was an explicit fixture grant.'
    },
    'obj01': {
        'state': 'standalone_lab_passed', 'map': lab['map'],
        'checks': ritual['checks'], 'report': '../RitualObjective_v01/RuntimeProbe.json',
        'default_seconds': 240, 'accelerated_lab_seconds': 30,
        'scope': 'Independent prototype, stationary interference targets and real hostile projectiles. Not ENEMY-03 or completed Level 02.'
    },
    'build': {'result': 'Succeeded', 'exit_code': 0, 'log': 'Build_02.log'},
    'automation': {key: automation[key] for key in ('succeeded', 'succeededWithWarnings', 'failed', 'notRun', 'inProcess')},
    'next_gdd_sequence': [
        'LEVEL-01: one LingQi upgrade, continuous playthrough and combat pacing; physical controller acceptance for COMBAT-05.',
        'OBJ-01: main-level entrance snapshots, restore preflight, retry and objective-stage progression.',
        'ENEMY-03 then LEVEL-02: channel/interrupt/leave/death source lifecycle and four-stage defense encounter.',
        'Boss phases, flying sword/shield/weakspot loop and LEVEL-03.',
        'PROG-01 full two-step growth and long-run VR performance/comfort acceptance.'
    ],
    'pending_limits': [
        'Main checkpoint preflight still rejects objective snapshots with CheckpointObjectiveUnsupported.',
        'Boss remains a 240-HP captain template.',
        'Physical headset/controller, manual full-run and VR performance acceptance remain unverified.',
        'MOVE-01 node movement is pending design lock; current free movement remains the implemented input model.'
    ],
    'handoff': '交接说明.txt'
}
(OUT / 'FinalReport.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'state': report['state'], 'four_seals': report['four_seals'], 'obj01': report['obj01'], 'automation': report['automation']}, ensure_ascii=False, indent=2))
