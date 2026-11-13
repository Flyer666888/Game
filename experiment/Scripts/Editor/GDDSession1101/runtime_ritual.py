"""Saved-map rescue integration probe. Scripted contacts are labelled; no human-play claims."""
from pathlib import Path
import math,time
import unreal
P=Path(unreal.Paths.project_dir()).resolve()
source=P/'Scripts/Editor/Level01PolishV01/runtime_first_level.py'
code=source.read_text(encoding='utf-8-sig')
assert code.count('first_level_probe = FirstLevelProbe()')==1
context={'__name__':'gdd28b_ritual_probe','__file__':str(source)}
exec(compile(code.replace('first_level_probe = FirstLevelProbe()',''),str(source),'exec'),context)
context['O']=P/'Docs/Gameplay/GDDSession1101/RitualRuntime'
IDS=('Cestablish','Cinterrupt','Csiege','Cunseal')

class RitualProbe(context['FirstLevelProbe']):
    def begin(self):
        assert self.editor.get_game_world() is None
        assert self.level.load_level(context['MAP'])
        ed=next(a for a in self.actors.get_all_level_actors() if isinstance(a,unreal.NLLevelEncounterDirector))
        self.editor_director=ed
        self.original_level=str(ed.get_editor_property('level_id'))
        self.original_stages=list(ed.get_editor_property('stages'))
        chosen=[s for s in self.original_stages if str(s.stage_id) in IDS]
        assert tuple(str(s.stage_id) for s in chosen)==IDS
        self.original_c_dependency=str(chosen[0].required_stage_id)
        chosen[0].set_editor_property('required_stage_id','None')
        ed.set_editor_property('stages',chosen)
        self.seen={};self.contact_times={};self.phase_entries=[];self.last_stage='';self.pause_started=None
        self.pause_done=False;self.retry_done=False;self.pilot=None;self.pilot_interrupted=False;self.pilot_complete=False
        self.pilot_sample=None;self.empty_seconds={};self.last_sample_time=None
        self.report['scope']=[
            'Actual saved main map and authored alchemy assets; only the preceding stages are temporarily omitted to isolate Level 02.',
            'Unique test LevelId; original stage array and dependency restored without saving the map.',
            'Ordinary enemies and later breakers are paused and defeated with explicitly labelled ordinary melee resolver contacts; no claim of continuous player combat.',
            'One real FormationBreaker uses native navigation, targeting, HighThreat scheduling, telegraph, finite interference and swept projectile damage without manually firing events.',
            'Runs the authored 240 effective-second rescue rate; no time acceleration or progress injection.',
            'Tests local pause and genuine player-death/retry rollback. No manual health restores during combat.',
            'No physical PICO/controller acceptance or frame-rate benchmark.'
        ]
        super().begin()

    def bootstrap(self):
        self.world=self.editor.get_game_world()
        if not self.world:return
        self.pawn=unreal.GameplayStatics.get_player_pawn(self.world,0)
        if not self.pawn:return
        self.director=unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.NLLevelEncounterDirector)[0]
        assert str(self.director.level_id)==self.test_level
        instance=unreal.GameplayStatics.get_game_instance(self.world)
        def sub(cls,outer):return next(o for o in unreal.ObjectIterator(cls) if self.valid(o) and o.get_outer()==outer)
        self.run=sub(unreal.NLRunStateSubsystem,instance)
        self.resolver=sub(unreal.NLCombatResolverSubsystem,self.world)
        self.run_ids.add(self.guid(self.run.get_run_id()))
        self.isolation['test_run_ids']=sorted(self.run_ids)
        self.vitals=self.pawn.get_editor_property('vitals')
        self.movement=self.pawn.get_component_by_class(unreal.CharacterMovementComponent)
        self.goal=unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.NLRitualObjective)[0]
        assert str(self.goal.objective_stable_id)=='Objective.Nilin.AlchemyRescue'
        assert self.goal.effective_rescue_seconds==240
        self.stage_defs=list(self.director.stages)
        self.result_listener=self.on_result
        self.resolver.get_editor_property('on_combat_result').add_callable(self.result_listener)
        self.player_id=self.guid(self.pawn.combat_identity.get_runtime_id())
        self.goal_id=self.guid(self.goal.combat_identity.get_runtime_id())
        self.move(self.stage_defs[0].entry_transform.translation)
        self.aim(self.goal)
        self.transition('stage_active')

    def shot(self,name):
        unreal.AutomationLibrary.take_high_res_screenshot(1600,1000,str(context['O']/(name+'.png')))

    def stage_tick(self):
        now=self.now();stage=str(self.director.get_active_stage_id())
        progress=self.goal.get_rescue_progress();integrity=self.goal.get_integrity()
        self.report['live']={'stage':stage,'game_time':now,'progress':progress,'integrity':integrity,
            'interference_sources':self.goal.get_interference_source_count(),
            'player_health':self.vitals.get_health(),
            'alive':self.director.get_active_encounter().get_alive_count() if self.director.get_active_encounter() else 0}
        if self.last_sample_time is not None and self.director.get_active_encounter():
            if self.director.get_active_encounter().get_alive_count()==0 and not self.goal.is_completion_pending():
                self.empty_seconds[stage]=self.empty_seconds.get(stage,0)+max(0,min(now-self.last_sample_time,.5))
        self.last_sample_time=now
        if stage in IDS and stage!=self.last_stage:
            snapshot=self.director.get_retry_objective_snapshot()
            row={'stage':stage,'game_time':now,'entry_progress':snapshot.rescue_progress,
                 'entry_integrity':snapshot.integrity,'target':self.goal.get_progress_target()}
            expected=IDS.index(stage)*25
            assert abs(snapshot.rescue_progress-expected)<.01,row
            if self.phase_entries:assert snapshot.integrity<=self.phase_entries[-1]['entry_integrity']+.01
            self.phase_entries.append(row);self.last_stage=stage
            self.report['phase_entries']=self.phase_entries
        if all(self.director.get_stage_status(i)==unreal.NLLevelStageState.COMPLETED for i in IDS):
            assert self.goal.is_rescue_completed() and abs(progress-100)<.01
            assert self.goal.get_completion_event_count()==1
            assert self.goal.get_phase_completion_event_count()==3
            assert self.pilot_complete and self.retry_done and self.pause_done
            final_growth=self.progression()
            assert final_growth['level']==3 and abs(final_growth['damage_multiplier']-1.5)<.001
            assert final_growth['ling_qi']==len(final_growth['event_ids'])
            self.report['checks'].update({'four_phases_completed':True,'one_final_rescue_event':True,
                'three_intermediate_events':True,'no_remaining_interference':self.goal.get_interference_source_count()==0,
                'level_three_guarantee_without_unearned_lingqi':True})
            self.report['final']={'integrity':integrity,'progress':progress,'game_time':now,
                'empty_stage_seconds':self.empty_seconds,'player_health':self.vitals.get_health(),
                'growth':final_growth}
            self.shot('RescueComplete');self.finish();return
        encounter=self.director.get_active_encounter()
        if not encounter:return
        assert not self.vitals.is_dead(),'Player unexpectedly died outside the explicit retry fixture'
        assert self.director.get_stage_status(stage)!=unreal.NLLevelStageState.FAILED,str(self.director.get_failure_reason())
        if stage=='Cestablish' and progress>=5 and not self.pause_done:
            if self.pause_started is None:
                encounter.set_encounter_paused(True)
                self.pause_started=time.monotonic();self.pause_progress=progress
                self.shot('RitualPaused')
            assert abs(self.goal.get_rescue_progress()-self.pause_progress)<.001
            if time.monotonic()-self.pause_started>=2:
                encounter.set_encounter_paused(False);self.pause_done=True
                self.report['checks']['local_pause_freezes_rescue_progress']=True
            return
        enemies=self.owned(pause=False)
        if stage=='Csiege' and progress>=53 and not self.retry_done and enemies:
            entry=self.director.get_retry_objective_snapshot()
            growth=self.director.get_retry_progression_state()
            result=self.resolve(enemies[0],self.pawn,self.death_damage,'explicit_player_death_fixture')
            if not self.vitals.is_dead():return
            assert self.director.get_stage_status(stage)==unreal.NLLevelStageState.FAILED
            self.pawn.reset_lab()
            assert not self.vitals.is_dead()
            assert abs(self.goal.get_rescue_progress()-entry.rescue_progress)<.001
            assert abs(self.goal.get_integrity()-entry.integrity)<.001
            assert self.run.get_progression_state().ling_qi==growth.ling_qi
            assert all(self.director.get_stage_status(i)==unreal.NLLevelStageState.COMPLETED for i in IDS[:2])
            self.retry_done=True
            self.report['checks']['death_retry_restores_phase_entry_and_prior_clears']=True
            self.report['retry_attempts'].append({'stage':stage,'before_progress':progress,
                'restored_progress':entry.rescue_progress,'restored_integrity':entry.integrity})
            return
        for enemy in enemies:
            key=self.guid(enemy.combat_identity.get_runtime_id())
            first=self.seen.setdefault(key,now)
            brain=enemy.get_enemy_brain()
            breaker=brain.role==unreal.NLEnemyRole.FORMATION_BREAKER
            if breaker and self.pilot is None and not self.pilot_complete:
                self.pilot=enemy;self.pilot_since=now;self.pilot_start=self.xyz(enemy.get_actor_location())
                self.pilot_integrity=integrity
            if enemy==self.pilot and not self.pilot_complete:
                assert now-self.pilot_since<45,'Real breaker failed to navigate/cast in 45 seconds'
                interfering=enemy.talisman_attack.is_interfering()
                if interfering:
                    if self.pilot_sample is None:
                        self.pilot_sample=(now,progress)
                        self.aim(enemy);self.shot('RealBreakerChannel')
                    elif now-self.pilot_sample[0]>.15 and abs(progress-self.pilot_sample[1])<.01:
                        self.report['checks']['real_channel_stops_rescue_progress']=True
                if interfering and integrity<self.pilot_integrity and not self.pilot_interrupted:
                    moved=math.dist(self.pilot_start,self.xyz(enemy.get_actor_location()))
                    assert moved>100,'Breaker did not navigate meaningfully'
                    before=self.goal.get_interference_source_count()
                    hit=self.resolve(self.pawn,enemy,self.low_damage,'ordinary_nonlethal_interrupt_fixture')
                    assert hit.applied_damage>0 and not enemy.vitals.is_dead()
                    assert before>0 and self.goal.get_interference_source_count()==0
                    self.pilot_interrupted=True;self.pilot_hit_time=now
                    self.report['checks']['native_navigation_and_swept_ritual_damage']=True
                    self.report['checks']['nonlethal_hit_interrupts_real_channel']=True
                    self.report['breaker_observation']={'walked_cm':moved,'integrity_before':self.pilot_integrity,
                        'integrity_after':integrity,'hit_damage':hit.applied_damage,'time_until_interrupt':now-self.pilot_since}
                if not self.pilot_interrupted or now-self.pilot_hit_time<1:continue
            else:
                enemy.set_lab_paused(True)
            if now-first<5 or now-self.contact_times.get(key,-1000)<.8:continue
            self.contact_times[key]=now
            self.resolve(self.pawn,enemy,self.melee,'ordinary_melee_scripted_clear')
            if enemy==self.pilot and enemy.vitals.is_dead():
                self.pilot_complete=True;self.report['checks']['breaker_death_leaves_no_interference']=self.goal.get_interference_source_count()==0
                self.aim(self.goal)

    def cleanup(self):
        if hasattr(self,'original_stages') and self.editor_director and self.valid(self.editor_director):
            first=next(s for s in self.original_stages if str(s.stage_id)==IDS[0])
            first.set_editor_property('required_stage_id',self.original_c_dependency)
            self.editor_director.set_editor_property('stages',self.original_stages)
            restored=list(self.editor_director.get_editor_property('stages'))
            assert len(restored)==16
            assert str(next(s for s in restored if str(s.stage_id)==IDS[0]).required_stage_id)==self.original_c_dependency
            self.isolation['full_stage_array_restored']=True
        super().cleanup()

ritual_probe=RitualProbe()
