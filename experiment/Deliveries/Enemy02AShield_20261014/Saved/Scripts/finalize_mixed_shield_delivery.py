"""Save the reviewed ENEMY-02A/shield batch. Plain Python; never runs UE or tests.

Run only after the root agent has reviewed both initial-presentation images:
    python finalize_mixed_shield_delivery.py --presentation-reviewed
The root writes Docs/AI/MixedDemoProcess-2026-10-14.json with the current PID first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


DATE = '2026-10-14'
PROJECT = Path(__file__).resolve().parents[2]
DOCS = PROJECT / 'Docs/AI'
ART = PROJECT / 'ArtSource/DragonShield'
DELIVERY = PROJECT / 'Deliveries/Enemy02AShield_20261014'
REPORT_NAME = f'Enemy02AShieldDelivery-{DATE}.json'
STATE_MARKER = '\nENEMY02A_Shield_Current_20261014:\n'


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise RuntimeError('Required delivery evidence is missing: ' + str(path))
    return path


def read_json(path: Path):
    return json.loads(require_file(path).read_text(encoding='utf-8-sig'))


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(PROJECT).as_posix()


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def find_editor_author() -> Path:
    for path in (ART / 'DragonShieldEditorAuthor.json', ART / 'EditorAuthor.json',
                 DOCS / 'DragonShieldEditorAuthor.json', DOCS / f'DragonShieldEditorAuthor-{DATE}.json'):
        if path.is_file():
            return path
    raise RuntimeError('The successful full-editor shield author report is missing.')


def make_manifest(folder: Path, kind: str, timestamp: str):
    if not folder.is_dir() or not folder.is_relative_to(PROJECT / 'Deliveries'):
        raise RuntimeError('Manifest target must be an existing project delivery directory.')
    entries = []
    for path in sorted(folder.rglob('*'), key=lambda item: item.as_posix().casefold()):
        if path.is_file() and path.name != 'Manifest.json':
            entries.append({'path': path.relative_to(folder).as_posix(),
                            'bytes': path.stat().st_size, 'sha256': sha256(path)})
    if not entries:
        raise RuntimeError('Delivery manifest must not be empty: ' + str(folder))
    manifest = {'kind': kind, 'generated_utc': timestamp, 'hash_algorithm': 'SHA256',
                'project': 'ReversedScale / 逆鳞', 'file_count': len(entries),
                'total_bytes': sum(item['bytes'] for item in entries), 'files': entries}
    write_json(folder / 'Manifest.json', manifest)
    return {'path': relative(folder / 'Manifest.json'), 'file_count': manifest['file_count'],
            'total_bytes': manifest['total_bytes']}


def copy_item(path: Path):
    if not path.exists() or not path.is_relative_to(PROJECT):
        raise RuntimeError('Snapshot source must exist inside the project: ' + str(path))
    destination = DELIVERY / path.relative_to(PROJECT)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir():
        shutil.copytree(path, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(path, destination)


def checkpoint_paths(saved):
    controller = saved['controller']
    ids = [controller['level_id'], controller['encounter_id'], controller['content_revision']]
    ids.extend(wave['wave_id'] for wave in saved['waves'])
    # These authored IDs are ASCII. C++ uses lower-case, length-prefixed UTF-8 IDs.
    key = ''.join(f'{len(value.lower())}:{value.lower()}' for value in ids)
    digest = hashlib.sha1(key.encode('utf-8')).hexdigest().upper()
    prefix = 'Saved/SaveGames/NilinCheckpoint/Checkpoint.' + digest
    return {'scope_key_ids': ids, 'key_encoding': 'lower-case length-prefixed stable IDs, UTF-8',
            'hash_algorithm': 'SHA1 namespace only, not a cryptographic integrity guarantee',
            'current': prefix + '.current.nlcp', 'backup': prefix + '.backup.nlcp',
            'legacy_current': 'Saved/SaveGames/NilinCheckpoint/Checkpoint.current.nlcp',
            'legacy_backup': 'Saved/SaveGames/NilinCheckpoint/Checkpoint.backup.nlcp',
            'legacy_slot_preserved': True,
            'new_node_example': 'Node.Encounter.MixedDisciples.Wave.01',
            'new_milestone_example': 'Milestone.Encounter.MixedDisciples.Wave.01'}


def updated_state(previous: str, report: dict) -> str:
    # Replace only the first current-state fields. SAVE01_Current and all older
    # evidence remain historical records, including their original limitations.
    value = previous.split(STATE_MARKER, 1)[0].rstrip() + '\n'
    fields = {
        'Updated': DATE + ' Asia/Shanghai',
        'Milestone': 'Desktop Combat Lab / COMBAT-04 + ENEMY-01 + DIR-01 + WAVE-01 + SAVE-01 + ENEMY-02A + Dragon Shield',
        'CurrentTask': 'ENEMY-02A mixed sword/talisman encounter and supplied Dragon Shield integrated; user play pending',
        'TaskStatus': 'Compiled_AssetsSaved_InitialPresentationReviewed_AwaitingUserPlay',
        'OpenMap': '/Game/ReversedScale/Maps/L_CombatLabMixed',
        'NextAction': 'User play mixed demo and review shield grip; ENEMY-02B Guard Captain is the next content batch before LEVEL-01.',
    }
    for name, text in fields.items():
        pattern = rf'(?m)^{re.escape(name)}:.*$'
        if re.search(pattern, value):
            value = re.sub(pattern, name + ': ' + text, value, count=1)
        else:
            value = name + ': ' + text + '\n' + value
    value = re.sub(r'(?m)^  CurrentAuthorization:.*$',
                   '  CurrentAuthorization: Direct user continuation and supplied shield-model integration; no automated tests.',
                   value, count=1)
    value = value.replace('Assets:\n', 'PreviousSwordDuelAssets:\n', 1)
    value = value.replace('DesktopDemo:\n', 'PreviousSwordDuelDesktopDemo:\n', 1)
    value = re.sub(r'(?ms)^LastBuild:\n.*?(?=^Validation:)',
                   'LastBuild:\n  Result: Succeeded\n  ExitCode: 0\n'
                   '  Target: experimentEditor Win64 Development\n'
                   '  Toolchain: MSVC 14.44.35229 / SDK 10.0.22621.0\n'
                   f'  Log: Docs/AI/BuildLog-Shield-Polish-{DATE}.txt\n'
                   f'  ShieldIntegrationLog: Docs/AI/BuildLog-Shield-{DATE}.txt\n'
                   '  PreviousBatchLog: Docs/AI/BuildLog-Enemy02A-2026-10-13.txt\n', value, count=1)
    value = value.replace('  AssetSave: Animation import and map commandlets completed successfully',
                          '  AssetSave: Mixed map commandlet exit0; shield full-editor import/LOD author success')
    value = value.replace('  InitialPresentation: Captured and visually reviewed; no gameplay inputs sent',
                          '  InitialPresentation: Captured and visually reviewed; agent sent no gameplay inputs; external user input may change guard normally')
    value = value.replace('  - General ranged/high-threat enemy behavior and final enemy balance are not yet implemented in this duel slice.',
                          '  - Talisman caster is implemented in the separate mixed scene; ENEMY-02B Guard Captain/high-threat content and final enemy balance remain pending.')
    value += STATE_MARKER
    value += f'''  Authorization: Continue development and integrate the user-provided Jade_Dragon_Shield_Refined.blend.
  Map: /Game/ReversedScale/Maps/L_CombatLabMixed
  Demo: Run_Mixed_Demo.cmd; local UE58 and base project assets required; not a packaged standalone EXE.
  ProcessIdAtDelivery: {report['demo']['process_id_at_delivery']}
  Scope: ENEMY-02A only; ENEMY-02B Guard Captain remains pending.
  Waves: 1 sword + 1 talisman, then 2 swords + 1 talisman; total5; maxalive3; auto-start false.
  Talisman: Health30; damage10; warning1.1s; active0.15s; recovery2s; projectile700cm/s; range450..1100cm; preferred700cm.
  Casting: New restrained left-hand gesture on existing 23-bone skeleton; planted idle root/legs; no sword damage notifies.
  Targeting: Aim locked at warning start; line of sight rechecked; no homing; hand_l muzzle; one shot per valid attack window.
  Director: Ranged slot and shared attack GUID; existing melee/ranged/high-threat limits retained; warning-start travel projection used.
  Cleanup: Owned/reflected projectiles cleared at wave boundary/cancel/retry/failure; local pause shifts projectile expiry clocks.
  Checkpoints: Level.CombatLab.Mixed / Encounter.MixedDisciples / MixedDisciples.ENEMY02A.1.
  Slots: Original checkpoint lab retains fixed slot; mixed scene uses SHA1-scoped filenames including ordered wave IDs.
  MixedPrimary: {report['checkpoint_extension']['current']}
  Ledger: Context-specific node/checkpoint/milestone IDs; no actual LingQi awards, upgrades or Burst effects.
  Shield: /Game/ReversedScale/Weapons/DragonShield/SM_DragonShield; normalized46cm; front+X/up+Z; eight material slots.
  ShieldSource: Original blend and preserved ArtSource/DragonShield/Source copy have matching SHA256; source never overwritten.
  ShieldMaterials: Seven procedural PBR approximations plus textured dragon face; UV0 color/UV1 normal; normal green channel flipped.
  ShieldLODs: Four generated LODs; visual has no collision sections or navigation data; exact triangle counts in import report.
  Grip: Mirrored existing right-hand mesh and grip animation; calibrated horizontal rear handle; left sleeve follows wrist/elbow; glove material unified across all left-hand slots.
  Guard: Existing rectangular BoxComponent and guard rules retained; circular visual has coarse rectangular coverage; collision renderer hidden after recursive visual updates without changing collision queries.
  Preserved: Combat mesh, Grounded death, face, feet, sword grip1/hilt, player slash10/qi15; old lab maps retained.
  Compile: Shield and ENEMY02A Editor builds succeeded; mixed author commandlet exit0; shield asset save/LOD author success true.
  ShieldEditorShutdown: Process exit3 after asset-save success; ModeManagerInteractiveToolsContext not-packaged fatal during shutdown; assets load in fresh game, shutdown fix remains unconfirmed.
  ShieldImportWarnings: Near-zero tangent/binormal FBX warnings retained; LOD0 degenerate removal changes184160 FBX triangles to167872; user visual acceptance pending.
  InitialScene: Ready, spawned0, observedHealth={report['initial_runtime_scene'].get('health')}, observedGuard={report['initial_runtime_scene'].get('guard')}; memory checkpoint exists; loaded shield and left hand recorded.
  GuardObservationAtArtCapture: active={report['shield']['visual_capture'].get('guard_active')}; collision={report['shield']['visual_capture'].get('real_guard_collision')}; external user input can affect normal guard state/resources.
  VisualScope: Actual held components shown by temporarily detaching GuardVisual presentation binding, then restoring it; no temporary actors, agent guard raise/input, collision-query edits, attacks, navigation or disk save exercise.
  Acceptance: Combat spawning/navigation, talisman warning/aim, block/reflection, death/reset, pause, checkpoint persistence and VR await user play.
  Tests: No tests added or run; screenshots do not establish gameplay acceptance.
  Automation: Existing automation remains PAUSED; no new recurring work created.
  Delivery: Docs/AI/{REPORT_NAME}
  Snapshot: Deliveries/Enemy02AShield_20261014/Manifest.json
  BeforeSource: Deliveries/BeforeEnemy02A_20261013/Manifest.json; Deliveries/BeforeShield_20261014/Manifest.json
  Next: User feedback, then ENEMY-02B Guard Captain; LEVEL-01 follows enemy content.
'''
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--presentation-reviewed', action='store_true',
                        help='Root agent confirms both initial-presentation images were visually reviewed.')
    parser.add_argument('--process-id', type=int, default=None,
                        help='Optional freshly verified demo PID, otherwise read the root-written process report.')
    args = parser.parse_args()
    if not args.presentation_reviewed:
        parser.error('Visual review must be complete before delivery. Pass --presentation-reviewed only after that review.')
    saved_path = DOCS / 'MixedLabSaved-2026-10-13.json'
    runtime_path = DOCS / f'MixedLabRuntimeScene-{DATE}.json'
    visual_path = DOCS / f'DragonShieldVisual-{DATE}.json'
    prepared_path = ART / 'DragonShieldPrepared.json'
    imported_path = ART / 'DragonShieldImported.json'
    editor_path = find_editor_author()
    saved, runtime, visual = read_json(saved_path), read_json(runtime_path), read_json(visual_path)
    prepared, imported, editor = read_json(prepared_path), read_json(imported_path), read_json(editor_path)
    review_path = DOCS / f'MixedShieldPresentationReview-{DATE}.json'
    review = read_json(review_path)
    if not {'MixedLabFirstPerson.png', 'DragonShieldFirstPerson.png'}.issubset(set(review.get('reviewed_images', []))):
        raise RuntimeError('The presentation review must identify both current screenshots.')
    if review.get('presentation_binding_restored') is not True:
        raise RuntimeError('The reviewed shield presentation must have restored its GuardVisual binding.')
    process_path = DOCS / f'MixedDemoProcess-{DATE}.json'
    process = read_json(process_path) if process_path.is_file() else {}
    pid = args.process_id if args.process_id is not None else process.get('pid')
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise RuntimeError('Root must supply a freshly verified positive demo PID; no process discovery is performed here.')
    if editor.get('success') is not True:
        raise RuntimeError('Shield full-editor authoring did not report success.')
    if saved.get('map') != '/Game/ReversedScale/Maps/L_CombatLabMixed':
        raise RuntimeError('Mixed author report names the wrong map.')
    if 'READY' not in runtime.get('controller_state', '').upper() or runtime.get('spawned_count') != 0:
        raise RuntimeError('Runtime evidence must describe the initial Ready presentation, not gameplay.')
    if runtime.get('melee_damage') != 10 or runtime.get('has_memory_checkpoint') is not True:
        raise RuntimeError('Runtime evidence must retain slash damage10 and its in-memory entry checkpoint.')
    for field in ('health', 'guard'):
        observed = runtime.get(field)
        if (isinstance(observed, bool) or not isinstance(observed, (int, float))
                or not math.isfinite(observed) or not 0 <= observed <= 100):
            raise RuntimeError('Observed runtime resources must be finite and within0..100: ' + field)
    if visual.get('ready') is not True or not isinstance(visual.get('guard_active'), bool):
        raise RuntimeError('Shield image must record Ready and the actual boolean guard state.')
    if visual.get('presentation_binding_temporarily_detached') is not True or visual.get('temporary_art_actor_count') != 0:
        raise RuntimeError('Shield image must use actual held components with temporary presentation binding detachment, not spawned copies.')
    if saved.get('authored_wave_counts') != [2, 3] or saved['attack_definition'].get('damage') != 10:
        raise RuntimeError('Mixed composition or talisman damage differs from this authorized batch.')
    original = require_file(Path(prepared['source']))
    preserved = require_file(ART / 'Source' / original.name)
    source_hash = sha256(original)
    if source_hash != prepared.get('source_sha256') or sha256(preserved) != source_hash:
        raise RuntimeError('Original shield/source copy hash no longer matches its inspected source.')
    build_paths = [DOCS / f'BuildLog-Shield-Polish-{DATE}.txt', DOCS / f'BuildLog-Shield-{DATE}.txt',
                   DOCS / 'BuildLog-Enemy02A-2026-10-13.txt']
    for path in build_paths:
        if 'Result: Succeeded' not in require_file(path).read_text(encoding='utf-8-sig', errors='replace'):
            raise RuntimeError('A required source build did not report success: ' + str(path))
    mixed_author = require_file(DOCS / f'MixedLabAuthor-{DATE}.log')
    author_log = mixed_author.read_text(encoding='utf-8-sig', errors='replace')
    if 'MIXED_LAB_SAVED' not in author_log or 'Success - 0 error(s)' not in author_log:
        raise RuntimeError('Mixed author commandlet success evidence is missing.')
    shield_editor_log = require_file(DOCS / f'DragonShieldEditorImport-{DATE}.log')
    editor_log = shield_editor_log.read_text(encoding='utf-8-sig', errors='replace')
    if 'DRAGON_SHIELD_EDITOR_AUTHOR_SUCCESS' not in editor_log:
        raise RuntimeError('Shield full-editor asset-save success log marker is missing.')
    first_preview_log = require_file(DOCS / f'MixedPreview-FirstAttempt-{DATE}.log')
    preview_log = require_file(DOCS / f'MixedPreview-{DATE}.log')
    if 'SHIELD_VISUAL_BINDING_RESTORED' not in preview_log.read_text(encoding='utf-8-sig', errors='replace'):
        raise RuntimeError('The current preview log must confirm presentation binding restoration.')
    images = [require_file(DOCS / 'MixedLabFirstPerson.png'), require_file(DOCS / 'DragonShieldFirstPerson.png')]
    required_assets = [
        'Content/ReversedScale/Maps/L_CombatLabMixed.umap',
        'Content/ReversedScale/Characters/WuxiaMale/BP_EnemyTalismanDisciple.uasset',
        'Content/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Cast_Talisman.uasset',
        'Content/ReversedScale/Encounters/DA_WaveMixed01.uasset',
        'Content/ReversedScale/Encounters/DA_WaveMixed02.uasset',
        'Content/ReversedScale/Combat/DA_EnemyTalisman.uasset',
        'Content/ReversedScale/Combat/Materials/M_TalismanPaper.uasset',
        'Content/ReversedScale/Combat/Materials/M_TalismanCast.uasset',
        'Content/ReversedScale/Weapons/DragonShield/SM_DragonShield.uasset',
    ]
    for path in required_assets:
        require_file(PROJECT / path)
    required_scripts = ('author_talisman_cast.py', 'create_mixed_lab.py', 'capture_mixed_lab.py',
                        'import_dragon_shield.py', 'import_dragon_shield_editor.py',
                        'capture_shield_visual.py', 'finalize_mixed_shield_delivery.py')
    for name in required_scripts:
        require_file(PROJECT / 'Saved/Scripts' / name)
    for name in ('Run_Mixed_Demo.cmd', 'Run_Mixed_Demo.ps1', 'Build_CombatModule.ps1'):
        require_file(PROJECT / name)
    require_file(PROJECT / 'Binaries/Win64/UnrealEditor-experiment.dll')
    require_file(PROJECT / 'Binaries/Win64/UnrealEditor.modules')
    for name in ('BeforeEnemy02A_20261013', 'BeforeShield_20261014'):
        if not (PROJECT / 'Deliveries' / name).is_dir():
            raise RuntimeError('Required before-edit backup is missing: ' + name)
    timestamp = datetime.now(timezone.utc).isoformat()
    evidence_paths = [saved_path, runtime_path, visual_path, prepared_path, imported_path, editor_path,
                      review_path, mixed_author, shield_editor_log, preview_log, first_preview_log, *build_paths, *images]
    report = {
        'date': DATE, 'generated_utc': timestamp, 'project': 'ReversedScale / 逆鳞',
        'task': 'ENEMY-02A + user-provided Dragon Shield integration',
        'status': 'Compiled_AssetsSaved_InitialPresentationReviewed_AwaitingUserPlay',
        'scope': 'ENEMY-02A only; ENEMY-02B Guard Captain is not implemented in this batch.',
        'demo': {'launcher': 'Run_Mixed_Demo.cmd', 'map': saved['map'],
                 'process_id_at_delivery': pid, 'process_evidence': relative(process_path) if process_path.is_file() else 'root-supplied CLI PID',
                 'controls': 'WASD/mouse; G start/cancel; R latest entry then G; P/Esc pause; LMB slash10; RMB guard; E bladeqi15',
                 'packaged_standalone_exe': False,
                 'requirements': 'Installed local UE5.8, current project, and referenced original/base project assets.'},
        'mixed_encounter': saved, 'initial_runtime_scene': runtime,
        'live_scene_observation_note': 'The agent sent no gameplay input. External/user input may raise guard or spend guard normally; these observed resources are not an immutable startup preset.',
        'talisman_implementation': {
            'role': 'TalismanCaster', 'warning_seconds': 1.1, 'active_seconds': .15,
            'recover_seconds': 2, 'projectile_speed_cm_per_second': 700,
            'range_cm': [450, 1100], 'preferred_range_cm': 700, 'damage': 10,
            'aim': 'Locked at warning start; repeated LOS validation; hand_l muzzle; no homing.',
            'cast': 'Authored restrained left-arm gesture on existing 23-bone skeleton; planted root/legs, no damage notifies.',
            'director': 'Shared attack GUID, ranged reservation, immutable warning aim and projected travel time.',
            'lifecycle': 'One release per valid attack window; owned/reflected shots cleaned at wave boundary/cancel/retry/failure; local projectile pause adjusts expiry.'},
        'checkpoint_extension': checkpoint_paths(saved),
        'progression_limit': 'Context-specific defeat/node/checkpoint/milestone identities; no actual currency awards, upgrades or Burst mechanics.',
        'shield': {
            'source': str(original), 'preserved_source': relative(preserved),
            'source_sha256': source_hash, 'source_and_copy_hash_match': True, 'original_blend_preserved': True,
            'mesh': imported['mesh'], 'nominal_diameter_cm': prepared['nominal_diameter_cm'],
            'direction': prepared['direction'], 'export_grip_center_cm': prepared['grip_center_cm'],
            'lod_count': imported.get('lod_count'), 'lod_triangle_counts': imported.get('lod_triangle_counts'),
            'fbx_source_triangle_count': prepared.get('triangles'),
            'lod0_triangle_note': 'UE degenerate removal reduced source184160 triangles to167872 at imported LOD0.',
            'material_slots': imported.get('material_slots'), 'textures': imported.get('textures'),
            'material_approximations': 'Seven procedural source materials use constant linear PBR approximations; textured dragon face retained.',
            'texture_uvs': 'Base color UV0; normal UV1; OpenGL normal green flipped to DirectX convention.',
            'hand': {'mesh': runtime.get('left_hand_mesh'), 'existing_right_hand_mirrored_y': True,
                     'animation': '/Game/ReversedScale/Player/Animations/A_Yueyao_Grip_Right',
                     'grip_relative_transform': visual.get('hand_relative_transform'),
                     'calibration': 'Grip center/axis derived from existing hand_r pose and original held-weapon local grip; horizontal rear handle.',
                     'sleeve': 'Cylinder sleeve aligns to left wrist and authored elbow; follows guard pivot visibility.',
                     'left_glove_all_material_slots_unified': True},
            'guard': {'behavior_changed': False, 'collision_owner': 'Existing GuardCollision BoxComponent',
                      'unscaled_box_half_extent_cm': [3, 24, 28],
                      'collision_renderer_hidden_after_recursive_visual_update': True,
                      'collision_query_settings_changed': False,
                      'visual_only_mesh': True, 'coverage_limit': 'Existing rectangular collision coarsely covers the circular46cm visual; final acceptance remains manual.'},
            'editor_author': editor, 'visual_capture': visual},
        'preserved': ['Wuxia Combat mesh, refined face/feet', 'Wuxia_Death_Grounded and safe death transition',
                      'EnemyGrip_R=1 sword grip and original weapon hilt', 'player melee10 and bladeqi15',
                      'old SwordDuel/Waves/Checkpoint maps and legacy checkpoint slot'],
        'compilation': {'target': 'experimentEditor Win64 Development', 'result': 'Succeeded', 'exit_code': 0,
                        'toolchain': 'MSVC14.44.35229 / SDK10.0.22621.0', 'logs': [relative(path) for path in build_paths]},
        'asset_authoring': {'mixed_commandlet_result': 'Succeeded', 'mixed_commandlet_exit_code': 0,
                            'mixed_log': relative(mixed_author), 'shield_full_editor_success': True,
                            'shield_asset_save_result': 'Passed',
                            'shield_editor_report': relative(editor_path),
                            'shield_editor_log': relative(shield_editor_log),
                            'shield_editor_process_exit_code': 3,
                            'shield_editor_shutdown_error': {
                                'phase': 'Shutdown after successful asset save and LOD authoring',
                                'message': 'Object is not packaged: ModeManagerInteractiveToolsContext None',
                                'asset_availability_recovery': 'Assets load in a fresh game process for current initial-presentation review.',
                                'shutdown_error_resolution': 'Unconfirmed. Editor wrapper now defers startup/quit but was not reexecuted; exit3 remains actual authoring-process evidence.'},
                            'shield_import_warnings': 'Near-zero tangent/binormal FBX warnings remain after front-face UV corrections; final appearance awaits user acceptance.',
                            'no_zero_error_process_claim': True},
        'validation': {'initial_presentation': 'Reviewed by root before running this finalizer',
                       'presentation_review': review,
                       'presentation_review_evidence': relative(review_path),
                       'current_preview_log': relative(preview_log),
                       'shield_preview': 'Actual held components displayed by temporarily detaching/restoring GuardVisual presentation binding. No temporary actors, agent guard raise/input, collision-query edits or attacks. Actual guard may remain active through external user input.',
                       'observed_guard_active_at_art_capture': visual.get('guard_active'),
                       'observed_guard_collision_at_art_capture': visual.get('real_guard_collision'),
                       'observed_health_at_scene_capture': runtime.get('health'),
                       'observed_guard_at_scene_capture': runtime.get('guard'),
                       'first_preview_failure': 'PID34080 was gracefully closed after an unsupported Blueprint-internal GameplayStatics spawn API caused art screenshot callback errors. First-attempt log archived; no combat input or test was sent.',
                       'first_preview_failure_evidence': relative(first_preview_log),
                       'automated_tests': 'Not added or run',
                       'pending_user_play': ['spawn/navigation and enemy grounding', 'talisman warning/locked aim/readability',
                                             'block/perfect reflection and coarse circular visual coverage', 'death/hit/reset transitions',
                                             'pause/cancel/retry cleanup', 'scoped persistent save/load and second-wave retry',
                                             'actual headset/controller VR acceptance'],
                       'evidence_limits': 'Idle screenshots do not establish combat, block/reflection, navigation, checkpoint write/read roundtrip or VR correctness.'},
        'automation': {'id': 'automation', 'status': 'PAUSED', 'changed_this_batch': False},
        'next_task': 'User feedback, then ENEMY-02B Guard Captain, followed by LEVEL-01.',
        'evidence': [{'path': relative(path), 'sha256': sha256(path)} for path in evidence_paths],
        'snapshot': {'manifest': relative(DELIVERY / 'Manifest.json'),
                     'kind': 'Incremental project source/assets/evidence snapshot; not a standalone game package.'},
    }
    # All required evidence is checked before changing state or creating manifests.
    before_info = []
    for name in ('BeforeEnemy02A_20261013', 'BeforeShield_20261014'):
        before_info.append(make_manifest(PROJECT / 'Deliveries' / name, 'Historical before-edit source backup', timestamp))
    report['before_source_backups'] = before_info
    state_path = require_file(DOCS / 'State.md')
    state_backup = DOCS / f'State-BeforeEnemy02AShield-{DATE}.md'
    if not state_backup.exists():
        shutil.copy2(state_path, state_backup)
    previous_state = state_path.read_text(encoding='utf-8-sig')
    state_path.write_text(updated_state(previous_state, report), encoding='utf-8')
    write_json(DOCS / REPORT_NAME, report)
    DELIVERY.mkdir(parents=True, exist_ok=True)
    sources = [PROJECT / 'Source', PROJECT / 'Config', PROJECT / 'experiment.uproject',
               PROJECT / 'Content/ReversedScale/Weapons/DragonShield', ART,
               PROJECT / 'ArtSource/WuxiaMale/TalismanCast',
               state_path, state_backup, DOCS / REPORT_NAME,
               *[PROJECT / name for name in required_assets[:-1]]]
    sources += [PROJECT / name for name in ('Run_Mixed_Demo.cmd', 'Run_Mixed_Demo.ps1', 'Build_CombatModule.ps1')]
    sources += [PROJECT / 'Saved/Scripts' / name for name in required_scripts]
    sources += evidence_paths
    if process_path.is_file():
        sources.append(process_path)
    sources += list((PROJECT / 'Binaries/Win64').glob('UnrealEditor-experiment.*'))
    sources += [PROJECT / 'Binaries/Win64/UnrealEditor.modules']
    if (PROJECT / 'Binaries/Win64/experimentEditor.target').is_file():
        sources.append(PROJECT / 'Binaries/Win64/experimentEditor.target')
    # Include batch logs, reports and images that are present, including failed
    # first attempts. Keeping them does not label failed attempts as successes.
    for pattern in ('*Enemy02A*2026-10-13*', '*Mixed*2026-10-13*', '*Mixed*2026-10-14*',
                    '*Shield*2026-10-14*', '*Talisman*2026-10-13*'):
        sources.extend(DOCS.glob(pattern))
    for source in dict.fromkeys(sources):
        copy_item(source)
    manifest_info = make_manifest(DELIVERY, 'ENEMY-02A + Dragon Shield incremental project delivery', timestamp)
    print(json.dumps({'delivery': relative(DOCS / REPORT_NAME), 'snapshot': manifest_info,
                      'before_source_backups': before_info, 'process_id_at_delivery': pid,
                      'tests': 'Not added or run'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
