"""Observe no-input player movement during native melee on the saved main map."""
import json,time
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve(); O=P/'Docs/Gameplay/PlayerBackstep1106'
SOURCE=P/'Scripts/Editor/SlashRevision1104/runtime_motion.py'
ctx={'__name__':'backstep_helper','__file__':str(SOURCE)}
exec(compile(SOURCE.read_text(encoding='utf-8-sig').replace('motion_probe = MotionProbe()',''),str(SOURCE),'exec'),ctx)

class BackstepProbe(ctx['MotionProbe']):
    def __init__(self):
        self.ordinary_dir=P/'Saved/SaveGames/NilinOrdinaryLoot'
        self.existing_ordinary={p.name.lower() for p in self.ordinary_dir.glob('*.nllo')}
        super().__init__()
    def save(self):
        self.report['elapsed_seconds']=time.monotonic()-self.started
        self.report['fixture_isolation']=self.isolation
        (O/'Runtime.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
    def cleanup(self):
        super().cleanup();removed=[]
        for run_id in self.run_ids:
            path=self.ordinary_dir/(run_id.upper()+'.nllo')
            assert path.resolve().parent==self.ordinary_dir.resolve() and path.name.lower() not in self.existing_ordinary
            for file in (path,Path(str(path)+'.tmp')):
                if file.exists():file.unlink();removed.append(str(file))
        self.isolation['ordinary_ledger_cleanup']=removed
    def bootstrap(self):
        super().bootstrap()
        if self.phase!='stage_active':return
        self.report['scope']='Real saved main map, zero movement input, native StartDesktopSlash and normal player CharacterMovement. AI frozen only in stationary cases; explicit short-range placements are fixture setup.'
        self.report['cases']=[];self.subject=None;self.case_index=0;self.case=None
    def stage_tick(self):
        names=[('idle_clear',100,False,2),('slash_clear',100,True,3),
               ('idle_touch',57,False,2),('slash_touch',57,True,3),
               ('idle_overlap',45,False,2),('slash_overlap',45,True,3),
               ('live_exchanges',105,True,8),('live_lunge',65,False,8)]
        if self.subject is None:
            enemies=self.owned(pause=False)
            if len(enemies)<2:return
            self.subject=enemies[0];self.subject_origin=self.subject.get_actor_location()
            for e in enemies:
                e.get_enemy_brain().set_component_tick_enabled(False)
                e.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
                if e!=self.subject:e.set_actor_enable_collision(False);e.set_actor_hidden_in_game(True)
            self.pawn.lower_mirror()
        if self.case is None:
            if self.case_index==len(names):
                self.report['checks']={'eight_cases_recorded':len(self.report['cases'])==8,
                    'no_input_xy_drift':all(r['max_xy_drift_cm']<.1 for r in self.report['cases']),
                    'native_hits_observed':any(r['origin']=='engine_physical' and r['target_defeated']==False and r['damage']>0 for r in self.report['combat_results'])}
                self.subject=None;self.finish();return
            name,distance,slash,duration=names[self.case_index]
            self.subject.set_actor_location(self.subject_origin,False,True)
            self.subject.vitals.restore_resource_preset(30,100)
            live=name.startswith('live_')
            self.subject.get_enemy_brain().set_component_tick_enabled(live)
            enemy_movement=self.subject.get_component_by_class(unreal.CharacterMovementComponent)
            if live:
                enemy_movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)
                self.subject.set_combat_enabled(False);self.subject.set_combat_enabled(True)
            else:enemy_movement.disable_movement()
            self.move(self.subject_origin-unreal.Vector(distance,0,0))
            self.movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)
            unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(unreal.Rotator())
            self.zero=self.now();self.next_slash=.4
            self.case={'name':name,'initial':self.xyz(self.pawn.get_actor_location()),'samples':[]}
            self.report['cases'].append(self.case)
        name,distance,slash,duration=names[self.case_index]
        elapsed=self.now()-self.zero
        if self.vitals.get_health()<60:self.vitals.restore_resource_preset(100,100)
        if slash and elapsed>=self.next_slash:
            self.subject.vitals.restore_resource_preset(30,100)
            self.pawn.start_desktop_slash();self.next_slash+=.8
        self.case['samples'].append({'t':elapsed,'player':self.xyz(self.pawn.get_actor_location()),
            'velocity':self.xyz(self.pawn.get_velocity()),'pending_input':self.xyz(self.pawn.get_pending_movement_input_vector()),
            'last_input':self.xyz(self.pawn.get_last_movement_input_vector()),
            'enemy_state':str(self.subject.get_enemy_brain().get_state()),
            'enemy':self.xyz(self.subject.get_actor_location()),'enemy_health':self.subject.vitals.get_health()})
        if elapsed>=duration:
            self.case['delta_x_cm']=self.pawn.get_actor_location().x-self.case['initial'][0]
            initial=self.case['initial']
            self.case['max_xy_drift_cm']=max(((s['player'][0]-initial[0])**2+(s['player'][1]-initial[1])**2)**.5 for s in self.case['samples'])
            self.case_index+=1;self.case=None;self.save()

probe=BackstepProbe()
