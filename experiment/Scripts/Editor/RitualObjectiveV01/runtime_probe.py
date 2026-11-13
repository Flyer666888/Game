"""Exercise real hostile projectile damage and isolated ritual rules in the saved lab.

Only PIE state changes. Source deaths use explicit real resolver contacts; no
manual player input, continuous playthrough or VR acceptance is claimed.
"""
import json,time,traceback
from pathlib import Path
import unreal
OUT=Path(unreal.Paths.project_dir()).resolve()/'Docs/Gameplay/RitualObjective_v01';OUT.mkdir(parents=True,exist_ok=True)

class RitualProbe:
    def __init__(self):
        self.editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.started=time.monotonic();self.phase='begin';self.busy=False
        self.goal=self.trial=self.pawn=self.resolver=None;self.pause_started=0
        self.report={'state':'starting','failures':[],'events':[],'scope':'Saved isolated OBJ-01 lab. Native training launcher creates real swept projectiles and the real resolver damages the ritual. Source defeats are explicit resolver contacts, interruption/restoration use public runtime APIs. No map or asset save, synthetic input or headset test.'}
        self.handle=unreal.register_slate_post_tick_callback(self.tick)
    def save(self):
        (OUT/'RuntimeProbe.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
    def event(self,name,**extra):
        self.report['events'].append({'name':name,'integrity':self.goal.get_integrity(),'progress':self.goal.get_rescue_progress(),
            'interference':self.goal.get_interference_source_count(),'threats':self.goal.get_remaining_threat_count(),
            'objective_state':str(self.goal.get_objective_state()),'trial_state':str(self.trial.get_trial_result()),**extra});self.save()
    def finish(self):
        world=self.editor.get_game_world()
        if world:unreal.GameplayStatics.set_game_paused(world,False)
        self.goal=self.trial=self.pawn=self.resolver=None;self.phase='ending';self.level.editor_request_end_play();self.save()
    def defeat(self,actor):
        definition=unreal.load_asset('/Game/ReversedScale/Combat/DA_YueyaoMelee');assert definition
        vitals=actor.get_component_by_class(unreal.NLCombatVitalsComponent)
        source_id=self.pawn.get_component_by_class(unreal.NLCombatIdentityComponent).ensure_runtime_id()
        target_id=actor.get_component_by_class(unreal.NLCombatIdentityComponent).ensure_runtime_id()
        for _ in range(40):
            if vitals.is_dead():return
            contact=unreal.NLCombatContact();contact.attack_instance_id=unreal.GuidLibrary.new_guid()
            contact.source_runtime_id=source_id;contact.target_runtime_id=target_id;contact.projectile_generation=-1
            contact.contact_time_seconds=unreal.GameplayStatics.get_time_seconds(self.world)
            contact.attack_definition_id=definition.get_editor_property('stable_id');contact.hit_position=actor.get_actor_location()
            result=self.resolver.resolve_contact(self.pawn,actor,contact,definition)
            assert result.get_editor_property('outcome')==unreal.NLCombatOutcome.HIT
        assert vitals.is_dead(),'Could not defeat lab source using real melee resolver'
    def tick(self,delta):
        if self.busy:return
        self.busy=True
        try:
            if self.phase=='ending':
                if self.editor.get_game_world() is None:
                    self.report['state']='failed' if self.report['failures'] else 'passed';self.save()
                    unreal.unregister_slate_post_tick_callback(self.handle)
                return
            assert time.monotonic()-self.started<180,'Ritual lab probe deadline'
            if self.phase=='begin':
                assert self.editor.get_game_world() is None
                assert '/L_RitualObjectiveV01.' in self.editor.get_editor_world().get_path_name(),'Load independent ritual lab first'
                self.level.editor_request_begin_play();self.phase='wait';return
            self.world=self.editor.get_game_world()
            if not self.world:return
            if self.phase=='wait':
                trials=unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.NLRitualLabController)
                pawn=unreal.GameplayStatics.get_player_pawn(self.world,0)
                if not trials or not pawn or str(trials[0].get_trial_result())!='Ready':return
                self.trial=trials[0];self.goal=self.trial.get_editor_property('objective');self.pawn=pawn
                self.resolver=next(o for o in unreal.ObjectIterator(unreal.NLCombatResolverSubsystem)
                    if unreal.SystemLibrary.is_valid(o) and o.get_outer()==self.world)
                self.casters=list(self.trial.get_editor_property('interference_actors'))
                self.launchers=list(self.trial.get_editor_property('launchers'))
                assert self.trial.start_trial();assert self.goal.get_interference_source_count()==2
                self.started_game=unreal.GameplayStatics.get_time_seconds(self.world);self.phase='physical_damage';self.event('started_two_sources')
                self.preview_task=unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(OUT/'LabPreview.png'))
            now=unreal.GameplayStatics.get_time_seconds(self.world)
            if self.phase=='physical_damage':
                assert now-self.started_game<20,'Native hostile projectile did not contact ritual'
                assert self.goal.get_rescue_progress()==0,'Interference failed to stop progress'
                if self.goal.get_integrity()<=90:
                    self.event('real_swept_projectile_damaged_ritual');self.paused_integrity=self.goal.get_integrity()
                    self.paused_progress=self.goal.get_rescue_progress();self.paused_game=now
                    unreal.GameplayStatics.set_game_paused(self.world,True);self.pause_started=time.monotonic();self.phase='paused'
            elif self.phase=='paused' and time.monotonic()-self.pause_started>=1.0:
                assert self.goal.get_integrity()==self.paused_integrity and self.goal.get_rescue_progress()==self.paused_progress
                assert abs(now-self.paused_game)<.001,'Pause advanced gameplay clock'
                self.event('global_pause_froze_ritual');unreal.GameplayStatics.set_game_paused(self.world,False)
                self.defeat(self.casters[0]);assert self.goal.get_interference_source_count()==1
                self.event('first_real_resolver_defeat_removed_one_source')
                assert self.goal.unregister_interference_source('Lab.Caster.02')
                assert self.goal.get_interference_source_count()==0
                self.event('second_source_interrupted');self.resumed_game=now;self.phase='progress'
            elif self.phase=='progress' and now-self.resumed_game>=1.0:
                assert self.goal.get_rescue_progress()>0
                for launcher in self.launchers:launcher.set_firing_enabled(False)
                for shot in unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.NLCombatProjectile):shot.destroy_actor()
                snapshot=self.goal.capture_objective_snapshot();assert self.goal.restore_objective_snapshot(snapshot)
                assert self.goal.finish_source_rebuild()==0
                for index,actor in enumerate(self.trial.get_editor_property('required_threat_actors'),1):
                    self.goal.register_remaining_threat('Lab.Threat.%02d'%index,actor)
                self.event('runtime_snapshot_restored',saved_integrity=snapshot.integrity,saved_progress=snapshot.rescue_progress)
                self.trial.reset_trial();assert self.goal.get_interference_source_count()==0 and self.goal.get_rescue_progress()==0
                assert self.goal.get_integrity()==100
                self.event('full_retry_cleared_sources_and_restored_integrity')
                self.trial.set_editor_property('lab_rescue_seconds',1.0);assert self.trial.start_trial()
                for actor in self.trial.get_editor_property('required_threat_actors'):self.defeat(actor)
                self.phase='completion';self.completion_began=now
            elif self.phase=='completion':
                assert now-self.completion_began<10,'Objective failed to complete after sources/threats cleared'
                if self.goal.is_rescue_completed():
                    assert str(self.trial.get_trial_result())=='Completed' and self.goal.get_completion_event_count()==1
                    self.event('one_shot_completion_after_required_threats')
                    self.goal.set_editor_property('max_integrity',10.0);self.trial.set_editor_property('lab_rescue_seconds',30.0)
                    assert self.trial.start_trial();self.phase='failure';self.failure_began=now
            elif self.phase=='failure':
                assert now-self.failure_began<20,'Real hostile projectile did not break 10-integrity trial'
                if self.goal.is_failure_locked():
                    assert self.goal.get_failure_event_count()==1 and str(self.trial.get_trial_result())=='Failed'
                    assert self.goal.get_interference_source_count()==0
                    self.event('real_projectile_failure_stopped_trial_and_cleared_sources')
                    self.trial.reset_trial();assert not self.goal.is_failure_locked() and not self.goal.is_rescue_completed()
                    assert self.goal.get_integrity()==10 and self.goal.get_rescue_progress()==0
                    self.event('retry_after_failure_ready');self.report['checks']={
                        'actual_projectile_damage':True,'two_independent_sources':True,'global_pause':True,
                        'source_death_and_interrupt':True,'snapshot_roundtrip':True,'retry_cleanup':True,
                        'one_shot_success':True,'actual_projectile_failure':True}
                    self.finish()
        except Exception:
            self.report['failures'].append(traceback.format_exc());self.finish()
        finally:self.busy=False

ritual_probe=RitualProbe()
