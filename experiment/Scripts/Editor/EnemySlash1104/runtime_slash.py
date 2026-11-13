"""Observe native sword sweeps and verify the two live player damage definitions."""
import hashlib
import json
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUT = PROJECT / 'Docs/Gameplay/EnemySlash1104'
helper = PROJECT / 'Scripts/Editor/Level01PolishV01/runtime_first_level.py'
context = {'__name__': 'slash_runtime_helper', '__file__': str(helper)}
source = helper.read_text(encoding='utf-8-sig').replace('first_level_probe = FirstLevelProbe()', '')
exec(compile(source, str(helper), 'exec'), context)
context['O'] = OUT
assets = json.loads((OUT / 'AssetChanges.json').read_text(encoding='utf-8'))


class SlashProbe(context['FirstLevelProbe']):
    def begin(self):
        assert self.editor.get_game_world() is None
        assert self.level.load_level(context['MAP'])
        self.editor_director = next(a for a in self.actors.get_all_level_actors()
                                    if isinstance(a, unreal.NLLevelEncounterDirector))
        self.original_level = str(self.editor_director.level_id)
        assert not self.original_level.startswith('Test.')
        self.mapfile = PROJECT / 'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
        self.map_hash = hashlib.sha256(self.mapfile.read_bytes()).hexdigest()
        self.editor_director.level_id = self.test_level
        self.level.editor_request_begin_play()
        self.owns_pie = True
        self.enemy = None
        self.cycle = None
        self.completed = []
        self.damage_results = []
        self.frames = []
        self.report['cycles'] = self.completed
        self.report['attack_frames'] = self.frames
        self.report['player_damage_checks'] = self.damage_results
        self.report['scope'] = ['Saved main map, normal opening sword AI and normal player capsule.',
            'Enemy attacks use actual animation notifies and blade sweeps. Other enemies are paused.',
            'Player damage uses two labelled resolver contacts with the definitions equipped by the normal pawn.']
        self.transition('bootstrap')

    def bootstrap(self):
        super().bootstrap()
        if self.phase != 'damage_level1':
            return
        self.melee = self.pawn.blade.attack_definition
        self.qi = self.pawn.blade_qi_definition
        assert self.melee.get_editor_property('damage') == 15.0
        assert self.qi.get_editor_property('damage') == 10.0
        self.transition('stage_active')

    def stage_tick(self):
        world_time = self.now()
        enemies = self.owned(pause=False)
        if self.enemy is None:
            assert world_time < 20, 'No sword enemy reached the opening stage'
            if not enemies:
                return
            self.enemy = enemies[0]
            assert self.enemy.attack_animation.get_path_name() == assets['clip']
            self.brain = self.enemy.get_enemy_brain()
            for prop, value in zip(('telegraph_seconds', 'attack_seconds', 'recover_seconds'), assets['enemies'][0]['after_seconds']):
                assert abs(self.brain.get_editor_property(prop) - value) < 0.001
            self.enemy.set_actor_rotation(unreal.Rotator(yaw=0), True)
            self.enemy_start = self.enemy.get_actor_location()
            self.move(self.enemy_start + unreal.Vector(129.5, 0, 0))
            self.movement.disable_movement()
            self.pawn.set_actor_tick_enabled(False)
            self.pawn.guard.set_guard_held(False)
            for component in self.pawn.get_components_by_class(unreal.PrimitiveComponent):
                if component.get_name() in ('RightHand', 'HeldWeapon', 'RightSleeve'):
                    component.set_hidden_in_game(True)
            self.previous_state = None
            self.previous_active = False
            self.health = self.vitals.get_health()
            self.zero = world_time
            self.next_damage_time = None
        for enemy in enemies:
            if enemy != self.enemy:
                enemy.set_lab_paused(True)
                enemy.set_actor_enable_collision(False)
                enemy.set_actor_hidden_in_game(True)
        assert world_time - self.zero < 35, 'Slash validation timed out'
        if len(self.completed) == 2:
            if self.next_damage_time is None:
                self.enemy.set_lab_paused(True)
                self.next_damage_time = world_time
            if world_time >= self.next_damage_time:
                definition, expected = (self.melee, 15.0) if not self.damage_results else (self.qi, 10.0)
                result = self.resolve(self.pawn, self.enemy, definition, 'scripted_definition_damage_check')
                actual = result.get_editor_property('applied_damage')
                assert abs(actual - expected) < 0.01, (definition.get_name(), actual)
                self.damage_results.append({'definition': definition.get_name(), 'applied_damage': actual})
                self.next_damage_time = world_time + 1.1
                if len(self.damage_results) == 2:
                    self.report['checks'] = {'two_native_slashes': True, 'one_hit_per_slash': True,
                        'damage_window_matches_visible_swing': True, 'melee_damage_15': True, 'sword_qi_damage_10': True}
                    self.finish()
            return

        state = self.brain.get_state()
        blade = self.enemy.blade
        mesh = self.enemy.get_component_by_class(unreal.SkeletalMeshComponent)
        animation_position = mesh.get_position()
        active = blade.get_swing_state() == unreal.NLBladeSwingState.SWING_ACTIVE
        if state == unreal.NLEnemyState.TELEGRAPH and self.previous_state != state:
            assert self.cycle is None
            self.cycle = {'started': world_time, 'hit_times': [], 'max_animation_position': 0.0}
        if self.cycle:
            self.cycle['max_animation_position'] = max(self.cycle['max_animation_position'], animation_position)
            if active:
                assert self.brain.is_attack_window_active(), 'Attack became active outside the brain window'
            self.frames.append({'elapsed': world_time - self.cycle['started'], 'pose_time': animation_position,
                'state': str(state), 'blade_active': active,
                'distance_cm': (self.enemy.get_actor_location() - self.pawn.get_actor_location()).length()})
        health = self.vitals.get_health()
        if health < self.health - 0.001:
            assert self.cycle and (active or self.previous_active), 'Damage outside the sword sweep'
            self.cycle['hit_times'].append(world_time - self.cycle['started'])
        self.health = health
        if self.cycle and self.previous_state == unreal.NLEnemyState.RECOVER and state != self.previous_state:
            self.cycle['duration'] = world_time - self.cycle['started']
            assert len(self.cycle['hit_times']) == 1, self.cycle
            assert 0.58 <= self.cycle['hit_times'][0] <= 0.86, self.cycle
            assert 1.46 <= self.cycle['duration'] <= 1.61, self.cycle
            assert self.cycle['max_animation_position'] >= 1.40, self.cycle
            self.completed.append(self.cycle)
            self.cycle = None
        self.previous_state, self.previous_active = state, active

        center = self.enemy_start + unreal.Vector(27, 0, 3)
        location = center + unreal.Vector(207, -209, 65)
        rotation = unreal.MathLibrary.find_look_at_rotation(location, center)
        self.pawn.player_camera.set_world_transform(unreal.Transform(location=location, rotation=rotation), False, True)
        unreal.GameplayStatics.get_player_controller(self.world, 0).set_control_rotation(rotation)


slash_probe = SlashProbe()
