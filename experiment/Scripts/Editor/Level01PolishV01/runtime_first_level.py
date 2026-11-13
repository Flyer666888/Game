"""Isolated LEVEL-01 progression/encounter integration on the saved gameplay map.

The opening probe uses real CharacterMovement and StartDesktopSlash against one
live sword AI. The later rule probe uses explicit ordinary-damage resolver contacts
and stage-entry teleports; it is not a human continuous playthrough or a pacing
benchmark. No stage, death, reward or combat-result delegate is broadcast manually.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import time
import traceback
import uuid

import unreal

P = Path(unreal.Paths.project_dir()).resolve()
O = P / 'Docs/Gameplay/Level01Polish_v01'
MAP = '/Game/ReversedScale/Maps/L_NilinGameplayV01'
STAGE_IDS = ('Aoutside', 'Ainside', 'R01', 'Bcourt', 'Bexit')
COUNTS = (2, 6, 2, 36, 6)


class FirstLevelProbe:
    def __init__(self):
        O.mkdir(parents=True, exist_ok=True)
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self.started = time.monotonic()
        self.phase = 'start'
        self.phase_started = self.started
        self.busy = False
        self.owns_pie = False
        self.uid = uuid.uuid4().hex
        self.test_level = 'Test.Level01.' + self.uid
        self.marker_dir = P / 'Saved/SaveGames/NilinLevelRuns'
        self.ledger_dir = P / 'Saved/SaveGames/NilinMasterRewards'
        self.marker = self.marker_dir / (hashlib.sha1(self.test_level.lower().encode()).hexdigest() + '.nlrun')
        self.existing_ledgers = {p.name.lower() for p in self.ledger_dir.glob('*.nlmr')}
        self.run_ids = set()
        self.fixture_assets = []
        self.editor_director = None
        self.original_level = None
        self.map_hash = None
        self.world = self.pawn = self.director = self.resolver = self.run = None
        self.vitals = self.movement = self.attack_director = None
        self.low_damage = self.death_damage = self.melee = None
        self.target = None
        self.bindings = []
        self.stage_index = 0
        self.stage = None
        self.stages = []
        self.stage_defs = []
        self.last_save = 0.0
        self.contact_times = {}
        self.seen_ids = set()
        self.origin = 'engine_physical'
        self.screenshot_tasks = []
        self.report = {
            'state': 'starting', 'success': False, 'map': MAP, 'deadline_seconds': 600,
            'failures': [], 'checks': {}, 'stages': [], 'retry_attempts': [],
            'combat_results': [], 'physical_opening': {}, 'damage_multiplier': {},
            'threshold': {}, 'fallback': {}, 'mixed_ai': {'state': 'pending'},
            'scope': [
                'Saved gameplay map with temporary Test.Level01 identity; main profile is never used.',
                'Opening movement uses AddMovementInput and real collision/CharacterMovement; attack uses StartDesktopSlash and native blade sweeps against one live sword AI.',
                'Opening automation is not human input. Other opening enemies are paused to isolate the probe.',
                'Later stage entries are explicit teleports and most AI is paused. Defeats use the unchanged ordinary player melee attack definition through genuine resolver contacts.',
                'The multiplier probe uses an explicitly labelled 10-damage fixture, not lethal 999 damage. A 100-damage enemy contact produces the retry test death.',
                'Bcourt wave 3 includes a bounded live mixed melee/ranged observation. Protective health restores, if necessary, are reported.',
                'Natural LingQi accumulation is verified to 40/level 2. Before Bexit, an explicit low-LingQi fixture tests the authored level-end floor without granting currency.',
                'No claim of manual continuous completion, seven-minute pacing, headset/controller acceptance or VR performance.'
            ]
        }
        self.isolation = {'state': 'pending', 'temporary_level_id': self.test_level,
                          'test_marker': str(self.marker), 'test_run_ids': []}
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.save()

    def save(self):
        self.report['elapsed_seconds'] = time.monotonic() - self.started
        (O / 'RuntimeFirstLevel.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
        (O / 'FixtureIsolation.json').write_text(json.dumps(self.isolation, ensure_ascii=False, indent=2), encoding='utf-8')
        self.last_save = time.monotonic()

    @staticmethod
    def valid(obj):
        try:
            return obj is not None and unreal.SystemLibrary.is_valid(obj)
        except (TypeError, RuntimeError):
            # UE may already have invalidated the Python wrapper for a destroyed
            # previous encounter; even IsValid cannot nativize that wrapper.
            return False

    @staticmethod
    def guid(value):
        text = re.sub('[^0-9a-fA-F]', '', value.to_string())
        assert re.fullmatch('[0-9a-fA-F]{32}', text), text
        return text.lower()

    @staticmethod
    def xyz(value):
        return [float(value.x), float(value.y), float(value.z)]

    def now(self):
        return float(unreal.GameplayStatics.get_time_seconds(self.world))

    def transition(self, phase):
        self.phase = phase
        self.phase_started = time.monotonic()
        self.save()

    def progression(self):
        state = self.run.get_progression_state()
        return {'ling_qi': state.ling_qi, 'level': state.upgrade_level, 'burst_energy': state.burst_energy,
                'event_ids': list(map(str, state.rewarded_event_ids)), 'damage_multiplier': self.run.get_player_damage_multiplier()}

    def checkpoint_scalar(self):
        state = self.director.get_retry_progression_state()
        return {'ling_qi': state.ling_qi, 'level': state.upgrade_level,
                'burst_energy': state.burst_energy, 'event_ids': list(map(str, state.rewarded_event_ids))}

    def contact(self, source, target, definition):
        value = unreal.NLCombatContact()
        value.set_editor_property('attack_instance_id', unreal.GuidLibrary.new_guid())
        value.set_editor_property('source_runtime_id', source.get_component_by_class(unreal.NLCombatIdentityComponent).ensure_runtime_id())
        value.set_editor_property('target_runtime_id', target.get_component_by_class(unreal.NLCombatIdentityComponent).ensure_runtime_id())
        value.set_editor_property('projectile_generation', -1)
        value.set_editor_property('contact_time_seconds', self.now())
        value.set_editor_property('attack_definition_id', definition.get_editor_property('stable_id'))
        value.set_editor_property('hit_position', target.get_actor_location())
        return value

    def resolve(self, source, target, definition, origin):
        self.origin = origin
        try:
            return self.resolver.resolve_contact(source, target, self.contact(source, target, definition), definition)
        finally:
            self.origin = 'engine_physical'

    def on_result(self, result):
        if result.get_editor_property('outcome') == unreal.NLCombatOutcome.IGNORED:
            return
        self.report['combat_results'].append({
            'game_time': self.now(), 'phase': self.phase, 'origin': self.origin,
            'source_id': self.guid(result.get_editor_property('source_runtime_id')),
            'target_id': self.guid(result.get_editor_property('target_runtime_id')),
            'outcome': str(result.get_editor_property('outcome')),
            'damage': result.get_editor_property('applied_damage'),
            'target_defeated': result.get_editor_property('target_defeated')})

    def owned(self, pause=True):
        encounter = self.director.get_active_encounter()
        if not encounter:
            return []
        enemies = []
        for enemy in unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLEnemyCharacter):
            if not self.valid(enemy) or not encounter.owns_enemy(enemy):
                continue
            if enemy.get_editor_property('vitals').is_dead():
                enemy.set_lab_paused(False)
                continue
            if pause:
                enemy.set_lab_paused(True)
            enemies.append(enemy)
        return sorted(enemies, key=lambda actor: actor.get_name())

    def move(self, position):
        self.pawn.set_actor_location(position, False, True)
        self.movement.stop_movement_immediately()
        self.movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)

    def aim(self, actor):
        camera = unreal.GameplayStatics.get_player_camera_manager(self.world, 0)
        target = actor.get_actor_location() + unreal.Vector(0, 0, 38)
        rotation = unreal.MathLibrary.find_look_at_rotation(camera.get_camera_location(), target)
        unreal.GameplayStatics.get_player_controller(self.world, 0).set_control_rotation(rotation)

    def create_fixture(self, label, damage):
        path = '/Game/ReversedScale/Tests/TransientIntegration/DA_Level01_' + label + '_' + self.uid
        assert not unreal.EditorAssetLibrary.does_asset_exist(path)
        factory = unreal.DataAssetFactory()
        factory.set_editor_property('data_asset_class', unreal.NLAttackDefinition)
        asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(path.rsplit('/', 1)[-1], path.rsplit('/', 1)[0], unreal.NLAttackDefinition, factory)
        assert asset
        self.fixture_assets.append(path)
        asset.set_editor_property('stable_id', 'Automation.Level01.' + label)
        asset.set_editor_property('damage', damage)
        return asset

    def begin(self):
        assert self.editor.get_game_world() is None, 'Stop PIE before running this probe'
        if not self.editor.get_editor_world().get_path_name().startswith(MAP + '.'):
            assert self.level.load_level(MAP)
        directors = [actor for actor in self.actors.get_all_level_actors() if isinstance(actor, unreal.NLLevelEncounterDirector)]
        assert len(directors) == 1
        self.editor_director = directors[0]
        self.original_level = str(self.editor_director.get_editor_property('level_id'))
        assert not self.original_level.startswith('Test.'), 'Restore any earlier fixture first'
        self.mapfile = P / 'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
        self.map_hash = hashlib.sha256(self.mapfile.read_bytes()).hexdigest()
        assert not self.marker.exists()
        self.low_damage = self.create_fixture('DamageTen', 10.0)
        self.death_damage = self.create_fixture('EnemyDeathContact', 100.0)
        self.melee = unreal.load_asset('/Game/ReversedScale/Combat/DA_YueyaoMelee')
        assert self.melee and 0 < self.melee.get_editor_property('damage') <= 40
        self.report['ordinary_melee_definition_damage'] = float(self.melee.get_editor_property('damage'))
        self.isolation.update({'original_level_id': self.original_level, 'map_sha256_before': self.map_hash,
                               'map': MAP, 'temporary_assets': list(self.fixture_assets)})
        self.editor_director.set_editor_property('level_id', self.test_level)
        self.level.editor_request_begin_play()
        self.owns_pie = True
        self.transition('bootstrap')

    def bootstrap(self):
        self.world = self.editor.get_game_world()
        if not self.world:
            return
        self.pawn = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        if not self.pawn:
            return
        self.director = unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLLevelEncounterDirector)[0]
        assert str(self.director.get_editor_property('level_id')) == self.test_level
        for controller in unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLEncounterController):
            assert not controller.get_editor_property('enable_checkpoints')
        instance = unreal.GameplayStatics.get_game_instance(self.world)
        def subsystem(cls, outer):
            return next(obj for obj in unreal.ObjectIterator(cls) if self.valid(obj) and obj.get_outer() == outer)
        self.run = subsystem(unreal.NLRunStateSubsystem, instance)
        self.resolver = subsystem(unreal.NLCombatResolverSubsystem, self.world)
        self.attack_director = subsystem(unreal.NLAttackDirectorSubsystem, self.world)
        self.run_ids.add(self.guid(self.run.get_run_id()))
        self.director.set_actor_tick_enabled(False)
        assert self.run.begin_new_level_run(self.test_level)
        self.run_ids.add(self.guid(self.run.get_run_id()))
        self.isolation['test_run_ids'] = sorted(self.run_ids)
        self.isolation['player_checkpoint_context'] = 'Disabled; no main profile used'
        self.vitals = self.pawn.get_editor_property('vitals')
        self.movement = self.pawn.get_component_by_class(unreal.CharacterMovementComponent)
        self.stage_defs = list(self.director.get_editor_property('stages'))
        assert tuple(str(stage.get_editor_property('stage_id')) for stage in self.stage_defs[:5]) == STAGE_IDS
        assert self.run.get_ling_qi_per_defeat() == 1.0
        self.player_id = self.guid(self.pawn.get_editor_property('combat_identity').get_runtime_id())
        self.result_listener = self.on_result
        self.resolver.get_editor_property('on_combat_result').add_callable(self.result_listener)
        self.initial_progression = self.run.get_progression_state()
        assert self.initial_progression.ling_qi == 0 and self.initial_progression.upgrade_level == 1
        self.move(self.stage_defs[0].get_editor_property('entry_transform').translation)
        self.director.set_actor_tick_enabled(True)
        unreal.SystemLibrary.execute_console_command(self.world, 't.IdleWhenNotForeground 0')
        unreal.SystemLibrary.execute_console_command(self.world, 'Slate.bAllowThrottling 0')
        self.transition('damage_level1')

    def damage_probe(self):
        enemies = self.owned()
        if not enemies:
            return
        if self.phase == 'damage_level1':
            self.target = enemies[0]
            before = self.target.get_editor_property('vitals').get_health()
            assert before > 22.5
            result = self.resolve(self.pawn, self.target, self.low_damage, 'ten_damage_multiplier_fixture')
            assert math.isclose(result.applied_damage, 10, abs_tol=.01)
            self.report['damage_multiplier']['level1'] = {'damage': result.applied_damage, 'health_before': before}
            state = self.run.get_progression_state()
            state.set_editor_property('upgrade_level', 2)
            assert self.run.restore_progression_state(state)
            self.damage_ready = self.now() + .8
            self.transition('damage_level2')
        elif self.now() >= self.damage_ready:
            before = self.target.get_editor_property('vitals').get_health()
            result = self.resolve(self.pawn, self.target, self.low_damage, 'ten_damage_multiplier_fixture')
            assert math.isclose(result.applied_damage, 12.5, abs_tol=.01)
            self.report['damage_multiplier']['level2'] = {'damage': result.applied_damage, 'health_before': before}
            self.report['checks']['central_damage_multiplier_10_to_12_5'] = True
            assert self.run.restore_progression_state(self.initial_progression)
            self.pawn.reset_lab()
            self.target = None
            self.last_position = self.pawn.get_actor_location()
            self.walk_distance = 0.0
            self.last_slash = -100.0
            self.physical_start = self.now()
            self.physical_telegraph = False
            self.physical_states = []
            self.physical_spawn_start = None
            self.physical_spawn_samples = []
            self.physical_max_reservations = 0
            self.transition('physical_opening')

    def physical_opening(self):
        # Never pause/unpause the live target each tick: doing so cancels its
        # reservation and restarts its telegraph before an attack can complete.
        enemies = self.owned(pause=False)
        encounter = self.director.get_active_encounter()
        if encounter:
            sample = {'failed_attempts': encounter.get_failed_spawn_count(),
                      'spawned': encounter.get_spawned_count(), 'alive': encounter.get_alive_count()}
            if self.physical_spawn_start is None:
                self.physical_spawn_start = sample['failed_attempts']
            if not self.physical_spawn_samples or any(sample[key] != self.physical_spawn_samples[-1][key] for key in sample):
                self.physical_spawn_samples.append(dict(sample, game_time=self.now()))
        if self.target is None and enemies:
            self.target = min(enemies, key=lambda e: math.dist(self.xyz(e.get_actor_location()), self.xyz(self.pawn.get_actor_location())))
            self.physical_target_id = self.guid(self.target.get_editor_property('combat_identity').get_runtime_id())
            self.target.set_lab_paused(False)
        for enemy in enemies:
            if enemy != self.target:
                enemy.set_lab_paused(True)
        if self.target is None:
            return
        position = self.pawn.get_actor_location()
        delta = math.dist(self.xyz(position), self.xyz(self.last_position))
        assert delta < 500, 'Physical probe unexpectedly teleported'
        self.walk_distance += delta
        self.last_position = position
        if not self.target.get_editor_property('vitals').is_dead():
            brain = self.target.get_enemy_brain()
            self.physical_telegraph |= brain.get_state() == unreal.NLEnemyState.TELEGRAPH
            state = str(brain.get_state())
            if not self.physical_states or self.physical_states[-1]['state'] != state:
                self.physical_states.append({'state': state, 'game_time': self.now()})
            self.physical_max_reservations = max(self.physical_max_reservations, self.attack_director.get_reservation_count())
            self.aim(self.target)
            direction = self.target.get_actor_location() - position
            distance = math.hypot(direction.x, direction.y)
            if distance > 118:
                self.pawn.add_movement_input(unreal.Vector(direction.x / distance, direction.y / distance, 0), 1.0, False)
            else:
                self.movement.stop_movement_immediately()
            if distance < 180 and self.now() - self.last_slash > .65:
                self.pawn.start_desktop_slash()
                self.last_slash = self.now()
            assert not self.vitals.is_dead(), 'Automated opening player died; this probe does not heal or use invulnerability'
            assert self.now() - self.physical_start < 45, 'Real blade opening did not defeat its live target in 45 game seconds'
            return
        hits = [r for r in self.report['combat_results'] if r['phase'] == 'physical_opening' and r['origin'] == 'engine_physical'
                and r['source_id'] == self.player_id and r['target_id'] == self.physical_target_id]
        assert hits and hits[-1]['target_defeated'], 'Opening defeat was not an actual engine blade result'
        assert self.walk_distance >= 25, 'Opening did not meaningfully move through CharacterMovement'
        growth = self.progression()
        assert growth['ling_qi'] == 1 and growth['level'] == 1 and len(growth['event_ids']) == 1
        event = growth['event_ids'][0]
        assert not self.run.award_ling_qi(event, 1)
        assert self.progression() == growth, 'Duplicate ordinary defeat granted another reward'
        self.report['physical_opening'] = {'state': 'passed', 'native_blade_results': hits,
            'walked_cm': self.walk_distance, 'health_after': self.vitals.get_health(),
            'real_ai_telegraph_observed': self.physical_telegraph, 'game_seconds': self.now() - self.physical_start,
            'ai_states': self.physical_states, 'max_reservations': self.physical_max_reservations,
            'spawn_observation': {'failed_attempts_start': self.physical_spawn_start,
                'failed_attempts_end': encounter.get_failed_spawn_count(),
                'failed_attempts_delta': encounter.get_failed_spawn_count() - self.physical_spawn_start,
                'samples': self.physical_spawn_samples,
                'scope': 'Only the opening live-target observation. The other opening enemy is paused; this is not a full-live-AI spawn benchmark.'},
            'progression_after_first_defeat': growth, 'duplicate_reward_rejected': True,
            'scope': 'One live AI and scripted CharacterMovement/StartDesktopSlash. Other owned AI paused; no player heals, teleports, direct resolver calls or damage edits inside this phase.'}
        self.movement.stop_movement_immediately()
        self.target = None
        self.transition('death_retry')

    def death_retry(self):
        enemies = self.owned()
        if not enemies:
            return
        source = enemies[0]
        self.pawn.lower_mirror()
        result = self.resolve(source, self.pawn, self.death_damage, 'enemy_100_damage_death_fixture')
        if result.get_editor_property('outcome') == unreal.NLCombatOutcome.IGNORED:
            return
        assert self.vitals.is_dead()
        assert self.director.get_stage_status('Aoutside') == unreal.NLLevelStageState.FAILED
        before = self.progression()
        self.pawn.reset_lab()
        after = self.progression()
        assert after['ling_qi'] == 0 and after['level'] == 1 and not after['event_ids'] and after['burst_energy'] == 0
        self.report['retry_attempts'].append({'index': 1, 'trigger': 'real_enemy_resolver_death', 'before': before, 'after': after})
        self.transition('retry_loop')

    def retry_loop(self):
        enemies = self.owned()
        if not enemies:
            return
        enemy = enemies[0]
        result = self.resolve(self.pawn, enemy, self.melee, 'ordinary_melee_resolver_retry_fixture')
        if not enemy.get_editor_property('vitals').is_dead():
            return
        assert result.get_editor_property('outcome') == unreal.NLCombatOutcome.HIT
        before = self.progression()
        assert before['ling_qi'] == 1 and len(before['event_ids']) == 1
        self.pawn.reset_lab()
        after = self.progression()
        assert after['ling_qi'] == 0 and after['level'] == 1 and not after['event_ids'] and after['burst_energy'] == 0
        self.report['retry_attempts'].append({'index': len(self.report['retry_attempts']) + 1,
            'trigger': 'living_player_R_reset', 'before': before, 'after': after})
        if len(self.report['retry_attempts']) == 10:
            self.report['checks']['ten_retries_do_not_farm_lingqi_or_burst'] = True
            self.report['checks']['duplicate_defeat_reward_rejected'] = True
            self.report['checks']['native_movement_and_blade_defeat'] = True
            self.transition('stage_setup')

    def bind_stage(self, encounter):
        current = self.stage
        if current.get('bound'):
            return
        current['bound'] = True
        def defeated(enemy, runtime_id, ordinal):
            current['defeat_events'].append({'runtime_id': self.guid(runtime_id), 'ordinal': ordinal,
                'wave_index': encounter.get_wave_index(), 'progression': self.progression()})
            state = self.run.get_progression_state()
            if self.stage_index <= 3 and state.upgrade_level == 2 and not self.report['threshold']:
                assert state.ling_qi == 40, 'Natural first upgrade did not occur at 40 LingQi'
                self.report['threshold'] = {'state': 'passed', 'ling_qi': state.ling_qi,
                    'level': state.upgrade_level, 'event_count': len(state.rewarded_event_ids),
                    'stage': current['id'], 'wave': encounter.get_wave_index() + 1}
                screenshot = O / 'Screenshots/FirstUpgrade.png'
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, str(screenshot), delay=.2))
        def completed():
            current['completion'] = {'spawned': encounter.get_spawned_count(), 'defeated': encounter.get_defeated_count(),
                'planned': encounter.get_planned_count(), 'completed_waves': encounter.get_completed_wave_count(),
                'failed_spawn_attempts': encounter.get_failed_spawn_count(), 'progression': self.progression()}
        encounter.get_editor_property('on_enemy_defeated').add_callable(defeated)
        encounter.get_editor_property('on_encounter_completed').add_callable(completed)
        self.bindings.append((encounter, 'on_enemy_defeated', defeated))
        self.bindings.append((encounter, 'on_encounter_completed', completed))

    def setup_stage(self):
        if self.stage_index == 5:
            assert len(self.report['stages']) == 5 and self.director.get_completed_stage_count() == 5
            assert sum(s['completion']['defeated'] for s in self.report['stages']) == 52
            assert sum(s['completion']['completed_waves'] for s in self.report['stages']) == 10
            assert self.report['threshold'].get('state') == 'passed'
            assert self.report['mixed_ai'].get('state') == 'passed'
            assert self.run.get_progression_state().upgrade_level == 2
            self.report['checks']['five_stages_ten_waves_52_real_defeat_events'] = True
            self.report['checks']['natural_threshold_40'] = True
            self.report['checks']['authored_level_end_floor_without_currency_grant'] = True
            self.finish()
            return
        definition = self.stage_defs[self.stage_index]
        waves = list(definition.get_editor_property('waves'))
        self.stage = {'id': STAGE_IDS[self.stage_index], 'expected': COUNTS[self.stage_index],
            'warnings': [], 'defeat_events': [], 'observed_waves': {}, 'state': 'entering',
            'waves': [{'id': str(w.get_editor_property('wave_id')),
                       'planned': sum(entry.count for entry in w.get_editor_property('spawn_entries')),
                       'max_alive': w.get_editor_property('max_alive')} for w in waves]}
        self.report['stages'].append(self.stage)
        if self.stage_index == 4:
            natural = self.progression()
            assert natural['ling_qi'] == 46 and natural['level'] == 2 and len(natural['event_ids']) == 46
            state = self.run.get_progression_state()
            state.set_editor_property('ling_qi', 10.0)
            state.set_editor_property('upgrade_level', 1)
            assert self.run.restore_progression_state(state)
            self.report['fallback'] = {'natural_before_fixture': natural, 'fixture_entry': self.progression(),
                'scope': 'Explicit low-currency scalar fixture before actual Bexit entry. Existing 46 defeat IDs are retained. Six ordinary deaths must add six currency; the boundary floor must add no currency.'}
        self.move(definition.get_editor_property('entry_transform').translation)
        self.transition('stage_active')

    def mixed_observe(self, owned):
        probe = self.report['mixed_ai']
        if probe['state'] == 'passed':
            return True
        casters = [e for e in owned if e.get_enemy_brain().get_editor_property('role') == unreal.NLEnemyRole.TALISMAN_CASTER]
        if not casters:
            return True  # The final ranged entry may be gated behind the four-alive budget.
        if probe['state'] == 'pending':
            encounter = self.director.get_active_encounter()
            probe.update({'state': 'observing', 'began_game_time': self.now(), 'actors': {},
                'projectile_ids': [], 'protective_heals': [], 'max_reservations': 0,
                'health_before': self.vitals.get_health(),
                'failed_spawn_attempts_start': encounter.get_failed_spawn_count(),
                'wave_spawned_at_observation_start': encounter.get_current_wave_spawned_count(),
                'wave_planned': encounter.get_current_wave_planned_count()})
        for enemy in owned:
            identity = self.guid(enemy.get_editor_property('combat_identity').get_runtime_id())
            brain = enemy.get_enemy_brain()
            if identity not in probe['actors']:
                # Transition once when admitting an actor into this live probe.
                # Later samples only observe it; the surrounding stage tick also
                # leaves all live actors unpaused throughout this phase.
                enemy.set_lab_paused(False)
            row = probe['actors'].setdefault(identity, {'role': str(brain.get_editor_property('role')), 'states': []})
            state = str(brain.get_state())
            if state not in row['states']:
                row['states'].append(state)
        probe['max_reservations'] = max(probe['max_reservations'], self.attack_director.get_reservation_count())
        assert self.attack_director.get_reservation_count() <= 3, 'Mixed normal wave exceeded its 2 melee + 1 ranged reservation budget'
        for projectile in unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLCombatProjectile):
            if not self.valid(projectile) or projectile.get_source_actor() not in casters:
                continue
            attack = self.guid(projectile.get_attack_instance_id())
            if attack not in probe['projectile_ids']:
                probe['projectile_ids'].append(attack)
        if self.vitals.get_health() < 50:
            probe['protective_heals'].append({'at': self.now(), 'before': self.vitals.get_health(), 'after': 90})
            assert self.vitals.restore_resource_preset(90, 100)
        self.aim(casters[0])
        elapsed = self.now() - probe['began_game_time']
        probe['observed_game_seconds'] = elapsed
        caster_telegraph = any('TALISMAN_CASTER' in row['role'] and any('TELEGRAPH' in s for s in row['states']) for row in probe['actors'].values())
        melee_telegraph = any('TALISMAN_CASTER' not in row['role'] and any('TELEGRAPH' in s for s in row['states']) for row in probe['actors'].values())
        if elapsed >= 2 and 'screenshot' not in probe:
            path = O / 'Screenshots/MixedWave.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, str(path), delay=.2))
            probe['screenshot'] = str(path)
        if elapsed >= 8 and caster_telegraph and melee_telegraph and probe['projectile_ids']:
            encounter = self.director.get_active_encounter()
            probe.update({'state': 'passed', 'health_after': self.vitals.get_health(),
                'caster_telegraph': True, 'melee_telegraph': True, 'real_projectile_emitted': True,
                'failed_spawn_attempts_end': encounter.get_failed_spawn_count(),
                'failed_spawn_attempts_delta': encounter.get_failed_spawn_count() - probe['failed_spawn_attempts_start'],
                'wave_spawned_at_observation_end': encounter.get_current_wave_spawned_count(),
                'spawn_observation_scope': 'Counter delta only during live mixed AI observation; earlier isolated-wave retries are excluded. If all wave actors were already spawned at entry, this window is not a spawning-performance sample.'})
            self.report['checks']['live_mixed_melee_and_ranged_observation'] = True
            for enemy in owned:
                enemy.set_lab_paused(True)
            self.vitals.restore_resource_preset(100, 100)
            return True
        assert elapsed < 30, 'Mixed wave did not show both telegraphs and a real ranged projectile within 30 seconds'
        return False

    def stage_tick(self):
        stage_id = self.stage['id']
        state = self.director.get_stage_status(stage_id)
        assert state != unreal.NLLevelStageState.FAILED, (stage_id, str(self.director.get_failure_reason()))
        if state == unreal.NLLevelStageState.COMPLETED:
            completion = self.stage.get('completion')
            assert completion and completion['spawned'] == completion['defeated'] == completion['planned'] == self.stage['expected']
            assert len(self.stage['defeat_events']) == self.stage['expected']
            assert completion['completed_waves'] == len(self.stage['waves'])
            for wave_index, planned in enumerate(self.stage['waves'], 1):
                observed = self.stage['observed_waves'][str(wave_index)]
                assert len(observed['actors']) == planned['planned'], 'Observed actor count differs from completed wave budget'
                assert observed['max_alive'] <= planned['max_alive']
            if stage_id == 'Bcourt':
                for number in ('3', '5'):
                    roles = list(self.stage['observed_waves'][number]['actors'].values())
                    assert len(roles) == 6 and sum('TALISMAN_CASTER' in role for role in roles) == 1
                self.report['checks']['two_mixed_waves_keep_five_swords_one_caster'] = True
            self.stage['state'] = 'passed'
            if stage_id == 'Bexit':
                after = self.progression()
                assert after['ling_qi'] == 16 and after['level'] == 2 and len(after['event_ids']) == 52
                timestamp = self.run.get_last_upgrade_time_seconds()
                assert self.run.ensure_upgrade_level(2)
                assert self.progression() == after and self.run.get_last_upgrade_time_seconds() == timestamp
                self.report['fallback'].update({'state': 'passed', 'after_actual_boundary': after, 'repeat_floor_did_not_reward_or_reannounce': True})
            self.stage_index += 1
            self.transition('stage_setup')
            return
        if state == unreal.NLLevelStageState.WARNING:
            self.stage['warnings'].append(self.director.get_warning_remaining())
            return
        if state != unreal.NLLevelStageState.ACTIVE:
            assert time.monotonic() - self.phase_started < 25, 'Stage trigger did not activate: ' + stage_id
            return
        encounter = self.director.get_active_encounter()
        assert encounter and str(self.director.get_active_stage_id()) == stage_id
        self.bind_stage(encounter)
        index = encounter.get_wave_index()
        if index < 0:
            return
        wave = self.stage['waves'][index]
        observed = self.stage['observed_waves'].setdefault(str(index + 1), {'max_alive': 0, 'actors': {}})
        observed['max_alive'] = max(observed['max_alive'], encounter.get_alive_count())
        assert encounter.get_alive_count() <= wave['max_alive']
        live_mixed = stage_id == 'Bcourt' and index == 2 and self.report['mixed_ai']['state'] == 'observing'
        owned = self.owned(pause=not live_mixed)
        for enemy in owned:
            identity = self.guid(enemy.get_editor_property('combat_identity').get_runtime_id())
            observed['actors'][identity] = str(enemy.get_enemy_brain().get_editor_property('role'))
        defeated_in_wave = sum(row['wave_index'] == index for row in self.stage['defeat_events'])
        threshold = min(wave['max_alive'], wave['planned'] - defeated_in_wave)
        if encounter.get_alive_count() < threshold and encounter.get_current_wave_spawned_count() < wave['planned']:
            return
        if stage_id == 'Bcourt' and index == 2 and not self.mixed_observe(owned):
            return
        if stage_id == 'Bcourt' and index in (2, 4):
            roles = list(observed['actors'].values())
            if any('TALISMAN_CASTER' in role for role in roles):
                observed['mixed_caster_spawned'] = True
        # Use normal damage and normal protection intervals. Never overwrite enemy health.
        # In the first mixed wave, retire only two of an initial four-sword group
        # so the final caster can spawn alongside surviving melee actors.
        candidates = owned
        if stage_id == 'Bcourt' and index == 2 and self.report['mixed_ai']['state'] == 'pending':
            candidates = owned[:2]
        for enemy in candidates:
            identity = self.guid(enemy.get_editor_property('combat_identity').get_runtime_id())
            if self.now() - self.contact_times.get(identity, -1000) < .8:
                continue
            self.contact_times[identity] = self.now()
            result = self.resolve(self.pawn, enemy, self.melee, 'ordinary_melee_resolver_main_fixture')
            assert result.get_editor_property('outcome') in (unreal.NLCombatOutcome.HIT, unreal.NLCombatOutcome.IGNORED)

    def finish(self, error=None):
        if self.phase == 'ending':
            return
        if error:
            self.report['failures'].append(error)
        if self.world and self.valid(self.world):
            unreal.GameplayStatics.set_game_paused(self.world, False)
        if self.movement and self.valid(self.movement):
            self.movement.stop_movement_immediately()
        for owner, field, callback in self.bindings:
            if self.valid(owner):
                owner.get_editor_property(field).remove_callable(callback)
        self.bindings.clear()
        if self.resolver and self.valid(self.resolver) and hasattr(self, 'result_listener'):
            self.resolver.get_editor_property('on_combat_result').remove_callable(self.result_listener)
        self.world = self.pawn = self.director = self.resolver = self.run = None
        self.vitals = self.movement = self.attack_director = self.target = None
        self.stage_defs = []
        self.initial_progression = None
        if self.owns_pie:
            self.level.editor_request_end_play()
        self.transition('ending')

    def cleanup(self):
        if self.editor_director is not None and self.valid(self.editor_director):
            current = str(self.editor_director.get_editor_property('level_id'))
            assert current in (self.test_level, self.original_level), 'Another operation changed editor LevelId during fixture'
            self.editor_director.set_editor_property('level_id', self.original_level)
            self.isolation['restored_level_id'] = str(self.editor_director.get_editor_property('level_id'))
        if self.marker.exists():
            blob = self.marker.read_bytes()
            assert len(blob) == 48 and blob[8:28] == hashlib.sha1(self.test_level.lower().encode()).digest()
            self.run_ids.add(''.join(f'{part:08x}' for part in struct.unpack('<4I', blob[28:44])))
        removed = []
        for run_id in self.run_ids:
            assert re.fullmatch('[0-9a-f]{32}', run_id)
            target = self.ledger_dir / (run_id.upper() + '.nlmr')
            assert target.name.lower() not in self.existing_ledgers
            assert target.resolve().parent == self.ledger_dir.resolve()
            for path in (target, Path(str(target) + '.tmp')):
                if path.exists():
                    path.unlink()
                    removed.append(str(path))
        assert self.marker.resolve().parent == self.marker_dir.resolve()
        for path in (self.marker, Path(str(self.marker) + '.tmp')):
            if path.exists():
                path.unlink()
                removed.append(str(path))
        self.low_damage = self.death_damage = None
        for path in self.fixture_assets:
            assert path.endswith(self.uid) and path.startswith('/Game/ReversedScale/Tests/TransientIntegration/DA_Level01_')
            assert unreal.EditorAssetLibrary.delete_asset(path), 'Could not remove fixture asset ' + path
        self.fixture_assets.clear()
        if self.map_hash is not None:
            after = hashlib.sha256(self.mapfile.read_bytes()).hexdigest()
            assert after == self.map_hash, 'Probe modified the saved gameplay map'
            self.isolation['map_sha256_after'] = after
        self.isolation.update({'state': 'restored_without_saving_map', 'test_run_ids': sorted(self.run_ids),
            'removed_only_exact_test_paths': removed, 'temporary_assets_removed': True})
        self.report['fixture_isolation'] = self.isolation

    def tick(self, delta):
        if self.busy:
            return
        self.busy = True
        try:
            if self.phase == 'ending':
                if self.owns_pie and self.editor.get_game_world() is not None:
                    assert time.monotonic() - self.phase_started < 30, 'PIE failed to end'
                    return
                self.cleanup()
                self.report['success'] = not self.report['failures'] and bool(self.report['checks']) and all(self.report['checks'].values())
                self.report['state'] = 'passed' if self.report['success'] else 'failed'
                self.save()
                unreal.unregister_slate_post_tick_callback(self.handle)
                return
            assert time.monotonic() - self.started < 600, 'First-level runtime probe deadline'
            if self.phase == 'start':
                self.begin()
            elif self.phase == 'bootstrap':
                assert time.monotonic() - self.phase_started < 30, 'PIE bootstrap deadline'
                self.bootstrap()
            elif self.phase.startswith('damage_level'):
                self.damage_probe()
            elif self.phase == 'physical_opening':
                self.physical_opening()
            elif self.phase == 'death_retry':
                self.death_retry()
            elif self.phase == 'retry_loop':
                self.retry_loop()
            elif self.phase == 'stage_setup':
                self.setup_stage()
            elif self.phase == 'stage_active':
                self.stage_tick()
            if time.monotonic() - self.last_save >= 2:
                self.save()
        except Exception:
            failure = {'phase': self.phase, 'error': traceback.format_exc()}
            if self.phase == 'ending':
                self.report['failures'].append(failure)
                self.report['state'] = 'failed'
                self.report['success'] = False
                self.isolation['state'] = 'cleanup_failed_needs_review'
                self.save()
                unreal.unregister_slate_post_tick_callback(self.handle)
            else:
                self.finish(failure)
        finally:
            self.busy = False


first_level_probe = FirstLevelProbe()
