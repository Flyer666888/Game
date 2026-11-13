"""Compare original and candidate clips on the real combat mesh in unsaved PIE."""
import json,time,traceback
from pathlib import Path
import unreal
OUT=Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v01')
PREFIX='/Game/ReversedScale/Characters/WuxiaMale/Animations/'
class BodyPreview:
    def __init__(self):
        self.editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.start=time.monotonic();self.busy=False;self.phase='start';self.enemies=[];self.camera=None;self.task=None;self.index=0;self.changed=0;self.camera_transform=None
        self.specs=[('Wuxia_Idle_Planted',0),('Wuxia_Attack_Sword',.6),('Wuxia_Attack_Sword',1.1),('Wuxia_Attack_Sword',1.5),('Wuxia_Walk_Sword',.2),('Wuxia_Walk_Sword',.8),('Wuxia_Hit_Sword',.3),('Wuxia_Cast_Talisman',1.1)]
        self.report={'state':'starting','scope':'Original on left, candidate on right, real meshes in temporary PIE. Enemy simulation disabled to inspect identical sample times. No saved map changes.','captures':[],'failures':[]}
        self.handle=unreal.register_slate_post_tick_callback(self.tick)
    def save(self):
        (OUT/'BodyPreview.json').write_text(json.dumps(self.report,indent=2),encoding='utf-8')
    def end(self):
        self.enemies=[];self.camera=self.task=None;self.phase='ending';self.level.editor_request_end_play();self.save()
    def tick(self,delta):
        if self.busy:return
        self.busy=True
        try:
            if self.phase=='ending':
                if self.editor.get_game_world() is None:
                    self.report['state']='failed' if self.report['failures'] else 'passed';self.save();unreal.unregister_slate_post_tick_callback(self.handle)
                return
            assert time.monotonic()-self.start<100,'Preview deadline exceeded'
            if self.phase=='start':
                assert self.editor.get_game_world() is None
                self.level.editor_request_begin_play();self.phase='wait';return
            world=self.editor.get_game_world()
            if not world:return
            pawn=unreal.GameplayStatics.get_player_pawn(world,0)
            if not pawn:return
            if self.phase=='wait':
                enemies=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.NLEnemyCharacter)
                if len(enemies)<2:return
                self.enemies=sorted(enemies,key=lambda a:a.get_name())[:2]
                base=self.enemies[0].get_actor_location()
                for index,enemy in enumerate(self.enemies):
                    enemy.set_combat_enabled(False);enemy.set_actor_tick_enabled(False)
                    enemy.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
                    enemy.set_actor_location(base+unreal.Vector(0,95 if index==0 else -95,0),False,True)
                    enemy.set_actor_rotation(unreal.Rotator(yaw=0),True)
                    enemy.get_component_by_class(unreal.TextRenderComponent).set_text('Original' if index==0 else 'Adjusted')
                pawn.set_actor_tick_enabled(False)
                for component in pawn.get_components_by_class(unreal.PrimitiveComponent):
                    if component.get_name() in ('RightHand','HeldWeapon','RightSleeve'):component.set_hidden_in_game(True)
                self.camera=pawn.get_editor_property('player_camera');self.camera.set_editor_property('field_of_view',43)
                center=base+unreal.Vector(0,0,0);location=center+unreal.Vector(590,-75,70)
                rotation=unreal.MathLibrary.find_look_at_rotation(location,center)
                unreal.GameplayStatics.get_player_controller(world,0).set_control_rotation(rotation)
                self.camera.set_world_transform(unreal.Transform(location=location,rotation=rotation),False,True)
                self.camera_transform=unreal.Transform(location=location,rotation=rotation)
                unreal.SystemLibrary.execute_console_command(world,'showhud')
                self.phase='pose';self.report['state']='previewing'
            if self.camera and self.camera_transform:
                self.camera.set_world_transform(self.camera_transform,False,True)
            if self.phase=='pose':
                name,seconds=self.specs[self.index]
                for index,enemy in enumerate(self.enemies):
                    mesh=enemy.get_component_by_class(unreal.SkeletalMeshComponent)
                    asset=unreal.load_asset(PREFIX+name+('_Upright_v01' if index else ''))
                    assert asset,'Missing candidate '+name
                    mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
                    mesh.set_animation(asset);mesh.set_position(seconds,False);mesh.stop()
                self.changed=time.monotonic();self.phase='settle';return
            if self.phase=='settle' and time.monotonic()-self.changed>1.2:
                path=OUT/'Screenshots'/'BodyComparison'/('%02d.png'%self.index);path.parent.mkdir(parents=True,exist_ok=True)
                self.task=unreal.AutomationLibrary.take_high_res_screenshot(1600,1000,str(path))
                self.report['captures'].append({'file':str(path),'clip':self.specs[self.index][0],'clip_time':self.specs[self.index][1]})
                self.changed=time.monotonic();self.phase='captured';self.save();return
            if self.phase=='captured' and time.monotonic()-self.changed>1.1:
                self.index+=1
                if self.index==len(self.specs):self.end()
                else:self.phase='pose'
        except Exception:
            self.report['failures'].append(traceback.format_exc());self.end()
        finally:self.busy=False
body_preview=BodyPreview()
