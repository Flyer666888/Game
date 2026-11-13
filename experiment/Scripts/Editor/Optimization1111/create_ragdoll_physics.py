"""Author independent, constrained enemy physics assets without modal factories.

Run after the Optimization1111 native module has compiled. Only enemy Blueprint
overrides and new physics packages are saved; mesh/skeleton/animation bytes stay
protected. Failures are written to the report and raised to the editor runner.
"""
import hashlib
import json
import shutil
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUT = ROOT / 'Docs/Gameplay/Optimization1111'
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / 'RagdollPhysics.json'
ASSETS = unreal.EditorAssetLibrary
DEST = '/Game/ReversedScale/Characters/Physics1111'


def disk_path(asset_path):
    package = asset_path.split('.')[0]
    assert package.startswith('/Game/'), package
    return ROOT / 'Content' / (package[6:] + '.uasset')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def backup(asset_path):
    source = disk_path(asset_path)
    assert source.is_file(), str(source)
    target = OUT / 'Backups' / 'Content' / source.relative_to(ROOT / 'Content')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source, target)
    return {'path': str(target), 'sha256': digest(target),
            'source_sha256_before_this_run': digest(source)}


def object_path(value):
    return value.get_path_name() if value else None


def validate(asset, mesh, component):
    # These arrays are protected UPROPERTYs in UE5.8. Read them through the
    # native, read-only inspector instead of treating missing Python API as success.
    scale = component.get_editor_property('relative_scale3d')
    inspect = getattr(unreal.NLEnemyCharacter, 'inspect_ragdoll_physics_asset_for_editor', None)
    assert inspect, 'Compile the native physics inspector before this script'
    details = json.loads(inspect(asset, mesh, scale))
    assert details.get('state') == 'passed', 'Physics asset inspection failed: ' + json.dumps(details)
    assert 5 <= details['body_count'] <= 80, 'Incomplete/excessive body count'
    assert details['constraint_count'] >= details['body_count'] - 1, 'Disconnected ragdoll constraints'
    assert details['bone_names_match'] and details['constraints_valid'], 'Physics asset uses another skeleton'
    assert details['shapes_valid'] and details['preview_mesh_matches'], 'Invalid shape scale or mesh binding'
    details['mesh_component_scale'] = [float(scale.x), float(scale.y), float(scale.z)]
    return details


report = {'state': 'running', 'meshes': [], 'enemies': [],
          'scope': 'New physics packages and enemy ragdoll overrides only'}
try:
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None, 'Stop PIE first'
    bridge = getattr(unreal.NLEnemyCharacter, 'create_ragdoll_physics_asset_for_editor', None)
    assert bridge, 'Compile the non-modal physics bridge before this script'
    enemies = []
    protected = {}
    for path in ASSETS.list_assets('/Game/ReversedScale/Gameplay/V01/Enemies', recursive=True, include_folder=False):
        cls = ASSETS.load_blueprint_class(path)
        if not cls:
            continue
        default = unreal.get_default_object(cls)
        if not isinstance(default, unreal.NLEnemyCharacter):
            continue
        component = default.get_component_by_class(unreal.SkeletalMeshComponent)
        mesh = default.get_editor_property('enemy_skeletal_mesh') or component.get_editor_property('skeletal_mesh')
        assert mesh, path + ' has no skeletal mesh'
        preserved = {}
        for prop in ('enemy_skeletal_mesh', 'idle_animation', 'walk_animation', 'attack_animation',
                     'cast_animation', 'hit_reaction_animation', 'death_animation'):
            value = default.get_editor_property(prop)
            preserved[prop] = object_path(value)
            if value:
                protected[str(disk_path(value.get_path_name()))] = digest(disk_path(value.get_path_name()))
        protected[str(disk_path(mesh.skeleton.get_path_name()))] = digest(disk_path(mesh.skeleton.get_path_name()))
        enemies.append((path, default, component, mesh, preserved))
    assert enemies, 'No enemy archetypes found'
    ASSETS.make_directory(DEST)
    physics_by_mesh = {}
    for path, default, component, mesh, preserved in enemies:
        mesh_path = mesh.get_path_name()
        physics = physics_by_mesh.get(mesh_path)
        if physics is None:
            package = DEST + '/PHYS_' + mesh.get_name() + '_Fitted'
            physics = ASSETS.load_asset(package) if ASSETS.does_asset_exist(package) else None
            if physics is None:
                physics = bridge(mesh, package, 8.0)
            assert physics, 'Physics generation returned null for ' + mesh_path
            details = validate(physics, mesh, component)
            assert ASSETS.save_loaded_asset(physics, False), 'Failed to save independent physics asset'
            report['meshes'].append({'mesh': mesh_path, 'physics': physics.get_path_name(), **details})
            physics_by_mesh[mesh_path] = physics
        original = backup(path)
        default.set_editor_property('ragdoll_physics_asset', physics)
        default.set_editor_property('use_ragdoll_death', True)
        bp = ASSETS.load_asset(path)
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        check = unreal.get_default_object(ASSETS.load_blueprint_class(path))
        assert check.get_editor_property('ragdoll_physics_asset') == physics
        assert check.get_editor_property('use_ragdoll_death')
        assert all(object_path(check.get_editor_property(prop)) == value for prop, value in preserved.items()), 'Animation/mesh changed'
        assert ASSETS.save_loaded_asset(bp, False), 'Failed to save enemy physics override'
        report['enemies'].append({'asset': path, 'physics': physics.get_path_name(),
                                  'backup': original, 'preserved': preserved})
    assert all(digest(Path(path)) == before for path, before in protected.items()), 'Protected mesh/skeleton/animation bytes changed'
    report['protected_asset_count'] = len(protected)
    report['state'] = 'passed'
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('OPTIMIZATION1111_RAGDOLL_PHYSICS_PASSED')
except Exception as error:
    report['state'] = 'failed'
    report['error'] = repr(error)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    raise
