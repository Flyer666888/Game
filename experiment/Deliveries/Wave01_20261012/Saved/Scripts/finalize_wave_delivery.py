"""Record the authored/compiled WAVE-01 delivery and copy its project update snapshot."""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'Docs/AI'
saved = json.loads((DOCS / 'WaveLabSaved-2026-10-12.json').read_text(encoding='utf-8'))
runtime = json.loads((DOCS / 'WaveLabRuntimeScene-2026-10-12.json').read_text(encoding='utf-8'))
build = DOCS / 'BuildLog-Wave01-2026-10-12.txt'
report_path = DOCS / 'Wave01Delivery-2026-10-12.json'
delivery = {
    'date': '2026-10-12', 'task_id': 'WAVE-01',
    'status': 'Compiled_AssetsSaved_InitialPresentationReviewed_AwaitingUserPlay',
    'request': 'Continue development and complete the next task.',
    'reference': 'Docs/AI/ReferencePack/UE5.8_AI开发方案.md, WAVE-01 / section 12.2',
    'map': saved['map'], 'wave_counts': saved['authored_planned_counts'],
    'total_planned': saved['authored_total_planned_count'],
    'configuration': {
        'seed': 20261012, 'max_alive': 3, 'spawn_interval_seconds': 0.8,
        'intermission_seconds': 3.0, 'max_spawns_or_attempts_per_tick': 1,
        'spawn_grace_seconds': 0.35, 'retries_after_initial_failure': 3,
        'retry_delay_seconds': 0.5, 'corpse_hold_seconds': 2.0,
        'maximum_total_plan': 1024, 'maximum_plan_per_wave': 512,
        'maximum_supported_alive': 12,
    },
    'implemented': [
        'Finite DataAsset spawn entries and five stable world capsule-origin spawn points.',
        'Independent seeded FRandomStream; sorted entry/point IDs; retries do not alter later composition.',
        'Ready, Spawning, WaitingClear, Intermission, Completed, Failed and Cancelled states.',
        'Wave clear waits for the complete spawn plan, no pending spawn, and no owned living enemies.',
        'Unique runtime identity/ordinal death accounting; navigation despawn gives failure, not defeat.',
        'Cancellation cleans only owned enemies and AI controllers; generations invalidate stale callbacks.',
        'Finite spawn retry budget; failures terminate instead of leaving an endless wave.',
        'Global and controller-only pause freeze clocks/animation/movement; animation deadlines and snapshot blend are shifted on local resume.',
        'Corpse retirement waits for pending/playing death presentation, including when hold is zero; retired handles are removed while cumulative counts remain.',
        'R cancels owned actors before projectile/Director/Guard/Vitals/Blade/Resolver reset, then restores the initial seed to Ready.',
        'Desktop HUD shows wave progress and five human-readable failure reasons; default initial wave eye height matches the existing swordsman.',
    ],
    'failure_reasons': ['InvalidWaveConfig', 'SpawnFailed', 'NavigationFailed', 'EnemyRemoved', 'PlayerDefeated'],
    'controls': {
        'G': 'Start/cancel; completed/failed encounters require R.',
        'R': 'Reset for retry, then G starts the same seeded plan.',
        'P or Esc': 'Pause/resume.', 'WASD': 'Move.', 'Mouse': 'Look.',
        'LMB': 'Slash, damage 10.', 'RMB': 'Hold mirror.', 'E': 'Blade qi, damage 15.',
        'Alt+F4': 'Exit.',
    },
    'preserved': {
        'duel_map': saved['source_map_preserved'],
        'enemy_prefab': saved['enemy_prefab']['blueprint'],
        'mesh': saved['enemy_prefab']['cdo_refs']['enemy_skeletal_mesh'],
        'death': saved['enemy_prefab']['cdo_refs']['death_animation'],
        'grip_morph': saved['enemy_prefab']['grip_morph_name'],
        'grip_weight': saved['enemy_prefab']['grip_morph_weight'],
        'weapon': saved['enemy_prefab']['sword_mesh'],
        'face_feet_hilt_assets_modified_this_batch': False,
        'melee_damage': runtime['player']['melee_damage'],
    },
    'evidence': {
        'editor_compile': 'Passed, exit 0, 11 actions, MSVC 14.44.35229; ' + str(build.relative_to(ROOT)),
        'asset_authoring': 'Passed commandlet exit 0; Docs/AI/WaveLabAuthor-2026-10-12.log',
        'asset_report': 'Docs/AI/WaveLabSaved-2026-10-12.json',
        'initial_runtime': 'Docs/AI/WaveLabRuntimeScene-2026-10-12.json',
        'initial_image': 'Docs/AI/WaveLabFirstPerson.png',
        'initial_image_review': 'Chinese glyphs and panels readable; held weapon and birth-area markers visible.',
        'observed_ready_state': runtime['controllers'][0],
        'observed_eye_height_cm': runtime['player']['camera_cm'][2],
        'agent_gameplay_inputs_sent': False,
        'tests_added_or_run': False,
        'initial_capture_limit': 'A live desktop scene can receive human input. The captured frame has mirror raised and guard about 70; it is presentation evidence, not an untouched baseline or gameplay acceptance.',
    },
    'awaiting_user_play': [
        'G starts 2 enemies; after both defeats, next 3 enemies appear following the 3-second intermission.',
        'All 5 defeated reaches Completed exactly once; navigation/spawn failure shows a retry reason.',
        'Pause during attack/hit/death resumes without skipping the retained death presentation.',
        'G cancellation and R retry leave no enemies/projectiles/attack reservations; seeded plan repeats.',
        'Enemy pathing, group combat, grip and fatal-hit transition remain subject to manual play feedback.',
    ],
    'demo': {
        'launcher': 'Run_Wave_Demo.cmd', 'powershell_launcher': 'Run_Wave_Demo.ps1',
        'process_id_at_open': 59420, 'engine_required': 'Local UE 5.8.2',
        'packaged_standalone_exe': False,
        'snapshot': 'Deliveries/Wave01_20261012/Manifest.json',
    },
    'next_dependency': 'SAVE-01 checkpoint snapshots and restoration after this batch user feedback.',
    'automation': 'Existing automation remains PAUSED; this is the directly requested next module.',
}
report_path.write_text(json.dumps(delivery, ensure_ascii=False, indent=2), encoding='utf-8')

plan_path = DOCS / 'WaveNextTask-2026-10-12.json'
plan = json.loads(plan_path.read_text(encoding='utf-8'))
plan['status'] = delivery['status']
plan['prefab']['death'] = '/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Grounded'
plan['prefab']['configuration_evidence'] = 'Docs/AI/SelectedDeathSaved-2026-10-12.json; current read-only CDO in WaveLabSaved-2026-10-12.json'
plan['delivery'] = str(report_path.relative_to(ROOT)).replace('\\', '/')
plan['acceptance'] = 'Editor compile and initial presentation completed; no tests or game inputs sent by the agent. Wave gameplay acceptance is pending user play.'
plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')

state_path = DOCS / 'State.md'
state = state_path.read_text(encoding='utf-8')
state = state.replace('Milestone: Desktop Combat Lab / COMBAT-04 + ENEMY-01 + DIR-01 implementation',
                      'Milestone: Desktop Combat Lab / COMBAT-04 + ENEMY-01 + DIR-01 + WAVE-01 implementation')
state = state.replace('CurrentTask: Selected DeathPL refined for grounded relaxation and implanted; updated demo ready for user play',
                      'CurrentTask: WAVE-01 two finite seeded sword-disciple waves implemented; demo open for user play')
state = state.replace('TaskStatus: Compiled_AssetsSaved_AuthoringPresented_AwaitingUserPlay',
                      'TaskStatus: Compiled_AssetsSaved_InitialPresentationReviewed_AwaitingUserPlay')
state = state.replace('OpenMap: /Game/ReversedScale/Maps/L_CombatLabSwordDuel',
                      'OpenMap: /Game/ReversedScale/Maps/L_CombatLabWaves')
state = state.replace('  CurrentAuthorization: User resumed development after pause; this batch completes the current enemy module.',
                      '  CurrentAuthorization: User requested continuing work and completing the next module; WAVE-01 delivered in this batch.')
state = state.replace('  - No waves, checkpoint snapshot restoration, skills, boss or packaged standalone EXE yet.',
                      '  - Wave implementation saved; gameplay acceptance pending. Checkpoint snapshot restoration, skills, boss and packaged standalone EXE remain pending.')
state = state.replace('NextAction: User play natural death/grip demo. WAVE-01 design and reusable sword Blueprint are saved; Wave controller remains next, followed by SAVE-01.',
                      'NextAction: User play WAVE-01 two-wave demo; next module is SAVE-01 checkpoint snapshot and restoration.')
state = state.replace('  Purpose: Reusable configured enemy for next WAVE-01 batch; controller not implemented.',
                      '  Purpose: Reusable configured enemy used by WAVE-01; current Grounded references are recorded in WaveLabSaved-2026-10-12.json.')
state += '''

WAVE01_Current:
  Authorization: Continue work and complete the next task.
  Map: /Game/ReversedScale/Maps/L_CombatLabWaves
  Counts: 2 then 3 sword disciples; total5; maxalive3.
  DataAssets: /Game/ReversedScale/Encounters/DA_WaveSword01; DA_WaveSword02
  Seed: 20261012; sorted authored IDs; composition stream independent of collision/navigation.
  Timing: Spawn interval0.8s; grace>=0.35s; intermission3s; retries3 with0.5s delay; corpse hold2s.
  Bounds: Total plan1024; perwave512; alive<=12; attempts per Tick1 in this map.
  Source: NLWaveTypes; NLWaveDefinition; NLEncounterController; desktop player/HUD integration.
  StateFlow: Ready/Spawning/WaitingClear/Intermission/Completed/Failed/Cancelled; terminal completion once.
  Cleanup: Owned actors+AI only; death identity/ordinal dedup; generations; expired corpse handles pruned; wait complete death presentation.
  Pause: Controller clock, enemy animation/death deadlines and snapshot blend timing freeze; global pause retained.
  Retry: Cancel before old world reset; restore initial seed and Ready; G starts after R.
  Preserved: Combat mesh, Grounded death, grip1, face, feet, original hilt; melee10; bladeqi15; old duel map.
  Controls: G start/cancel; R retry; P/Esc pause; WASD/mouse; LMB slash; RMB mirror; E bladeqi.
  Compile: Editor target Passed, exit0, 11 actions, MSVC14.44.35229.
  Assets: Author commandlet saved separate map and two DataAssets, exit0.
  InitialPresentation: Ready; one controller; plan5; spawned0; living0; eyeZ146.8158; Chinese HUD readable.
  InitialPresentationLimit: Live captured frame includes raised mirror and guard~70; agent sent no gameplay inputs.
  Acceptance: Spawn/navigation/death/pause/cancel/retry/seed replay behavior awaits user play; no tests added or run.
  Delivery: Docs/AI/Wave01Delivery-2026-10-12.json
  Snapshot: Deliveries/Wave01_20261012/Manifest.json
  Demo: Run_Wave_Demo.cmd; local UE58 required; no standalone packaged EXE.
  ProcessAtOpen: 59420
  Automation: Existing automation remains PAUSED.
  Next: SAVE-01 after manual feedback; R is still a lab retry, not checkpoint restoration.
'''
state_path.write_text(state, encoding='utf-8')

snapshot = ROOT / 'Deliveries/Wave01_20261012'
snapshot.mkdir(parents=True, exist_ok=True)
relative_files = [p.relative_to(ROOT) for p in (ROOT / 'Source').rglob('*') if p.is_file()]
relative_files += [p.relative_to(ROOT) for p in (ROOT / 'Config').rglob('*') if p.is_file()]
relative_files += [Path(p) for p in [
    'experiment.uproject', 'Build_CombatModule.ps1', 'Run_Wave_Demo.ps1', 'Run_Wave_Demo.cmd',
    'Saved/Scripts/create_wave_lab.py', 'Saved/Scripts/capture_wave_lab.py',
    'Saved/Scripts/finalize_wave_delivery.py',
    'Content/ReversedScale/Maps/L_CombatLabWaves.umap',
    'Content/ReversedScale/Encounters/DA_WaveSword01.uasset',
    'Content/ReversedScale/Encounters/DA_WaveSword02.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/BP_EnemySwordDisciple.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Grounded.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Combat.uasset',
    'Docs/AI/State.md', 'Docs/AI/State-before-Wave01-2026-10-12.txt',
    'Docs/AI/WaveNextTask-2026-10-12.json', 'Docs/AI/Wave01Delivery-2026-10-12.json',
    'Docs/AI/WaveLabSaved-2026-10-12.json', 'Docs/AI/WaveLabRuntimeScene-2026-10-12.json',
    'Docs/AI/WaveLabFirstPerson.png', 'Docs/AI/BuildLog-Wave01-2026-10-12.txt',
    'Docs/AI/WaveLabAuthor-2026-10-12.log',
    'Binaries/Win64/UnrealEditor-experiment.dll', 'Binaries/Win64/UnrealEditor.modules',
]]
rows = []
for relative in sorted(set(relative_files)):
    source = ROOT / relative
    if not source.is_file():
        raise FileNotFoundError(source)
    destination = snapshot / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    rows.append({'relative_path': relative.as_posix(), 'bytes': source.stat().st_size,
                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
manifest = {'date': '2026-10-12', 'task_id': 'WAVE-01',
            'created_local': datetime.now().isoformat(timespec='seconds'),
            'snapshot_type': 'Current project update, source/config/new assets/evidence; referenced existing project assets and local UE are required. Not a packaged standalone game.',
            'source_backup_scope': 'Full current Source and Config after implementation; historical State.md copied before its WAVE update. No pre-edit full source backup is claimed.',
            'files': rows}
(snapshot / 'Manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'report': str(report_path), 'manifest': str(snapshot / 'Manifest.json'),
                  'snapshot_files': len(rows), 'snapshot_bytes': sum(row['bytes'] for row in rows)},
                 ensure_ascii=False))
