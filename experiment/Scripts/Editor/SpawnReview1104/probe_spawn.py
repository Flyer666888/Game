"""Measure first-wave births with the player beside an authored spawn point."""
import json
from pathlib import Path
import time
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
output = project / 'Docs/Gameplay/SpawnReview1104'
config = json.loads((output / 'ProbeConfig.json').read_text(encoding='utf-8-sig'))
helper = project / 'Scripts/Editor/SlashRevision1104/runtime_motion.py'
context = {'__name__': 'spawn_probe_helper', '__file__': str(helper)}
exec(compile(helper.read_text(encoding='utf-8-sig').replace('motion_probe = MotionProbe()', ''), str(helper), 'exec'), context)


class SpawnProbe(context['MotionProbe']):
    def save(self):
        self.report['fixture_isolation'] = self.isolation
        (output / config['report']).write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.last_save = time.monotonic()

    def bootstrap(self):
        super().bootstrap()
        if self.phase != 'stage_active':
            return
        stage = self.stage_defs[0]
        points = list(stage.get_editor_property('spawn_points'))
        self.entry = stage.get_editor_property('entry_transform').translation
        self.near = points[0].get_editor_property('spawn_transform').translation
        self.report['spawn_points'] = [self.xyz(point.get_editor_property('spawn_transform').translation) for point in points]
        self.report['births'] = []
        self.report['entry_clearance'] = []
        for definition in self.stage_defs:
            entry = definition.get_editor_property('entry_transform').translation
            locations = {str(point.get_editor_property('spawn_point_id')): point.get_editor_property('spawn_transform').translation
                         for point in definition.get_editor_property('spawn_points')}
            for wave in definition.get_editor_property('waves'):
                for group in wave.get_editor_property('spawn_entries'):
                    furthest = max((entry - locations[str(point_id)]).length()
                                   for point_id in group.get_editor_property('spawn_point_ids'))
                    self.report['entry_clearance'].append({
                        'stage': str(definition.get_editor_property('stage_id')),
                        'wave': str(wave.get_editor_property('wave_id')),
                        'group': str(group.get_editor_property('entry_id')),
                        'furthest_cm': furthest,
                    })
        self.near_case = config.get('near_player', True)
        self.report['scope'] = ('Actual saved map. Move the test pawn 100 cm from the first spawn point during the warning.'
            if self.near_case else 'Actual saved map. Observe both opening spawns from the entry position.')
        self.seen = set()
        self.positioned = False
        self.started_game = self.now()

    def stage_tick(self):
        assert self.now() - self.started_game < 12, 'Opening wave did not produce both enemies'
        state = self.director.get_stage_status('Aoutside')
        assert state != unreal.NLLevelStageState.FAILED, str(self.director.get_failure_reason())
        if self.near_case and state == unreal.NLLevelStageState.WARNING and not self.positioned:
            self.move(self.near + unreal.Vector(100, 0, 0))
            self.positioned = True
        encounter = self.director.get_active_encounter()
        if not encounter:
            return
        for enemy in self.owned(pause=False):
            actor_id = self.guid(enemy.combat_identity.get_runtime_id())
            if actor_id in self.seen:
                continue
            self.seen.add(actor_id)
            self.report['births'].append({
                'enemy': self.xyz(enemy.get_actor_location()),
                'player': self.xyz(self.pawn.get_actor_location()),
                'distance_cm': (enemy.get_actor_location()-self.pawn.get_actor_location()).length(),
                'time': self.now(),
            })
            if len(self.seen) == 1:
                self.move(self.entry)
        if len(self.seen) == 2:
            minimum = min(row['distance_cm'] for row in self.report['births'])
            self.report['failed_spawn_count'] = encounter.get_failed_spawn_count()
            self.report['checks'] = {'player_followed_fixture': self.positioned == self.near_case,
                'both_enemies_spawned': encounter.get_spawned_count() == 2,
                'observed_expected_clearance': minimum >= 300 if config['fixed'] else minimum < 150}
            if config['fixed']:
                self.report['checks']['different_birth_points'] = (
                    self.report['births'][0]['enemy'] != self.report['births'][1]['enemy'])
                self.report['checks']['no_collision_retry'] = encounter.get_failed_spawn_count() == 0
                self.report['checks']['all_stage_entries_have_distant_candidates'] = all(
                    row['furthest_cm'] >= 300 for row in self.report['entry_clearance'])
            self.finish()


spawn_probe = SpawnProbe()
