"""Isolated main-map keyboard playtest with actor/camera/input frame traces."""
import json,time
from collections import deque
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/PlayerBackstepIntermittent1106'
SOURCE=P/'Scripts/Editor/SlashRevision1104/runtime_motion.py'
ctx={'__name__':'interactive_motion_helper','__file__':str(SOURCE)}
exec(compile(SOURCE.read_text(encoding='utf-8-sig').replace('motion_probe = MotionProbe()',''),str(SOURCE),'exec'),ctx)

class InteractiveProbe(ctx['MotionProbe']):
    def __init__(self):
        self.ordinary_dir=P/'Saved/SaveGames/NilinOrdinaryLoot'
        self.existing_ordinary={p.name.lower() for p in self.ordinary_dir.glob('*.nllo')}
        self.buffer=[];self.recent=deque(maxlen=150);self.last_sample=None;self.frame_count=0
        self.events=[];self.s_flags={};self.protects=0
        super().__init__()
    def save(self):
        self.report['elapsed_seconds']=time.monotonic()-self.started
        self.report['fixture_isolation']=self.isolation
        self.report['frame_count']=self.frame_count;self.report['events']=self.events
        self.report['protective_health_restores']=self.protects
        (O/'Runtime.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
        if self.buffer:
            with (O/'Frames.jsonl').open('a',encoding='utf-8') as f:
                f.write(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in self.buffer))
            self.buffer=[]
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
        self.pc=unreal.GameplayStatics.get_player_controller(self.world,0)
        self.keys={}
        for name in ['W','A','S','D','LeftMouseButton','RightMouseButton','Tab']:
            key=unreal.Key();key.set_editor_property('key_name',unreal.Name(name));self.keys[name]=key
        self.report['scope']='Visible PIE main map, isolated Test.Level01 run. Real OS keyboard/mouse input. Player health restored below 60 only to permit diagnosis. Initial entry placement is fixture setup; no scripted combat or movement after bootstrap.'
        self.report['checks']={}
        self.report['module_note']='Diagnosis of intermittent movement after the earlier focus-only fix.'
        self.near_target_setup=False
    def stage_tick(self):
        control=O/'InteractiveControl.json'
        if control.exists() and json.loads(control.read_text(encoding='utf-8-sig')).get('finish'):
            self.report['checks']={'frames_recorded':self.frame_count>60,
                'input_events_recorded':any('key' in e for e in self.events) or any(
                    r['source_id']==self.player_id and r['damage']>0 for r in self.report['combat_results'])}
            self.pc=None;self.finish();return
        if not self.vitals.is_dead() and self.vitals.get_health()<60:
            self.protects+=1;self.vitals.restore_resource_preset(100,100)
        if not self.near_target_setup:
            enemies=self.owned(pause=False)
            if enemies:
                target=enemies[0].get_actor_location()
                self.move(target-unreal.Vector(0,110,0))
                self.pc.set_control_rotation(unreal.Rotator(yaw=90))
                self.near_target_setup=True
                self.events.append({'fixture':'initial_near_target_setup','t':self.now()})
        keys={k:self.pc.is_input_key_down(v) for k,v in self.keys.items()}
        row={'session':self.uid,'t':self.now(),'wall_t':time.monotonic()-self.started,
            'player':self.xyz(self.pawn.get_actor_location()),'camera':self.xyz(self.pawn.player_camera.get_world_location()),
            'camera_relative':self.xyz(self.pawn.player_camera.get_editor_property('relative_location')),
            'velocity':self.xyz(self.pawn.get_velocity()),'pending':self.xyz(self.pawn.get_pending_movement_input_vector()),
            'last_input':self.xyz(self.pawn.get_last_movement_input_vector()),'keys':keys,
            'values':{k:self.pc.get_input_analog_key_state(v) for k,v in self.keys.items()},
            'yaw':self.pc.get_control_rotation().yaw,'pitch':self.pc.get_control_rotation().pitch,
            'paused':unreal.GameplayStatics.is_game_paused(self.world),
            'cursor':self.pc.get_editor_property('show_mouse_cursor'),
            'move_mode':str(self.movement.get_editor_property('movement_mode')),
            'stage':str(self.director.get_active_stage_id())}
        try:
            base=self.pawn.get_editor_property('based_movement').get_editor_property('movement_base')
            row['movement_base']=base.get_path_name() if base else None
        except Exception:row['movement_base']='not_exposed'
        for key,value in keys.items():
            if self.s_flags.get(key,False)!=value:
                self.events.append({'key':key,'down':value,'t':row['t'],'wall_t':row['wall_t'],'player':row['player']})
        self.s_flags=keys
        if self.last_sample and row['wall_t']-self.last_sample['wall_t']<.2:
            row['delta']=[a-b for a,b in zip(row['player'],self.last_sample['player'])]
        self.last_sample=row;self.recent.append(row);self.buffer.append(row);self.frame_count+=1
        if self.frame_count%60==0:self.save()

probe=InteractiveProbe()
