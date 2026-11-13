"""Save the reviewed shield material batch. Plain Python; never launches UE or tests.

Root must first finish successful asset authoring, visually review both front/back
screenshots, and write the freshly verified demo PID evidence. Then run once:
    python finalize_shield_surface_delivery.py --presentation-reviewed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path


DATE = '2026-10-14'
PROJECT = Path(__file__).resolve().parents[2]
DOCS = PROJECT / 'Docs/AI'
ART = PROJECT / 'ArtSource/DragonShield'
SURFACE = ART / 'RealisticSurface'
BEFORE = PROJECT / 'Deliveries/BeforeShieldSurface_20261014'
DELIVERY = PROJECT / 'Deliveries/ShieldSurface_20261014'
BASELINE = PROJECT / 'Deliveries/Enemy02AShield_20261014/Manifest.json'
REPORT_NAME = f'ShieldSurfaceDelivery-{DATE}.json'
MARKER = '\nShieldSurface_Current_20261014:\n'
MATERIAL_PATH = 'Content/ReversedScale/Weapons/DragonShield/Materials'
TEXTURE_PATH = 'Content/ReversedScale/Weapons/DragonShield/Textures/RealisticSurface'
EXPECTED_PROFILES = {'bronze', 'worn_bronze', 'dark_bronze', 'jade', 'patina', 'leather', 'brass'}
EXPECTED_IMAGES = {'DragonShieldRealistic_Back.png', 'DragonShieldRealistic_Front.png'}


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise RuntimeError('Required delivery evidence is missing: ' + str(path))
    return path


def read_json(path: Path):
    return json.loads(require_file(path).read_text(encoding='utf-8-sig'))


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with require_file(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(PROJECT).as_posix()


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def png_dimensions(path: Path):
    # Header inspection only. Pixels are neither decoded nor modified.
    with require_file(path).open('rb') as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
        raise RuntimeError('Expected a saved PNG screenshot or surface tile: ' + str(path))
    return list(struct.unpack('>II', header[16:24]))


def asset_file(value: str) -> Path:
    package = value.split('.', 1)[0]
    if not package.startswith('/Game/ReversedScale/Weapons/DragonShield/'):
        raise RuntimeError('Author report contains a non-shield asset: ' + value)
    path = PROJECT / ('Content/' + package[len('/Game/'): ] + '.uasset')
    require_file(path)
    return path


def make_manifest(folder: Path, kind: str, timestamp: str):
    if not folder.is_dir() or not folder.resolve().is_relative_to((PROJECT / 'Deliveries').resolve()):
        raise RuntimeError('Manifest target must be an existing project delivery folder.')
    entries = []
    for path in sorted(folder.rglob('*'), key=lambda item: item.as_posix().casefold()):
        if path.is_file() and path.name != 'Manifest.json':
            entries.append({'path': path.relative_to(folder).as_posix(),
                            'bytes': path.stat().st_size, 'sha256': sha256(path)})
    if not entries:
        raise RuntimeError('A delivery manifest must not be empty.')
    manifest = {'kind': kind, 'generated_utc': timestamp, 'hash_algorithm': 'SHA256',
                'project': 'ReversedScale / 逆鳞', 'file_count': len(entries),
                'total_bytes': sum(item['bytes'] for item in entries), 'files': entries}
    write_json(folder / 'Manifest.json', manifest)
    return {'path': relative(folder / 'Manifest.json'), 'file_count': len(entries),
            'total_bytes': manifest['total_bytes']}


def copy_item(path: Path):
    if not path.exists() or not path.resolve().is_relative_to(PROJECT.resolve()):
        raise RuntimeError('Snapshot source must exist inside the project: ' + str(path))
    target = DELIVERY / path.relative_to(PROJECT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir():
        # Blender recovery copies and bytecode caches are not delivery source.
        shutil.copytree(path, target, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('*.blend1', '*.blend2', '__pycache__', '*.pyc'))
    else:
        shutil.copy2(path, target)


def validate_baseline():
    baseline = read_json(BASELINE)
    entries = {entry['path']: entry for entry in baseline['files']}
    required = [
        'Content/ReversedScale/Weapons/DragonShield/SM_DragonShield.uasset',
        'ArtSource/DragonShield/Source/Jade_Dragon_Shield_Refined.blend',
        'Content/ReversedScale/Weapons/DragonShield/Textures/T_DragonShield_07_BaseColor.uasset',
        'Content/ReversedScale/Weapons/DragonShield/Textures/T_DragonShield_07_Normal.uasset',
        'Content/ReversedScale/Maps/L_CombatLabMixed.umap',
        'Binaries/Win64/UnrealEditor-experiment.dll',
    ]
    paths = {key for key in entries if key.startswith(('Source/', 'Config/'))}
    paths.update(required)
    paths.update(key for key in entries if key.startswith((
        'Content/ReversedScale/Characters/', 'Content/ReversedScale/Combat/',
        'Content/ReversedScale/Encounters/')))
    records = []
    for key in sorted(paths):
        if key not in entries:
            raise RuntimeError('Required unchanged-content baseline entry is missing: ' + key)
        actual = sha256(PROJECT / key)
        if actual != entries[key]['sha256']:
            raise RuntimeError('This material-only delivery found changed baseline content: ' + key)
        records.append({'path': key, 'sha256': actual, 'matches_previous_delivery': True})
    return {'reference_manifest': relative(BASELINE), 'hash_algorithm': 'SHA256',
            'verified_files': records,
            'scope_limit': 'Only baseline files listed here have byte equality evidence; retained unrelated artwork is declared by authoring scope.'}


def update_state(previous: str, report: dict) -> str:
    # Preserve all prior enemy/checkpoint/shield integration history. Only this
    # batch marker is replaced on an authorized re-run.
    value = previous.split(MARKER, 1)[0].rstrip() + '\n'
    fields = {
        'Updated': DATE + ' Asia/Shanghai',
        'Milestone': 'Desktop Combat Lab / COMBAT-04 + ENEMY-01 + DIR-01 + WAVE-01 + SAVE-01 + ENEMY-02A + Dragon Shield PBR',
        'CurrentTask': 'Supplied Dragon Shield realistic surface materials saved and front/back appearance reviewed; user visual/combat review pending',
        'TaskStatus': 'ShieldMaterialsSaved_ShaderAuthoringPassed_InitialPresentationReviewed_AwaitingUserPlay',
        'OpenMap': '/Game/ReversedScale/Maps/L_CombatLabMixed',
        'NextAction': 'User review shield material appearance in mixed demo; ENEMY-02B Guard Captain remains the next content batch before LEVEL-01.',
    }
    for name, text in fields.items():
        pattern = rf'(?m)^{re.escape(name)}:.*$'
        if re.search(pattern, value):
            value = re.sub(pattern, name + ': ' + text, value, count=1)
        else:
            value = name + ': ' + text + '\n' + value
    value = re.sub(r'(?m)^  CurrentAuthorization:.*$',
                   '  CurrentAuthorization: User requested realistic shield surface polish; material authoring and initial visual review only; no automated tests.',
                   value, count=1)
    value += MARKER
    value += f'''  Authorization: User requested more realistic material texture on the supplied shield.
  Scope: Existing eight shield materials and21 new surface texture assets; no new mesh geometry, source-model edits, C++ or combat changes.
  Surface: Seven1024x1024 repeating PBR profiles from source bronze/jade/patina/leather/brass palettes; BaseColor + ORM + Normal.
  PackedMasks: ORM is linear R=local micro-cavity AO, G=roughness, B=metallic; not a full baked mesh-occlusion map.
  Projection: Object-local triplanar colour/ORM stays attached to the moving shield; fine normals use existing UV0.
  Normals: OpenGL tile +Y maps imported with green-channel flip; UE uses restrained strength recorded per material.
  DragonFront: Original BaseColor UV0 and original normal UV1 graphs retained; gold-versus-green oxide mask adds distinct metal/roughness response.
  Details: Forged-metal variation, restrained rim wear, darker recesses, oxide and leather grain; no new sculpted dragon relief.
  Preserved: Shield46cm/mesh/held transforms; player slash10 and blade qi15; combat/source/config hashes match previous delivery. Face, feet, sword hilt/grip and Grounded death retained.
  ShaderAuthoring: Eight material recompile error arrays empty; full-editor wrapper success true; all reported assets saved.
  CppCompile: Not required for this material-only batch; previous successful shield/combat build remains the current native binary.
  InitialPresentation: Root visually reviewed front and back screenshots; actual held mesh temporarily presented, original mirror transform/visual/HUD bindings restored.
  InputsAndTests: Agent sent no gameplay inputs; no tests added or run. Images establish material appearance only.
  Performance: Material texture-fetch graph counts recorded; GPU timing and real VR performance remain unmeasured.
  Demo: Run_Mixed_Demo.cmd; local UE58/base project required; no packaged standalone EXE.
  ProcessIdAtPreview: {report['demo']['process_id_at_preview']}
  RunningAtFinalCheck: {report['demo']['running_at_final_check']}
  Screenshots: Docs/AI/DragonShieldRealistic_Back.png; Docs/AI/DragonShieldRealistic_Front.png
  AuthorReport: Docs/AI/ShieldRealisticMaterials-{DATE}.json
  SurfaceSource: ArtSource/DragonShield/RealisticSurface/RealisticSurface.json
  Delivery: Docs/AI/{REPORT_NAME}
  Snapshot: Deliveries/ShieldSurface_20261014/Manifest.json
  BeforeMaterials: Deliveries/BeforeShieldSurface_20261014/Manifest.json
  Acceptance: User material review; combat block/reflection/navigation/checkpoint/death/pause and real VR still await user play.
  Automation: Existing automation remains PAUSED.
  Next: User feedback, then ENEMY-02B Guard Captain; LEVEL-01 follows enemy content.
'''
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--presentation-reviewed', action='store_true',
                        help='Root confirms both current front/back material screenshots were visually reviewed.')
    args = parser.parse_args()
    if not args.presentation_reviewed:
        parser.error('Root must complete front/back image review before passing --presentation-reviewed.')
    author_path = DOCS / f'ShieldRealisticMaterials-{DATE}.json'
    editor_path = DOCS / f'ShieldSurfaceEditorAuthor-{DATE}.json'
    capture_path = DOCS / f'ShieldSurfacePresentation-{DATE}.json'
    process_path = DOCS / f'ShieldSurfaceDemoProcess-{DATE}.json'
    manifest_path = SURFACE / 'RealisticSurface.json'
    author, editor, capture = read_json(author_path), read_json(editor_path), read_json(capture_path)
    process, surface, prepared = read_json(process_path), read_json(manifest_path), read_json(ART / 'DragonShieldPrepared.json')
    if editor.get('success') is not True:
        raise RuntimeError('Full-editor material authoring has not reported success.')
    if author.get('module') != 'ART-SHIELD-REALISTIC':
        raise RuntimeError('The material author report is not this shield surface batch.')
    textures, materials = author.get('textures', []), author.get('materials', [])
    if len(textures) != 21 or len(materials) != 8 or set(surface.get('profiles', {})) != EXPECTED_PROFILES:
        raise RuntimeError('This delivery requires seven profiles,21 texture tiles and eight existing materials.')
    if any(record.get('material_recompile_errors') != [] for record in materials):
        raise RuntimeError('Every material must report an explicitly empty compile-error list.')
    expected_materials = {'M_DragonShield_%02d' % index for index in range(8)}
    actual_materials = {record['asset'].split('.', 1)[0].rsplit('/', 1)[-1] for record in materials}
    if actual_materials != expected_materials:
        raise RuntimeError('Author report must include exactly the existing eight shield materials.')
    if capture.get('visual_and_hud_restored') is not True or capture.get('no_agent_gameplay_inputs') is not True or capture.get('tests_added_or_run') is not False:
        raise RuntimeError('Capture must confirm restored presentation, no agent gameplay input, and no tests.')
    views = capture.get('views', [])
    if len(views) != 2 or {Path(view['file']).name for view in views} != EXPECTED_IMAGES:
        raise RuntimeError('Capture must describe exactly the current front and back screenshots.')
    pid = process.get('pid')
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise RuntimeError('Root must record a freshly verified positive demo PID; this script does not inspect processes.')
    if prepared.get('nominal_diameter_cm') != 46.0:
        raise RuntimeError('Existing normalized shield diameter must remain46cm.')
    original = require_file(Path(prepared['source']))
    preserved = require_file(ART / 'Source' / original.name)
    original_hash = sha256(original)
    if any(value != original_hash for value in (sha256(preserved), prepared.get('source_sha256'), surface.get('source_sha256'), surface.get('source_sha256_after'))):
        raise RuntimeError('Source blend or its preserved copy no longer matches the original inspected hash.')
    for index in range(8):
        require_file(BEFORE / MATERIAL_PATH / ('M_DragonShield_%02d.uasset' % index))
    require_file(BEFORE / 'State.md')
    require_file(BEFORE / 'BeforeSurfaceFirstPerson.png')
    author_log = require_file(DOCS / f'ShieldSurfaceAuthor-{DATE}.log')
    if 'SHIELD_REALISTIC_MATERIALS_COMPLETE' not in author_log.read_text(encoding='utf-8-sig', errors='replace'):
        raise RuntimeError('Full-editor author log does not contain its completed material-save marker.')
    assets, tile_records = [], []
    profile_roles = set()
    for record in textures:
        profile, role = record['profile'], record['role']
        if profile not in EXPECTED_PROFILES or role not in {'base_color', 'orm', 'normal'}:
            raise RuntimeError('Unexpected profile/role in the texture report.')
        if (profile, role) in profile_roles:
            raise RuntimeError('Duplicate profile/role in the texture report.')
        profile_roles.add((profile, role))
        source = Path(record['source']).resolve()
        if not source.is_relative_to(SURFACE.resolve()) or png_dimensions(source) != [1024, 1024]:
            raise RuntimeError('Surface tile must be a1024x1024 PNG inside the authoring folder.')
        if sha256(source) != record.get('source_sha256'):
            raise RuntimeError('A baked tile changed after its UE import: ' + str(source))
        if record.get('srgb') is not (role == 'base_color'):
            raise RuntimeError('Only BaseColor textures may be sRGB.')
        if role == 'normal' and (record.get('normal_convention') != 'opengl' or record.get('flip_green_channel') is not True):
            raise RuntimeError('OpenGL normals must have the UE green-channel flip.')
        if role == 'orm' and record.get('packed_channels') != 'R=AO, G=roughness, B=metallic':
            raise RuntimeError('Packed mask channel interpretation must be explicit.')
        assets.append(asset_file(record['asset']))
        tile_records.append({'profile': profile, 'role': role, 'path': relative(source),
                             'resolution': [1024, 1024], 'sha256': record['source_sha256']})
    assets.extend(asset_file(record['asset']) for record in materials)
    if set(author.get('changed_assets', [])) != {record['asset'] for record in textures + materials}:
        raise RuntimeError('Changed-assets evidence must match the reported textures and materials.')
    images = [require_file(DOCS / name) for name in sorted(EXPECTED_IMAGES)]
    for path in images:
        width, height = png_dimensions(path)
        if width <= 0 or height <= 0:
            raise RuntimeError('Appearance screenshot dimensions must be positive.')
    scripts = [PROJECT / 'Saved/Scripts' / name for name in (
        'author_shield_realistic_materials.py', 'capture_shield_surface_preview.py',
        'finalize_shield_surface_delivery.py')]
    for path in scripts:
        require_file(path)
    for name in ('Run_Mixed_Demo.cmd', 'Run_Mixed_Demo.ps1'):
        require_file(PROJECT / name)
    preserved_content = validate_baseline()
    timestamp = datetime.now(timezone.utc).isoformat()
    before_manifest = make_manifest(BEFORE, 'Before shield realistic surface material changes', timestamp)
    report = {
        'module': 'ART-SHIELD-REALISTIC', 'generated_utc': timestamp, 'user_facing_date': DATE + ' Asia/Shanghai',
        'status': 'MaterialsSaved_ShaderAuthoringPassed_InitialAppearanceReviewed_AwaitingUserPlay',
        'scope': 'Shield-only material/texture polish; source blend, mesh, held transforms, C++ and combat preserved.',
        'source': {'original': str(original), 'preserved_copy': relative(preserved), 'sha256': original_hash, 'original_unchanged': True},
        'shield': {'mesh': '/Game/ReversedScale/Weapons/DragonShield/SM_DragonShield', 'diameter_cm': 46.0,
                   'material_count': 8, 'profile_count': 7, 'texture_count': 21,
                   'tiles': tile_records, 'material_graphs': materials,
                   'dragon_front': 'Existing UV0 base-image and UV1 normal retained; gold-versus-green-oxide metal/roughness variation added.',
                   'colour_orm_projection': 'Object-local triplanar with physical tile sizes; attached to the moving mesh.',
                   'normal_policy': 'OpenGL source +Y normal tiles flipped at UE import; actual restrained strengths in material_graphs.',
                   'mask_policy': 'Linear ORM, R=local micro cavity AO; G=roughness; B=metallic. AO is not a full mesh bake.'},
        'authoring': {'surface_manifest': relative(manifest_path), 'ue_report': relative(author_path),
                      'full_editor_report': relative(editor_path), 'log': relative(author_log),
                      'shader_recompile_errors': [], 'asset_save': 'Successful full-editor author completion',
                      'cpp_compile': 'Not required; unchanged native binary verified against previous delivery'},
        'presentation': {'report': relative(capture_path), 'reviewed_images': [relative(path) for path in images],
                         'root_visual_review_confirmed': True, 'bindings_transforms_hud_restored': True,
                         'agent_gameplay_inputs': False, 'capture': capture},
        'preserved_content': preserved_content,
        'retained_by_scope': ['Enemy face/feet, sword hilt/grip, Grounded death and prior lab content',
                              'Player melee damage10, blade qi15, shield grip and existing collision/guard/reflection logic'],
        'demo': {'launcher': 'Run_Mixed_Demo.cmd', 'process_id_at_preview': pid,
                 'running_at_final_check': process.get('running_at_final_check'),
                 'map': '/Game/ReversedScale/Maps/L_CombatLabMixed',
                 'requires': 'Local UE5.8 and existing project assets; incremental asset snapshot, not a packaged standalone EXE'},
        'before_manifest': before_manifest, 'snapshot_manifest': 'Deliveries/ShieldSurface_20261014/Manifest.json',
        'limitations': ['Procedural surface tiles and approximate rim wear; no new sculpted relief or full mesh AO bake.',
                        'Texture-fetch counts are graph counts only; actual GPU timing and VR performance remain unmeasured.',
                        'Initial material pictures do not establish combat, navigation, reflection, checkpoint or animation acceptance.',
                        'User visual approval and real VR/headset/controller acceptance remain pending.'],
        'tests_added_or_run': False, 'automation': 'Existing automation remains PAUSED',
        'next': 'User material feedback; ENEMY-02B Guard Captain remains pending before LEVEL-01'}
    write_json(DOCS / REPORT_NAME, report)
    state_path = require_file(DOCS / 'State.md')
    state_path.write_text(update_state(state_path.read_text(encoding='utf-8-sig'), report), encoding='utf-8')
    snapshot_items = [PROJECT / MATERIAL_PATH, PROJECT / TEXTURE_PATH, SURFACE,
                      author_path, editor_path, capture_path, process_path, author_log,
                      DOCS / REPORT_NAME, state_path, ART / 'DragonShieldPrepared.json',
                      ART / 'DragonShieldImported.json', PROJECT / 'Run_Mixed_Demo.cmd',
                      PROJECT / 'Run_Mixed_Demo.ps1', *images, *scripts]
    # Optional root wrapper is included if its authoring helper exists. It is not
    # required because roots may dispatch the author through an inline wrapper.
    for name in ('author_shield_surface_editor.py', 'run_shield_surface_editor.py'):
        candidate = PROJECT / 'Saved/Scripts' / name
        if candidate.is_file():
            snapshot_items.append(candidate)
    for item in snapshot_items:
        copy_item(item)
    result = make_manifest(DELIVERY, 'Shield realistic surface incremental asset delivery', timestamp)
    print(json.dumps({'delivery_report': relative(DOCS / REPORT_NAME), 'snapshot': result,
                      'before_materials': before_manifest, 'tests_added_or_run': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
