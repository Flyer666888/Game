"""Render real native-rig death physics and reset in an isolated main-map PIE.

An unowned clone uses the first real sword disciple Blueprint, including its
saved fitted physics override. A labelled resolver fixture supplies the lethal
hit. Bone poses and animations are never assigned by this script.
"""

import hashlib
import json
import math
from pathlib import Path
import re
import struct
import time
import zlib

import unreal


ROOT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = ROOT / 'Docs/Gameplay/Optimization1111/RagdollDemo'
SOURCE = ROOT / 'Scripts/Editor/SlashRevision1104/runtime_motion.py'
OUTPUT.mkdir(parents=True, exist_ok=True)
legacy = SOURCE.read_text(encoding='utf-8-sig')
assert legacy.count('motion_probe = MotionProbe()') == 1
base_context = {'__name__': 'optimization1111_ragdoll_helper', '__file__': str(SOURCE)}
exec(compile(legacy.replace('motion_probe = MotionProbe()', ''), str(SOURCE), 'exec'), base_context)


def xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def path_of(obj):
    return obj.get_path_name() if obj else None


def save_hashes():
    return {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / 'Saved/SaveGames').rglob('*') if path.is_file()}


class OptimizationRagdollDemo(base_context['MotionProbe']):
    def __init__(self):
        self.protected_saves = save_hashes()
        self.old_console = {name: unreal.SystemLibrary.get_console_variable_float_value(name)
                            for name in ('t.MaxFPS', 't.IdleWhenNotForeground', 'Slate.bAllowThrottling')}
        engines = [engine for engine in unreal.ObjectIterator(unreal.Engine)
                   if engine.get_path_name().startswith('/Engine/Transient.')]
        assert len(engines) == 1, 'Expected one running transient editor Engine'
        self.engine = engines[0]
        self.old_fixed_rate = (self.engine.get_editor_property('use_fixed_frame_rate'),
                               self.engine.get_editor_property('fixed_frame_rate'))
        self.fixed_rate_changed = False
        self.clone = None
        self.clone_mesh = None
        self.lethal_fixture = None
        self.capture_phase = 'waiting_for_source'
        self.pending_frame = None
        self.samples = []
        self.next_frame_t = 0.0
        self.last_sample_time = None
        self.record_start = None
        self.death_time = None
        self.reset_time = None
        super().__init__()

    def save(self):
        self.report['elapsed_seconds'] = time.monotonic() - self.started
        self.report['fixture_isolation'] = self.isolation
        (OUTPUT / 'Capture.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.last_save = time.monotonic()

    def begin(self):
        super().begin()
        self.isolation.update(original_level_id=self.original_level, map_sha256_before=self.map_hash,
                              protected_save_file_count=len(self.protected_saves))
        self.report['scope'] = [
            'Saved main map in a temporary Test.Level01 PIE identity, with original encounter enemies paused, hidden and non-blocking.',
            'A non-Encounter-owned clone is spawned in the PIE GameWorld from the first real SwordDisciple Blueprint class. The saved mesh, idle animation, grip and fitted physics override are retained.',
            'After a natural standing interval, an explicitly labelled 999-damage CombatResolver fixture defeats only the unowned clone. This is not a player-controlled kill or a completed encounter.',
            'No manual animation, bone transform, physics pose, fall teleport or forced collision response is applied. Death physics and ResetForEncounter are native gameplay code.',
            'The same fixed observer camera captures standing, three game-seconds of gravity-driven ragdoll/floor contact, and reset to standing.',
            'A transient 60 Hz engine fixed-frame-rate setting is restored on cleanup; screenshots target 12 game-fps at 960x540. This is a deterministic demonstration, not a performance benchmark.',
            'No map, Blueprint, skeleton or animation package is saved. Exact test markers/ledgers/assets are cleaned and prior user-save hashes are checked.',
        ]

    def bootstrap(self):
        super().bootstrap()
        if self.phase != 'stage_active':
            return
        self.lethal_fixture = self.create_fixture('OptimizationRagdollLethal', 999)
        self.record_dir = OUTPUT / ('Frames_' + self.uid)
        self.record_dir.mkdir()
        self.report['frames'] = self.frames
        self.report['world_tick_samples'] = self.samples
        self.report['capture'] = {'width': 960, 'height': 540, 'screenshot_game_fps': 12,
                                  'requested_world_tick_fps': 60, 'standing_seconds': 1.0,
                                  'ragdoll_seconds': 3.0, 'reset_seconds': .75,
                                  'frame_directory': str(self.record_dir)}

    def pause_other_enemies(self):
        enemies = self.owned(pause=True)
        for enemy in enemies:
            enemy.set_actor_hidden_in_game(True)
            enemy.set_actor_enable_collision(False)
        return enemies

    def spawn_clone(self, source):
        encounter = self.director.get_active_encounter()
        assert encounter and encounter.owns_enemy(source)
        transform = source.get_actor_transform()
        source_physics = source.get_editor_property('ragdoll_physics_asset')
        assert source_physics and source.get_editor_property('use_ragdoll_death'), 'Install fitted physics before capture'
        clone = unreal.GameplayStatics.begin_deferred_actor_spawn_from_class(
            self.world, source.get_class(), transform, unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None)
        assert clone, 'Deferred GameWorld clone spawn failed'
        self.clone = clone  # Preserve exact ownership for cleanup even if finishing fails.
        clone.set_editor_property('auto_possess_ai', unreal.AutoPossessAI.DISABLED)
        clone.get_enemy_brain().set_component_tick_enabled(False)
        clone.set_combat_enabled(False)
        unreal.GameplayStatics.finish_spawning_actor(clone, transform)
        assert clone in unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLEnemyCharacter)
        assert not encounter.owns_enemy(clone), 'Clone must not use encounter corpse expiry/progression'
        clone.set_combat_enabled(False)
        clone.get_enemy_brain().set_component_tick_enabled(False)
        clone.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
        assert not clone.is_combat_enabled(), 'Demonstration clone must not start combat'
        self.clone_mesh = clone.get_component_by_class(unreal.SkeletalMeshComponent)
        assert self.clone_mesh and self.clone_mesh.does_socket_exist('Hips')
        assert clone.get_editor_property('ragdoll_physics_asset') == source_physics
        assert self.clone_mesh.get_editor_property('physics_asset_override') == source_physics
        self.baseline_progression = self.progression()
        self.baseline_defeats = encounter.get_defeated_count()
        self.baseline_completed = self.director.get_completed_stage_count()
        self.baseline_stage = str(self.director.get_stage_status(self.director.get_active_stage_id()))
        self.clone_start = clone.get_actor_location()
        capsule = clone.get_component_by_class(unreal.CapsuleComponent)
        self.initial_foot_z = self.clone_start.z - capsule.get_scaled_capsule_half_height()
        self.camera_position = self.clone_start + unreal.Vector(500, -600, 200)
        self.camera_rotation = unreal.MathLibrary.find_look_at_rotation(
            self.camera_position, self.clone_start + unreal.Vector(0, 0, -10))
        self.pawn.player_camera.set_field_of_view(52)
        self.pawn.lower_mirror()
        self.movement.disable_movement()
        self.pawn.set_actor_tick_enabled(False)
        for component in self.pawn.get_components_by_class(unreal.PrimitiveComponent):
            component.set_hidden_in_game(True)
        controller = unreal.GameplayStatics.get_player_controller(self.world, 0)
        unreal.SystemLibrary.execute_console_command(self.world, 'showhud')
        unreal.SystemLibrary.execute_console_command(self.world, 't.MaxFPS 60')
        unreal.GameplayStatics.set_global_time_dilation(self.world, 1.0)
        # Set the live engine object, never a CDO/config file; restore in cleanup.
        self.fixed_rate_changed = True
        self.engine.set_editor_property('fixed_frame_rate', 60.0)
        self.engine.set_editor_property('use_fixed_frame_rate', True)
        self.capture_phase = 'settle_standing'
        self.warmup_start = self.now()
        self.report['clone_fixture'] = {
            'source_actor': source.get_name(), 'class': source.get_class().get_path_name(),
            'clone_actor': clone.get_name(), 'spawn_transform': str(transform),
            'physics_asset': source_physics.get_path_name(),
            'mesh': path_of(self.clone_mesh.get_editor_property('skeletal_mesh')),
            'idle_animation': path_of(clone.get_editor_property('idle_animation')),
            'attack_animation_retained': path_of(clone.get_editor_property('attack_animation')),
            'encounter_owned': False, 'combat_enabled': False,
            'body_setups': len(source_physics.get_editor_property('skeletal_body_setups')),
            'constraints': len(source_physics.get_editor_property('constraint_setup')),
            'camera_position_cm': xyz(self.camera_position), 'initial_capsule_foot_z_cm': self.initial_foot_z,
        }

    def apply_camera(self):
        self.pawn.player_camera.set_world_transform(
            unreal.Transform(location=self.camera_position, rotation=self.camera_rotation), False, True)
        unreal.GameplayStatics.get_player_controller(self.world, 0).set_control_rotation(self.camera_rotation)

    def snapshot(self, elapsed):
        hips = self.clone_mesh.get_socket_location('Hips')
        bones = {bone: xyz(self.clone_mesh.get_socket_location(bone))
                 for bone in ('Hips', 'Head', 'LeftHand', 'RightHand', 'LeftFoot', 'RightFoot')
                 if self.clone_mesh.does_socket_exist(bone)}
        assert all(math.isfinite(value) for values in bones.values() for value in values), 'Non-finite physical bone position'
        return {'t': elapsed, 'phase': self.capture_phase, 'hips_cm': xyz(hips), 'bones_cm': bones,
                'ragdoll_active': self.clone.is_ragdoll_active(),
                'simulating_physics': self.clone_mesh.is_simulating_physics(),
                'pawn_collision_response': str(self.clone_mesh.get_collision_response_to_channel(unreal.CollisionChannel.PAWN)),
                'dead': self.clone.get_editor_property('vitals').is_dead(),
                'actor_position_cm': xyz(self.clone.get_actor_location())}

    def floor_under(self, hips):
        hit = unreal.SystemLibrary.line_trace_single(
            self.world, unreal.Vector(hips[0], hips[1], max(self.initial_hips[2], hips[2]) + 150),
            unreal.Vector(hips[0], hips[1], self.initial_foot_z - 500),
            unreal.TraceTypeQuery.ECC_VISIBILITY, False, [self.clone, self.pawn], unreal.DrawDebugTrace.NONE)
        assert hit, 'No actual world floor found beneath ragdoll'
        values = hit.to_tuple()
        point, normal = values[5], values[7]
        assert normal.z >= .7, 'Expected an upward-facing supporting world floor'
        return {'point_cm': xyz(point), 'normal': xyz(normal),
                'actor': values[9].get_name() if values[9] else None}

    def finalize_frame(self):
        if not self.pending_frame:
            return True
        path = Path(self.pending_frame['file'])
        if not path.is_file() or path.stat().st_size == 0:
            return False
        self.frames.append(self.pending_frame)
        self.pending_frame = None
        return True

    def capture_frame(self, sample):
        if not self.finalize_frame() or sample['t'] + 1e-6 < self.next_frame_t:
            return
        self.next_frame_t = (math.floor(sample['t'] * 12) + 1) / 12.0
        path = self.record_dir / ('frame_%04d.png' % len(self.frames))
        self.pending_frame = {'file': str(path), **sample}
        self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(960, 540, str(path)))

    def stage_tick(self):
        enemies = self.pause_other_enemies()
        if self.clone is None:
            source = next((enemy for enemy in enemies
                           if enemy.get_enemy_brain().get_editor_property('role') == unreal.NLEnemyRole.SWORD_DISCIPLE), None)
            if source:
                self.spawn_clone(source)
            return
        assert self.valid(self.clone), 'Temporary clone disappeared before cleanup'
        self.apply_camera()
        if self.capture_phase == 'settle_standing':
            if self.now() - self.warmup_start < .3:
                return
            self.record_start = self.now()
            self.capture_phase = 'standing'
        elapsed = self.now() - self.record_start
        sample = self.snapshot(elapsed)
        if self.last_sample_time is None or elapsed > self.last_sample_time + 1e-6:
            if self.last_sample_time is not None:
                sample['world_tick_delta_seconds'] = elapsed - self.last_sample_time
            self.samples.append(sample)
            self.last_sample_time = elapsed
        self.capture_frame(sample)
        if self.capture_phase == 'standing' and elapsed >= 1.0:
            self.initial_hips = sample['hips_cm']
            self.report['standing_snapshot'] = sample
            self.death_time = elapsed
            result = self.resolve(self.pawn, self.clone, self.lethal_fixture, 'explicit_lethal_resolver_fixture_unowned_clone')
            assert result.target_defeated and self.clone.get_editor_property('vitals').is_dead(), 'Native resolver must cause real death'
            self.capture_phase = 'falling'
        elif self.capture_phase == 'falling' and elapsed - self.death_time >= 3.0:
            self.report['fallen_snapshot'] = sample
            self.report['supporting_floor'] = self.floor_under(sample['hips_cm'])
            self.clone.reset_for_encounter()
            self.clone.get_enemy_brain().set_component_tick_enabled(False)
            self.reset_time = elapsed
            self.capture_phase = 'reset'
        elif self.capture_phase == 'reset' and elapsed - self.reset_time >= .75:
            if not self.finalize_frame():
                return
            self.report['reset_snapshot'] = sample
            self.complete_capture()

    def complete_capture(self):
        fall = [row for row in self.samples if row['phase'] == 'falling']
        assert fall, 'No fall samples'
        final = self.report['fallen_snapshot']
        restored = self.report['reset_snapshot']
        floor_z = self.report['supporting_floor']['point_cm'][2]
        tail = [row['hips_cm'][2] for row in fall if row['t'] >= final['t'] - .3]
        dt = [row['world_tick_delta_seconds'] for row in fall if 'world_tick_delta_seconds' in row]
        active = [row for row in fall if row['ragdoll_active'] and row['simulating_physics']]
        self.report['measurements'] = {
            'ragdoll_game_seconds': final['t'] - self.death_time,
            'world_tick_count_during_fall': len(fall), 'mean_world_tick_delta_seconds': sum(dt) / len(dt) if dt else None,
            'max_world_tick_delta_seconds': max(dt) if dt else None,
            'pelvis_drop_cm': self.initial_hips[2] - final['hips_cm'][2],
            'pelvis_above_support_cm': final['hips_cm'][2] - floor_z,
            'final_pelvis_vertical_range_cm': max(tail) - min(tail) if tail else None,
            'maximum_horizontal_pelvis_travel_cm': max(math.hypot(row['hips_cm'][0] - self.initial_hips[0],
                row['hips_cm'][1] - self.initial_hips[1]) for row in fall),
        }
        encounter = self.director.get_active_encounter()
        same_progress = (self.progression() == self.baseline_progression
                         and encounter.get_defeated_count() == self.baseline_defeats
                         and self.director.get_completed_stage_count() == self.baseline_completed
                         and str(self.director.get_stage_status(self.director.get_active_stage_id())) == self.baseline_stage)
        pawn_ignore = str(unreal.CollisionResponse.IGNORE)
        self.report['checks'] = {
            'real_saved_blueprint_physics_override': bool(self.report['clone_fixture']['physics_asset'])
                and self.report['clone_fixture']['body_setups'] >= 5 and self.report['clone_fixture']['constraints'] >= 4,
            'standing_frame_captured': any(row['phase'] == 'standing' and not row['dead'] for row in self.frames),
            'native_ragdoll_and_real_physics_observed': len(active) >= 150,
            'recorded_three_seconds_of_world_physics': final['t'] - self.death_time >= 3.0,
            'sixty_hz_world_tick_samples': len(fall) >= 175 and bool(dt)
                and abs(sum(dt) / len(dt) - 1.0 / 60.0) < .002,
            'hips_physically_fell': self.initial_hips[2] - final['hips_cm'][2] > 20,
            'actual_floor_supports_ragdoll': -25 <= final['hips_cm'][2] - floor_z <= 110,
            'landing_is_stable': bool(tail) and max(tail) - min(tail) < 20,
            'ragdoll_does_not_explode': self.report['measurements']['maximum_horizontal_pelvis_travel_cm'] < 1000,
            'corpse_ignores_player_capsule': bool(active) and all(row['pawn_collision_response'] == pawn_ignore for row in active),
            'fall_frames_show_measured_bone_changes': sum(row['phase'] == 'falling' and row['ragdoll_active']
                and abs(row['hips_cm'][2] - self.initial_hips[2]) > 20 for row in self.frames) >= 12,
            'reset_stops_simulation_and_revives': not restored['ragdoll_active'] and not restored['simulating_physics'] and not restored['dead'],
            'reset_restores_standing_hips': abs(restored['hips_cm'][2] - self.initial_hips[2]) < 15,
            'reset_frame_captured': any(row['phase'] == 'reset' and not row['dead'] for row in self.frames),
            'clone_never_changes_real_level_progression': same_progress and not encounter.owns_enemy(self.clone),
            'recorded_frames': len(self.frames) >= 45,
        }
        self.report['recorded_game_seconds'] = self.samples[-1]['t']
        self.report['frame_count'] = len(self.frames)
        self.finish()

    def finish(self, error=None):
        if self.world and self.valid(self.world):
            unreal.GameplayStatics.set_global_time_dilation(self.world, 1.0)
        if self.clone and self.valid(self.clone):
            self.clone.destroy_actor()
        self.clone = self.clone_mesh = None
        self.lethal_fixture = None
        super().finish(error)

    def cleanup(self):
        try:
            super().cleanup()
        finally:
            if self.fixed_rate_changed:
                self.engine.set_editor_property('use_fixed_frame_rate', self.old_fixed_rate[0])
                self.engine.set_editor_property('fixed_frame_rate', self.old_fixed_rate[1])
                self.fixed_rate_changed = False
            for name, value in self.old_console.items():
                unreal.SystemLibrary.execute_console_command(None, '%s %s' % (name, value))
        loot_directory = (ROOT / 'Saved/SaveGames/NilinOrdinaryLoot').resolve()
        removed = []
        for run_id in self.run_ids:
            assert re.fullmatch('[0-9a-f]{32}', run_id)
            target = loot_directory / (run_id.upper() + '.nllo')
            assert target.resolve().parent == loot_directory
            for path in (target, Path(str(target) + '.tmp')):
                if not path.exists():
                    continue
                assert str(path.resolve()) not in self.protected_saves
                blob = path.read_bytes()
                assert len(blob) >= 44
                magic, version = struct.unpack_from('<II', blob)
                owner = ''.join('%08x' % part for part in struct.unpack_from('<4I', blob, 8))
                assert magic == 0x4E4C4F4C and version == 1 and owner == run_id
                assert zlib.crc32(blob[:-4]) == struct.unpack_from('<I', blob, len(blob) - 4)[0]
                path.unlink()
                removed.append(str(path))
        self.isolation['removed_only_exact_test_loot_paths'] = removed
        current = save_hashes()
        unchanged = all(current.get(path) == digest for path, digest in self.protected_saves.items())
        unexpected = sorted(set(current) - set(self.protected_saves))
        self.isolation.update(protected_save_hashes_unchanged=unchanged, unexpected_new_save_paths=unexpected,
                              transient_fixed_frame_rate_restored=True)
        self.report['checks']['user_saves_unchanged'] = unchanged
        self.report['checks']['only_exact_fixture_save_paths_created_and_removed'] = not unexpected
        assert unchanged and not unexpected, 'User-save isolation mismatch; preserve unknown files for review'


demo = OptimizationRagdollDemo()
