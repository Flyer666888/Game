"""Patch only two existing wave assets, one upgrade asset and the playable map.

Run after the FirstAscent C++ API is compiled and with PIE stopped. This script
never rebuilds the whitebox, navigation, enemy Blueprints, meshes or animations.
Every existing target package is backed up and hashed before the first edit.
"""
import datetime
import hashlib
import json
import re
import shutil
import traceback
import uuid
from pathlib import Path

import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUT = PROJECT / 'Docs/Gameplay/Level01Polish_v01'
OUT.mkdir(parents=True, exist_ok=True)
MAP = '/Game/ReversedScale/Maps/L_NilinGameplayV01'
WAVE_ROOT = '/Game/ReversedScale/Gameplay/V01/Waves'
ENEMY_ROOT = '/Game/ReversedScale/Gameplay/V01/Enemies'
UPGRADE_PATH = '/Game/ReversedScale/Progression/DA_FirstAscentUpgrade'
TARGET_WAVE_IDS = ('Bcourt_W03', 'Bcourt_W05')
UPGRADE_VALUES = {
    'stable_id': 'Progression.FirstAscent',
    'ling_qi_per_defeat': 1,
    'first_upgrade_threshold': 40,
    'level_two_damage_multiplier': 1.25,
}
INSTRUCTIONS = {
    'Aoutside': '左键挥剑；敌人命中前右键精准格挡',
    'Ainside': '正面迎敌，精准格挡蓄积化劲回元',
    'R01': '留意高处符光，E 剑气反击岩台敌人',
    'Bcourt': 'Q 震荡清群；第 3、5 波留意远程',
    'Bexit': '清除出口守卫，晋升二阶后进入丹道',
}
TIMING_FIELDS = (
    'spawn_interval_seconds', 'intermission_seconds', 'max_alive',
    'max_spawn_retries', 'retry_delay_seconds',
)
PRESERVED_STAGE_FIELDS = (
    'stage_id', 'display_name', 'required_stage_id', 'trigger_center',
    'trigger_extent', 'entry_transform', 'warning_seconds', 'seed',
    'master_id', 'seal_id', 'required_seal_ids',
)
A = unreal.EditorAssetLibrary
SAVE = unreal.EditorLoadingAndSavingUtils
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
report = {
    'state': 'preflight', 'map': MAP, 'failures': [], 'backups': [],
    'saved_packages': [],
    'scope': 'Two mixed Bcourt waves, FirstAscent definition and existing Director growth/instruction fields only.',
    'runtime_validation': 'Not performed by this authoring script. Readback is asset/configuration validation only.',
}


def flush_report():
    (OUT / 'AuthoringReport.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_file(asset_path, suffix='.uasset'):
    assert asset_path.startswith('/Game/'), asset_path
    return PROJECT / 'Content' / (asset_path.removeprefix('/Game/') + suffix)


def native_value(value):
    # UE's struct repr includes a transient allocation address. Retain all field
    # names and numeric values, removing only those non-semantic addresses.
    if isinstance(value, (bool, int, float, str)):
        return value
    return re.sub(r'0x[0-9a-fA-F]+', '0xPTR', str(value))


def path_of(value):
    return value.get_path_name() if value else None


def find_director():
    found = [actor for actor in ACTORS.get_all_level_actors()
             if isinstance(actor, unreal.NLLevelEncounterDirector)]
    assert len(found) == 1, 'Expected exactly one existing level Director'
    return found[0]


def describe_wave(wave):
    return {
        'asset': path_of(wave),
        'wave_id': str(wave.get_editor_property('wave_id')),
        'timing': {key: wave.get_editor_property(key) for key in TIMING_FIELDS},
        'entries': [{
            'entry_id': str(entry.get_editor_property('entry_id')),
            'enemy_class': path_of(entry.get_editor_property('enemy_class')),
            'count': int(entry.get_editor_property('count')),
            'spawn_point_ids': list(map(str, entry.get_editor_property('spawn_point_ids'))),
        } for entry in wave.get_editor_property('spawn_entries')],
    }


def stage_signature(stages):
    result = []
    for stage in stages:
        item = {key: native_value(stage.get_editor_property(key))
                for key in PRESERVED_STAGE_FIELDS}
        item['required_seal_ids'] = list(map(str, stage.get_editor_property('required_seal_ids')))
        item['spawn_points'] = [{
            'id': str(point.get_editor_property('spawn_point_id')),
            'transform': native_value(point.get_editor_property('spawn_transform')),
        } for point in stage.get_editor_property('spawn_points')]
        item['waves'] = [path_of(wave) for wave in stage.get_editor_property('waves')]
        result.append(item)
    return result


def budgets(stages):
    rows = []
    for stage in stages:
        waves = list(stage.get_editor_property('waves'))
        rows.append({
            'stage_id': str(stage.get_editor_property('stage_id')),
            'wave_count': len(waves),
            'enemy_count': sum(int(entry.get_editor_property('count'))
                               for wave in waves for entry in wave.get_editor_property('spawn_entries')),
        })
    return {
        'stages': len(rows), 'waves': sum(row['wave_count'] for row in rows),
        'enemies': sum(row['enemy_count'] for row in rows), 'by_stage': rows,
    }


def backup_package(asset_path, primary_suffix, backup_root):
    primary = package_file(asset_path, primary_suffix)
    record = {'package': asset_path, 'existed_before': primary.exists(), 'files': []}
    for suffix in (primary_suffix, '.uexp', '.ubulk'):
        source = package_file(asset_path, suffix)
        if not source.exists():
            continue
        target = backup_root / source.relative_to(PROJECT)
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists(), 'Refusing to overwrite an existing recovery copy'
        before_hash = sha(source)
        shutil.copy2(source, target)
        assert sha(target) == before_hash, 'Backup copy failed hash validation'
        record['files'].append({
            'source': str(source), 'backup': str(target), 'sha256_before': before_hash,
        })
    report['backups'].append(record)


def hash_protected_packages(stages):
    targets = {WAVE_ROOT + '/DA_' + name for name in TARGET_WAVE_IDS}
    packages = {ENEMY_ROOT + '/BP_Level_' + key for key in (
        'sword', 'talisman', 'rock_talisman', 'GM01', 'GM02', 'GM03', 'GM04', 'boss')}
    packages.update({
        '/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Hands_v04',
        '/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Natural_v04',
    })
    for stage in stages:
        for wave in stage.get_editor_property('waves'):
            package = path_of(wave).split('.')[0]
            if package not in targets:
                packages.add(package)
    paths = [package_file(package) for package in sorted(packages)]
    paths.append(package_file('/Game/ReversedScale/Maps/L_NilinBlockoutV10', '.umap'))
    for path in paths:
        assert path.is_file(), 'Missing protected source package: ' + str(path)
    return {str(path): sha(path) for path in paths}


def validate_upgrade(asset):
    observed = {key: asset.get_editor_property(key) for key in UPGRADE_VALUES}
    assert str(observed['stable_id']) == UPGRADE_VALUES['stable_id']
    assert int(observed['ling_qi_per_defeat']) == 1
    assert int(observed['first_upgrade_threshold']) == 40
    assert abs(float(observed['level_two_damage_multiplier']) - 1.25) < 0.00001
    return {key: native_value(value) for key, value in observed.items()}


def main():
    assert EDITOR.get_game_world() is None, 'Stop PIE before authoring'
    assert not SAVE.get_dirty_map_packages(), 'Save the current edited map before running this patch'
    upgrade_class = unreal.load_class(None, '/Script/experiment.NLUpgradeDefinition')
    assert upgrade_class, 'Compile FirstAscent C++ before running this script'
    # Reject a stale editor DLL before any assets or map state are changed.
    defaults = unreal.get_default_object(upgrade_class)
    for key in UPGRADE_VALUES:
        defaults.get_editor_property(key)
    if not EDITOR.get_editor_world().get_path_name().startswith(MAP + '.'):
        assert LEVEL.load_level(MAP), 'Could not load existing gameplay map'
    director = find_director()
    director.get_editor_property('upgrade_definition')
    stages = list(director.get_editor_property('stages'))
    for stage in stages:
        stage.get_editor_property('minimum_upgrade_level_on_complete')
        stage.get_editor_property('instruction_text')
    before_budgets = budgets(stages)
    assert (before_budgets['stages'], before_budgets['waves'], before_budgets['enemies']) == (16, 27, 109)
    assert set(INSTRUCTIONS).issubset({str(s.get_editor_property('stage_id')) for s in stages})
    before_stages = stage_signature(stages)
    before_level_id = str(director.get_editor_property('level_id'))
    assert before_level_id == 'Level.Nilin.Playable', 'Refusing to save a temporary test profile into the main map'
    before_other_instructions = {
        str(stage.get_editor_property('stage_id')): str(stage.get_editor_property('instruction_text'))
        for stage in stages if str(stage.get_editor_property('stage_id')) not in INSTRUCTIONS
    }
    protected = hash_protected_packages(stages)
    sword = A.load_blueprint_class(ENEMY_ROOT + '/BP_Level_sword')
    talisman = A.load_blueprint_class(ENEMY_ROOT + '/BP_Level_talisman')
    assert sword and talisman, 'Existing validated enemy classes are required'
    class_paths = {path_of(sword), path_of(talisman)}
    targets = {name: A.load_asset(WAVE_ROOT + '/DA_' + name) for name in TARGET_WAVE_IDS}
    assert all(targets.values()), 'Only existing target waves may be patched'
    before_waves = {name: describe_wave(asset) for name, asset in targets.items()}
    for name, data in before_waves.items():
        assert data['wave_id'] == name and sum(entry['count'] for entry in data['entries']) == 6
        assert all(entry['enemy_class'] in class_paths for entry in data['entries']), 'Unexpected authored enemy class'
        assert all(entry['spawn_point_ids'] for entry in data['entries'])
        assert data['timing']['max_alive'] == 4, 'Do not replace a separately retuned concurrent limit'
    bcourt = next(stage for stage in stages if str(stage.get_editor_property('stage_id')) == 'Bcourt')
    bcourt_paths = {path_of(wave) for wave in bcourt.get_editor_property('waves')}
    assert all(path_of(asset) in bcourt_paths for asset in targets.values())
    valid_points = {str(point.get_editor_property('spawn_point_id')) for point in bcourt.get_editor_property('spawn_points')}
    for data in before_waves.values():
        assert all(set(entry['spawn_point_ids']).issubset(valid_points) for entry in data['entries'])
    changed_paths = {MAP, UPGRADE_PATH, *(WAVE_ROOT + '/DA_' + name for name in TARGET_WAVE_IDS)}
    dirty_targets = [package.get_path_name() for package in SAVE.get_dirty_content_packages()
                     if package.get_path_name() in changed_paths]
    assert not dirty_targets, 'Save existing target edits before patching: ' + ', '.join(dirty_targets)

    backup_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    backup_root = OUT / 'Backups' / backup_id
    for name in TARGET_WAVE_IDS:
        backup_package(WAVE_ROOT + '/DA_' + name, '.uasset', backup_root)
    backup_package(UPGRADE_PATH, '.uasset', backup_root)
    backup_package(MAP, '.umap', backup_root)
    report.update({
        'state': 'backed_up', 'backup_id': backup_id,
        'before_budgets': before_budgets, 'waves_before': before_waves,
        'protected_package_hashes_before': protected,
        'recovery': 'Restore only the exact target package copies listed in backups while the editor is closed. A newly created upgrade package has no previous copy.',
    })
    flush_report()

    for name, wave in targets.items():
        points = list(dict.fromkeys(point for entry in before_waves[name]['entries']
                                   for point in entry['spawn_point_ids']))
        entries = []
        for suffix, enemy_class, count in (('Enemies', sword, 5), ('Talisman', talisman, 1)):
            entry = unreal.NLWaveSpawnEntry()
            for key, value in {
                'entry_id': name + '_' + suffix, 'enemy_class': enemy_class,
                'count': count, 'spawn_point_ids': points,
            }.items():
                entry.set_editor_property(key, value)
            entries.append(entry)
        wave.set_editor_property('spawn_entries', entries)
        assert A.save_loaded_asset(wave, False), 'Could not save ' + name
        report['saved_packages'].append(WAVE_ROOT + '/DA_' + name)
        flush_report()

    upgrade = A.load_asset(UPGRADE_PATH) if A.does_asset_exist(UPGRADE_PATH) else None
    if not upgrade:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property('data_asset_class', upgrade_class)
        upgrade = TOOLS.create_asset('DA_FirstAscentUpgrade', '/Game/ReversedScale/Progression', None, factory)
    assert upgrade and upgrade.get_class() == upgrade_class, 'Unexpected upgrade asset class'
    for key, value in UPGRADE_VALUES.items():
        upgrade.set_editor_property(key, value)
    assert A.save_loaded_asset(upgrade, False), 'Could not save FirstAscent definition'
    report['saved_packages'].append(UPGRADE_PATH)
    flush_report()

    # This reflected UE 5.8 API reloads the saved top-level data packages. The
    # next checks therefore read serialized values rather than only setter state.
    packages = [asset.get_outer() for asset in targets.values()] + [upgrade.get_outer()]
    reload_result = SAVE.reload_packages(packages, unreal.ReloadPackagesInteractionMode.ASSUME_NEGATIVE)
    assert reload_result[0] and not str(reload_result[1]), 'Data package reload failed: ' + str(reload_result)
    targets = {name: A.load_asset(WAVE_ROOT + '/DA_' + name) for name in TARGET_WAVE_IDS}
    upgrade = A.load_asset(UPGRADE_PATH)
    after_waves = {name: describe_wave(asset) for name, asset in targets.items()}
    for name, data in after_waves.items():
        assert data['timing'] == before_waves[name]['timing'], 'Wave timing or limits changed'
        assert len(data['entries']) == 2
        by_class = {entry['enemy_class']: entry['count'] for entry in data['entries']}
        assert by_class == {path_of(sword): 5, path_of(talisman): 1}, 'Mixed-wave readback mismatch'
    report['upgrade_readback'] = validate_upgrade(upgrade)
    report['waves_after_reload'] = after_waves

    director = find_director()
    stages = list(director.get_editor_property('stages'))
    for stage in stages:
        key = str(stage.get_editor_property('stage_id'))
        stage.set_editor_property('minimum_upgrade_level_on_complete', 2 if key == 'Bexit' else 1)
        if key in INSTRUCTIONS:
            stage.set_editor_property('instruction_text', unreal.Text(INSTRUCTIONS[key]))
    director.set_editor_property('stages', stages)
    director.set_editor_property('upgrade_definition', upgrade)
    assert LEVEL.save_current_level(), 'Could not save the patched main map'
    report['saved_packages'].append(MAP)
    flush_report()
    assert LEVEL.load_level(MAP), 'Could not reload the saved main map'
    director = find_director()
    stages = list(director.get_editor_property('stages'))
    assert str(director.get_editor_property('level_id')) == before_level_id
    assert stage_signature(stages) == before_stages, 'A preserved stage field changed'
    after_budgets = budgets(stages)
    assert after_budgets == before_budgets, 'Stage/wave/enemy budgets changed'
    assert path_of(director.get_editor_property('upgrade_definition')) == path_of(upgrade)
    stage_readback = []
    for stage in stages:
        key = str(stage.get_editor_property('stage_id'))
        minimum = int(stage.get_editor_property('minimum_upgrade_level_on_complete'))
        instruction = str(stage.get_editor_property('instruction_text'))
        assert minimum == (2 if key == 'Bexit' else 1)
        assert instruction == INSTRUCTIONS.get(key, before_other_instructions.get(key, ''))
        stage_readback.append({'stage_id': key, 'minimum_upgrade_level_on_complete': minimum,
                               'instruction_text': instruction})
    for name, before_hash in protected.items():
        assert sha(Path(name)) == before_hash, 'Protected asset was modified: ' + name
    files_after = {}
    for package in sorted(changed_paths):
        path = package_file(package, '.umap' if package == MAP else '.uasset')
        assert path.is_file(), 'Saved package file is missing: ' + str(path)
        files_after[str(path)] = sha(path)
    report.update({
        'state': 'passed', 'after_budgets': after_budgets,
        'director_upgrade_definition': path_of(director.get_editor_property('upgrade_definition')),
        'stages_after_map_reload': stage_readback, 'target_package_hashes_after': files_after,
        'protected_packages_unchanged': True, 'protected_package_count': len(protected),
        'preserved_stage_fields_equal_after_reload': True,
        'completed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    flush_report()
    unreal.log('LEVEL01_POLISH_AUTHORING_PASSED: 16 stages, 27 waves, 109 enemies; two 5+1 mixed waves; FirstAscent configured.')


try:
    main()
except Exception:
    report['state'] = 'failed'
    report['failures'].append(traceback.format_exc())
    flush_report()
    raise
