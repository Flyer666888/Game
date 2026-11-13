"""Seal the ordered GDD delivery only after the final-map evidence passes."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

P = Path(__file__).resolve().parents[3]
O = P / 'Docs/Gameplay/GDDOrdered1105'

def read(name):
    return json.loads((O / name).read_text(encoding='utf-8-sig'))

def write(name, value):
    (O / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()

window = read('Window.json')
start = datetime.fromisoformat(window['start_utc'].replace('Z', '+00:00'))
deadline = datetime.fromisoformat(window['deadline_utc'].replace('Z', '+00:00'))
now = datetime.now(timezone.utc)
assert start <= now <= deadline, 'Delivery must finish within the authorized two-hour window'
editor_status = read('Status.json')
assert editor_status['state'] == 'closed', 'Close the owned verification editor before final handoff'
mapfile = P / 'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
map_sha = sha(mapfile)
runtime = {}
for name, expected_count in [('QueueRuntime', 9), ('WeakPointRuntime', 4),
                             ('LootRuntime', 9), ('FullRulesRuntime', 12)]:
    report = read(name + '.json')
    assert report['state'] == 'passed' and report['success'] and not report['failures'], name
    assert len(report['checks']) == expected_count and all(report['checks'].values()), name
    isolation = report['fixture_isolation']
    assert isolation['state'] == 'restored_without_saving_map', name
    # The shared cleanup asserts its in-memory starting hash, and exports the final hash.
    assert isolation['map_sha256_after'] == map_sha, name
    if 'map_sha256_before' in isolation:
        assert isolation['map_sha256_before'] == map_sha, name
    for key in ['removed_only_exact_test_paths', 'ordinary_ledger_cleanup']:
        assert all(not Path(path).exists() for path in isolation.get(key, [])), name
    runtime[name] = {'passed': len(report['checks']), 'failed': 0,
                     'report': name + '.json', 'map_sha256': map_sha,
                     'fixture_isolation': isolation['state']}

native = read('Phase3Automation/index.json')
assert native['failed'] == native['notRun'] == native['inProcess'] == 0
assert native['succeeded'] + native['succeededWithWarnings'] == 107
art = read('ArtApplied.json')
qa = read('ArtVisualQA.json')
postflight = read('ArtPostflight.json')
assert art['state'] == qa['state'] == postflight['state'] == 'passed'
assert art['map_sha256_after'] == qa['map_sha256'] == map_sha
assert qa['all_screenshots_after_final_save']
assert len(postflight['checks']) == 8 and all(postflight['checks'].values())
receipt = read('ChangeReceipt.json')
assert receipt['state'] == 'passed'
assert all(item['matches'] for item in receipt['protected_prior_rig_animation_sword_and_talisman'])
binary = P / 'Binaries/Win64/UnrealEditor-experiment.dll'
source_rows = receipt['modified_existing_sources'] + receipt['new_sources']
assert all(sha(P / row['path']) == row.get('after_sha256', row.get('sha256')) for row in source_rows)
assert all((P / row['path']).stat().st_mtime <= binary.stat().st_mtime for row in source_rows)
assert (O / 'Phase3Automation/index.json').stat().st_mtime >= binary.stat().st_mtime
for file in ['Run_Gameplay_Demo.cmd', 'Run_Gameplay_VR.cmd']:
    assert (P / file).is_file()
comparison = read('SceneComparison.json')
assert comparison['state'] == 'composed'
assert sha(O / 'SceneComparison.png') == comparison['output_sha256']
gameplay_evidence = read('GameplayEvidence.json')
assert gameplay_evidence['state'] == 'composed'
assert sha(O / 'GameplayEvidence.png') == gameplay_evidence['output_sha256']

full = read('FullRulesRuntime.json')
delivery = {
    'state': 'passed',
    'scope': 'Original six supplemental GDD requirements: finish the remaining playable prototype items 3 through 6 in order.',
    'started_utc': start.isoformat(), 'completed_utc': now.isoformat(),
    'deadline_utc': deadline.isoformat(), 'elapsed_minutes': round((now - start).total_seconds() / 60, 2),
    'map': '/Game/ReversedScale/Maps/L_NilinGameplayV01', 'map_sha256': map_sha,
    'ordered_features': [
        {'number': 3, 'name': 'Visible staging and native reinforcement entry', 'state': 'passed'},
        {'number': 4, 'name': 'Head weak point damage and HUD/audio feedback', 'state': 'passed', 'multiplier': 1.5},
        {'number': 5, 'name': 'Ordinary healing drops with fifth-roll hard pity', 'state': 'passed',
         'base_probability': .2, 'small_health': 10, 'large_health': 20, 'small_weight': .8},
        {'number': 6, 'name': 'Foreground, midground, distant scene depth', 'state': 'passed',
         'material_count': len(art['materials']), 'material_overrides': len(art['material_overrides']),
         'decorative_instances': len(art['decorations']), 'instance_groups': art['instance_groups']}
    ],
    'native_regression': {'passed': 107, 'failed': 0, 'clean': native['succeeded'],
                          'passed_with_warnings': native['succeededWithWarnings'], 'report': 'Phase3Automation/index.json'},
    'saved_map_runtime': runtime,
    'complete_route_rules': {'stages': len(full['stage_summaries']),
                             'owned_defeats': full['final']['owned_defeats'],
                             'ordinary_rolls': full['final']['ordinary_rolls'],
                             'seals': full['final']['seals'],
                             'ritual_effective_seconds': full['final']['ritual_effective_seconds'],
                             'ritual_elapsed_game_seconds': full['final']['ritual_elapsed_game_seconds']},
    'environment_postflight': {'passed': 8, 'spawn_point_references': postflight['spawn_reference_count'],
                               'report': 'ArtPostflight.json'},
    'source_and_asset_integrity': {'changed_existing_sources': len(receipt['modified_existing_sources']),
                                  'new_sources': len(receipt['new_sources']),
                                  'protected_prior_files': len(receipt['protected_prior_rig_animation_sword_and_talisman']),
                                  'report': 'ChangeReceipt.json'},
    'tested_module': {'path': str(binary), 'sha256': sha(binary), 'sources_older_than_binary': True},
    'verification_editor': {'state': editor_status['state'], 'pid': int((O / 'Editor.pid').read_text())},
    'entry_points': {'desktop': str(P / 'Run_Gameplay_Demo.cmd'), 'headset': str(P / 'Run_Gameplay_VR.cmd')},
    'handoff': ['DesignAndVerification.txt', 'PlayGuide.txt', 'SceneComparison.png', 'GameplayEvidence.png'],
    'verification_limits': [
        'Rules probes use isolated Test.Level01 runs and explicit placement/damage fixtures; not a human continuous playthrough.',
        'The first full-route probe stopped at a stair entry outside the arena trigger. Its report is retained; only fixture placement was corrected for the final run.',
        'No physical PICO input, comfort or VR frame-rate acceptance was performed.'
    ],
    'remaining_full_gdd_work': [
        'Boss full flying-sword, reflected-formation, break, vulnerability-window and recovery cycle.',
        'The four masters complete unique move sets.',
        'Physical headset/controller, comfort and performance acceptance; further environment geometry polish.'
    ]
}
write('Delivery.json', delivery)
progress = read('Progress.json')
progress['environment'] = {'state': 'passed', 'material_count': len(art['materials']),
                           'decorative_instances': len(art['decorations']), 'postflight_checks': 8,
                           'map_sha256': map_sha}
progress['full_route'] = {'state': 'passed', 'stages': 16, 'checks': 12, 'runtime': 'FullRulesRuntime.json'}
progress['state'] = 'complete'
write('Progress.json', progress)
window.update({'state': 'complete', 'completed_utc': now.isoformat(), 'elapsed_minutes': delivery['elapsed_minutes']})
write('Window.json', window)
print(json.dumps({'state': 'passed', 'elapsed_minutes': delivery['elapsed_minutes'],
                  'native_tests': 107, 'full_route_checks': 12, 'map_sha256': map_sha}))
