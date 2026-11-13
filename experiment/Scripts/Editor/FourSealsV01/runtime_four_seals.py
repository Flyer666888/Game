"""Real saved-map quest integration with a temporary level/run profile.

Uses real owned-enemy deaths through the combat resolver, never broadcasts reward
events or writes stage completion. Teleports and temporary lethal contacts isolate
the authored orchestration; this is not a human/VR playthrough.
"""
import hashlib,json,re,shutil,time,traceback,uuid
from pathlib import Path
import unreal

P=Path(r'D:\game design\experiment')
O=P/'Docs/Gameplay/FourSeals_v01';O.mkdir(parents=True,exist_ok=True)
source=P/'Scripts/Editor/Gameplay/runtime_encounter_recovery_v01.py'
context={'__name__':'four_seals_base','__file__':str(source)}
prefix=source.read_text(encoding='utf-8').split('encounter_recovery_integration = EncounterRecoveryIntegration()')[0]
exec(compile(prefix,str(source),'exec'),context)
Base=context['EncounterRecoveryIntegration']

class FourSealIntegration(Base):
    OUT=O/'RuntimeIntegration.json'
    def __init__(self):
        super().__init__()
        assert self.editor.get_game_world() is None,'Stop existing PIE'
        if not self.editor.get_editor_world().get_path_name().startswith(self.MAP+'.'):assert self.level.load_level(self.MAP)
        actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        directors=[a for a in actors.get_all_level_actors() if isinstance(a,unreal.NLLevelEncounterDirector)]
        assert len(directors)==1
        self.editor_director=directors[0]
        self.original_level=str(self.editor_director.get_editor_property('level_id'))
        self.test_level='Test.FourSeals.'+uuid.uuid4().hex
        self.mapfile=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
        self.map_hash=hashlib.sha256(self.mapfile.read_bytes()).hexdigest()
        self.marker=P/'Saved/SaveGames/NilinLevelRuns'/(hashlib.sha1(self.test_level.lower().encode('utf-8')).hexdigest()+'.nlrun')
        assert not self.marker.exists()
        self.extra_ledgers=[]
        self.isolated_ready=False
        self.isolation={'state':'pending','original_level_id':self.original_level,'temporary_level_id':self.test_level,
            'map':self.MAP,'map_sha256_before':self.map_hash,'test_marker':str(self.marker),'test_run_ids':[]}
        self.write_isolation()
        self.editor_director.set_editor_property('level_id',self.test_level)
        shutil.copyfile(P/'Docs/Gameplay/EncounterRecovery_v01/EncounterConfig.json',O/'EncounterConfig.json')
        self.report['kind']='Real resolver-driven Four Seals integration on saved map with isolated test LevelId/RunId'
        self.report['four_seals']=[]
        self.report['scope'].append('Editor LevelId is changed only temporarily and restored without saving. The dedicated test profile and exact test run ledger are removed after PIE.')

    def write_isolation(self):
        (O/'FixtureIsolation.json').write_text(json.dumps(self.isolation,ensure_ascii=False,indent=2),encoding='utf-8')

    def prepare_services(self,world):
        if not super().prepare_services(world):return False
        if self.isolated_ready:return True
        controllers=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.NLEncounterController)
        self.require(all(not c.get_editor_property('enable_checkpoints') for c in controllers),
            'Fixture refuses an encounter with an active real checkpoint context')
        self.require(str(self.director.get_editor_property('level_id'))==self.test_level,'PIE did not duplicate isolated LevelId')
        initial=self.guid_text(self.run.get_run_id())
        self.extra_ledgers.append(self.LEDGER_DIR/(initial.upper()+'.nlmr'))
        self.isolation['test_run_ids'].append(initial)
        self.write_isolation()
        # Exercise the actual explicit-new-trial operation to reset any initial
        # auto-warning before testing the summit gate. Never write StageStates.
        self.director.set_actor_tick_enabled(False)
        self.require(self.run.begin_new_level_run(self.test_level),'Cannot initialize isolated new trial')
        run_id=self.guid_text(self.run.get_run_id())
        self.ledger_file=self.LEDGER_DIR/(run_id.upper()+'.nlmr')
        self.isolation['test_run_ids'].append(run_id)
        self.isolation['player_checkpoint_context']='Disabled; no main profile used'
        self.write_isolation()
        self.report['run_id_digits']=run_id
        self.report['cleanup']['file']=str(self.ledger_file)
        boss=next(s for s in self.stage_defs if len(s.get_editor_property('required_seal_ids'))==4)
        boss_id=boss.get_editor_property('stage_id')
        self.move_player(self.stage_center_capsule(boss))
        self.require(len(self.director.get_missing_seal_ids(boss_id))==4,'Boss does not expose four missing seals')
        self.require(self.director.get_stage_status(boss_id)==unreal.NLLevelStageState.LOCKED,'Boss status is not seal-locked')
        accepted=self.director.try_activate_stage(boss_id,self.pawn)
        self.require(not accepted and str(self.director.get_entry_block_reason())=='MissingRequiredSeals','Empty inventory did not block actual summit entry')
        self.require(self.director.get_active_encounter() is None,'A boss controller spawned through the missing-seal gate')
        self.report['summit_empty_gate']={'passed':True,'stage':str(boss_id),'missing':list(map(str,self.director.get_missing_seal_ids(boss_id))),
            'accepted':False,'controller_spawned':False}
        self.move_player(self.stage_center_capsule(self.stage_defs[0]))
        self.director.set_actor_tick_enabled(True)
        self.isolated_ready=True
        return True

    def verify_master_reward(self,master_id,location):
        seal=next(str(s.get_editor_property('seal_id')) for s in self.stage_defs if s.get_editor_property('master_id')==master_id)
        self.require(self.run.has_seal(seal),'Real master defeat did not automatically collect its quest seal',master=str(master_id),seal=seal)
        before=list(map(str,self.run.get_collected_seal_ids()))
        super().verify_master_reward(master_id,location)
        self.require(self.run.has_seal(seal),'Health pickup consumed the quest item')
        self.require(list(map(str,self.run.get_collected_seal_ids()))==before,'Healing interaction changed quest ownership')
        if not any(r['seal']==seal for r in self.report['four_seals']):
            self.report['four_seals'].append({'master':str(master_id),'seal':seal,'auto_collected_on_real_defeat':True,
                'independent_of_full_health_and_healing_pickup':True,'collected_count':len(before)})

    def finish(self,error=None):
        if error is None and self.run:
            self.require(len(self.report['four_seals'])==4,'Not all four actual quest drops were observed')
            self.require(len(self.run.get_collected_seal_ids())==4,'Boss completion consumed the four seals')
            self.report['boss_seals_retained_after_completion']=True
        super().finish(error)

    def cleanup_ledger(self):
        # Restore editor state before doing the marker cleanup so a filesystem
        # failure cannot leave the visible map pointed at a test identity.
        current=str(self.editor_director.get_editor_property('level_id'))
        self.require(current in (self.test_level,self.original_level),'Editor LevelId changed externally during the fixture')
        self.editor_director.set_editor_property('level_id',self.original_level)
        self.isolation['restored_level_id']=str(self.editor_director.get_editor_property('level_id'))
        self.isolation['state']='editor_restored_cleanup_pending'
        self.write_isolation()
        super().cleanup_ledger()
        for target in self.extra_ledgers:
            self.require(target.parent.resolve()==self.LEDGER_DIR.resolve(),'Unexpected fixture ledger directory')
            self.require(target.name.lower() not in {n.lower() for n in self.existing_ledgers},'Refusing existing ledger cleanup')
            for path in (target,Path(str(target)+'.tmp')):
                if path.exists():path.unlink()
        self.isolation['map_sha256_after']=hashlib.sha256(self.mapfile.read_bytes()).hexdigest()
        self.require(self.isolation['map_sha256_after']==self.map_hash,'Fixture changed the saved gameplay map')
        self.require(self.marker.parent.resolve()==(P/'Saved/SaveGames/NilinLevelRuns').resolve(),'Marker escaped test directory')
        self.require(re.fullmatch(r'[0-9a-fA-F]{40}\.nlrun',self.marker.name) is not None,'Unexpected profile filename')
        for path in (self.marker,Path(str(self.marker)+'.tmp')):
            if path.exists():path.unlink()
        self.isolation['state']='restored_without_saving_map'
        self.write_isolation()
        self.report['fixture_isolation']=self.isolation
        self.editor_director=None

try:
    four_seals_integration=FourSealIntegration()
    four_seals_integration.start()
except Exception:
    # Constructor/start failures occur before the normal deferred cleanup exists.
    restore=P/'Scripts/Editor/FourSealsV01/restore_fixture_editor.py'
    if (O/'FixtureIsolation.json').exists():
        try:exec(compile(restore.read_text(encoding='utf-8'),str(restore),'exec'),{'__name__':'__main__'})
        except Exception:unreal.log_error(traceback.format_exc())
    raise
