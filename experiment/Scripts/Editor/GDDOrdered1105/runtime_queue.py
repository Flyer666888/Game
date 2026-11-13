"""Observe the saved main map's pending queue, real AI entry, pause and clear."""
import json,time
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve(); O=P/'Docs/Gameplay/GDDOrdered1105'
helper=P/'Scripts/Editor/SlashRevision1104/runtime_motion.py'
ctx={'__name__':'queue_motion_helper','__file__':str(helper)}
exec(compile(helper.read_text(encoding='utf-8-sig').replace('motion_probe = MotionProbe()',''),str(helper),'exec'),ctx)

class QueueProbe(ctx['MotionProbe']):
    def __init__(self):
        self.loot_dir=P/'Saved/SaveGames/NilinOrdinaryLoot'
        self.existing_loot={p.name.lower() for p in self.loot_dir.glob('*.nllo')}
        super().__init__()
    def cleanup(self):
        super().cleanup();removed=[]
        for run_id in self.run_ids:
            path=self.loot_dir/(run_id.upper()+'.nllo')
            assert path.resolve().parent==self.loot_dir.resolve() and path.name.lower() not in self.existing_loot
            for file in (path,Path(str(path)+'.tmp')):
                if file.exists():file.unlink();removed.append(str(file))
        self.isolation['ordinary_ledger_cleanup']=removed
    def save(self):
        self.report['elapsed_seconds']=time.monotonic()-self.started
        self.report['fixture_isolation']=self.isolation
        (O/'QueueRuntime.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.last_save=time.monotonic()
    def bootstrap(self):
        super().bootstrap()
        if self.phase!='stage_active':return
        self.setup_hit=self.create_fixture('QueueSetup',999)
        self.route_index=0;self.zero=None;self.killed=False;self.cleared=False
        self.frames=[];self.report['frames']=self.frames;self.shots=set()
        self.seen_queue=False;self.cap_seen=False;self.reinforced=False
        self.pause_started=None;self.pause_done=False;self.pause_snapshot=None
        self.report['scope']='Saved map and native spawn/AI. Aoutside cleared with labelled 999-damage setup fixture; Ainside is observed live. Two further fixture defeats open slots. Fixed observer camera; no HMD/manual-play claim.'
    def previews(self,encounter):
        return [a for a in unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.SkeletalMeshActor)
                if self.valid(a) and a.get_owner()==encounter and 'NL_StagedEnemyPreview' in list(map(str,a.tags))]
    def capture(self,name):
        if name in self.shots:return
        self.shots.add(name)
        self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(O/(name+'.png'))))
    def stage_tick(self):
        if self.route_index==0:
            if self.director.get_stage_status('Aoutside')==unreal.NLLevelStageState.COMPLETED:
                self.route_index=1;self.move(self.stage_defs[1].entry_transform.translation);return
            for enemy in self.owned():
                self.resolve(self.pawn,enemy,self.setup_hit,'queue_setup_skip_prior')
            return
        encounter=self.director.get_active_encounter()
        if not encounter:return
        if self.zero is None:
            self.zero=self.now();self.pawn.set_actor_tick_enabled(False);self.movement.disable_movement()
            for c in self.pawn.get_components_by_class(unreal.PrimitiveComponent):c.set_hidden_in_game(True)
            unreal.SystemLibrary.execute_console_command(self.world,'showhud')
        camera=unreal.Vector(2600,0,1350);look=unreal.Vector(0,1500,100)
        rotation=unreal.MathLibrary.find_look_at_rotation(camera,look)
        self.pawn.player_camera.set_field_of_view(65)
        self.pawn.player_camera.set_world_transform(unreal.Transform(location=camera,rotation=rotation),False,True)
        unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(rotation)
        t=self.now()-self.zero;enemies=self.owned(pause=False);queue=self.previews(encounter)
        row={'t':t,'alive':encounter.get_alive_count(),'spawned':encounter.get_spawned_count(),
             'defeated':encounter.get_defeated_count(),'queue':len(queue),'paused':encounter.is_encounter_paused(),
             'queue_positions':[self.xyz(a.get_actor_location()) for a in queue],
             'queue_has_no_combat_identity':all(a.get_component_by_class(unreal.NLCombatIdentityComponent) is None for a in queue),
             'queue_collision_disabled':all(not a.get_actor_enable_collision() for a in queue),
             'enemy_speeds':[e.get_velocity().length() for e in enemies]}
        self.frames.append(row)
        if queue:self.seen_queue=True;self.capture('Queue_Waiting')
        if row['alive']==4 and queue:
            self.cap_seen=True;self.capture('Queue_FourActive')
        if self.cap_seen and not self.pause_done:
            if self.pause_started is None:
                encounter.set_encounter_paused(True);self.pause_started=time.monotonic()
                self.pause_snapshot=(row['spawned'],row['queue_positions']);return
            if time.monotonic()-self.pause_started<1:return
            self.report['pause_freezes_queue']=(row['spawned'],row['queue_positions'])==self.pause_snapshot
            encounter.set_encounter_paused(False);self.pause_done=True
        if t>6 and not self.killed and self.pause_done:
            for e in enemies[:2]:self.resolve(self.pawn,e,self.setup_hit,'queue_open_two_slots_fixture')
            self.killed=True
        if self.killed and row['spawned']==6:
            self.reinforced=True;self.capture('Queue_ReinforcementsEntered')
        if self.vitals.get_health()<35:
            self.vitals.restore_resource_preset(100,100)
            self.report['protective_health_restores']=self.report.get('protective_health_restores',0)+1
        if t>10 and self.reinforced and not self.cleared:
            for e in enemies:self.resolve(self.pawn,e,self.setup_hit,'queue_clear_fixture')
            self.cleared=True
        if self.director.get_stage_status('Ainside')==unreal.NLLevelStageState.COMPLETED:
            self.report['checks']={'pending_enemies_visible':self.seen_queue,'alive_cap_holds_with_queue':self.cap_seen,
                'slots_release_into_real_ai':self.reinforced,'queue_freezes_on_pause':self.report.get('pause_freezes_queue',False),
                'cosmetic_only':all(r['queue_has_no_combat_identity'] and r['queue_collision_disabled'] for r in self.frames),
                'native_ai_moves':any(any(s>100 for s in r['enemy_speeds']) for r in self.frames),
                'all_six_real_defeats':encounter.get_defeated_count()==6,'queue_removed_after_clear':not queue,
                'no_spawn_failures':encounter.get_failed_spawn_count()==0}
            self.setup_hit=None;self.finish();return
        assert t<35,'Queue observation deadline'

probe=QueueProbe()

