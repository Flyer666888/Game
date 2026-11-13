"""Save the shield mesh refinement record after authoring and initial art capture."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'Docs/AI'
ART = ROOT / 'ArtSource/DragonShield/ModelRefinement_20261016'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    model = read(ART / 'DragonShieldRefined.json')
    imported = read(DOCS / 'ShieldModelImported-2026-10-16.json')
    presentation = read(DOCS / 'ShieldModelPresentation-2026-10-16.json')
    if not imported.get('success') or not presentation.get('success'):
        raise RuntimeError('Mesh authoring and presentation must complete before delivery.')
    if not imported.get('materials_unchanged'):
        raise RuntimeError('Mesh-only import must retain the current realistic materials.')
    if imported['fbx_sha256'] != digest(ART / 'DragonShieldRefined.fbx'):
        raise RuntimeError('The final FBX differs from the imported geometry.')
    if imported['mesh_uasset_sha256'] != presentation.get('mesh_asset_sha256'):
        raise RuntimeError('Initial presentation must use this batch of the shield mesh.')
    if presentation.get('initial_state', {}).get('melee_damage') != 10:
        raise RuntimeError('The initial scene must retain the existing melee damage of 10.')
    screenshots = ['ShieldModel_Equipped.png', 'ShieldModel_Back.png', 'ShieldModel_Front.png']
    for name in screenshots:
        if not (DOCS / name).is_file():
            raise RuntimeError('Missing shield presentation: ' + name)
    original = ROOT / 'ArtSource/DragonShield/Source/Jade_Dragon_Shield_Refined.blend'
    if digest(original) != '12501cd53192416d293547b1fb213018ba2ae7a289df846cc81d0d725c486c5b':
        raise RuntimeError('The preserved original shield source differs from its recorded copy.')
    report = {
        'date': '2026-10-16',
        'status': 'RefinedMeshSaved_InitialArtReviewed_AwaitingUserVRReview',
        'request': '精细一下护心镜的建模',
        'mesh': '/Game/ReversedScale/Weapons/DragonShield/SM_DragonShield',
        'model_authoring': model,
        'model_render_manifest': read(ART / 'RenderManifest.json'),
        'ue_import': imported,
        'initial_presentation': presentation,
        'original_source_unchanged': True,
        'scope': 'Shield visual geometry refinement and mesh-only replacement; existing PBR materials retained.',
        'native_compile': 'Not needed; no native code changed in this batch.',
        'tests_added_or_run': False,
        'real_hmd_acceptance': 'Pending user review',
        'known_import_warning': 'UE still reports some near-zero tangents/binormals (tolerance 1E-4). The original 2026-10-14 import also reported this warning; source triangle/UV cleanup does not by itself prove every render tangent is valid.',
        'import_log': 'Docs/AI/ShieldModelImportLog-2026-10-16.txt',
        'backup': 'Deliveries/BeforeShieldModel_20261016',
        'snapshot': 'Deliveries/ShieldModelRefinement_20261016',
        'snapshot_requires': 'Existing full experiment project and local UE5.8; incremental asset delivery, not a standalone executable.',
        'launcher': 'Run_VR_Demo.cmd',
    }
    report_path = DOCS / 'ShieldModelDelivery-2026-10-16.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    state_path = DOCS / 'State.md'
    lines = state_path.read_text(encoding='utf-8').splitlines()
    replacements = {
        'Updated:': 'Updated: 2026-10-16 Asia/Shanghai',
        'CurrentTask:': 'CurrentTask: Dragon shield geometry refined, imported with existing realistic materials and initial held art captured; user VR review pending',
        'TaskStatus:': 'TaskStatus: ShieldModelRefinement_AssetsSaved_InitialArtReviewed_AwaitingUserVRReview',
        '  CurrentAuthorization:': '  CurrentAuthorization: User requested finer dragon shield modeling; refine geometry, preserve grip compatibility, save asset and review initial art. No new tests authorized.',
    }
    for index, line in enumerate(lines):
        for prefix, value in replacements.items():
            if line.startswith(prefix):
                lines[index] = value
                break
    text = '\n'.join(lines) + '\n'
    marker = 'ShieldModelRefinement_Current_20261016:'
    if marker not in text:
        text += '''
ShieldModelRefinement_Current_20261016:
  - User requested finer modeling of the existing dragon shield.
  - Editable detailed Blender source and canonical FBX saved under ArtSource/DragonShield/ModelRefinement_20261016.
  - Actual visual mesh replaced at the existing SM_DragonShield path; current realistic material assets reused by imported slot name.
  - Original 46cm size, pivot and left-hand grip anchor retained; original source preserved.
  - Four mesh LODs authored; Nanite off, no visual collision or navigation data.
  - Actual desktop Ready held/back/front art captured; no controller simulation or gameplay inputs.
  - Sword A, melee damage10, native VR entry/navigation fixes and enemy assets retained.
  - No native compile required and no tests run; real-HMD visual acceptance remains with the user.
  - Details: Docs/AI/ShieldModelDelivery-2026-10-16.json.
  - Backup: Deliveries/BeforeShieldModel_20261016; snapshot: Deliveries/ShieldModelRefinement_20261016.
'''
    state_path.write_text(text, encoding='utf-8')

    dev_path = DOCS / 'DevelopmentStatus.md'
    text = dev_path.read_text(encoding='utf-8')
    heading = '## 2026-10-16：护心镜建模精修'
    if heading not in text:
        text += '''

## 2026-10-16：护心镜建模精修

- 本批精修护心镜几何：龙纹浮雕、金属边框、背柄皮革包覆和固定件；细项与面数见 ShieldModelDelivery-2026-10-16.json。
- 可编辑 Blender 文件和 FBX 位于 ArtSource/DragonShield/ModelRefinement_20261016，原始模型保留，UE 继续使用原 SM_DragonShield 资产路径及写实材质。
- 保持46厘米尺寸、原点与左手握持锚点，四级LOD和原格挡碰撞归属。已保存资产并采集初始持握、正面与背面画面。
- 本批未改动原生代码，无需重新编译；没有添加或运行测试。头显中的近距离观感与握持仍待用户试玩确认。
- 试玩入口：Run_VR_Demo.cmd；本批备份：Deliveries/BeforeShieldModel_20261016；增量交付：Deliveries/ShieldModelRefinement_20261016。
'''
    dev_path.write_text(text, encoding='utf-8')

    files = set()
    for folder in (ART, ROOT / 'Content/ReversedScale/Weapons/DragonShield'):
        files.update(p for p in folder.rglob('*') if p.is_file()
                     and p.suffix not in {'.blend1', '.log', '.err'} and '_Quick' not in p.stem
                     and not any(part.lower().startswith(('rejected', 'candidates')) for part in p.parts)
                     and not ('candidate' in p.stem.lower() and p.suffix in {'.blend', '.png', '.json'}))
    for name in screenshots + ['State.md', 'DevelopmentStatus.md', 'ShieldModelDelivery-2026-10-16.json',
                               'ShieldModelImported-2026-10-16.json', 'ShieldModelPresentation-2026-10-16.json',
                               'ShieldModelImportLog-2026-10-16.txt', 'ShieldModelPresentationLog-2026-10-16.txt']:
        files.add(DOCS / name)
    for name in ['import_refined_shield_model.py', 'capture_refined_shield_model.py', 'save_shield_model_delivery.py']:
        files.add(ROOT / 'Saved/Scripts' / name)
    for name in ['Run_VR_Demo.cmd', 'Run_VR_Demo.ps1', 'VRDemo_操作说明.txt']:
        files.add(ROOT / name)
    snapshot = ROOT / 'Deliveries/ShieldModelRefinement_20261016'
    manifest = []
    for src in sorted(files):
        rel = src.relative_to(ROOT)
        dest = snapshot / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        manifest.append({'path': rel.as_posix(), 'bytes': src.stat().st_size, 'sha256': digest(src)})
    (snapshot / 'Manifest.json').write_text(json.dumps({
        'date': '2026-10-16', 'requires': report['snapshot_requires'], 'files': manifest
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SHIELD_MODEL_DELIVERED', len(manifest), 'files; snapshot:', snapshot)


if __name__ == '__main__':
    main()
