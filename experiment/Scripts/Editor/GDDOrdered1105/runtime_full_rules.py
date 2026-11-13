"""Integrate all 16 saved-map encounter rules at normal game speed in an isolated run.

Stage entries are teleports. Real encounter-owned NPCs are paused and defeated
through the production combat resolver with one labelled 999-damage fixture.
The authored ritual still advances naturally for 240 effective game seconds.
This is an integration rules probe, not a manual or headset playthrough.
"""
import json
import math
import time
from pathlib import Path

import unreal

P = Path(unreal.Paths.project_dir()).resolve()
O = P / 'Docs/Gameplay/GDDOrdered1105'
SOURCE = P / 'Scripts/Editor/SlashRevision1104/runtime_motion.py'
ctx = {'__name__': 'full_rules_motion_helper', '__file__': str(SOURCE)}
exec(compile(SOURCE.read_text(encoding='utf-8-sig').replace('motion_probe = MotionProbe()', ''), str(SOURCE), 'exec'), ctx)

EXPECTED_STAGES = ('Aoutside', 'Ainside', 'R01', 'Bcourt', 'Bexit', 'R02', 'R03',
                   'Cestablish', 'Cinterrupt', 'Csiege', 'Cunseal', 'GM01', 'GM02', 'GM03', 'GM04', 'Boss')
RITUAL_STAGES = ('Cestablish', 'Cinterrupt', 'Csiege', 'Cunseal')
MASTER_IDS = ('GM01', 'GM02', 'GM03', 'GM04')


class FullRulesProbe(ctx['MotionProbe']):
    def __init__(self):
        self.ordinary_dir = P / 'Saved/SaveGames/NilinOrdinaryLoot'
        self.existing_ordinary = {p.name.lower() for p in self.ordinary_dir.glob('*.nllo')}
        super().__init__()

    def save(self):
        self.report['elapsed_seconds'] = time.monotonic() - self.started
        self.report['fixture_isolation'] = self.isolation
        (O / 'FullRulesRuntime.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.last_save = time.monotonic()

    def cleanup(self):
        super().cleanup()
        removed = []
        for run_id in self.run_ids:
            target = self.ordinary_dir / (run_id.upper() + '.nllo')
            assert target.resolve().parent == self.ordinary_dir.resolve()
            assert target.name.lower() not in self.existing_ordinary
            for file in (target, Path(str(target) + '.tmp')):
                if file.exists():
                    assert file.is_file(), str(file)
                    file.unlink()
                    removed.append(str(file))
        self.isolation['ordinary_ledger_cleanup'] = removed

    def bootstrap(self):
        super().bootstrap()
        if self.phase != 'stage_active':
            return
        assert tuple(str(s.stage_id) for s in self.stage_defs) == EXPECTED_STAGES
        assert abs(unreal.GameplayStatics.get_global_time_dilation(self.world) - 1.0) < 1.e-6
        self.loot = next(x for x in unreal.ObjectIterator(unreal.NLOrdinaryLootSubsystem)
                         if self.valid(x) and x.get_outer() == self.world)
        self.master_rewards = next(x for x in unreal.ObjectIterator(unreal.NLMasterRewardSubsystem)
                                   if self.valid(x) and x.get_outer() == self.world)
        assert self.loot.get_processed_count() == 0 and self.loot.get_consecutive_misses() == 0
        # Keep the authored production 20% rule. No probability or random-seed fixture is installed.
        self.clear_hit = self.create_fixture('FullRulesOwnedDefeat', 999)
        self.route_index = 0
        self.current_row = None
        self.bound_encounters = set()
        self.defeat_ids = set()
        self.event_ids = set()
        self.ordinary_events = []
        self.objective = None
        self.ritual_started = None
        self.ritual_completed = None
        self.ritual_last = None
        self.ritual_effective_seconds = 0.0
        self.last_sample = -1000.0
        self.report['deadline_seconds'] = 600
        self.report['scope'] = [
            'Actual saved L_NilinGameplayV01 with all 16 authored stages, wave assets, progression, ordinary supplies and four fixed master rewards.',
            'Unique Test.Level01 identity. Only the original LevelId is changed temporarily; the stage array, waves, timing, objective percentage and source assets are never rewritten.',
            'Stage-entry teleports and a position near the ritual are explicit setup. AI is paused and at most four real owned NPCs per callback are defeated via a labelled 999-damage production-resolver contact fixture.',
            'All actual spawn intervals, alive caps, intermissions, dependencies and the ritual 240-effective-second rate remain active at global time dilation 1.',
            'The player stays at full health to retain ordinary/master pickups for inspection. This is a rule integration check, not continuous human combat, difficulty, headset or performance acceptance.'
        ]
        self.report['stage_summaries'] = []
        self.report['setup_placements'] = []
        self.report['owned_defeats'] = []
        self.report['progress_samples'] = []
        self.report['ordinary_events'] = self.ordinary_events
        self.pawn.set_actor_tick_enabled(False)
        self.movement.stop_movement_immediately()
        self.movement.disable_movement()
        assert self.vitals.get_health() == self.vitals.get_max_health()
        self.place_stage(self.stage_defs[0])
        unreal.SystemLibrary.execute_console_command(self.world, 't.MaxFPS 60')

    def place_stage(self, stage):
        """Enter the trigger for this teleport-only fixture, with room for authored spawns."""
        entry = stage.entry_transform.translation
        center = stage.trigger_center
        extent = stage.trigger_extent
        points = [point.spawn_transform.translation for point in stage.spawn_points]

        def inside(point):
            return all(abs(a - b) <= limit for a, b, limit in zip(self.xyz(point), self.xyz(center), self.xyz(extent)))

        def clearance(point):
            return min(((point - other).length() for other in points), default=float('inf'))

        if inside(entry) and clearance(entry) >= 300.0:
            selected = entry
            reason = 'authored_entry_inside_trigger_and_clear'
        elif clearance(center) >= 300.0:
            selected = center
            reason = 'entry_outside_trigger_use_center' if not inside(entry) else 'entry_near_spawn_use_center'
        else:
            # Fallback remains inside the authored trigger; never rewrite the trigger or spawn points.
            candidates = [unreal.Vector(center.x + extent.x * x, center.y + extent.y * y, center.z)
                          for x in (-.7, -.4, 0, .4, .7) for y in (-.7, -.4, 0, .4, .7)]
            selected = max(candidates, key=clearance)
            reason = 'safe_interior_grid_for_fixture'
        assert inside(selected) and clearance(selected) >= 300.0, {
            'fixture_error': 'No teleport setup point is inside the trigger and at least 300cm from authored spawns',
            'stage': str(stage.stage_id), 'entry': self.xyz(entry), 'center': self.xyz(center),
            'extent': self.xyz(extent), 'best_clearance_cm': clearance(selected)}
        self.move(selected)
        self.movement.disable_movement()
        self.report['setup_placements'].append({
            'stage': str(stage.stage_id), 'game_time': self.now(), 'reason': reason,
            'authored_entry_cm': self.xyz(entry), 'trigger_center_cm': self.xyz(center),
            'trigger_extent_cm': self.xyz(extent), 'fixture_position_cm': self.xyz(selected),
            'inside_trigger': inside(selected), 'minimum_spawn_distance_cm': clearance(selected)})

    def bind_encounter(self, encounter):
        key = encounter.get_path_name()
        if key in self.bound_encounters:
            return
        self.bound_encounters.add(key)
        stage_id = str(self.stage_defs[self.route_index].stage_id)
        row = self.current_row

        def defeated(enemy, runtime_id, ordinal):
            assert row is self.current_row and stage_id == row['stage'], 'Stale defeat callback'
            identity = self.guid(runtime_id)
            assert identity not in self.defeat_ids, 'Duplicate owned defeat notification'
            self.defeat_ids.add(identity)
            wave = encounter.get_wave_index()
            event = f'{self.test_level}.{stage_id}.Wave.{wave + 1:02d}.Spawn.{ordinal:04d}'
            assert event not in self.event_ids, 'Duplicate stable reward event'
            self.event_ids.add(event)
            master_body = stage_id in MASTER_IDS and wave == encounter.get_wave_count() - 1 \
                and ordinal == encounter.get_planned_count() - 1
            eligible = stage_id != 'Boss' and not master_body
            item = {'stage': stage_id, 'wave': wave, 'ordinal': ordinal, 'runtime_id': identity,
                    'event': event, 'ordinary_eligible': eligible, 'game_time': self.now()}
            self.report['owned_defeats'].append(item)
            row['defeats'].append(item)
            if eligible:
                assert self.loot.has_processed_event(event), 'A real ordinary defeat did not commit its loot roll'
                self.ordinary_events.append(event)
            else:
                assert not self.loot.has_processed_event(event), 'Master/Boss body consumed an ordinary roll'
            assert 0 <= self.loot.get_consecutive_misses() <= 4

        encounter.get_editor_property('on_enemy_defeated').add_callable(defeated)
        self.bindings.append((encounter, 'on_enemy_defeated', defeated))

    def begin_stage_row(self, stage):
        stage_id = str(stage.stage_id)
        self.current_row = {'stage': stage_id, 'entered_game_time': self.now(), 'defeats': [],
                            'waves_observed': [], 'loot_before': self.loot.get_processed_count(),
                            'misses_before': self.loot.get_consecutive_misses(), 'planned_candidates': 0,
                            'max_alive_observed': 0, 'failed_spawn_attempts': 0}
        self.report['stage_summaries'].append(self.current_row)

    def observe_objective(self, stage_id):
        if stage_id not in RITUAL_STAGES:
            return
        objective = self.director.get_active_objective()
        if not objective:
            return
        assert abs(objective.effective_rescue_seconds - 240.0) < .01
        if self.objective is None:
            self.objective = objective
            self.ritual_started = self.now()
        assert objective == self.objective, 'The four phases must share the authored ritual'
        progress = float(objective.get_rescue_progress())
        if self.ritual_last is not None:
            assert progress >= self.ritual_last - .001, 'Ritual progress rolled backward without a retry'
            self.ritual_effective_seconds += (progress - self.ritual_last) * 2.4
        else:
            self.ritual_effective_seconds = progress * 2.4
        self.ritual_last = progress
        goal = objective.get_actor_location()
        # A near-ritual standing position is setup only. Objective progress uses its native clock.
        position = unreal.Vector(goal.x + 200, goal.y - 120, goal.z + 90)
        if (self.pawn.get_actor_location() - position).length() > 5:
            self.move(position)
            self.movement.disable_movement()

    def stage_tick(self):
        assert not self.vitals.is_dead(), 'Player unexpectedly died in the paused-AI rule fixture'
        assert abs(unreal.GameplayStatics.get_global_time_dilation(self.world) - 1.0) < 1.e-6
        stage = self.stage_defs[self.route_index]
        stage_id = str(stage.stage_id)
        if self.current_row is None:
            self.begin_stage_row(stage)
        row = self.current_row
        state = self.director.get_stage_status(stage_id)
        assert state != unreal.NLLevelStageState.FAILED, str(self.director.get_failure_reason())
        if state in (unreal.NLLevelStageState.AVAILABLE, unreal.NLLevelStageState.LOCKED):
            assert self.now() - row['entered_game_time'] < 15.0, {
                'fixture_error': 'Stage did not enter its warning within 15 game seconds of trigger placement',
                'stage': stage_id, 'state': str(state), 'position_cm': self.xyz(self.pawn.get_actor_location()),
                'placement': self.report['setup_placements'][-1],
                'entry_block_reason': str(self.director.get_entry_block_reason()),
                'missing_seals': list(map(str, self.director.get_missing_seal_ids(stage_id)))}
        self.observe_objective(stage_id)
        encounter = self.director.get_active_encounter()
        if encounter and str(self.director.get_active_stage_id()) == stage_id:
            self.bind_encounter(encounter)
            wave = encounter.get_wave_index()
            if wave >= 0 and wave not in row['waves_observed']:
                row['waves_observed'].append(wave)
            row['planned_candidates'] = encounter.get_planned_count()
            row['max_alive_observed'] = max(row['max_alive_observed'], encounter.get_alive_count())
            row['failed_spawn_attempts'] = encounter.get_failed_spawn_count()
            if wave >= 0:
                assert encounter.get_alive_count() <= stage.waves[wave].max_alive
            for enemy in self.owned(pause=True)[:4]:
                identity = self.guid(enemy.combat_identity.get_runtime_id())
                if identity in self.defeat_ids:
                    continue
                result = self.resolve(self.pawn, enemy, self.clear_hit, 'full_rules_owned_999_fixture')
                assert result.outcome in (unreal.NLCombatOutcome.HIT, unreal.NLCombatOutcome.IGNORED), str(result.outcome)
        if self.now() - self.last_sample >= 2:
            self.last_sample = self.now()
            self.report['progress_samples'].append({
                'stage': stage_id, 'state': str(state), 'game_time': self.now(),
                'total_defeats': len(self.defeat_ids), 'loot_processed': self.loot.get_processed_count(),
                'loot_misses': self.loot.get_consecutive_misses(),
                'ritual_progress': self.objective.get_rescue_progress() if self.objective else None})
        if self.director.get_stage_status(stage_id) != unreal.NLLevelStageState.COMPLETED:
            return
        row.update({'completed_game_time': self.now(), 'actual_defeats': len(row['defeats']),
                    'loot_processed': self.loot.get_processed_count(), 'misses_after': self.loot.get_consecutive_misses(),
                    'ordinary_eligible_defeats': sum(x['ordinary_eligible'] for x in row['defeats'])})
        if stage_id in RITUAL_STAGES:
            row['ritual_progress_at_completion'] = self.objective.get_rescue_progress()
            assert abs(row['ritual_progress_at_completion'] - (RITUAL_STAGES.index(stage_id) + 1) * 25) < .01
            # The director may have released its ActiveObjective during the final native callback.
            final_progress = float(self.objective.get_rescue_progress())
            if self.ritual_last is None or final_progress > self.ritual_last:
                self.ritual_effective_seconds += (final_progress - (self.ritual_last or 0.0)) * 2.4
                self.ritual_last = final_progress
            if stage_id == 'Cunseal':
                self.ritual_completed = self.now()
        self.route_index += 1
        self.current_row = None
        if self.route_index == len(self.stage_defs):
            self.final_checks()
            return
        self.place_stage(self.stage_defs[self.route_index])
        self.save()

    def final_checks(self):
        growth = self.progression()
        rewarded = list(growth['event_ids'])
        pending = list(self.loot.get_pending_supplies())
        ordinary_items = [{'event': str(pickup.get_event_id()), 'health': pickup.get_health_amount(),
                           'kind': str(self.loot.get_supply_kind(pickup.get_event_id()))} for pickup in pending]
        masters = []
        for master_id in MASTER_IDS:
            pickup = self.master_rewards.get_pending_reward(master_id)
            masters.append({'master': master_id, 'has_fixed_pickup': self.valid(pickup),
                            'health': pickup.get_health_amount() if self.valid(pickup) else None})
        expected_seals = {'SwordSeal', 'TalismanSeal', 'AlchemySeal', 'WindSeal'}
        seals = set(map(str, self.run.get_collected_seal_ids()))
        native_results = [r for r in self.report['combat_results']
                          if r['origin'] == 'full_rules_owned_999_fixture' and r['target_defeated']]
        valid_items = all((item['health'] == 10 and 'SMALL' in item['kind'])
                          or (item['health'] == 20 and 'LARGE' in item['kind']) for item in ordinary_items)
        self.report['checks'] = {
            'all_16_authored_stages_completed': self.director.get_completed_stage_count() == 16
                and all(self.director.get_stage_status(s) == unreal.NLLevelStageState.COMPLETED for s in EXPECTED_STAGES),
            'all_four_seals_acquired': seals == expected_seals,
            'growth_reached_level_three': growth['level'] == 3,
            'every_owned_defeat_has_one_native_combat_result': len(native_results) == len(self.defeat_ids),
            'every_owned_defeat_rewards_lingqi_once': len(rewarded) == len(set(rewarded)) == len(self.defeat_ids)
                and set(rewarded) == self.event_ids and math.isclose(growth['ling_qi'], len(self.defeat_ids), abs_tol=.01),
            'ordinary_rolls_exclude_exactly_four_masters_and_boss': self.loot.get_processed_count() == len(self.defeat_ids) - 5
                == len(self.ordinary_events) == len(set(self.ordinary_events)),
            'pity_never_exceeds_four_misses': 0 <= self.loot.get_consecutive_misses() <= 4
                and all(0 <= sample['loot_misses'] <= 4 for sample in self.report['progress_samples']),
            'ordinary_supplies_have_only_ten_or_twenty_health': bool(ordinary_items) and valid_items,
            'four_fixed_master_supplies_remain_twenty_five': all(x['has_fixed_pickup'] and x['health'] == 25 for x in masters),
            'ritual_uses_240_effective_seconds_and_completes_once': self.objective is not None
                and abs(self.ritual_effective_seconds - 240) < .1 and self.objective.is_rescue_completed()
                and self.objective.get_completion_event_count() == 1 and self.objective.get_phase_completion_event_count() == 3,
            'ritual_received_at_least_240_normal_game_seconds': self.ritual_completed is not None
                and self.ritual_completed - self.ritual_started >= 239.5,
            'global_time_dilation_never_changed': abs(unreal.GameplayStatics.get_global_time_dilation(self.world) - 1) < 1.e-6,
        }
        self.report['final'] = {'game_time': self.now(), 'growth': growth, 'seals': sorted(seals),
                                'owned_defeats': len(self.defeat_ids), 'ordinary_rolls': self.loot.get_processed_count(),
                                'ordinary_items': ordinary_items, 'fixed_master_rewards': masters,
                                'ritual_effective_seconds': self.ritual_effective_seconds,
                                'ritual_elapsed_game_seconds': self.ritual_completed - self.ritual_started,
                                'player_health': self.vitals.get_health()}
        self.clear_hit = self.loot = self.master_rewards = self.objective = None
        self.finish()


full_rules_probe = FullRulesProbe()
