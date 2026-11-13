"""Native sweeps against a posed, saved-map enemy: body versus head."""
import hashlib,json,time
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/GDDOrdered1105'
helper=P/'Scripts/Editor/SlashRevision1104/runtime_motion.py'
ctx={'__name__':'weak_motion_helper','__file__':str(helper)}
exec(compile(helper.read_text(encoding='utf-8-sig').replace('motion_probe = MotionProbe()',''),str(helper),'exec'),ctx)

class WeakProbe(ctx['MotionProbe']):
    def __init__(self):
        self.ordinary_dir=P/'Saved/SaveGames/NilinOrdinaryLoot'
        self.existing_ordinary={p.name.lower() for p in self.ordinary_dir.glob('*.nllo')}
        super().__init__()
    def begin(self):
        assert self.editor.get_game_world() is None
        assert self.level.load_level('/Game/ReversedScale/Maps/L_NilinGameplayV01')
        self.editor_director=next(a for a in self.actors.get_all_level_actors() if isinstance(a,unreal.NLLevelEncounterDirector))
        self.original_level=str(self.editor_director.level_id);assert not self.original_level.startswith('Test.')
        self.mapfile=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
        self.map_hash=hashlib.sha256(self.mapfile.read_bytes()).hexdigest();self.editor_director.level_id=self.test_level
        self.projectile_fixtures=[]
        for name in ['SphereBody','SphereHead','HorizontalQiHead']:
            a=self.actors.spawn_actor_from_class(unreal.NLCombatProjectile,unreal.Vector(0,-2500,160))
            assert a;a.tags=[unreal.Name('WeakFixture.'+self.uid+'.'+name)];self.projectile_fixtures.append(a)
        self.frames=[];self.shots=set();self.report['frames']=self.frames
        self.level.editor_request_begin_play();self.owns_pie=True;self.transition('bootstrap')
    def cleanup(self):
        for a in getattr(self,'projectile_fixtures',[]):
            if self.valid(a):assert self.actors.destroy_actor(a)
        self.projectile_fixtures=[]
        super().cleanup()
        removed=[]
        for run_id in self.run_ids:
            path=self.ordinary_dir/(run_id.upper()+'.nllo')
            assert path.resolve().parent==self.ordinary_dir.resolve()
            assert path.name.lower() not in self.existing_ordinary
            for file in (path,Path(str(path)+'.tmp')):
                if file.exists():
                    assert file.is_file()
                    file.unlink();removed.append(str(file))
        self.isolation['ordinary_ledger_cleanup']=removed
    def save(self):
        self.report['elapsed_seconds']=time.monotonic()-self.started;self.report['fixture_isolation']=self.isolation
        (O/'WeakPointRuntime.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8');self.last_save=time.monotonic()
    def bootstrap(self):
        super().bootstrap()
        if self.phase!='stage_active':return
        self.test_attack=self.create_fixture('WeakTen',10);self.case_index=0;self.current=None;self.subject=None
        self.case_rows=[];self.report['physical_cases']=self.case_rows;self.shots=set()
        self.report['scope']='Saved map/native projectile and blade sweeps against a real configured enemy. AI and pose are frozen by tick controls, combat remains enabled. 10 damage fixture and per-case health restore isolate region damage; no direct resolver contact or HMD input.'
    def on_result(self,result):
        super().on_result(result)
        if not getattr(self,'current',None):return
        if self.guid(result.target_runtime_id)!=self.guid(self.subject.combat_identity.get_runtime_id()):return
        if result.outcome==unreal.NLCombatOutcome.HIT:
            self.current['hits'].append({'damage':result.applied_damage,'weak':result.weak_point_hit,
                'multiplier':result.weak_point_multiplier,'tag':str(result.feedback_tag)})
    def capture(self,name):
        if name in self.shots:return
        self.shots.add(name);self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(O/(name+'.png'))))
    def stage_tick(self):
        enemies=self.owned(pause=False)
        if self.subject is None:
            if len(enemies)<2:return
            self.subject=enemies[0]
            for e in enemies:
                e.get_enemy_brain().set_component_tick_enabled(False);e.set_actor_tick_enabled(False)
                e.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
                e.get_component_by_class(unreal.SkeletalMeshComponent).set_editor_property('pause_anims',True)
                e.blade.set_component_tick_enabled(False)
                if e!=self.subject:e.set_actor_enable_collision(False);e.set_actor_hidden_in_game(True)
            self.pawn.set_actor_tick_enabled(False);self.movement.disable_movement();self.pawn.lower_mirror()
            self.weak=self.subject.get_component_by_class(unreal.NLWeakPointComponent)
            assert self.weak and self.weak.has_valid_weak_point()
            self.head=self.weak.get_weak_point_center();self.body=self.subject.get_actor_location()
            self.report['head_cm']=self.xyz(self.head);self.report['body_cm']=self.xyz(self.body)
            self.report['mesh']=self.subject.enemy_skeletal_mesh.get_path_name()
            self.report['weak_bone']=str(self.weak.get_weak_point_bone())
            for c in self.pawn.get_components_by_class(unreal.PrimitiveComponent):c.set_hidden_in_game(True)
            self.camera=self.body+unreal.Vector(-290,-370,150)
        rotation=unreal.MathLibrary.find_look_at_rotation(self.camera,self.head-unreal.Vector(0,0,35))
        self.pawn.player_camera.set_field_of_view(54)
        self.pawn.player_camera.set_world_transform(unreal.Transform(location=self.camera,rotation=rotation),False,True)
        unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(rotation)
        names=['SphereBody','SphereHead','BladeHead','HorizontalQiHead']
        if self.current is None:
            if self.case_index==len(names):
                self.report['checks']={r['name']:r['passed'] for r in self.case_rows}
                self.test_attack=None;self.subject=None;self.weak=None;self.finish();return
            name=names[self.case_index];self.subject.vitals.restore_resource_preset(30,100)
            self.current={'name':name,'started':self.now(),'hits':[]};self.case_rows.append(self.current)
            if name=='BladeHead':
                blade=self.pawn.blade;blade.set_editor_property('attack_definition',self.test_attack)
                blade.configure_blade(self.pawn.held_weapon,self.pawn.get_editor_property('root_component'))
                blade.reset_blade_history()
                self.blade_origin=self.head+unreal.Vector(-80,-50,0)
                self.pawn.held_weapon.set_hidden_in_game(False)
                self.pawn.held_weapon.set_world_location_and_rotation(self.blade_origin,unreal.MathLibrary.make_rot_from_z(unreal.Vector(1,0,0)),False,True)
                assert blade.begin_attack_window()
            else:
                target=self.body if name=='SphereBody' else self.head
                transform=unreal.Transform(location=target-unreal.Vector(100,0,0),rotation=unreal.Rotator())
                tag='WeakFixture.'+self.uid+'.'+name
                shot=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.NLCombatProjectile)
                          if a.actor_has_tag(tag))
                shot.set_actor_transform(transform,False,True)
                if name=='HorizontalQiHead':shot.configure_horizontal_blade_qi()
                assert shot.initialize_projectile(self.pawn,self.test_attack,unreal.Vector(1,0,0),300,3,3)
            return
        elapsed=self.now()-self.current['started']
        if self.current['name']=='BladeHead' and elapsed>.08:
            step=min(100,(elapsed-.08)*500)
            self.pawn.held_weapon.set_world_location(self.blade_origin+unreal.Vector(0,step,0),False,True)
        if self.current['hits']:
            self.capture('Weak_'+self.current['name'])
        if elapsed>1.1:
            expected=10 if self.current['name']=='SphereBody' else 15
            hits=self.current['hits'];self.current['health_after']=self.subject.vitals.get_health()
            self.current['passed']=len(hits)==1 and abs(hits[0]['damage']-expected)<.01 and hits[0]['weak']==(expected==15)
            self.pawn.blade.end_attack_window();self.pawn.held_weapon.set_hidden_in_game(True)
            self.case_index+=1;self.current=None

probe=WeakProbe()

