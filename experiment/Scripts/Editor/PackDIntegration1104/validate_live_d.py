"""Live saved-map AI probe: chosen D, real capsule travel and blade contacts."""
import unreal,json,time,math
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/PackDIntegration1104'
source=P/'Scripts/Editor/SlashRevision1104/runtime_motion.py'
ctx={'__name__':'d_live_helper','__file__':str(source)}
text=source.read_text().replace("O = P / 'Docs/Gameplay/SlashRevision1104'","O = P / 'Docs/Gameplay/PackDIntegration1104'").replace('motion_probe = MotionProbe()','')
exec(compile(text,str(source),'exec'),ctx)

class DLiveProbe(ctx['MotionProbe']):
    def save(self):
        self.report['elapsed_seconds']=time.monotonic()-self.started
        self.report['fixture_isolation']=self.isolation
        (O/'LiveD.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.last_save=time.monotonic()
    def stage_tick(self):
        super().stage_tick()
        if self.enemy is None:return
        row=self.frames[-1]
        mesh=self.enemy.get_component_by_class(unreal.SkeletalMeshComponent)
        row['animation_asset']=mesh.get_anim_instance().get_animation_asset().get_path_name()
        row['root_curve']=self.enemy.attack_root_motion_curve.get_path_name() if self.enemy.attack_root_motion_curve else None
        hips=unreal.MathLibrary.inverse_transform_location(self.enemy.get_actor_transform(),mesh.get_socket_location('Hips'))
        row['hips_relative_to_capsule']=self.xyz(hips)
        row['movement_mode']=str(self.enemy.get_component_by_class(unreal.CharacterMovementComponent).movement_mode)
        if 'configuration' not in self.report:
            self.report['configuration']={'attack':self.enemy.attack_animation.get_path_name(),'curve':row['root_curve'],
                'grip':str(self.enemy.sword_grip_transform),'range':self.brain.attack_range,
                'timing':[self.brain.telegraph_seconds,self.brain.attack_seconds,self.brain.recover_seconds]}
            self.report['scope']=['Live saved-map sword enemy using the selected D. Real AI, swept capsule travel, animation notifies and blade damage resolver.',
                'Temporary isolated save identity, fixed observer camera, scripted player retreat; not a human or HMD playtest.']
    def finish(self,failure=None):
        rows=[r for r in getattr(self,'frames',[]) if 'animation_asset' in r]
        if rows and failure is None:
            active=[r for r in rows if 'A_Wuxia_Attack_PackD' in r['animation_asset']]
            travel=[]
            for a,b in zip(rows,rows[1:]):
                if 'A_Wuxia_Attack_PackD' in a['animation_asset'] and 'A_Wuxia_Attack_PackD' in b['animation_asset']:
                    travel.append(math.dist(a['enemy_location'][:2],b['enemy_location'][:2]))
            self.report['checks'].update({'uses_selected_D':bool(active),'curve_is_assigned':all(r['root_curve'] for r in active),
                'capsule_advances_during_D':sum(travel)>50,
                'body_stays_with_capsule':bool(active) and max(math.hypot(*r['hips_relative_to_capsule'][:2]) for r in active)<75,
                'one_forward_damage_window':all(.36<=r['animation_time']<=.84 for r in rows if r['attack_window'])})
            self.report['root_motion_summary']={'total_attack_travel_cm':sum(travel),
                'max_body_offset_cm':max((math.hypot(*r['hips_relative_to_capsule'][:2]) for r in active),default=None),
                'minimum_player_health':min(r['player_health'] for r in rows)}
        super().finish(failure)

d_live_probe=DLiveProbe()
