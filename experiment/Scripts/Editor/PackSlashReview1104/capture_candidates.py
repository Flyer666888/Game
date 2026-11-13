"""Sample complete package retargets on the saved native character; no game assets saved."""
import json, time, math
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve()
O=P/'Docs/Gameplay/PackSlashReview1104'
CONFIG=json.loads((O/'CaptureConfig.json').read_text(encoding='utf-8-sig'))
FRAMES=O/CONFIG.get('frame_folder','CandidateFrames');FRAMES.mkdir(exist_ok=True)
source=P/'Scripts/Editor/SlashRevision1104/runtime_motion.py'
ctx={'__name__':'candidate_helper','__file__':str(source)}
exec(compile(source.read_text().replace('motion_probe = MotionProbe()',''),str(source),'exec'),ctx)

class CandidateProbe(ctx['MotionProbe']):
    def save(self):
        self.report['elapsed_seconds']=time.monotonic()-self.started
        self.report['fixture_isolation']=self.isolation
        (O/CONFIG.get('report','CandidateCapture.json')).write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.last_save=time.monotonic()

    def next_clip(self):
        self.clip_index+=1
        if self.clip_index>=len(CONFIG['clips']):
            self.report['checks']={'all_clips_captured':len(self.report['clips'])==len(CONFIG['clips']),
                'all_frames_exist':all(Path(f['file']).is_file() for c in self.report['clips'] for f in c['frames']),
                'every_clip_animates':all(max(f['hand_world'][2] for f in c['frames'])-min(f['hand_world'][2] for f in c['frames'])>5 for c in self.report['clips'])}
            self.enemy=self.mesh=self.clip=None
            self.finish();return
        spec=CONFIG['clips'][self.clip_index]
        self.clip=unreal.load_asset(spec['asset'])
        assert self.clip and self.clip.get_editor_property('skeleton')==self.mesh.get_editor_property('skeletal_mesh_asset').skeleton
        duration=self.clip.get_play_length()
        fps=CONFIG.get('fps',30)
        self.times=([duration*f for f in CONFIG['fractions']] if 'fractions' in CONFIG else [min(i/fps,duration) for i in range(math.ceil(duration*fps)+1)])
        self.row={'key':spec['key'],'label':spec['label'],'asset':spec['asset'],'source_asset':spec.get('source_asset'),
            'duration_seconds':duration,'fps':fps,'frames':[]}
        self.report['clips'].append(self.row)
        self.index=0;self.stage='pose';self.wait_frames=0

    def stage_tick(self):
        enemies=self.owned(pause=False)
        if self.enemy is None:
            if not enemies:return
            self.enemy=enemies[0]
            for e in enemies:
                e.set_lab_paused(True);e.blade.end_attack_window();e.blade.set_component_tick_enabled(False)
                if e!=self.enemy:e.set_actor_hidden_in_game(True);e.set_actor_enable_collision(False)
            self.enemy.set_actor_tick_enabled(False)
            self.enemy.get_enemy_brain().set_component_tick_enabled(False)
            self.enemy.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
            self.enemy.set_actor_rotation(unreal.Rotator(yaw=0),True)
            self.enemy.status_text.set_hidden_in_game(True)
            if 'grip_override' in CONFIG:
                g=CONFIG['grip_override']
                self.enemy.sword.set_relative_transform(unreal.Transform(location=unreal.Vector(*g['translation']),
                    rotation=unreal.Quat(*g['quaternion_xyzw']).rotator(),scale=unreal.Vector(*g['scale'])),False,True)
            self.mesh=self.enemy.get_component_by_class(unreal.SkeletalMeshComponent)
            self.mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            self.mesh.set_editor_property('visibility_based_anim_tick_option',unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
            self.mesh.set_editor_property('pause_anims',False);self.mesh.set_component_tick_enabled(True)
            self.pawn.set_actor_tick_enabled(False);self.pawn.set_actor_enable_collision(False);self.movement.disable_movement()
            for c in self.pawn.get_components_by_class(unreal.PrimitiveComponent):
                if c.get_name() in ('RightHand','HeldWeapon','RightSleeve','LeftSleeve','Mirror','MirrorFace'):c.set_hidden_in_game(True)
            center=self.enemy.get_actor_location()+unreal.Vector(0,0,5)
            self.camera_base_z=center.z
            self.camera_position=center+unreal.Vector(280,-310,100)
            self.camera_rotation=unreal.MathLibrary.find_look_at_rotation(self.camera_position,center)
            unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(self.camera_rotation)
            unreal.SystemLibrary.execute_console_command(self.world,'showhud')
            unreal.SystemLibrary.execute_console_command(self.world,'t.MaxFPS 60')
            self.report['scope']=['Original supplied sword animations retargeted to the confirmed native41 rig; sampled in Unreal on actual mesh and materials.',
                'AI/collision held during animation comparison. No manual playthrough or headset test claimed. No saved gameplay asset edited.']
            self.report['mesh']=self.mesh.get_editor_property('skeletal_mesh_asset').get_path_name()
            self.report['grip_override']=CONFIG.get('grip_override')
            self.report['clips']=[];self.clip_index=-1
            self.next_clip()
        # Follow horizontal pelvis travel so the package's full advancing steps stay visible.
        hips=self.mesh.get_socket_location('Hips')
        self.camera_position=unreal.Vector(hips.x,hips.y,self.camera_base_z)+unreal.Vector(280,-310,100)
        self.pawn.player_camera.set_world_transform(unreal.Transform(location=self.camera_position,rotation=self.camera_rotation),False,True)
        if self.stage=='pose':
            if self.index>=len(self.times):
                self.next_clip();return
            self.mesh.set_animation(self.clip);self.mesh.set_position(self.times[self.index],False);self.mesh.stop()
            self.mesh.override_animation_data(self.clip,False,False,self.times[self.index],0.0)
            self.stage='settle';self.wait_frames=0
        elif self.stage=='settle':
            self.wait_frames+=1
            if self.wait_frames<4:return
            self.path=FRAMES/(self.row['key']+f'_{self.index:03d}.png')
            self.task=unreal.AutomationLibrary.take_high_res_screenshot(960,720,str(self.path))
            self.screenshot_tasks.append(self.task)
            self.stage='capture';self.wait_frames=0
        elif self.stage=='capture':
            self.wait_frames+=1
            if self.wait_frames<12 or not self.path.is_file():return
            self.row['frames'].append({'index':self.index,'animation_time':self.times[self.index],
                'actual_time':self.mesh.get_position(),'hand_world':self.xyz(self.mesh.get_socket_location(self.enemy.sword_attach_bone)),
                'head_world':self.xyz(self.mesh.get_socket_location('Head')),'file':str(self.path)})
            self.index+=1;self.stage='pose'
            self.save()

candidate_probe=CandidateProbe()
