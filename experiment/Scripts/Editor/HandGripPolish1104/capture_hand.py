"""Close-ups of the actual saved enemy hand and sword, in isolated PIE."""
import unreal,json,time
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/HandGripPolish1104'
C=json.loads((O/'CaptureConfig.json').read_text(encoding='utf-8-sig'))
OUT=O/C['folder'];OUT.mkdir(exist_ok=True)
src=P/'Scripts/Editor/SlashRevision1104/runtime_motion.py';ctx={'__name__':'hand_capture_helper','__file__':str(src)}
exec(compile(src.read_text().replace('motion_probe = MotionProbe()',''),str(src),'exec'),ctx)
class HandProbe(ctx['MotionProbe']):
    def save(self):
        self.report['elapsed_seconds']=time.monotonic()-self.started;self.report['fixture_isolation']=self.isolation
        (O/C['report']).write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8');self.last_save=time.monotonic()
    def stage_tick(self):
        enemies=self.owned(pause=False)
        if self.enemy is None:
            if not enemies:return
            self.enemy=enemies[0]
            for e in enemies:
                e.set_lab_paused(True);e.blade.end_attack_window();e.blade.set_component_tick_enabled(False)
                if e!=self.enemy:e.set_actor_hidden_in_game(True);e.set_actor_enable_collision(False)
            self.enemy.set_actor_tick_enabled(False);self.enemy.get_enemy_brain().set_component_tick_enabled(False)
            self.enemy.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
            self.enemy.status_text.set_hidden_in_game(True)
            self.mesh=self.enemy.get_component_by_class(unreal.SkeletalMeshComponent)
            self.mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            self.mesh.set_editor_property('pause_anims',False);self.mesh.set_component_tick_enabled(True)
            self.mesh.set_editor_property('visibility_based_anim_tick_option',unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
            if C.get('grip'):
                g=C['grip'];t=unreal.Transform(location=unreal.Vector(*g['p']),scale=unreal.Vector(*g['s']));t.rotation=unreal.Quat(*g['q'])
                self.enemy.sword.set_relative_transform(t,False,True)
            if C.get('sword_asset'):
                self.enemy.sword.set_static_mesh(unreal.load_asset(C['sword_asset']))
            self.pawn.set_actor_tick_enabled(False);self.pawn.set_actor_enable_collision(False);self.movement.disable_movement()
            for component in self.pawn.get_components_by_class(unreal.PrimitiveComponent):component.set_hidden_in_game(True)
            self.pawn.player_camera.set_field_of_view(40.)
            unreal.SystemLibrary.execute_console_command(self.world,'showhud')
            self.index=0;self.stage='pose';self.wait_frames=0
            self.report['frames']=[];self.report['scope']=['Actual native enemy mesh and sword in Unreal; animation sampled for hand-contact inspection. AI paused, main save isolated.']
        if self.stage=='pose':
            if self.index>=len(C['shots']):
                self.report['checks']={'all_closeups_captured':len(self.report['frames'])==len(C['shots'])}
                self.enemy=self.mesh=self.clip=None;self.finish();return
            self.shot=C['shots'][self.index]
            self.clip=unreal.load_asset(self.shot['asset']) if 'asset' in self.shot else self.enemy.get_editor_property(self.shot['property'])
            self.mesh.set_animation(self.clip);self.mesh.set_position(self.shot['time'],False);self.mesh.stop()
            self.mesh.override_animation_data(self.clip,False,False,self.shot['time'],0.0)
            self.stage='settle';self.wait_frames=0
        hand=self.mesh.get_socket_transform('RightHand',unreal.RelativeTransformSpace.RTS_WORLD)
        hand.scale3d=unreal.Vector(1,1,1)
        center=self.mesh.get_socket_location('RightHand')*.35+self.enemy.sword.get_world_location()*.65
        if C.get('camera_target_hand_cm'):
            center=unreal.MathLibrary.transform_location(hand,unreal.Vector(*C['camera_target_hand_cm']))
        position=unreal.MathLibrary.transform_location(hand,unreal.Vector(*self.shot['camera']))
        if self.shot.get('view')=='body':
            center=self.enemy.get_actor_location()
            position=center+unreal.Vector(*self.shot['camera'])
        rot=unreal.MathLibrary.find_look_at_rotation(position,center)
        self.pawn.player_camera.set_world_transform(unreal.Transform(location=position,rotation=rot),False,True)
        unreal.GameplayStatics.get_player_controller(self.world,0).set_control_rotation(rot)
        if self.stage=='settle':
            self.wait_frames+=1
            if self.wait_frames<6:return
            self.path=OUT/(self.shot['key']+'.png')
            self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1000,1000,str(self.path)))
            self.stage='capture';self.wait_frames=0
        elif self.stage=='capture':
            self.wait_frames+=1
            if self.wait_frames<12 or not self.path.is_file():return
            self.report['frames'].append({'key':self.shot['key'],'asset':self.clip.get_path_name(),'t':self.mesh.get_position(),
                'file':str(self.path),'grip':str(self.enemy.sword.get_relative_transform()),'sword_asset':self.enemy.sword.static_mesh.get_path_name()})
            self.index+=1;self.stage='pose';self.save()
hand_probe=HandProbe()
