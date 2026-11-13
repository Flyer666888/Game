"""Run the proven encounter probe only through the two live R01 rock casters.

The original integration script is loaded as class definitions without executing
its global auto-start. Prior encounters end only through real resolver damage.
"""
import ast
import math
import time
import traceback
from pathlib import Path

import unreal


SOURCE = Path(r'D:\game design\experiment\Scripts\Editor\Gameplay\runtime_encounter_recovery_v01.py')
parsed = ast.parse(SOURCE.read_text(encoding='utf-8'), filename=str(SOURCE))
parsed.body = [node for node in parsed.body
               if isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef))]
base_context = {'__name__': 'rig_polish_encounter_probe', '__file__': str(SOURCE)}
exec(compile(parsed, str(SOURCE), 'exec'), base_context)
BaseIntegration = base_context['EncounterRecoveryIntegration']


class RangedPresentationProbe(BaseIntegration):
    OUT = Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v01\RangedValidation.json')
    DEADLINE_SECONDS = 180
    EXPECTED_CAST = '/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Cast_Talisman_Upright_v01.Wuxia_Cast_Talisman_Upright_v01'

    def __init__(self):
        super().__init__()
        self.report['kind'] = 'Real PIE R01 upright-cast / stationary-position validation'
        self.report['scope'] = [
            'Actual saved Gameplay V01 map and its first three encounter regions.',
            'The first eight enemies are defeated through the real combat resolver with an isolated test definition.',
            'R01 real caster AI runs for 12 game seconds; enemies remain alive when this probe ends.',
            'Checks runtime upright casting animation, facing before warning, real projectiles, and stationary rock positions.',
            'Setup teleports and automatic player healing isolate presentation; no stage state or delegates are forced.',
            'No map or animation assets are saved. The inherited unique temporary test definitions and only this fresh run ledger are cleaned up.',
        ]
        self.report['perfect_parry'] = {'state': 'not_run_in_focused_probe'}
        self.report['retry'] = {'state': 'not_run_in_focused_probe'}
        self.report['upright_cast'] = {'expected_asset': self.EXPECTED_CAST, 'casters': {}}

    def prepare_services(self, world):
        # The base method reads the existing EncounterConfig beside its normal
        # report. Keep that read path without copying or editing the config.
        output = self.OUT
        self.OUT = BaseIntegration.OUT
        try:
            return super().prepare_services(world)
        finally:
            self.OUT = output

    def guard_probe(self, world):
        # This focused run needs no synthetic guard contact or retry.
        self.phase = 'stage_setup'
        self.report['state'] = 'clearing_real_predecessor_encounters'
        self.save()

    def observe_rock_ai(self, world, encounter, owned):
        upright = self.report['upright_cast']['casters']
        now = self.world_time(world)
        for enemy in owned:
            runtime_id = self.guid_text(enemy.get_editor_property('combat_identity').get_runtime_id())
            configured_cast = enemy.get_editor_property('cast_animation')
            self.require(configured_cast and configured_cast.get_path_name() == self.EXPECTED_CAST,
                         'R01 actual enemy did not load the new upright casting clip',
                         actor=enemy.get_name(), configured_cast=configured_cast.get_path_name() if configured_cast else None)
            item = upright.setdefault(runtime_id, {
                'actor': enemy.get_name(), 'class': enemy.get_class().get_path_name(),
                'configured_cast': configured_cast.get_path_name(), 'observed_upright_cast_playing': False,
                'telegraph_entries': [], 'frames': [], 'last_state': None,
            })
            state = enemy.get_enemy_brain().get_state()
            mesh = enemy.get_component_by_class(unreal.SkeletalMeshComponent)
            instance = mesh.get_anim_instance()
            animation = instance.get_animation_asset() if instance else None
            actual_asset = animation.get_path_name() if animation else None
            direction = self.pawn.get_actor_location() - enemy.get_actor_location()
            target_yaw = math.degrees(math.atan2(direction.y, direction.x))
            yaw = enemy.get_actor_rotation().yaw
            error = abs((yaw - target_yaw + 180.0) % 360.0 - 180.0)
            row = {'game_time': now, 'state': str(state), 'actor_yaw': yaw,
                   'target_yaw': target_yaw, 'facing_error_degrees': error,
                   'animation_asset': actual_asset,
                   'animation_instance': instance.get_class().get_name() if instance else None,
                   'position_cm': self.vec_list(enemy.get_actor_location())}
            item['frames'].append(row)
            if state == unreal.NLEnemyState.TELEGRAPH and item['last_state'] != str(state):
                item['telegraph_entries'].append(dict(row))
                self.require(error <= 5.0, 'R01 cast warning began before facing the player',
                             caster=runtime_id, error_degrees=error)
            if state in (unreal.NLEnemyState.TELEGRAPH, unreal.NLEnemyState.ATTACK) and actual_asset == self.EXPECTED_CAST:
                item['observed_upright_cast_playing'] = True
            item['last_state'] = str(state)

        passed = super().observe_rock_ai(world, encounter, owned)
        if not passed:
            return False
        self.require(len(upright) == 2, 'Did not observe both upright R01 casters')
        for runtime_id, item in upright.items():
            self.require(item['observed_upright_cast_playing'] and item['telegraph_entries'],
                         'Configured upright cast was not actually played', caster=runtime_id)
            self.require(self.report['rock_r01_ai']['casters'][runtime_id]['max_xy_displacement_cm'] <= 5.0,
                         'Fixed rock caster drifted more than five centimetres', caster=runtime_id)
        self.require(self.director.get_completed_stage_count() == 2,
                     'Focused run unexpectedly advanced past the two prerequisite encounters')
        self.require(self.report['total_resolver_defeats'] == len(self.killed_ids) == 8,
                     'Predecessor encounters were not cleared by exactly eight resolved defeats')
        self.report['upright_cast']['success'] = True
        self.report['r01_left_alive'] = encounter.get_alive_count()
        self.report['checks'] = {
            'predecessors_completed_through_resolver': True,
            'both_new_upright_cast_clips_played': True,
            'faced_player_before_cast_warning': True,
            'both_casters_emitted_actual_projectiles': True,
            'both_rock_positions_remained_within_five_cm': True,
        }
        self.finish()
        # The inherited encounter method must return without defeating R01.
        return False

    def tick(self, delta):
        if self.phase != 'ending':
            super().tick(delta)
            return
        if self.busy:
            return
        self.busy = True
        try:
            if self.owns_play and self.editor.get_game_world() is not None:
                self.require(time.monotonic() - self.phase_time < 30, 'PIE did not close before focused-probe cleanup')
                return
            self.cleanup_ledger()
            for path in self.fixture_paths:
                self.require(unreal.EditorAssetLibrary.delete_asset(path), 'Cannot remove temporary test definition', path=path)
            self.fixture_paths.clear()
            self.report['success'] = (not self.report['failures']
                                      and self.report['rock_r01_ai'].get('success', False)
                                      and self.report['upright_cast'].get('success', False)
                                      and self.report.get('r01_left_alive') == 2)
            self.report['state'] = 'passed' if self.report['success'] else 'failed'
            self.phase = 'finished'
            self.save()
            if self.handle is not None:
                unreal.unregister_slate_post_tick_callback(self.handle)
                self.handle = None
        except Exception:
            self.report['failures'].append({'error': traceback.format_exc(), 'phase': self.phase})
            self.report['success'] = False
            self.report['state'] = 'failed'
            self.phase = 'finished'
            self.save()
            if self.handle is not None:
                unreal.unregister_slate_post_tick_callback(self.handle)
                self.handle = None
        finally:
            self.busy = False


ranged_presentation_probe = RangedPresentationProbe()
ranged_presentation_probe.start()
