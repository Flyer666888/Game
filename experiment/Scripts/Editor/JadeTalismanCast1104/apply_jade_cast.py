"""Install the approved jade talisman and golden cast on current caster defaults."""
import hashlib
import json
import shutil
from pathlib import Path
import unreal

P = Path(unreal.Paths.project_dir()).resolve()
O = P / 'Docs/Gameplay/JadeTalismanCast1104'
A = unreal.EditorAssetLibrary
DEST = '/Game/ReversedScale/Weapons/TalismanJade1104/'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
mesh = A.load_asset(DEST + 'SM_Nilin_JadeTalisman')
orb = A.load_asset(DEST + 'M_TalismanGoldenOrb')
assert isinstance(mesh, unreal.StaticMesh) and isinstance(orb, unreal.Material)
paths = ['/Game/ReversedScale/Characters/WuxiaMale/BP_EnemyTalismanDisciple']
paths += ['/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_' + k
          for k in ('talisman', 'rock_talisman', 'GM02', 'GM03')]
rows = []
for path in paths:
    bp = A.load_asset(path)
    obj = unreal.get_default_object(A.load_blueprint_class(path))
    brain = obj.get_enemy_brain()
    if brain.role != unreal.NLEnemyRole.TALISMAN_CASTER:
        rows.append({'asset': path, 'role': str(brain.role), 'changed': False})
        continue
    component = obj.get_component_by_class(unreal.NLTalismanAttackComponent)
    assert component, path
    source = P / 'Content' / (path.removeprefix('/Game/') + '.uasset')
    backup = O / 'Backups' / source.relative_to(P)
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(source, backup)
    before = {k: str(component.get_editor_property(k)) for k in
              ('muzzle_socket_name', 'muzzle_local_offset', 'talisman_hand_transform', 'projectile_material')}
    timings = [brain.telegraph_seconds, brain.attack_seconds, brain.recover_seconds, brain.projectile_speed]
    component.set_editor_property('talisman_mesh', mesh)
    component.set_editor_property('float_before_hand', True)
    component.set_editor_property('floating_hand_distance_cm', 17.0)
    component.set_editor_property('floating_orb_distance_cm', 13.0)
    # These ranged archetypes still use the hand_l casting clip and its matching skeleton.
    assert str(component.muzzle_socket_name) == 'hand_l', (path, str(component.muzzle_socket_name))
    component.set_editor_property('muzzle_local_offset', unreal.Vector(0, 0, 0))
    component.set_editor_property('talisman_material', None)
    component.set_editor_property('cast_glow_material', orb)
    component.set_editor_property('projectile_material', orb)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert A.save_loaded_asset(bp, False)
    check = unreal.get_default_object(A.load_blueprint_class(path))
    c = check.get_component_by_class(unreal.NLTalismanAttackComponent)
    b = check.get_enemy_brain()
    assert c.talisman_mesh == mesh and c.float_before_hand and c.projectile_material == orb
    assert [b.telegraph_seconds, b.attack_seconds, b.recover_seconds, b.projectile_speed] == timings
    rows.append({'asset': path, 'role': str(b.role), 'changed': True, 'before': before,
                 'socket': str(c.muzzle_socket_name), 'timings_and_speed': timings,
                 'mesh': mesh.get_path_name(), 'orb': orb.get_path_name(), 'backup': str(backup)})
assert any('rock_talisman' in r['asset'] and r['changed'] for r in rows)
(O / 'Applied.json').write_text(json.dumps({'state': 'passed', 'blueprints': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
