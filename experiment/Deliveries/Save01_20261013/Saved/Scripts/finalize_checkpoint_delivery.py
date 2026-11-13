"""Save implementation/presentation evidence and project update snapshots; no gameplay."""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'Docs/AI'
saved = json.loads((DOCS / 'CheckpointLabSaved-2026-10-13.json').read_text(encoding='utf-8'))
runtime = json.loads((DOCS / 'CheckpointLabRuntimeScene-2026-10-13.json').read_text(encoding='utf-8'))
delivery_path = DOCS / 'Save01Delivery-2026-10-13.json'
report = {
    'date': '2026-10-13', 'task_id': 'SAVE-01',
    'status': 'Compiled_AssetsSaved_InitialPresentationReviewed_AwaitingUserPlay',
    'reference': 'Docs/AI/ReferencePack/UE5.8_AI开发方案.md section15 and SAVE-01 task sequence',
    'slice': 'Desktop two-wave section-entry checkpoints with persistence and retry rollback.',
    'map': saved['map'], 'wave_counts': saved['wave_counts'],
    'implemented': [
        'USaveGame snapshot v1 contains content/run/level/node/encounter/checkpoint IDs, ordered wave IDs, section index, initial seed and whole-plan random state.',
        'Snapshots contain desktop root/control rotation, living entry health/guard, progression fields, unique defeat ledger and prior-wave milestones.',
        'Initial Ready entrance is memory-only. G commits the same immutable entrance; entering the next wave captures and commits its new entrance.',
        'R and G after cancellation restore the saved entrance, rather than resaving partial-attempt resources or defeat events.',
        'Restore preflight checks schema, stable content/node/milestone IDs, current resource maxima and rebuilt deterministic plan before actor cleanup.',
        'Restore locks input/movement, cancels wave actors and AI, removes projectiles, resets Director/Guard/Blade/Resolver/transient combat feedback, restores resources/root/run ledger and reconstructs selected wave in Ready.',
        'Past waves count as completed/spawned/defeated without spawning their actors or replaying defeat reward events.',
        'Load uses matching valid primary then backup; failed or incompatible reads keep existing valid memory and display an error instead of silently overwriting saves.',
        'Synchronous disk commit writes flushed same-directory temporary files, retains a valid backup and uses Windows MoveFileExW REPLACE_EXISTING|WRITE_THROUGH for replacement.',
        '4MiB bounded payload, CRC32 envelope, exact USaveGame native type and bounded string/array parsing; v1 content/schema validation rejects unsupported data.',
        'Chinese HUD shows selected checkpoint and distinguishes saved, backup recovered, memory-only retry and failed write/restore.',
    ],
    'snapshot_contract': {
        'save_version': 1, 'content_revision': 'SwordWaves.SAVE01.1',
        'level_id': 'Level.CombatLab.Checkpoint', 'encounter_id': 'Encounter.SwordWaves',
        'node_id_format': 'Node.SwordWaves.Wave.%02d',
        'checkpoint_id_format': 'Checkpoint.SwordWaves.Wave.%02d',
        'wave_initial_seed': 20261012,
        'random_state_semantics': 'Final FRandomStream state of all preplanned waves. Rebuilding the full plan verifies the seed/state pair, then selects the saved section. Physics/navigation/user actions are not replayed.',
        'resources': 'Living health and guard observed at section entry; no forced entry heal.',
        'partial_attempts': 'Restore replaces progression and defeat ledger from entrance snapshot, discarding failed/cancelled section additions.',
        'disk_write_triggers': 'Human G starts a section; automatic next-wave entry during normal gameplay. No initial idle disk write and no R disk write.',
        'arbitrary_midcombat_save': False,
    },
    'disk_files': {
        'primary': 'Saved/SaveGames/NilinCheckpoint/Checkpoint.current.nlcp',
        'backup': 'Saved/SaveGames/NilinCheckpoint/Checkpoint.backup.nlcp',
        'temps': ['Checkpoint.current.tmp', 'Checkpoint.backup.tmp'],
        'write_failure': 'Last valid disk copy remains; current in-memory section can still retry, with warning that exit/restart persistence is not guaranteed.',
        'scope': 'One fixed slot for this matching lab content; full multi-level transitions and content migrations remain future integration.',
    },
    'preserved': {
        'old_wave_scene': saved['source_map_preserved'],
        'old_duel_scene': '/Game/ReversedScale/Maps/L_CombatLabSwordDuel',
        'old_scene_checkpoint_flag': 'Disabled by default; existing lab reset preserved.',
        'enemy_death': saved['preserved_death'], 'grip_weight': saved['preserved_grip_weight'],
        'melee_damage': runtime['melee_damage'], 'blade_qi_damage': 15,
        'art_assets_edited': False,
    },
    'evidence': {
        'compile': 'Passed, exit0. First attempt found C4458 local Mesh shadowing ACharacter::Mesh; renamed ReferenceMesh, second attempt completed 4 actions and linked new DLL.',
        'build_log': 'Docs/AI/BuildLog-Save01-2026-10-13.txt',
        'first_build_log': 'Docs/AI/BuildLog-Save01-FirstAttempt-2026-10-13.txt',
        'author_commandlet': 'Exit0, saved separate map; Docs/AI/CheckpointLabAuthor-2026-10-13.log',
        'asset_report': 'Docs/AI/CheckpointLabSaved-2026-10-13.json',
        'initial_runtime_report': 'Docs/AI/CheckpointLabRuntimeScene-2026-10-13.json',
        'initial_screenshot': 'Docs/AI/CheckpointLabFirstPerson.png',
        'capture_interface_fix': 'First screenshot attempt used SubsystemBlueprintLibrary, unavailable in the local Python wrapper. Replaced it with read-only ObjectIterator filtered by GameInstance owner and reopened the initial scene.',
        'initial_scene_observed': runtime,
        'initial_visual_review': 'Chinese selected-wave and checkpoint Ready prompts readable; player weapon and environment displayed.',
        'agent_gameplay_inputs_sent': False,
        'tests_added_or_run': False,
        'save_disk_write_exercised_by_agent': False,
        'initial_presentation_limit': 'Normal startup reads matching disk or builds/restores memory-only entrance. This initial presentation is not proof of persistent round-trip, retry cleanup or interruption recovery.',
    },
    'remaining_acceptance': [
        'Manually start/clear first wave and observe second-wave checkpoint message before its enemies spawn.',
        'R during second wave returns to that entrance, shows prior2/total5 defeats, removes old enemies/projectiles and starts only3 after G.',
        'G cancel/start and repeated R do not retain partial-wave ledger additions, attacks, collisions or reservations.',
        'After Saved message, exit and relaunch resumes the matching saved section and resources.',
        'Actual primary/backup file writes, corrupt-primary recovery and interrupted commit robustness require authorized manual/automated validation.',
    ],
    'limits': [
        'Progression storage and defeat dedup are foundations only: LingQi gain, Burst gameplay and upgrade effects belong to PROG-01 and are not implemented here.',
        'Objective schema exists but this lab rejects nonempty objective data; ritual/Boss actor state restoration is not implemented.',
        'Real VR root/pose/tracking restoration awaits the VR pawn and hardware. This batch operates only the desktop adapter.',
        'USaveGame snapshot version1 and local UE5.8 SAVG header are supported; migrations across changed content/version remain explicit future work.',
        'Local UE5.8 required; this is an independent scene within the project, not a packaged standalone EXE.',
    ],
    'demo': {'launcher': 'Run_Checkpoint_Demo.cmd', 'process_at_open': 48372,
             'controls': 'G start/cancel; R return to checkpoint then G start; P/Esc pause; WASD/mouse; LMB slash10; RMB guard; E bladeqi15.',
             'before_source_backup': 'Deliveries/BeforeSave01_20261013/Manifest.json',
             'snapshot': 'Deliveries/Save01_20261013/Manifest.json'},
    'automation': 'Existing automation remains PAUSED; direct user continuation only.',
    'next_action': 'User play this checkpoint slice; next content dependency is ENEMY-02 ranged/elite combinations before LEVEL-01.',
}
delivery_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

state_path = DOCS / 'State.md'
state = state_path.read_text(encoding='utf-8')
state = state.replace('Updated: 2026-10-12 Asia/Shanghai', 'Updated: 2026-10-13 Asia/Shanghai')
state = state.replace('Milestone: Desktop Combat Lab / COMBAT-04 + ENEMY-01 + DIR-01 + WAVE-01 implementation',
                      'Milestone: Desktop Combat Lab / COMBAT-04 + ENEMY-01 + DIR-01 + WAVE-01 + SAVE-01 implementation')
state = state.replace('CurrentTask: WAVE-01 two finite seeded sword-disciple waves implemented; demo open for user play',
                      'CurrentTask: SAVE-01 desktop section-entry checkpoint persistence and retry implemented; demo open for user play')
state = state.replace('OpenMap: /Game/ReversedScale/Maps/L_CombatLabWaves',
                      'OpenMap: /Game/ReversedScale/Maps/L_CombatLabCheckpoint')
state = state.replace('  CurrentAuthorization: User requested continuing work and completing the next module; WAVE-01 delivered in this batch.',
                      '  CurrentAuthorization: User requested continuing work; SAVE-01 is the next authorized batch, with no automated tests.')
state = state.replace('  - Wave implementation saved; gameplay acceptance pending. Checkpoint snapshot restoration, skills, boss and packaged standalone EXE remain pending.',
                      '  - Wave and desktop checkpoint implementation saved; gameplay/persistence acceptance pending. Skills, ritual/Boss state restore and packaged standalone EXE remain pending.')
state = state.replace('  - R remains a lab reset, not SAVE-01 checkpoint restoration.',
                      '  - Old maps retain lab reset; dedicated checkpoint map R restores section entrance. Real VR checkpoint restore remains pending.')
state = state.replace('NextAction: User play WAVE-01 two-wave demo; next module is SAVE-01 checkpoint snapshot and restoration.',
                      'NextAction: User play SAVE-01 checkpoint demo; next content dependency is ENEMY-02 before LEVEL-01.')
state = state.replace('  Next: SAVE-01 after manual feedback; R is still a lab retry, not checkpoint restoration.',
                      '  Next: SAVE-01 now saved in a separate map; original Wave map retains its lab retry.')
state += '''

SAVE01_Current:
  Authorization: User continued development on 2026-10-13.
  Map: /Game/ReversedScale/Maps/L_CombatLabCheckpoint
  StableIds: Level.CombatLab.Checkpoint / Encounter.SwordWaves / SwordWaves.SAVE01.1
  Snapshot: USaveGame v1; run/level/node/encounter/checkpoint IDs; ordered waves; index; seed/state; desktop root/controlrot; living entry health/guard; progression ledger; completed priorwave milestones.
  EntryPolicy: Ready memory only; G saves immutable entry; wave2 saves new entry; no arbitrary midcombat save.
  Retry: R returns latest entry then G starts; G cancel/restart also rolls back partial attempt; prior waves counted without reward replay.
  RestoreOrder: Input/movement lock; cancel AI/owned wave; recycle projectiles; reset Director/Guard/Blade/Resolver; restore resources/root/run; rebuild selected wave; clear input/cooldowns; Ready; unlock.
  Persistence: Flushed same-directory temporary files; Windows atomic replace; matching valid backup; bounded4MiB/CRC32; version/content/native-class checks.
  Paths: Saved/SaveGames/NilinCheckpoint/Checkpoint.current.nlcp; Checkpoint.backup.nlcp
  Failures: Disk failure warns and keeps in-memory retry; read/restore mismatch locks/pause with diagnosis; existing unknown/corrupt slots not silently replaced.
  FoundationLimits: No LingQi awards/upgrades/Burst mechanics yet; objective schema only; real VR root/tracking restore not implemented; one matching lab slot.
  Compile: Passed after fixing C4458 Mesh local-name conflict; BuildLog-Save01-2026-10-13.txt.
  Assets: Separate checkpoint map saved, commandlet exit0; old Wave/SwordDuel scenes preserved.
  InitialPresentation: Ready selected wave and checkpoint prompts visible; current runtime metadata/screenshot saved.
  ValidationScope: Source compile and initial scene only; no agent gameplay inputs, disk save exercise, repeated retry or tests.
  Acceptance: Persistent save/load roundtrip, secondwave retry, no residual actors/rewards and interrupted commits await user validation.
  Delivery: Docs/AI/Save01Delivery-2026-10-13.json
  BeforeSourceBackup: Deliveries/BeforeSave01_20261013/Manifest.json
  Snapshot: Deliveries/Save01_20261013/Manifest.json
  Demo: Run_Checkpoint_Demo.cmd; local UE58 required; ProcessAtOpen48372.
  Preserved: Grounded death, Combat mesh, grip1, face, feet, hilt, slash10/qi15.
  Automation: Existing automation remains PAUSED.
  Next: User feedback then ENEMY-02 distant/elite combinations; LEVEL-01 follows.
'''
state_path.write_text(state, encoding='utf-8')

before = ROOT / 'Deliveries/BeforeSave01_20261013'
before_rows = []
for source in sorted(before.rglob('*')):
    if source.is_file() and source.name != 'Manifest.json':
        before_rows.append({'relative_path': source.relative_to(before).as_posix(),
                            'bytes': source.stat().st_size,
                            'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
(before / 'Manifest.json').write_text(json.dumps({
    'date': '2026-10-13', 'scope': 'Full Source, Config and State.md copied before SAVE-01 edits; rebuild required after source restoration.',
    'files': before_rows}, ensure_ascii=False, indent=2), encoding='utf-8')

snapshot = ROOT / 'Deliveries/Save01_20261013'
snapshot.mkdir(parents=True, exist_ok=True)
relative_files = [p.relative_to(ROOT) for folder in ('Source', 'Config') for p in (ROOT / folder).rglob('*') if p.is_file()]
relative_files += [Path(p) for p in [
    'experiment.uproject', 'Build_CombatModule.ps1', 'Run_Checkpoint_Demo.ps1', 'Run_Checkpoint_Demo.cmd',
    'Saved/Scripts/create_checkpoint_lab.py', 'Saved/Scripts/capture_checkpoint_lab.py',
    'Saved/Scripts/finalize_checkpoint_delivery.py',
    'Content/ReversedScale/Maps/L_CombatLabCheckpoint.umap',
    'Content/ReversedScale/Encounters/DA_WaveSword01.uasset', 'Content/ReversedScale/Encounters/DA_WaveSword02.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/BP_EnemySwordDisciple.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Grounded.uasset',
    'Docs/AI/State.md', 'Docs/AI/Save01Delivery-2026-10-13.json',
    'Docs/AI/CheckpointLabSaved-2026-10-13.json', 'Docs/AI/CheckpointLabRuntimeScene-2026-10-13.json',
    'Docs/AI/CheckpointLabFirstPerson.png', 'Docs/AI/CheckpointLabAuthor-2026-10-13.log',
    'Docs/AI/BuildLog-Save01-2026-10-13.txt', 'Docs/AI/BuildLog-Save01-FirstAttempt-2026-10-13.txt',
    'Binaries/Win64/UnrealEditor-experiment.dll', 'Binaries/Win64/UnrealEditor.modules',
]]
rows = []
for relative in sorted(set(relative_files)):
    source = ROOT / relative
    if not source.is_file():
        raise FileNotFoundError(source)
    target = snapshot / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    rows.append({'relative_path': relative.as_posix(), 'bytes': source.stat().st_size,
                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
(snapshot / 'Manifest.json').write_text(json.dumps({
    'date': '2026-10-13', 'created_local': datetime.now().isoformat(timespec='seconds'),
    'task_id': 'SAVE-01', 'snapshot_type': 'Project update, current source/config/map/binary/evidence. Existing referenced project art and local UE5.8 required; not a standalone packaged game.',
    'checkpoint_save_files_included': False, 'files': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'snapshot_files': len(rows), 'before_source_files': len(before_rows),
                  'snapshot_bytes': sum(row['bytes'] for row in rows)}, ensure_ascii=False))
