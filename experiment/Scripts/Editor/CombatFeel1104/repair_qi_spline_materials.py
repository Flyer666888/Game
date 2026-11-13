"""Persist spline shader permutations for sword Qi and both reflected faction materials.

Run in the idle review editor. Existing colors/emissive graphs stay unchanged.
The on-disk originals are copied before any mutation; saved flags are verified.
"""
import hashlib
import json
import shutil
from pathlib import Path
import unreal

P = Path(unreal.Paths.project_dir()).resolve()
OUT = P / 'Docs/Gameplay/CombatFeel1104'
A = unreal.EditorAssetLibrary
L = unreal.MaterialEditingLibrary
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None, 'Stop PIE before editing materials'
USAGE = unreal.MaterialUsage.MATUSAGE_SPLINE_MESH
PATHS = [
    '/Game/ReversedScale/Combat/Materials/M_BladeQi',
    '/Game/ReversedScale/Combat/Materials/M_EnemyShot',
    '/Game/ReversedScale/Combat/Materials/M_TalismanCast',
]
report = {'success': False, 'reason': 'Persist SplineMeshes usage; missing flag caused default gray material in game.', 'materials': []}
for path in PATHS:
    material = A.load_asset(path)
    assert material and isinstance(material, unreal.Material), path
    relative = Path(path.removeprefix('/Game/') + '.uasset')
    disk = P / 'Content' / relative
    backup = OUT / 'Backups/Content' / relative
    assert disk.is_file(), str(disk)
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(disk, backup)
    before_hash = hashlib.sha256(disk.read_bytes()).hexdigest()
    before_usage = L.has_material_usage(material, USAGE)
    L.set_base_material_usage(material, USAGE, True)
    L.recompile_material(material)
    assert L.has_material_usage(material, USAGE), path + ': spline usage not applied'
    assert A.save_loaded_asset(material, False), path + ': save failed'
    assert L.has_material_usage(A.load_asset(path), USAGE), path + ': saved material lacks usage'
    report['materials'].append({
        'asset': path, 'usage_before_in_memory': before_usage, 'usage_after': True,
        'saved': True, 'backup': str(backup), 'sha256_before': before_hash,
        'sha256_after': hashlib.sha256(disk.read_bytes()).hexdigest(),
    })
report['success'] = True
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'QiSplineMaterialRepair.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('Sword Qi spline material shader usage repaired and saved for all faction presentations.')
