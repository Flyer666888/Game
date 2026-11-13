"""Capture genuine R01 early casts and random volleys in a temporary PIE profile.

Earlier stages are cleared by explicit labelled damage fixtures, not by a human
playthrough. No map/Blueprint is saved. The existing runtime helper owns the
temporary level/run identity, transient attack assets and exact-path cleanup.
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
OUTPUT = ROOT / 'Docs/Gameplay/Optimization1111/RangedDemo'
SOURCE = ROOT / 'Scripts/Editor/RangedDemo1104/capture_ranged_demo.py'
OUTPUT.mkdir(parents=True, exist_ok=True)

# Load classes only: the root editor worker controls when this single PIE probe
# starts. The nested helper also strips its own legacy auto-start constructors.
legacy = SOURCE.read_text(encoding='utf-8-sig')
assert legacy.count('demo = RangedDemo()') == 1
base_context = {'__name__': 'optimization1111_ranged_helper', '__file__': str(SOURCE)}
exec(compile(legacy.replace('demo = RangedDemo()', ''), str(SOURCE), 'exec'), base_context)
base_context['output'] = OUTPUT


def asset_path(asset):
    return asset.get_path_name() if asset else None


def xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def save_hashes():
    directory = ROOT / 'Saved/SaveGames'
    return {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob('*') if path.is_file()}


class OptimizationRangedDemo(base_context['RangedDemo']):
    def __init__(self):
        self.protected_saves = save_hashes()
        self.old_console = {
            't.MaxFPS': unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS'),
            't.IdleWhenNotForeground': unreal.SystemLibrary.get_console_variable_int_value('t.IdleWhenNotForeground'),
            'Slate.bAllowThrottling': unreal.SystemLibrary.get_console_variable_int_value('Slate.bAllowThrottling'),
        }
        self.duration = 8.0
        self.ball_records = {}
        self.volley_records = {}
        self.caster_settings = {}
        self.telegraph_sources = set()
        self.protective_heals = []
        self.next_frame_t = 0.0
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
            'Saved main-level R01 and its two genuine fixed rock talisman disciples; normal AI/director reservations and native swept projectiles.',
            'Aoutside and Ainside are cleared with labelled 999-damage resolver fixtures solely to reach R01; this is not a complete or human playthrough.',
            'Only a temporary Test.Level01 identity is used. No user checkpoint/profile is selected, and no map or Blueprint is saved.',
            'A stationary player remains inside the new combat boundary, roughly 8–12 metres from the casters. Only the observer camera is repositioned.',
            'Protective health restores below 65 HP, if needed, are listed explicitly. Enemy timings, aim, projectile speed, material and volley counts are not overridden.',
            'Capture targets 960x540 at 20 samples per game-second over eight game-seconds with 0.25 time dilation for reliable asynchronous screenshots.',
            'Visibility fields mean visible render component inside the observer frustum; image review is required to judge pixel visibility/occlusion.',
        ]

    def bootstrap(self):
        super().bootstrap()
        if self.phase != 'stage_active':
            return
        self.report['frames'] = self.frames
        self.report['protective_health_restores'] = self.protective_heals
        self.report['capture'] = {'width': 960, 'height': 540, 'target_game_fps': 20,
                                  'duration_game_seconds': self.duration, 'time_dilation': .25,
                                  'frame_directory': str(self.record_dir)}
        self.report['setup_fixture'] = 'Prior-stage resolver damage only; R01 attacks and projectiles are native.'

    def move(self, position):
        # The previous stage's completion removes its boundary before the route
        # teleport. During R01, the observer setup must remain inside its boundary.
        if self.director and self.valid(self.director) and self.director.is_combat_boundary_locked():
            center = self.director.get_combat_boundary_center()
            extent = self.director.get_combat_boundary_extent()
            assert abs(position.x - center.x) < extent.x - 40, 'Setup would cross the X combat wall'
            assert abs(position.y - center.y) < extent.y - 40, 'Setup would cross the Y combat wall'
        super().move(position)

    def prepare_camera(self, enemies):
        super().prepare_camera(enemies)
        # Existing helper setup moves to this route position without sweeping or
        # removing any walls. Verify containment after that move as well.
        center = self.director.get_combat_boundary_center()
        extent = self.director.get_combat_boundary_extent()
        pawn_position = self.pawn.get_actor_location()
        assert self.director.is_combat_boundary_locked(), 'R01 boundary must remain enabled'
        assert abs(pawn_position.x - center.x) < extent.x - 40
        assert abs(pawn_position.y - center.y) < extent.y - 40
        self.report['boundary_setup'] = {
            'locked': True, 'center_cm': xyz(center), 'extent_cm': xyz(extent),
            'player_position_cm': xyz(pawn_position), 'player_inside_with_capsule_clearance': True,
            'boundary_disabled_for_fixture': False,
        }
        for enemy in enemies:
            brain = enemy.get_enemy_brain()
            attack = enemy.get_editor_property('talisman_attack')
            source_id = self.guid(enemy.combat_identity.get_runtime_id())
            self.caster_settings[source_id] = {
                'source_id': source_id, 'actor_name': enemy.get_name(), 'class': enemy.get_class().get_path_name(),
                'position_cm': xyz(enemy.get_actor_location()),
                'initial_distance_2d_cm': self.distance_2d(enemy.get_actor_location(), pawn_position),
                'hold_ranged_position': brain.get_editor_property('hold_ranged_position'),
                'projectile_speed_cm_s': float(brain.get_editor_property('projectile_speed')),
                'warning_seconds': float(brain.get_telegraph_presentation_duration()),
                'volley_min': int(attack.get_editor_property('minimum_volley_projectiles')),
                'volley_max': int(attack.get_editor_property('maximum_volley_projectiles')),
                'volley_half_spread_degrees': float(attack.get_editor_property('volley_half_spread_degrees')),
                'float_before_hand': attack.get_editor_property('float_before_hand'),
                'talisman_mesh': asset_path(attack.get_editor_property('talisman_mesh')),
                'golden_orb_material': asset_path(attack.get_editor_property('projectile_material')),
            }
        self.report['caster_settings'] = list(self.caster_settings.values())
        self.report['recording_started_game_time'] = self.record_start

    @staticmethod
    def distance_2d(left, right):
        return math.hypot(float(left.x - right.x), float(left.y - right.y))

    def in_observer_frustum(self, position):
        camera = self.pawn.player_camera
        offset = xyz(position - camera.get_world_location())
        depth = dot(offset, xyz(camera.get_forward_vector()))
        if depth <= 1.0:
            return False
        half_width = depth * math.tan(math.radians(float(camera.get_editor_property('field_of_view')) * .5))
        half_height = half_width / (960.0 / 540.0)
        return (abs(dot(offset, xyz(camera.get_right_vector()))) <= half_width + 10
                and abs(dot(offset, xyz(camera.get_up_vector()))) <= half_height + 10)

    def observe_projectiles(self, enemies, elapsed):
        rows = []
        for projectile in unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLCombatProjectile):
            if not self.valid(projectile):
                continue
            source = projectile.get_source_actor()
            if source not in enemies:
                continue
            actor_name = projectile.get_name()
            attack_id = self.guid(projectile.get_attack_instance_id())
            source_id = self.guid(source.combat_identity.get_runtime_id())
            position = projectile.get_actor_location()
            visual = projectile.get_editor_property('visual')
            component_visible = bool(visual and visual.is_visible()
                                     and not visual.get_editor_property('hidden_in_game'))
            visible = component_visible and self.in_observer_frustum(position)
            # Attack identity is shared by a whole volley. Actor NAME identifies
            # one real ball; never count attack IDs as projectile actors.
            record_key = attack_id + '/' + actor_name
            volley = self.volley_records.setdefault(attack_id, {
                'attack_id': attack_id, 'source_id': source_id, 'source_actor': source.get_name(),
                'first_observed_t': elapsed, 'projectile_actor_names': [],
                'launch_distance_2d_cm': self.distance_2d(source.get_actor_location(), self.pawn.get_actor_location()),
                'source_position_cm': xyz(source.get_actor_location()),
                'player_position_cm': xyz(self.pawn.get_actor_location()), 'visible_frame_indices': [],
            })
            assert volley['source_id'] == source_id, 'An attack identity changed source unexpectedly'
            if actor_name not in volley['projectile_actor_names']:
                volley['projectile_actor_names'].append(actor_name)
            assigned = asset_path(projectile.get_editor_property('visual_material'))
            materials = [asset_path(visual.get_material(i)) for i in range(visual.get_num_materials())] if visual else []
            row = {'actor_name': actor_name, 'attack_id': attack_id, 'source_id': source_id,
                   'position_cm': xyz(position), 'assigned_material': assigned,
                   'visual_materials': materials, 'render_component_visible': component_visible,
                   'inside_observer_frustum': visible}
            record = self.ball_records.get(record_key)
            if record is None:
                record = {**row, 'first_observed_t': elapsed, 'last_observed_t': elapsed,
                          'first_position_cm': xyz(position), 'last_position_cm': xyz(position),
                          'distance_sampled_cm': 0.0, 'time_sampled_seconds': 0.0,
                          'speed_samples': 0, 'visible_frame_indices': []}
                self.ball_records[record_key] = record
            else:
                dt = elapsed - record['last_observed_t']
                if dt > 1e-6:
                    distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(xyz(position), record['last_position_cm'])))
                    record['distance_sampled_cm'] += distance
                    record['time_sampled_seconds'] += dt
                    record['speed_samples'] += 1
                    row['measured_speed_cm_s'] = distance / dt
                record['last_observed_t'] = elapsed
                record['last_position_cm'] = xyz(position)
            rows.append(row)
        return rows

    def finalize_pending_frame(self):
        if not self.pending_frame:
            return True
        path = Path(self.pending_frame['file'])
        if not path.is_file() or path.stat().st_size == 0:
            return False
        frame = self.pending_frame
        index = len(self.frames)
        for row in frame['projectile_visuals']:
            if row['inside_observer_frustum']:
                self.ball_records[row['attack_id'] + '/' + row['actor_name']]['visible_frame_indices'].append(index)
                visible_frames = self.volley_records[row['attack_id']]['visible_frame_indices']
                if not visible_frames or visible_frames[-1] != index:
                    visible_frames.append(index)
        self.frames.append(frame)
        self.pending_frame = None
        return True

    def record(self, enemies):
        self.apply_camera()
        elapsed = self.now() - self.record_start
        assert len(enemies) == 2 and not self.vitals.is_dead(), 'Unexpected R01 outcome during capture'
        states = []
        for enemy in enemies:
            state = str(enemy.get_enemy_brain().get_state())
            states.append(state)
            if 'TELEGRAPH' in state:
                self.telegraph_sources.add(self.guid(enemy.combat_identity.get_runtime_id()))
        projectile_rows = self.observe_projectiles(enemies, elapsed)
        if self.vitals.get_health() < 65:
            before = self.vitals.get_health()
            assert self.vitals.restore_resource_preset(100, 100)
            self.protective_heals.append({'t': elapsed, 'before': before, 'after': self.vitals.get_health(),
                                          'scope': 'Explicit recording protection, not gameplay healing.'})
        if not self.finalize_pending_frame():
            return
        if elapsed >= self.duration:
            self.end_recording(elapsed)
            return
        if elapsed + 1e-6 < self.next_frame_t:
            return
        self.next_frame_t = (math.floor(elapsed * 20.0) + 1) / 20.0
        path = self.record_dir / ('frame_%04d.png' % len(self.frames))
        self.pending_frame = {'file': str(path), 't': elapsed, 'states': states,
                              'hp': self.vitals.get_health(), 'projectiles': [row['position_cm'] for row in projectile_rows],
                              'projectile_visuals': projectile_rows,
                              'visible_projectile_actor_names': [row['actor_name'] for row in projectile_rows if row['inside_observer_frustum']],
                              'camera_position_cm': xyz(self.camera_position), 'camera_rotation': str(self.camera_rotation)}
        self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(960, 540, str(path)))

    def end_recording(self, elapsed):
        volleys = list(self.volley_records.values())
        balls = list(self.ball_records.values())
        for volley in volleys:
            volley['projectile_count'] = len(volley['projectile_actor_names'])
        for ball in balls:
            sampled = ball['time_sampled_seconds']
            ball['mean_measured_speed_cm_s'] = ball['distance_sampled_cm'] / sampled if sampled > 0 else None
        speeds = [ball for ball in balls if ball['mean_measured_speed_cm_s'] is not None]
        hits = [row for row in self.report['combat_results'] if row['origin'] == 'engine_physical'
                and row['source_id'] in self.caster_ids and row['target_id'] == self.player_id and row['damage'] > 0]
        sources = {volley['source_id'] for volley in volleys}
        counts = [volley['projectile_count'] for volley in volleys]
        self.report.update(native_projectile_actor_count=len(balls), native_volley_count=len(volleys),
                           projectile_count_definition='Distinct real projectile actor names within each shared attack identity.',
                           native_projectiles=balls, native_volleys=volleys, observed_volley_counts=counts,
                           random_count_variation_observed=len(set(counts)) > 1,
                           early_first_volley_distance_cm={source: min(
                               (v for v in volleys if v['source_id'] == source), key=lambda v: v['first_observed_t'])['launch_distance_2d_cm']
                               for source in sources},
                           visible_frame_count=sum(bool(frame['visible_projectile_actor_names']) for frame in self.frames),
                           native_player_hits=hits, health_after=self.vitals.get_health(),
                           recorded_game_seconds=elapsed, frame_count=len(self.frames),
                           measured_game_sampling_fps=(len(self.frames) - 1) / max(.001, self.frames[-1]['t'] - self.frames[0]['t']) if len(self.frames) > 1 else 0,
                           minimum_frame_t=self.frames[0]['t'] if self.frames else None,
                           maximum_frame_t=self.frames[-1]['t'] if self.frames else None)
        self.report['checks'] = {
            'two_saved_R01_casters': len(self.caster_ids) == 2 and sources == self.caster_ids,
            'native_warning_observed_for_both': self.telegraph_sources == self.caster_ids,
            'attacks_begin_before_player_reaches_melee_distance': bool(volleys) and all(
                distance > 500 for distance in self.report['early_first_volley_distance_cm'].values()),
            'each_warning_emits_multiple_real_actors_with_one_attack_id': bool(volleys) and all(2 <= count <= 4 for count in counts),
            'count_uses_actors_not_volley_IDs': len(balls) == sum(counts) and len(balls) > len(volleys),
            'every_ball_keeps_configured_golden_material': bool(balls) and all(
                ball['assigned_material'] == self.caster_settings[ball['source_id']]['golden_orb_material']
                and ball['assigned_material'] in ball['visual_materials'] for ball in balls),
            'both_use_the_accepted_floating_talisman': all(row['float_before_hand'] and row['talisman_mesh']
                                                         for row in self.caster_settings.values()),
            'measured_flight_speed_matches_current_native_settings': len(speeds) == len(balls) and bool(speeds) and all(
                abs(ball['mean_measured_speed_cm_s'] - self.caster_settings[ball['source_id']]['projectile_speed_cm_s'])
                <= max(20, .05 * self.caster_settings[ball['source_id']]['projectile_speed_cm_s']) for ball in speeds),
            'multiple_ball_volley_in_a_captured_frustum': any(len(frame['visible_projectile_actor_names']) >= 2 for frame in self.frames),
            'native_caster_collision_hits_player': bool(hits),
            'recorded_at_least_eight_game_seconds': elapsed >= 8,
            'recorded_frames': len(self.frames) >= 120,
            'new_combat_boundary_preserved': self.director.is_combat_boundary_locked(),
        }
        self.finish()

    def finish(self, error=None):
        if self.world and self.valid(self.world):
            unreal.GameplayStatics.set_global_time_dilation(self.world, 1.0)
        # The fixture asset belongs to the inherited exact-path cleanup list.
        self.skip_damage = None
        super().finish(error)

    def cleanup(self):
        try:
            super().cleanup()
        finally:
            for name, value in self.old_console.items():
                unreal.SystemLibrary.execute_console_command(None, '%s %s' % (name, value))
        # Ordinary loot was added after the legacy helper. Its run-scoped ledger
        # needs the same exact-ID cleanup, with on-disk ownership checks first.
        loot_directory = (ROOT / 'Saved/SaveGames/NilinOrdinaryLoot').resolve()
        removed_loot = []
        for run_id in self.run_ids:
            assert re.fullmatch('[0-9a-f]{32}', run_id)
            target = loot_directory / (run_id.upper() + '.nllo')
            assert target.resolve().parent == loot_directory
            for path in (target, Path(str(target) + '.tmp')):
                if not path.exists():
                    continue
                assert str(path.resolve()) not in self.protected_saves, 'Never remove a pre-existing ledger'
                blob = path.read_bytes()
                assert len(blob) >= 44, 'Unexpected temporary loot ledger; preserve for review'
                magic, version = struct.unpack_from('<II', blob)
                owner = ''.join('%08x' % part for part in struct.unpack_from('<4I', blob, 8))
                assert magic == 0x4E4C4F4C and version == 1 and owner == run_id, 'Loot ledger does not belong to this fixture'
                assert zlib.crc32(blob[:-4]) == struct.unpack_from('<I', blob, len(blob) - 4)[0], 'Loot ledger checksum mismatch'
                path.unlink()
                removed_loot.append(str(path))
        self.isolation['removed_only_exact_test_loot_paths'] = removed_loot
        current = save_hashes()
        unchanged = all(current.get(path) == digest for path, digest in self.protected_saves.items())
        self.isolation['protected_save_hashes_unchanged'] = unchanged
        self.isolation['unexpected_new_save_paths'] = sorted(set(current) - set(self.protected_saves))
        self.report['checks']['existing_user_save_hashes_unchanged'] = unchanged
        assert unchanged, 'An existing user save changed during the isolated fixture'
        assert not self.isolation['unexpected_new_save_paths'], 'Unexpected save paths remain; do not delete them automatically'
        self.report['checks']['only_temporary_test_saves_created_and_removed'] = True


demo = OptimizationRangedDemo()
