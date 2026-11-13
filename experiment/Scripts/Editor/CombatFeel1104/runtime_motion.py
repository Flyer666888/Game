"""Real saved main-level AI in an isolated profile; fixed observer camera only."""
import hashlib, json
from pathlib import Path
import unreal
P = Path(unreal.Paths.project_dir()).resolve()
O = P / 'Docs/Gameplay/CombatFeel1104'
helper = P / 'Scripts/Editor/Level01PolishV01/runtime_first_level.py'
context = {'__name__': 'motion_helper', '__file__': str(helper)}
exec(compile(helper.read_text(encoding='utf-8-sig').replace('first_level_probe = FirstLevelProbe()', ''), str(helper), 'exec'), context)
context['O'] = O

class MotionProbe(context['FirstLevelProbe']):
    def begin(self):
        assert self.editor.get_game_world() is None
        assert self.level.load_level(context['MAP'])
        self.editor_director = next(a for a in self.actors.get_all_level_actors() if isinstance(a, unreal.NLLevelEncounterDirector))
        self.original_level = str(self.editor_director.level_id)
        assert not self.original_level.startswith('Test.')
        self.mapfile = P / 'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
        self.map_hash = hashlib.sha256(self.mapfile.read_bytes()).hexdigest()
        self.editor_director.level_id = self.test_level
        self.level.editor_request_begin_play()
        self.owns_pie = True
        self.enemy = None
        self.frames = []
        self.shots = set()
        self.report['frames'] = self.frames
        self.report['scope'] = ['Real main-level sword AI and collision; temporary test profile.',
            'Observer camera follows the enemy. Player starts 550cm away, then walks away at VR speed from 6 to 8 seconds using real CharacterMovement.',
            'Other enemies are paused. No HMD input or human playtest is claimed.']
        self.transition('bootstrap')

    def bootstrap(self):
        super().bootstrap()
        if self.phase == 'damage_level1': self.transition('stage_active')

    def capture(self, name):
        if name in self.shots: return
        self.shots.add(name)
        self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1280, 900, str(O / (name+'.png'))))

    def stage_tick(self):
        enemies = self.owned(pause=False)
        if self.enemy is None:
            if not enemies: return
            self.enemy = enemies[0]
            self.brain = self.enemy.get_enemy_brain()
            self.zero = self.now()
            self.start = self.enemy.get_actor_location()
            self.enemy.set_actor_rotation(unreal.Rotator(yaw=0), True)
            self.move(self.start + unreal.Vector(550, 0, 0))
            self.pawn.set_actor_tick_enabled(False)
            self.movement.disable_movement()
            self.pawn.guard.set_guard_held(False)
            for c in self.pawn.get_components_by_class(unreal.PrimitiveComponent):
                if c.get_name() in ('RightHand','HeldWeapon','RightSleeve','LeftSleeve','Mirror'): c.set_hidden_in_game(True)
            unreal.SystemLibrary.execute_console_command(self.world, 'showhud')
            unreal.SystemLibrary.execute_console_command(self.world, 't.MaxFPS 60')
        for e in enemies:
            if e != self.enemy:
                e.set_lab_paused(True)
                e.set_actor_enable_collision(False)
                e.set_actor_hidden_in_game(True)
        now = self.now() - self.zero
        if 6 <= now < 8:
            self.movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)
            self.movement.set_editor_property('max_walk_speed',180.0)
            self.pawn.add_movement_input(unreal.Vector(1,0,0),1.0,True)
        elif now >= 8:
            self.movement.stop_movement_immediately()
            self.movement.disable_movement()
        location = self.enemy.get_actor_location()
        center = location + unreal.Vector(0,0,0)
        camera_location = center + unreal.Vector(300,-345,120)
        rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, center)
        self.pawn.player_camera.set_world_transform(unreal.Transform(location=camera_location, rotation=rotation),False,True)
        unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(rotation)
        mesh = self.enemy.get_component_by_class(unreal.SkeletalMeshComponent)
        state = self.brain.get_state()
        row = dict(t=now,state=str(state),speed=self.enemy.get_velocity().length(),
            distance=(location-self.pawn.get_actor_location()).length(), animation_time=mesh.get_position(),
            attack_window=self.brain.is_attack_window_active(), player_health=self.vitals.get_health())
        row['enemy_location'] = self.xyz(location)
        row['player_location'] = self.xyz(self.pawn.get_actor_location())
        row['enemy_yaw'] = self.enemy.get_actor_rotation().yaw
        row['blade_points'] = {k:self.xyz(unreal.MathLibrary.transform_location(self.enemy.sword.get_world_transform(),self.enemy.blade.get_editor_property(k)))
            for k in ('blade_root_local','blade_mid_local','blade_tip_local')}
        self.frames.append(row)
        if row['speed'] > 250 and now > .4: self.capture('EnemyChase')
        if state == unreal.NLEnemyState.TELEGRAPH and mesh.get_position() > .22: self.capture('EnemyWindup')
        if row['attack_window'] and mesh.get_position() >= .72: self.capture('EnemyStrike')
        if state == unreal.NLEnemyState.RECOVER: self.capture('EnemyRecovery')
        if self.vitals.get_health() < 35: self.vitals.restore_resource_preset(100,100)
        if now > 12:
            self.report['checks'] = {'chases_faster_than_player': max(r['speed'] for r in self.frames) > 250,
                'closed_distance': min(r['distance'] for r in self.frames) < 180,
                'native_attack_window': any(r['attack_window'] for r in self.frames),
                'native_player_damage': any(r['player_health'] < 100 for r in self.frames),
                'player_retreats': max(r['player_location'][0] for r in self.frames)-min(r['player_location'][0] for r in self.frames)>200,
                'resumes_chase_after_player_retreat': any(r['t']>6 and r['speed']>250 for r in self.frames),
                'catches_retreating_player': any(r['t']>9 and r['distance']<150 for r in self.frames)}
            self.enemy = self.brain = None
            self.finish()

motion_probe = MotionProbe()
