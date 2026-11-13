"""Record native rock-caster AI on the saved map from an observer camera."""
import json
from pathlib import Path
import time
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
output = project / 'Docs/Gameplay/RangedDemo1104'
helper = project / 'Scripts/Editor/SlashRevision1104/runtime_motion.py'
context = {'__name__': 'ranged_demo_helper', '__file__': str(helper)}
exec(compile(helper.read_text(encoding='utf-8-sig').replace('motion_probe = MotionProbe()', ''), str(helper), 'exec'), context)


class RangedDemo(context['MotionProbe']):
    def save(self):
        self.report['elapsed_seconds'] = time.monotonic() - self.started
        self.report['fixture_isolation'] = self.isolation
        (output / 'Capture.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.last_save = time.monotonic()

    def bootstrap(self):
        super().bootstrap()
        if self.phase != 'stage_active':
            return
        self.skip_damage = self.create_fixture('RangedDemoEntry', 999)
        self.contact_times = {}
        self.route_index = 0
        self.record_start = None
        self.pending_frame = None
        self.projectile_ids = set()
        self.caster_ids = set()
        self.record_dir = output / ('Frames_' + self.uid)
        self.record_dir.mkdir()
        self.report['scope'] = 'Saved main level, native R01 AI. Earlier encounters cleared with a test hit fixture. Stationary player on the authored route and a fixed observer camera.'

    def stage_tick(self):
        stage_id = ('Aoutside', 'Ainside', 'R01')[self.route_index]
        state = self.director.get_stage_status(stage_id)
        assert state != unreal.NLLevelStageState.FAILED, str(self.director.get_failure_reason())
        if self.route_index < 2:
            if state == unreal.NLLevelStageState.COMPLETED:
                self.route_index += 1
                self.move(self.stage_defs[self.route_index].get_editor_property('entry_transform').translation)
                return
            for enemy in self.owned():
                key = self.guid(enemy.combat_identity.get_runtime_id())
                if self.now() - self.contact_times.get(key, -1000) >= .4:
                    self.contact_times[key] = self.now()
                    self.resolve(self.pawn, enemy, self.skip_damage, 'setup_skip_prior_encounters')
            return

        enemies = self.owned(pause=False)
        if self.record_start is None:
            for enemy in enemies:
                enemy.set_lab_paused(True)
            if len(enemies) < 2:
                return
            self.prepare_camera(enemies)
        self.record(enemies)

    def prepare_camera(self, enemies):
        for enemy in enemies:
            assert enemy.get_enemy_brain().get_editor_property('hold_ranged_position')
            self.caster_ids.add(self.guid(enemy.combat_identity.get_runtime_id()))
        self.move(unreal.Vector(0, 4527.5, 730))
        self.pawn.lower_mirror()
        self.vitals.restore_resource_preset(100, 100)
        self.movement.disable_movement()
        self.pawn.set_actor_tick_enabled(False)
        for component in self.pawn.get_components_by_class(unreal.PrimitiveComponent):
            component.set_hidden_in_game(True)
        self.camera_position = unreal.Vector(-450, 3900, 1225)
        self.camera_rotation = unreal.MathLibrary.find_look_at_rotation(
            self.camera_position, unreal.Vector(-570, 4630, 920))
        self.pawn.player_camera.set_field_of_view(86)
        self.apply_camera()
        unreal.SystemLibrary.execute_console_command(self.world, 'showhud')
        unreal.SystemLibrary.execute_console_command(self.world, 't.MaxFPS 60')
        unreal.GameplayStatics.set_global_time_dilation(self.world, .25)
        self.record_start = self.now()
        for enemy in enemies:
            enemy.set_lab_paused(False)
        self.report['casters'] = [enemy.get_class().get_name() for enemy in enemies]
        self.report['caster_positions_cm'] = [self.xyz(enemy.get_actor_location()) for enemy in enemies]

    def apply_camera(self):
        transform = unreal.Transform(location=self.camera_position, rotation=self.camera_rotation)
        self.pawn.player_camera.set_world_transform(transform, False, True)
        unreal.GameplayStatics.get_player_controller(self.world, 0).set_control_rotation(self.camera_rotation)

    def record(self, enemies):
        self.apply_camera()
        elapsed = self.now() - self.record_start
        assert len(enemies) == 2 and not self.vitals.is_dead(), 'Unexpected R01 outcome while recording'
        projectiles = []
        for projectile in unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLCombatProjectile):
            if self.valid(projectile) and projectile.get_source_actor() in enemies:
                self.projectile_ids.add(self.guid(projectile.get_attack_instance_id()))
                projectiles.append(self.xyz(projectile.get_actor_location()))
        if self.pending_frame:
            if not Path(self.pending_frame['file']).is_file():
                return
            self.frames.append(self.pending_frame)
            self.pending_frame = None
        if elapsed >= 7.3:
            self.report['projectile_count'] = len(self.projectile_ids)
            self.report['health_after'] = self.vitals.get_health()
            self.report['checks'] = {
                'both_live_casters': len(self.caster_ids) == 2,
                'native_projectile_emitted': bool(self.projectile_ids),
                'projectile_visible_in_capture': any(frame['projectiles'] for frame in self.frames),
                'player_hit': self.vitals.get_health() < 100,
                'recorded_frames': len(self.frames) >= 60,
            }
            unreal.GameplayStatics.set_global_time_dilation(self.world, 1.0)
            self.skip_damage = None
            self.finish()
            return
        if self.frames and elapsed - self.frames[-1]['t'] < 1 / 20:
            return
        path = self.record_dir / f'frame_{len(self.frames):04d}.png'
        states = [str(enemy.get_enemy_brain().get_state()) for enemy in enemies]
        self.pending_frame = {'file': str(path), 't': elapsed, 'states': states,
                              'hp': self.vitals.get_health(), 'projectiles': projectiles}
        self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(960, 540, str(path)))


demo = RangedDemo()
