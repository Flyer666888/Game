"""PIE observation of real AI reservation cancellation and skill resource gates.

The fixture holds the real player still, leaves one real sword AI running, and
temporarily grants 100 energy only for the Burst activation check. It does not
fake combat results, reset reservations, or call enemy stagger directly.
"""
import json,time,traceback
from pathlib import Path
import unreal
O=Path(r'D:\game design\experiment\Docs\Gameplay\CombatSkills_v01')
class AbilityGameplayProbe:
    def __init__(self):
        self.editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.start=time.monotonic();self.phase='begin';self.busy=False
        self.enemy=self.pawn=self.abilities=self.director=None
        self.report={'state':'starting','failures':[],'frames':[],
            'scope':'Real first-stage sword AI, real player ActivatePulse/ActivateBurst and live Director. Target is stationary and other AI disabled in temporary PIE. Burst energy=100 is an explicit fixture grant, not evidence of earning charge in manual play.'}
        self.handle=unreal.register_slate_post_tick_callback(self.tick)
    def save(self):
        O.mkdir(parents=True,exist_ok=True)
        (O/'AbilityGameplayProbe.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
    def finish(self):
        world=self.editor.get_game_world()
        if world and unreal.GameplayStatics.is_game_paused(world):unreal.GameplayStatics.set_game_paused(world,False)
        self.phase='ending';self.enemy=self.pawn=self.abilities=self.director=None
        self.level.editor_request_end_play();self.save()
    def tick(self,delta):
        if self.busy:return
        self.busy=True
        try:
            if self.phase=='ending':
                if self.editor.get_game_world() is None:
                    self.report['state']='failed' if self.report['failures'] else 'passed';self.save()
                    unreal.unregister_slate_post_tick_callback(self.handle)
                return
            assert time.monotonic()-self.start<100,'Ability gameplay deadline'
            if self.phase=='begin':
                assert self.editor.get_game_world() is None,'Stop PIE first'
                self.level.editor_request_begin_play();self.phase='wait';return
            world=self.editor.get_game_world()
            if not world:return
            pawn=unreal.GameplayStatics.get_player_pawn(world,0)
            if not pawn:return
            if self.phase=='wait':
                enemies=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.NLEnemyCharacter)
                if not enemies:return
                self.enemy=sorted(enemies,key=lambda a:a.get_name())[0];self.pawn=pawn
                for enemy in enemies:
                    if enemy!=self.enemy:
                        enemy.set_combat_enabled(False);enemy.set_actor_enable_collision(False);enemy.set_actor_hidden_in_game(True)
                self.enemy.set_combat_enabled(False)
                self.enemy.set_actor_rotation(unreal.Rotator(yaw=0),True)
                origin=self.enemy.get_actor_location()
                pawn.set_actor_location(origin+unreal.Vector(125,0,0),False,True)
                pawn.set_actor_rotation(unreal.Rotator(yaw=180),True)
                pawn.set_actor_tick_enabled(False)
                pawn.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
                pawn.get_editor_property('guard').set_guard_held(False)
                pawn.get_editor_property('vitals').restore_resource_preset(100,100)
                self.abilities=pawn.get_editor_property('abilities');assert self.abilities
                self.abilities.restore_ability_state(0)
                self.director=next(obj for obj in unreal.ObjectIterator(unreal.NLAttackDirectorSubsystem)
                    if unreal.SystemLibrary.is_valid(obj) and obj.get_outer()==world)
                self.enemy.set_combat_enabled(True)
                self.phase='await_pulse';self.report['state']='observing'
            brain=self.enemy.get_enemy_brain();blade=self.enemy.get_editor_property('blade')
            row={'time':unreal.GameplayStatics.get_time_seconds(world),'phase':self.phase,
                'enemy_state':str(brain.get_state()),'attack_window':brain.is_attack_window_active(),
                'blade_state':str(blade.get_swing_state()),'reservations':self.director.get_reservation_count(),
                'pulse_cooldown':self.abilities.get_pulse_cooldown_remaining(),'burst_energy':self.abilities.get_burst_energy()}
            self.report['frames'].append(row)
            if self.phase=='await_pulse' and brain.get_state()==unreal.NLEnemyState.TELEGRAPH:
                assert row['reservations']>=1,'Real AI has no telegraph reservation'
                self.report['pulse_before']=row
                before_position=self.enemy.get_actor_location()
                self.pawn.activate_pulse()
                assert brain.get_state()==unreal.NLEnemyState.STAGGERED,'Pulse did not interrupt real telegraph'
                assert not brain.is_attack_window_active()
                assert self.director.get_reservation_count()<row['reservations'],'Director reservation was not released'
                assert 'SWING_ACTIVE' not in str(blade.get_swing_state())
                assert self.abilities.get_pulse_cooldown_remaining()>7.5
                assert not self.abilities.try_activate_pulse(),'Repeated press bypassed cooldown'
                displacement=self.enemy.get_actor_location()-before_position
                self.report['pulse_result']={'enemies_interrupted':self.abilities.get_last_ability_result().enemies_interrupted,
                    'enemies_moved':self.abilities.get_last_ability_result().enemies_moved,
                    'horizontal_displacement_cm':(displacement.x**2+displacement.y**2)**.5}
                self.pawn.toggle_combat_pause();assert unreal.GameplayStatics.is_game_paused(world)
                self.paused_remaining=self.abilities.get_pulse_cooldown_remaining();self.pause_start=time.monotonic();self.phase='pause'
            elif self.phase=='pause' and time.monotonic()-self.pause_start>.7:
                assert abs(self.abilities.get_pulse_cooldown_remaining()-self.paused_remaining)<.01,'Pause consumed cooldown'
                assert not self.abilities.try_activate_burst(),'Paused Burst accepted'
                self.pawn.toggle_combat_pause();assert not unreal.GameplayStatics.is_game_paused(world)
                self.abilities.restore_ability_state(100)
                self.phase='await_burst'
            elif self.phase=='await_burst' and brain.get_state()==unreal.NLEnemyState.TELEGRAPH:
                self.report['burst_before']=row
                self.pawn.activate_burst()
                assert brain.get_state()==unreal.NLEnemyState.STAGGERED
                assert not brain.is_attack_window_active() and self.director.get_reservation_count()==0
                assert self.abilities.get_burst_energy()==0
                assert not self.abilities.try_activate_burst(),'Burst reused spent charge'
                self.report['checks']={'real_ai_pulse_interrupt':True,'reservation_released':True,'damage_window_closed':True,
                    'pulse_repeat_blocked':True,'pause_freezes_cooldown':True,'burst_spends_charge_and_interrupts':True}
                self.finish();return
            self.save()
        except Exception:
            self.report['failures'].append(traceback.format_exc());self.finish()
        finally:self.busy=False
ability_gameplay_probe=AbilityGameplayProbe()
