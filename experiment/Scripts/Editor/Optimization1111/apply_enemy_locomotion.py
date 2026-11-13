"""Synchronize saved enemy defaults with the provided walk's measured stride."""
import hashlib
import json
import shutil
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUT = ROOT / 'Docs/Gameplay/Optimization1111'
OUT.mkdir(parents=True, exist_ok=True)
A = unreal.EditorAssetLibrary
report = {'state': 'running', 'enemies': []}
try:
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None, 'Stop PIE first'
    stride_file = ROOT / 'Docs/Gameplay/SlashRevision1104/NativeSupportClips.json'
    stride_data = json.loads(stride_file.read_text(encoding='utf-8-sig'))
    stride = next(row['stride'] for row in stride_data['clips'] if row.get('stride'))
    measured_speed = float(stride['measured_speed_cm_s'])
    assert 199 <= measured_speed <= 206, 'Provided walk stride evidence changed; remeasure before applying'
    report['stride_evidence'] = {'path': str(stride_file), 'sha256': hashlib.sha256(stride_file.read_bytes()).hexdigest(),
                                 'measured_speed_cm_s': measured_speed,
                                 'left_support_median_m_s': stride['Left']['median_support_speed_m_s'],
                                 'right_support_median_m_s': stride['Right']['median_support_speed_m_s']}
    for path in A.list_assets('/Game/ReversedScale/Gameplay/V01/Enemies', recursive=True, include_folder=False):
        cls = A.load_blueprint_class(path)
        if not cls:
            continue
        default = unreal.get_default_object(cls)
        if not isinstance(default, unreal.NLEnemyCharacter):
            continue
        movement = default.get_component_by_class(unreal.CharacterMovementComponent)
        brain = default.get_enemy_brain()
        before = {'speed': float(movement.max_walk_speed), 'walk_animation_speed': float(default.walk_animation_speed),
                  'walk': default.walk_animation.get_path_name() if default.walk_animation else None,
                  'attack': default.attack_animation.get_path_name() if default.attack_animation else None,
                  'turn_rate': float(movement.rotation_rate.yaw)}
        source = ROOT / 'Content' / (path.split('.')[0][6:] + '.uasset')
        backup = OUT / 'Backups/Content' / source.relative_to(ROOT / 'Content')
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(source, backup)
        speed = before['speed']
        if brain.role == unreal.NLEnemyRole.SWORD_DISCIPLE:
            speed = max(280.0, speed)
        elif brain.role == unreal.NLEnemyRole.TALISMAN_CASTER and not brain.hold_ranged_position:
            speed = max(250.0, speed)
        movement.set_editor_property('max_walk_speed', speed)
        movement.set_editor_property('max_acceleration', 1400.0)
        movement.set_editor_property('braking_deceleration_walking', 1600.0)
        turn = movement.rotation_rate
        movement.set_editor_property('rotation_rate', unreal.Rotator(turn.pitch, max(420.0, turn.yaw), turn.roll))
        # The native walk and its GripB variant retain the same supplied leg keys.
        # 202.38429 cm/s was measured from planted-toe velocity, not guessed from chase speed.
        if default.walk_animation and default.walk_animation.get_name() in ('A_Wuxia_Walk_Native_v07', 'A_Wuxia_Walk_GripB'):
            default.set_editor_property('walk_animation_speed', measured_speed)
        bp = A.load_asset(path)
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        check = unreal.get_default_object(A.load_blueprint_class(path))
        move_check = check.get_component_by_class(unreal.CharacterMovementComponent)
        assert abs(move_check.max_walk_speed - speed) < .01
        assert not check.walk_animation or check.walk_animation.get_path_name() == before['walk']
        assert not check.attack_animation or check.attack_animation.get_path_name() == before['attack']
        assert A.save_loaded_asset(bp, False)
        report['enemies'].append({'asset': path, 'before': before, 'speed_cm_s': float(move_check.max_walk_speed),
                                  'walk_animation_speed_cm_s': float(check.walk_animation_speed),
                                  'turn_rate_degrees_s': float(move_check.rotation_rate.yaw),
                                  'hold_position': bool(brain.hold_ranged_position),
                                  'backup': str(backup), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    assert report['enemies'], 'No enemy Blueprints found'
    report['state'] = 'passed'
except Exception as error:
    report['state'] = 'failed'
    report['error'] = repr(error)
    raise
finally:
    (OUT / 'EnemyLocomotion.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
