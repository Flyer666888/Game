"""Sample the currently equipped UE attack for a deterministic animation review video."""
import json,time,hashlib
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve()
O=P/'Docs/Gameplay/CombatFeel1104'
FRAMES=O/'DemoFrames';FRAMES.mkdir(exist_ok=True)
source=P/'Scripts/Editor/CombatFeel1104/runtime_motion.py'
ctx={'__name__':'demo_helper','__file__':str(source)}
exec(compile(source.read_text().replace('motion_probe = MotionProbe()',''),str(source),'exec'),ctx)

class DemoProbe(ctx['MotionProbe']):
    def save(self):
        self.report['elapsed_seconds']=time.monotonic()-self.started
        (O/'DemoCapture.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')

    def stage_tick(self):
        enemies=self.owned(pause=False)
        if self.enemy is None:
            if not enemies:return
            self.enemy=enemies[0]
            for e in enemies:
                e.set_lab_paused(True)
                if e!=self.enemy:
                    e.set_actor_hidden_in_game(True);e.set_actor_enable_collision(False)
            self.enemy.set_actor_tick_enabled(False)
            self.enemy.get_enemy_brain().set_component_tick_enabled(False)
            self.enemy.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
            self.enemy.set_actor_rotation(unreal.Rotator(yaw=0),True)
            self.enemy.status_text.set_hidden_in_game(True)
            self.mesh=self.enemy.get_component_by_class(unreal.SkeletalMeshComponent)
            self.mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            self.clip=self.enemy.attack_animation
            self.mesh.set_animation(self.clip)
            self.mesh.play_animation(self.clip,False)
            self.mesh.set_play_rate(1.0)
            self.mesh.set_editor_property('visibility_based_anim_tick_option',unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
            self.mesh.set_editor_property('pause_anims',False)
            self.mesh.set_component_tick_enabled(True)
            self.pawn.set_actor_tick_enabled(False)
            self.movement.disable_movement()
            for c in self.pawn.get_components_by_class(unreal.PrimitiveComponent):
                if c.get_name() in ('RightHand','HeldWeapon','RightSleeve','LeftSleeve','Mirror','MirrorFace'):
                    c.set_hidden_in_game(True)
            center=self.enemy.get_actor_location()+unreal.Vector(0,0,5)
            position=center+unreal.Vector(255,-285,90)
            rotation=unreal.MathLibrary.find_look_at_rotation(position,center)
            self.camera_position=position;self.camera_rotation=rotation
            self.pawn.player_camera.set_world_transform(unreal.Transform(location=position,rotation=rotation),False,True)
            unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(rotation)
            unreal.SystemLibrary.execute_console_command(self.world,'showhud')
            unreal.SystemLibrary.execute_console_command(self.world,'t.MaxFPS 60')
            self.report['scope']=['Current saved v06 UE animation sampled at 30 fps on actual equipped mesh/materials.',
                'AI is held still while the animation clip is sampled; this is animation review, not real-time gameplay recording.',
                'No new source rig has been applied.']
            self.report['animation']=self.clip.get_path_name()
            self.report['mesh']=self.mesh.get_editor_property('skeletal_mesh_asset').get_path_name()
            self.report['duration_seconds']=self.clip.get_play_length()
            self.index=0;self.stage='pose';self.wait_frames=0
        self.pawn.player_camera.set_world_transform(unreal.Transform(location=self.camera_position,rotation=self.camera_rotation),False,True)
        if self.stage=='pose':
            if self.index>45:
                hands=[r['hand_world'] for r in self.report['frames']]
                self.report['checks']={'all_frames_captured':all((FRAMES/f'frame_{i:03d}.png').is_file() for i in range(46)),
                    'animated_hand_moves': max(p[2] for p in hands)-min(p[2] for p in hands)>10}
                self.enemy=self.mesh=self.clip=None
                self.finish();return
            self.mesh.set_animation(self.clip)
            self.mesh.set_position(self.index/30.0,False)
            self.mesh.stop()
            self.mesh.override_animation_data(self.clip,False,False,self.index/30.0,0.0)
            self.stage='settle';self.wait_frames=0
        elif self.stage=='settle':
            self.wait_frames+=1
            if self.wait_frames<4:return
            self.path=FRAMES/f'frame_{self.index:03d}.png'
            self.task=unreal.AutomationLibrary.take_high_res_screenshot(960,720,str(self.path))
            self.stage='capture';self.capture_started=time.monotonic();self.wait_frames=0
        elif self.stage=='capture':
            self.wait_frames+=1
            if self.wait_frames<12 or not self.path.is_file():return
            self.report['frames'].append({'index':self.index,'animation_time':self.index/30.0,
                'actual_time':self.mesh.get_position(),'instance':self.mesh.get_anim_instance().get_class().get_name(),
                'asset':str(self.mesh.get_anim_instance().get_animation_asset()),'paused':self.mesh.get_editor_property('pause_anims'),
                'hand_world':self.xyz(self.mesh.get_socket_location('hand_r')),'file':str(self.path)})
            self.index+=1;self.stage='pose';self.save()

demo_probe=DemoProbe()
