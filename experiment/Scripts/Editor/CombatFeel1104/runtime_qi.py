"""Saved player definition launched through the real projectile sweep; observer camera."""
from pathlib import Path
import unreal
P = Path(unreal.Paths.project_dir()).resolve()
source = P / 'Scripts/Editor/CombatFeel1104/runtime_motion.py'
ctx = {'__name__':'qi_helper','__file__':str(source)}
exec(compile(source.read_text().replace('motion_probe = MotionProbe()', ''),str(source),'exec'),ctx)

class QiProbe(ctx['MotionProbe']):
    def stage_tick(self):
        enemies = self.owned(pause=False)
        if self.enemy is None:
            if not enemies: return
            self.enemy = enemies[0]
            for e in enemies:
                e.set_lab_paused(True)
                if e != self.enemy:
                    e.set_actor_enable_collision(False)
                    e.set_actor_hidden_in_game(True)
            self.enemy.set_actor_rotation(unreal.Rotator(yaw=0),True)
            self.start = self.enemy.get_actor_location()
            self.move(self.start + unreal.Vector(620,0,0))
            self.pawn.set_actor_tick_enabled(False)
            self.movement.disable_movement()
            for c in self.pawn.get_components_by_class(unreal.PrimitiveComponent):
                if c.get_name() in ('RightHand','HeldWeapon','RightSleeve','LeftSleeve','Mirror'): c.set_hidden_in_game(True)
            unreal.SystemLibrary.execute_console_command(self.world,'showhud')
            self.pawn.player_camera.set_world_transform(unreal.Transform(location=self.start+unreal.Vector(500,0,12),rotation=unreal.Rotator(yaw=180)),False,True)
            unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(unreal.Rotator(yaw=180))
            self.pawn.set_editor_property('blade_qi_speed_cm_per_sec',700)
            self.pawn.fire_blade_qi()
            projectiles = unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.NLCombatProjectile)
            assert len(projectiles)==1, 'Native launcher did not create exactly one projectile'
            self.projectile = projectiles[0]
            location = self.start + unreal.Vector(480,-550,235)
            rotation = unreal.MathLibrary.find_look_at_rotation(location,self.start+unreal.Vector(175,0,0))
            self.pawn.player_camera.set_world_transform(unreal.Transform(location=location,rotation=rotation),False,True)
            unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(rotation)
            self.hp = self.enemy.vitals.get_health()
            self.zero = self.now()
            self.freeze = None
            self.report['scope'] = ['Native projectile initialized with saved 10-damage sword-Qi definition.',
                'Projectile paused briefly for shape screenshot, then its actual sweep hits a stationary enemy.',
                'No synthetic damage or manual controller acceptance.']
        now = self.now()-self.zero
        if now >= .22 and self.freeze is None and self.valid(self.projectile):
            self.projectile.set_actor_tick_enabled(False)
            self.freeze = now
        if self.freeze is not None and now >= self.freeze+.2: self.capture('HorizontalSwordQi')
        if self.freeze is not None and now >= self.freeze+.6 and self.valid(self.projectile):
            self.projectile.set_actor_tick_enabled(True)
        if now > 2.0:
            damage = self.hp-self.enemy.vitals.get_health()
            self.report['damage'] = damage
            self.report['checks'] = {'native_horizontal_qi_hit': abs(damage-10)<.01,
                'captured_horizontal_qi': 'HorizontalSwordQi' in self.shots}
            self.enemy = self.projectile = None
            self.finish()

qi_probe = QiProbe()
