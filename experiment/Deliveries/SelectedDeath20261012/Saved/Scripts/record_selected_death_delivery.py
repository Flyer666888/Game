"""Record the completed animation batch and copy changed files for recovery."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DOCS = PROJECT / 'Docs/AI'
OUT = PROJECT / 'ArtSource/WuxiaMale/DeathSelection20261012'
saved = json.loads((DOCS / 'SelectedDeathSaved-2026-10-12.json').read_text(encoding='utf-8'))
contacts = json.loads((OUT / 'OptimizedDeathContacts.json').read_text(encoding='utf-8'))
selection = json.loads((OUT / 'SelectionDecision.json').read_text(encoding='utf-8'))
baseline = json.loads((PROJECT / 'ArtSource/WuxiaMale/NaturalDeath/NaturalDeathBakeSummary.json').read_text(encoding='utf-8'))
scene = json.loads((DOCS / 'SwordDuelRuntimeScene-2026-10-12.json').read_text(encoding='utf-8'))
preview_file = DOCS / 'SelectedDeathAuthorPreviewRuntime.json'
preview = json.loads(preview_file.read_text(encoding='utf-8')) if preview_file.exists() else None
report = {
    'date': '2026-10-12', 'request': 'Choose the most natural supplied death animation, optimize and implant',
    'selected_source': selection['selected_source'], 'candidates_compared': len(selection['candidates']),
    'selection_reason': selection['selection_reason'], 'saved': saved,
    'status': 'Animation saved and UE authoring presentation reviewed; actual fatal hit/transition awaits user play',
    'refinements': ['One runtime entry blend; baked idle entry removed',
                    'Continuous root support trajectory instead of abrupt full-body support jumps',
                    'Post-impact attempt to raise the head/brace again replaced by continuous relaxation',
                    'Actual mesh contact correction for limbs/head and still-held sword',
                    'Exact static tail and non-looping playback'],
    'root_support_max_frame_step_cm': {'before': baseline['max_root_floor_offset_frame_step_cm'],
                                       'after': contacts['after_root_max_frame_step_cm']},
    'final_contact_cm': contacts['final_contact'],
    'whole_animation_lowest_skin_cm': contacts['lowest_body_skin_cm'],
    'held_sword_maximum_penetration_cm': contacts['maximum_sword_penetration_cm'],
    'source_build': {'result': 'Succeeded', 'exit_code': 0, 'target': 'experimentEditor Win64 Development',
                     'scope': 'Existing C++ target up to date; this batch changes animation assets and references.',
                     'log': 'Docs/AI/BuildLog-SelectedDeath-2026-10-12.txt'},
    'asset_save': {'exit_code': 0, 'errors': 0, 'warnings': 2,
                   'scope': 'Duplicate import-data dependency warning and headless CrowdManager navigation warning.',
                   'log': 'Docs/AI/SelectedDeathImport-2026-10-12.log'},
    'ue_animation_authoring_presentation': preview, 'initial_combat_scene': scene,
    'process_id_at_delivery': int(sys.argv[1]) if len(sys.argv) > 1 else None,
    'preserved': ['Original user source files and existing Combat mesh Basis/weights/skeleton',
                  'Face and feet geometry/weights', 'Grip morph/attachment and original hilt',
                  'Melee damage 10', 'Existing safe death transition and combat code', 'Prior death animations and map/prefab backups'],
    'demo_entry': 'Run_SwordDuel_Demo.cmd', 'requires_local_ue58': True,
    'gameplay_inputs_sent': False, 'automated_tests': 'Not added or run',
    'manual_acceptance': 'Pending user play, including fatal hit from walk/attack/hit reaction and R reset.',
    'recovery_snapshot': 'Deliveries/SelectedDeath20261012/Manifest.json',
    'automation': 'Previous three-hour heartbeat remains paused; this task was directly authorized by user.'
}
(DOCS / 'SelectedDeathDelivery-2026-10-12.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
state_file = DOCS / 'State.md'
state = state_file.read_text(encoding='utf-8')
state = state.replace('CurrentTask: Select and refine the most natural supplied death animation, then implant into Enemy',
                      'CurrentTask: Selected DeathPL refined for grounded relaxation and implanted; updated demo ready for user play')
state = state.replace('TaskStatus: SourceCompiled_AnimationAuthoringInProgress',
                      'TaskStatus: Compiled_AssetsSaved_AuthoringPresented_AwaitingUserPlay')
state = state.replace('SelectedDeathRefinement_InProgress:', 'SelectedDeathRefinement_Delivered:')
state = state.replace('NaturalGripRefinement_Current:', 'PreviousNaturalGripRefinement:')
state = state.replace('  NewAssetPlanned: /Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Grounded',
                      '  NewAssetSaved: /Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Grounded')
if 'SelectedDeath_Current:' not in state:
    state += '\nSelectedDeath_Current:\n  Asset: /Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Grounded\n  Source: Anim_DeathPL; nine candidates compared on final Combat mesh.\n  Changes: Single entry; continuous support; remove post-impact rise; relaxed physical mesh contacts; static tail.\n  Maps: SwordDuel, Reflection, Guard and Melee updated; reusable enemy prefab updated; previous references backed up.\n  Evidence: Docs/AI/SelectedDeathDelivery-2026-10-12.json\n  AuthorPreview: /Game/ReversedScale/Maps/L_DeathAuthorPreview; pure skeletal animation with held sword.\n  Acceptance: User fatal-hit/transition/reset play pending; no gameplay inputs or tests run.\n'
state_file.write_text(state, encoding='utf-8')

snapshot = PROJECT / 'Deliveries/SelectedDeath20261012'
selected = [
    'Content/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Grounded.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/BP_EnemySwordDisciple.uasset',
    'Content/ReversedScale/Maps/L_DeathAuthorPreview.umap',
    'Docs/AI/SelectedDeathSaved-2026-10-12.json', 'Docs/AI/SelectedDeathDelivery-2026-10-12.json',
    'Docs/AI/SelectedDeathAuthorPreviewSaved.json', 'Docs/AI/SelectedDeathAuthorPreviewRuntime.json',
    'Docs/AI/BuildLog-SelectedDeath-2026-10-12.txt', 'Docs/AI/State.md',
    'ArtSource/WuxiaMale/DeathSelection20261012/SelectionDecision.json',
    'ArtSource/WuxiaMale/DeathSelection20261012/OptimizedDeathPoses.json',
    'ArtSource/WuxiaMale/DeathSelection20261012/OptimizedDeathContacts.json',
    'Saved/Scripts/bake_selected_death.py', 'Saved/Scripts/render_selected_death.py',
    'Saved/Scripts/assemble_selected_death_preview.py', 'Saved/Scripts/import_selected_death.py',
    'Saved/Scripts/create_selected_death_preview.py', 'Saved/Scripts/capture_selected_death_author.py',
    'Saved/Scripts/record_selected_death_delivery.py', 'Run_SwordDuel_Demo.cmd', 'Run_SwordDuel_Demo.ps1'
]
selected += ['Content/ReversedScale/Maps/L_CombatLab' + suffix + '.umap' for suffix in ('SwordDuel', 'Reflection', 'Guard', 'Melee')]
selected += [str(path.relative_to(PROJECT)).replace('\\', '/') for path in OUT.glob('*.gif')]
rows = []
for relative in selected:
    source = PROJECT / relative
    if not source.is_file():
        continue
    destination = snapshot / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    rows.append({'relative_path': relative, 'bytes': source.stat().st_size,
                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
(snapshot / 'Manifest.json').write_text(json.dumps({'date': '2026-10-12', 'files': rows,
    'scope': 'Recoverable changed-file snapshot; retains original unchanged project dependencies.',
    'demo_entry': 'Run_SwordDuel_Demo.cmd in the original experiment project', 'requires_local_ue58': True}, indent=2), encoding='utf-8')
print('SELECTED_DEATH_DELIVERY_SAVED', len(rows))
