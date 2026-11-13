"""Saved-map owned defeats, fifth-roll guarantee and real overlap collection."""
import json,time
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/GDDOrdered1105'
helper=P/'Scripts/Editor/SlashRevision1104/runtime_motion.py'
ctx={'__name__':'loot_motion_helper','__file__':str(helper)}
exec(compile(helper.read_text(encoding='utf-8-sig').replace('motion_probe = MotionProbe()',''),str(helper),'exec'),ctx)

class LootProbe(ctx['MotionProbe']):
    def __init__(self):
        self.loot_dir=P/'Saved/SaveGames/NilinOrdinaryLoot'
        self.existing_loot={p.name.lower() for p in self.loot_dir.glob('*.nllo')}
        super().__init__()
    def save(self):
        self.report['elapsed_seconds']=time.monotonic()-self.started;self.report['fixture_isolation']=self.isolation
        (O/'LootRuntime.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8');self.last_save=time.monotonic()
    def cleanup(self):
        super().cleanup();removed=[]
        for run_id in self.run_ids:
            path=self.loot_dir/(run_id.upper()+'.nllo')
            assert path.resolve().parent==self.loot_dir.resolve() and path.name.lower() not in self.existing_loot
            for file in (path,Path(str(path)+'.tmp')):
                if file.exists():file.unlink();removed.append(str(file))
        self.isolation['ordinary_ledger_cleanup']=removed
    def bootstrap(self):
        super().bootstrap()
        if self.phase!='stage_active':return
        self.loot=next(x for x in unreal.ObjectIterator(unreal.NLOrdinaryLootSubsystem) if self.valid(x) and x.get_outer()==self.world)
        assert self.loot.get_processed_count()==0 and self.loot.configure_drop_rules(0.0,20261105)
        self.setup_hit=self.create_fixture('LootDefeat',999);self.route_index=0;self.step_name='defeats';self.last_hit=-100
        self.shots=set();self.rolls=[];self.report['rolls']=self.rolls
        self.report['scope']='Real saved-map owned defeats use a labelled 999-damage resolver fixture. Only this isolated run has 0% base chance to prove fifth-roll hard pity; production remains 20%. Paused enemy/corpse models are hidden for the pickup close-up. One real capsule overlap collects the ordinary supply. No manual/HMD play claim.'
        self.pawn.set_actor_tick_enabled(False);self.movement.disable_movement()
        for c in self.pawn.get_components_by_class(unreal.PrimitiveComponent):c.set_hidden_in_game(True)
    def capture(self,name):
        if name in self.shots:return
        self.shots.add(name);self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(O/(name+'.png'))))
    def stage_tick(self):
        if self.step_name=='defeats':
            if self.route_index==0 and self.director.get_stage_status('Aoutside')==unreal.NLLevelStageState.COMPLETED:
                self.route_index=1;self.move(self.stage_defs[1].entry_transform.translation)
            enemies=self.owned()
            if self.loot.get_processed_count()<5:
                if enemies and self.now()-self.last_hit>.4:
                    self.last_hit=self.now();before=self.loot.get_processed_count()
                    self.resolve(self.pawn,enemies[0],self.setup_hit,'loot_owned_defeat_fixture')
                    after=self.loot.get_processed_count();assert after==before+1
                    self.rolls.append({'eligible_count':after,'misses':self.loot.get_consecutive_misses(),
                        'pending':len(self.loot.get_pending_supplies())})
                return
            pending=list(self.loot.get_pending_supplies());assert len(pending)==1
            self.pickup=pending[0];self.event=self.pickup.get_event_id();self.drop=self.pickup.get_actor_location()
            self.amount=self.pickup.get_health_amount();self.report['item']={'event':str(self.event),'health':self.amount,'location':self.xyz(self.drop)}
            self.collect_position=unreal.Vector(self.drop.x,self.drop.y,self.stage_defs[self.route_index].entry_transform.translation.z)
            self.camera=self.drop+unreal.Vector(260,-340,190)
            for e in unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.NLEnemyCharacter):
                if self.valid(e):e.set_actor_hidden_in_game(True)
            self.move(self.collect_position+unreal.Vector(450,0,0));self.movement.disable_movement()
            self.step_name='full_health';self.step_started=self.now()
        rotation=unreal.MathLibrary.find_look_at_rotation(self.camera,self.drop+unreal.Vector(0,0,10))
        self.pawn.player_camera.set_field_of_view(55)
        self.pawn.player_camera.set_world_transform(unreal.Transform(location=self.camera,rotation=rotation),False,True)
        unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(rotation)
        if self.step_name=='full_health':
            if self.now()-self.step_started<.35:return
            self.capture('Loot_FifthDrop')
            if self.now()-self.step_started<1.5 or not (O/'Loot_FifthDrop.png').is_file():return
            self.report['visible_supply']={'mesh':self.pickup.visual.static_mesh.get_path_name(),
                'visible':self.pickup.visual.is_visible() and not self.pickup.visual.get_editor_property('hidden_in_game'),
                'position':self.xyz(self.pickup.visual.get_world_location()),
                'actor_hidden':self.pickup.get_editor_property('hidden'),
                'camera':self.xyz(self.pawn.player_camera.get_world_location())}
            self.report['full_health_preserves']=not self.pickup.try_collect(self.pawn) and self.valid(self.pickup)
            self.vitals.restore_resource_preset(60,100)
            unreal.GameplayStatics.set_game_paused(self.world,True)
            self.report['pause_preserves']=not self.pickup.try_collect(self.pawn) and self.valid(self.pickup)
            unreal.GameplayStatics.set_game_paused(self.world,False)
            self.step_name='overlap';self.step_started=self.now();return
        if self.step_name=='overlap':
            if self.now()-self.step_started<.25:return
            self.move(self.collect_position);self.movement.disable_movement()
            self.step_name='verify';self.step_started=self.now();return
        if self.step_name=='verify':
            if self.now()-self.step_started<.15:return
            self.capture('Loot_Collected')
            self.report['health_after']=self.vitals.get_health()
            self.report['overlap_collected']=self.loot.has_collected_supply(self.event)
            assert self.loot.record_eligible_defeat(self.event,self.drop)
            self.report['duplicate_preserves']=self.loot.get_processed_count()==5 and self.loot.get_consecutive_misses()==0 and not self.loot.get_pending_supplies()
            self.step_name='new_run';self.step_started=self.now();return
        if self.step_name=='new_run':
            if self.now()-self.step_started<.4:return
            assert self.run.begin_new_level_run(self.test_level);self.run_ids.add(self.guid(self.run.get_run_id()))
            self.report['checks']={'four_misses_then_fifth_item':[r['misses'] for r in self.rolls]==[1,2,3,4,0],
                'no_early_supplies':all(r['pending']==0 for r in self.rolls[:4]),'fifth_has_one_supply':self.rolls[-1]['pending']==1,
                'full_health_preserves_supply':self.report['full_health_preserves'],'pause_preserves_supply':self.report['pause_preserves'],
                'actual_overlap_collects':self.report['overlap_collected'],
                'actual_health_restored':abs(self.report['health_after']-(60+self.amount))<.01,
                'duplicate_does_not_reroll_or_reclaim':self.report['duplicate_preserves'],
                'new_run_starts_fresh':self.loot.get_processed_count()==0 and self.loot.get_consecutive_misses()==0 and not self.loot.get_pending_supplies()}
            self.setup_hit=None;self.pickup=None;self.loot=None;self.finish()

probe=LootProbe()
