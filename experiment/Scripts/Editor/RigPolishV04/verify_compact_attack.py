"""Two real AI swings at the player's unmodified capsule, with actual blade damage.

Run only in the editor outside PIE. Optionally set AttackValidationSpec.json to
{"candidate_asset":"/Game/...", "target_distance_cm":125, "cycles":2}.
Only the isolated PIE enemy may receive the candidate animation override.
No resolver contact, damage event, stage transition, notify, or asset is faked.
"""
import json,time,traceback
from pathlib import Path
import unreal

OUT=Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v04')
SPEC_PATH=OUT/'AttackValidationSpec.json'
SPEC=json.loads(SPEC_PATH.read_text(encoding='utf-8')) if SPEC_PATH.exists() else {}

def vec(v):return [v.x,v.y,v.z]

class NaturalAttackProbe:
    def __init__(self):
        self.editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.started=time.monotonic();self.busy=False;self.phase='begin';self.enemy=None;self.pawn=None
        self.previous=None;self.cycle=None;self.completed=[];self.last_health=None;self.camera=None
        self.distance=float(SPEC.get('target_distance_cm',125.0));self.required_cycles=int(SPEC.get('cycles',2))
        self.report={'state':'starting','failures':[],'frames':[],'cycles':[],'health_drops':[],
            'scope':'Real first-stage enemy brain, unchanged attack timers/definition/range and real NLBlade sweeps against the normal player capsule. Other enemies are disabled in PIE; target is stationary with guard released. No resolver/damage/notify calls, no map save.'}
        self.handle=unreal.register_slate_post_tick_callback(self.tick)

    def save(self):
        self.report['cycles']=self.completed+([self.cycle] if self.cycle else [])
        (OUT/'NaturalAttackValidation.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')

    def finish(self):
        self.enemy=self.pawn=self.camera=None;self.phase='ending'
        self.level.editor_request_end_play();self.save()

    def setup(self,world,pawn,enemies):
        self.enemy=sorted(enemies,key=lambda a:a.get_name())[0];self.pawn=pawn
        self.enemy.set_combat_enabled(False)
        source=self.enemy.get_editor_property('attack_animation')
        candidate=unreal.load_asset(SPEC.get('candidate_asset','/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Attack_Sword_Natural_v04'))
        assert candidate and 'Natural_v04' in candidate.get_name(),'Assign or specify the independent Natural v04 candidate before running'
        assert candidate.get_editor_property('skeleton')==source.get_editor_property('skeleton')
        assert abs(candidate.get_play_length()-source.get_play_length())<.001
        self.enemy.set_editor_property('attack_animation',candidate)
        candidate_mesh=unreal.load_asset(SPEC.get('candidate_mesh','/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Hands_v04'))
        assert candidate_mesh and candidate_mesh.get_editor_property('skeleton')==candidate.get_editor_property('skeleton')
        self.enemy.get_component_by_class(unreal.SkeletalMeshComponent).set_skeletal_mesh_asset(candidate_mesh)
        self.enemy.get_component_by_class(unreal.SkeletalMeshComponent).set_morph_target('EnemyGrip_R',1)
        self.report['mesh']=candidate_mesh.get_path_name()
        grip_data=json.loads((OUT/'CandidateGrip.json').read_text(encoding='utf-8'))
        grip=unreal.Transform(location=unreal.Vector(*grip_data['translation']),scale=unreal.Vector(*grip_data['scale']))
        grip.rotation=unreal.Quat(*grip_data['quaternion'])
        self.enemy.set_editor_property('sword_grip_transform',grip)
        self.enemy.get_editor_property('sword').set_relative_transform(grip,False,True)
        self.report['grip']=grip_data
        brain=self.enemy.get_enemy_brain()
        assert self.distance<=brain.get_editor_property('attack_range'),'Fixture must be inside the existing authored attack range'
        timing={p:brain.get_editor_property(p) for p in ('telegraph_seconds','attack_seconds','recover_seconds','attack_range')}
        expected_rate=candidate.get_play_length()/sum(timing[k] for k in ('telegraph_seconds','attack_seconds','recover_seconds'))
        definition=self.enemy.get_editor_property('blade').get_editor_property('attack_definition')
        windows=[]
        for track in unreal.AnimationLibrary.get_animation_notify_track_names(candidate):
            for event in unreal.AnimationLibrary.get_animation_notify_events_for_track(candidate,track):
                notify=event.get_editor_property('notify_state_class')
                if notify and notify.get_class().get_name()=='NLEnemyAttackWindowNotifyState':
                    windows.append({'start':unreal.AnimationLibrary.get_anim_notify_event_trigger_time(event),'duration':unreal.AnimationLibrary.get_anim_notify_event_duration(event)})
        assert len(windows)==1 and abs(windows[0]['start']-.8)<.001 and abs(windows[0]['duration']-.23)<.001,'Damage notify changed'
        self.report.update({'candidate':candidate.get_path_name(),'original_configured_animation':source.get_path_name(),
            'enemy_class':self.enemy.get_class().get_path_name(),'timing':timing,'expected_play_rate':expected_rate,
            'attack_definition':definition.get_path_name(),'notify_windows':windows,
            'target_distance_cm':self.distance,'required_completed_cycles':self.required_cycles})
        self.enemy.get_component_by_class(unreal.CharacterMovementComponent).stop_movement_immediately()
        self.enemy.set_actor_rotation(unreal.Rotator(yaw=0),True)
        self.origin=self.enemy.get_actor_location()
        pawn.set_actor_location(self.origin+unreal.Vector(self.distance,0,0),False,True)
        pawn.set_actor_rotation(unreal.Rotator(yaw=180),True)
        pawn.set_actor_tick_enabled(False)
        pawn.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
        pawn.get_editor_property('guard').set_guard_held(False)
        pawn.get_editor_property('blade').reset_blade_history()
        vitals=pawn.get_editor_property('vitals');vitals.restore_resource_preset(vitals.get_editor_property('max_health'),vitals.get_editor_property('max_guard'))
        self.last_health=vitals.get_health()
        self.report['initial_health']=self.last_health
        capsule=pawn.get_component_by_class(unreal.CapsuleComponent)
        self.report['player_capsule']={'radius_cm':capsule.get_scaled_capsule_radius(),'half_height_cm':capsule.get_scaled_capsule_half_height(),'collision_enabled':str(capsule.get_collision_enabled())}
        self.camera=pawn.get_editor_property('player_camera');self.camera.set_editor_property('field_of_view',52)
        for component in pawn.get_components_by_class(unreal.PrimitiveComponent):
            if component.get_name() in ('RightHand','HeldWeapon','RightSleeve'):component.set_hidden_in_game(True)
        self.zero=unreal.GameplayStatics.get_time_seconds(world)
        self.enemy.set_combat_enabled(True)
        self.phase='observe';self.report['state']='observing';self.save()

    def tick(self,delta):
        if self.busy:return
        self.busy=True
        try:
            if self.phase=='ending':
                if self.editor.get_game_world() is None:
                    self.report['state']='failed' if self.report['failures'] else 'passed';self.save()
                    unreal.unregister_slate_post_tick_callback(self.handle)
                return
            assert time.monotonic()-self.started<90,'Real swing validation deadline'
            if self.phase=='begin':
                assert self.editor.get_game_world() is None,'Stop PIE first'
                self.level.editor_request_begin_play();self.phase='wait';return
            world=self.editor.get_game_world()
            if not world:return
            pawn=unreal.GameplayStatics.get_player_pawn(world,0)
            if not pawn:return
            enemies=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.NLEnemyCharacter)
            if self.phase=='wait':
                if not enemies:return
                self.setup(world,pawn,enemies)
            for enemy in enemies:
                if enemy!=self.enemy:
                    enemy.set_combat_enabled(False);enemy.set_actor_enable_collision(False)
                    enemy.set_actor_hidden_in_game(True)
            assert unreal.SystemLibrary.is_valid(self.enemy)
            elapsed=unreal.GameplayStatics.get_time_seconds(world)-self.zero
            assert elapsed<25,'No complete attack cycles within 25 game seconds'
            brain=self.enemy.get_enemy_brain();mesh=self.enemy.get_component_by_class(unreal.SkeletalMeshComponent)
            instance=mesh.get_anim_instance();animation=instance.get_animation_asset() if instance else None
            state=brain.get_state();blade=self.enemy.get_editor_property('blade');sword=self.enemy.get_editor_property('sword')
            vitals=pawn.get_editor_property('vitals');health=vitals.get_health()
            row={'t':elapsed,'state':str(state),'animation':animation.get_path_name() if animation else None,
                'animation_time':mesh.get_position(),'play_rate':mesh.get_play_rate(),
                'brain_window':brain.is_attack_window_active(),'blade_state':str(blade.get_swing_state()),
                'health':health,'enemy_location':vec(self.enemy.get_actor_location()),'player_location':vec(pawn.get_actor_location()),
                'distance_cm':(self.enemy.get_actor_location()-pawn.get_actor_location()).length(),
                'attack_id':str(brain.get_attack_instance_id()),'blade_points':{}}
            for name in ('blade_root_local','blade_mid_local','blade_tip_local'):
                row['blade_points'][name]=vec(unreal.MathLibrary.transform_location(sword.get_world_transform(),blade.get_editor_property(name)))
            self.report['frames'].append(row)
            previous_state=self.previous['state'] if self.previous else None
            if state==unreal.NLEnemyState.TELEGRAPH and previous_state!=str(state):
                assert self.cycle is None,'Attack restarted before previous recovery completed'
                self.cycle={'ordinal':len(self.completed)+1,'started':elapsed,'damage_events':[],'states':[],
                    'maximum_animation_time':0.,'active_blade_frames':0,'rewinds':0}
            if self.cycle:
                if row['state'] not in self.cycle['states']:self.cycle['states'].append(row['state'])
                if row['animation']==self.report['candidate']:
                    self.cycle['maximum_animation_time']=max(self.cycle['maximum_animation_time'],row['animation_time'])
                    assert abs(row['play_rate']-self.report['expected_play_rate'])<.001,'Unexpected attack playback acceleration'
                    if self.previous and self.previous['animation']==row['animation'] and previous_state in (str(unreal.NLEnemyState.TELEGRAPH),str(unreal.NLEnemyState.ATTACK),str(unreal.NLEnemyState.RECOVER)):
                        if row['animation_time']<self.previous['animation_time']-.05:self.cycle['rewinds']+=1
                if 'SWING_ACTIVE' in row['blade_state']:
                    self.cycle['active_blade_frames']+=1
                    assert row['brain_window'],'Blade active outside brain damage window'
                    assert row['animation']==self.report['candidate'],'Blade active while candidate animation is not playing'
            if health<self.last_health-.001:
                assert self.cycle,'Health changed before actual AI telegraph'
                prior=self.previous or row
                assert row['brain_window'] or prior['brain_window'],'Health changed outside brain attack window'
                assert 'SWING_ACTIVE' in row['blade_state'] or 'SWING_ACTIVE' in prior['blade_state'],'Health changed outside blade notify window'
                event={'time':elapsed,'amount':self.last_health-health,'current':row,'previous':prior}
                self.cycle['damage_events'].append(event);self.report['health_drops'].append(event)
            self.last_health=health
            if self.cycle and previous_state==str(unreal.NLEnemyState.RECOVER) and state!=unreal.NLEnemyState.RECOVER:
                self.cycle['ended']=elapsed;self.cycle['duration']=elapsed-self.cycle['started']
                assert len(self.cycle['damage_events'])==1,'Each normal swing must cause exactly one real blade damage event'
                assert self.cycle['active_blade_frames']>0 and self.cycle['rewinds']==0
                assert self.cycle['maximum_animation_time']>=2.333333-.10,'Attack recovery was truncated'
                assert str(unreal.NLEnemyState.ATTACK) in self.cycle['states']
                self.completed.append(self.cycle);self.cycle=None;self.save()
                if len(self.completed)>=self.required_cycles:
                    for name,value in self.report['timing'].items():assert abs(brain.get_editor_property(name)-value)<.00001,'Authored attack configuration changed'
                    assert blade.get_editor_property('attack_definition').get_path_name()==self.report['attack_definition']
                    self.report['checks']={'two_actual_ai_swings_completed':True,'real_blade_damage_each_swing':True,
                        'one_damage_event_per_swing':True,'damage_only_inside_brain_and_notify_window':True,
                        'original_attack_timers_range_and_definition_preserved':True,'full_recovery_without_clip_restart':True}
                    self.report['final_health']=health;self.finish();return
            center=self.origin+unreal.Vector(45,0,0);camera_location=center+unreal.Vector(260,-280,130)
            rotation=unreal.MathLibrary.find_look_at_rotation(camera_location,center)
            unreal.GameplayStatics.get_player_controller(world,0).set_control_rotation(rotation)
            self.camera.set_world_transform(unreal.Transform(location=camera_location,rotation=rotation),False,True)
            self.previous=row
        except Exception:
            self.report['failures'].append(traceback.format_exc());self.finish()
        finally:self.busy=False

natural_attack_probe=NaturalAttackProbe()
