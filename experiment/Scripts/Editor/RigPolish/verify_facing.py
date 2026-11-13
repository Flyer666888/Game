"""Observe a real enemy's 180-degree turn and subsequent animation-owned attack.

Only the selected PIE enemy's facing is changed once. No brain state, event,
encounter data, map asset, or attack notification is forced by this probe.
"""
import json
import math
import time
import traceback
from pathlib import Path

import unreal


OUT = Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v01')
REPORT = OUT / 'FacingValidation.json'


def delta_yaw(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def target_yaw(enemy, pawn):
    direction = pawn.get_actor_location() - enemy.get_actor_location()
    return math.degrees(math.atan2(direction.y, direction.x))


class FacingProbe:
    def __init__(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.started = time.monotonic()
        self.phase = 'start'
        self.busy = False
        self.handle = None
        self.enemy = None
        self.previous = None
        self.injected = False
        self.injection_time = None
        self.ending_started = None
        self.owns_pie = False
        self.frames = []
        self.saw_telegraph = False
        self.saw_attack = False
        self.saw_blade_active = False
        self.report = {
            'state': 'starting',
            'scope': 'Actual first-stage sword enemy AI in PIE. One 180-degree facing '
                     'change while waiting; player health protection only. No brain '
                     'state changes, broadcasts, forced notifies, or map saves.',
            'deadline_seconds': 90,
            'expected_turn_rate_deg_s': 150,
            'telegraph_facing_tolerance_degrees': 5,
            'failures': [],
            'health_protection_count': 0,
            'turn_steps_checked': 0,
            'max_observed_turn_rate_deg_s': 0,
            'max_turn_step_excess_degrees': 0,
        }
        self.save()
        self.handle = unreal.register_slate_post_tick_callback(self.tick)

    def save(self):
        self.report['frames'] = self.frames
        self.report['elapsed_wall_seconds'] = time.monotonic() - self.started
        REPORT.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')

    def end(self):
        if self.phase == 'ending':
            return
        self.enemy = None
        self.previous = None
        self.phase = 'ending'
        self.ending_started = time.monotonic()
        self.report['state'] = 'ending'
        self.save()
        if self.owns_pie:
            self.level.editor_request_end_play()
        else:
            self.finish()

    def finish(self):
        self.report['state'] = 'failed' if self.report['failures'] else 'passed'
        self.save()
        self.enemy = None
        self.previous = None
        unreal.unregister_slate_post_tick_callback(self.handle)
        self.handle = None

    def tick(self, delta_seconds):
        if self.busy:
            return
        self.busy = True
        try:
            if self.phase == 'ending':
                if self.editor.get_game_world() is None:
                    self.finish()
                elif time.monotonic() - self.ending_started > 10:
                    self.report['failures'].append('PIE did not finish closing within 10 seconds.')
                    self.finish()
                return
            assert time.monotonic() - self.started < 90, 'Facing observation exceeded the 90-second deadline.'
            if self.phase == 'start':
                assert self.editor.get_game_world() is None, 'Run this probe with PIE stopped.'
                self.level.editor_request_begin_play()
                self.owns_pie = True
                self.phase = 'wait'
                return

            world = self.editor.get_game_world()
            if not world:
                return
            pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
            if not pawn:
                return
            vitals = pawn.get_editor_property('vitals')
            assert not vitals.is_dead(), 'The real player target died before health protection.'
            if vitals.get_health() < 70:
                vitals.restore_resource_preset(100, 100)
                self.report['health_protection_count'] += 1
            if self.enemy is None:
                enemies = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NLEnemyCharacter)
                enemies = [enemy for enemy in enemies
                           if unreal.SystemLibrary.is_valid(enemy)
                           and not enemy.get_editor_property('vitals').is_dead()
                           and enemy.get_enemy_brain().get_editor_property('role') != unreal.NLEnemyRole.TALISMAN_CASTER]
                if not enemies:
                    return
                self.enemy = sorted(enemies, key=lambda enemy: enemy.get_name())[0]
                self.report['enemy'] = self.enemy.get_name()
                self.report['enemy_class'] = self.enemy.get_class().get_path_name()
                self.report['state'] = 'waiting_for_real_wait_for_slot'
                unreal.SystemLibrary.execute_console_command(world, 't.IdleWhenNotForeground 0')
                unreal.SystemLibrary.execute_console_command(world, 'Slate.bAllowThrottling 0')

            assert unreal.SystemLibrary.is_valid(self.enemy), 'Selected enemy disappeared.'
            brain = self.enemy.get_enemy_brain()
            state = brain.get_state()
            assert state not in (unreal.NLEnemyState.DEAD, unreal.NLEnemyState.DESPAWN), 'Selected enemy ended before attack verification.'
            now = unreal.GameplayStatics.get_time_seconds(world)
            aim_yaw = target_yaw(self.enemy, pawn)
            actor_yaw = self.enemy.get_actor_rotation().yaw
            blade_state = self.enemy.get_editor_property('blade').get_swing_state()
            row = {
                'world_time': now,
                'state': str(state),
                'actor_yaw': actor_yaw,
                'target_yaw': aim_yaw,
                'facing_error_degrees': abs(delta_yaw(actor_yaw, aim_yaw)),
                'attack_window': brain.is_attack_window_active(),
                'blade_state': str(blade_state),
                'player_health': vitals.get_health(),
                'injection': False,
            }

            if not self.injected and state == unreal.NLEnemyState.WAIT_FOR_SLOT:
                before_yaw = actor_yaw
                backwards = (aim_yaw + 360.0) % 360.0 - 180.0
                self.enemy.set_actor_rotation(unreal.Rotator(yaw=backwards), True)
                self.injected = True
                self.injection_time = now
                row['actor_yaw'] = self.enemy.get_actor_rotation().yaw
                row['facing_error_degrees'] = abs(delta_yaw(row['actor_yaw'], aim_yaw))
                row['injection'] = True
                self.report['injection'] = {'world_time': now, 'before_yaw': before_yaw,
                                            'after_yaw': row['actor_yaw'], 'target_yaw': aim_yaw}
                self.report['state'] = 'observing_turn_and_attack'
                assert row['facing_error_degrees'] >= 179.5, 'The test did not initialize a 180-degree turn.'
            elif self.injected:
                row['seconds_after_injection'] = now - self.injection_time
                if self.previous is not None and not self.saw_telegraph:
                    game_delta = now - self.previous['world_time']
                    yaw_step = abs(delta_yaw(actor_yaw, self.previous['actor_yaw']))
                    if game_delta > 0.0001:
                        # One small final alignment can occur when a frame crosses
                        # from Brain waiting rotation to character telegraph rotation.
                        boundary_tolerance = 3.1 if state == unreal.NLEnemyState.TELEGRAPH else .25
                        allowance = 150.0 * game_delta + boundary_tolerance
                        excess = max(0.0, yaw_step - 150.0 * game_delta)
                        row['yaw_step_degrees'] = yaw_step
                        row['game_delta_seconds'] = game_delta
                        self.report['turn_steps_checked'] += 1
                        self.report['max_observed_turn_rate_deg_s'] = max(
                            self.report['max_observed_turn_rate_deg_s'], yaw_step / game_delta)
                        self.report['max_turn_step_excess_degrees'] = max(
                            self.report['max_turn_step_excess_degrees'], excess)
                        assert yaw_step <= allowance, 'Facing snapped %.2f degrees in %.4f game seconds.' % (yaw_step, game_delta)
                if state == unreal.NLEnemyState.TELEGRAPH and not self.saw_telegraph:
                    self.saw_telegraph = True
                    self.report['telegraph_entry'] = dict(row)
                    assert row['facing_error_degrees'] <= 5.0, 'Telegraph began before the enemy faced the target.'
                    assert now - self.injection_time >= 1.10, 'The 180-degree turn completed implausibly quickly.'
                if state == unreal.NLEnemyState.ATTACK:
                    self.saw_attack = True
                    if 'attack_observed' not in self.report:
                        self.report['attack_observed'] = dict(row)
                if blade_state == unreal.NLBladeSwingState.SWING_ACTIVE:
                    self.saw_blade_active = True
                    self.report['blade_swing_active_observed'] = dict(row)

            self.frames.append(row)
            self.previous = row
            if self.injected and self.saw_attack and self.saw_blade_active:
                assert self.saw_telegraph, 'The observer missed the actual telegraph phase.'
                assert self.report['turn_steps_checked'] >= 3, 'Insufficient samples to verify continuous rotation.'
                self.report['checks'] = {'single_180_degree_injection': True, 'continuous_turn': True,
                                         'faces_target_before_telegraph': True,
                                         'real_brain_attack_observed': True,
                                         'animation_owned_blade_swing_observed': True}
                self.end()
            elif len(self.frames) % 120 == 0:
                self.save()
        except Exception:
            self.report['failures'].append(traceback.format_exc())
            self.end()
        finally:
            self.busy = False


facing_probe = FacingProbe()
