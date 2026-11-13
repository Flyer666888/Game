"""Capture identical clip samples on two real enemies, without saving the map."""
import json,time,traceback
from pathlib import Path
import unreal
OUT=Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v03')
CONFIG=json.loads((OUT/'PreviewSpec.json').read_text(encoding='utf-8'))
class Comparison:
    def __init__(self):
        self.editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.start=time.monotonic();self.busy=False;self.phase='start';self.enemies=[];self.camera=None;self.task=None;self.index=0;self.changed=0;self.camera_transform=None
        self.specs=CONFIG['samples'];self.report={'state':'starting','scope':'Left/right labels identify the real mesh/clip assets. Same saved map, temporary PIE presentation only.','captures':[],'failures':[]}
        self.handle=unreal.register_slate_post_tick_callback(self.tick)
    def save(self):
        (OUT/(CONFIG['name']+'.json')).write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
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
            assert time.monotonic()-self.start<max(120,len(self.specs)*6),'Preview deadline'
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
                self.base=self.enemies[0].get_actor_location()
                for index,enemy in enumerate(self.enemies):
                    enemy.set_combat_enabled(False);enemy.set_actor_tick_enabled(False)
                    enemy.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
                    enemy.set_actor_location(self.base+unreal.Vector(0,95 if index==0 else -95,0),False,True)
                    enemy.set_actor_rotation(unreal.Rotator(yaw=0),True)
                pawn.set_actor_tick_enabled(False)
                for component in pawn.get_components_by_class(unreal.PrimitiveComponent):
                    if component.get_name() in ('RightHand','HeldWeapon','RightSleeve'):component.set_hidden_in_game(True)
                self.camera=pawn.get_editor_property('player_camera')
                unreal.SystemLibrary.execute_console_command(world,'showhud')
                self.phase='pose';self.report['state']='previewing'
            if self.phase=='pose':
                spec=self.specs[self.index]
                for index,key in enumerate(('left','right')):
                    enemy=self.enemies[index];item=spec[key]
                    mesh=enemy.get_component_by_class(unreal.SkeletalMeshComponent)
                    asset=unreal.load_asset(item['clip']);assert asset,item['clip']
                    if item.get('mesh'):
                        model=unreal.load_asset(item['mesh']);assert model,item['mesh'];mesh.set_skeletal_mesh_asset(model)
                    mesh.set_morph_target('EnemyGrip_R',1)
                    mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
                    mesh.set_animation(asset);mesh.set_position(item['time'],False);mesh.stop()
                    enemy.get_component_by_class(unreal.TextRenderComponent).set_text(item.get('label',key))
                center=self.base+unreal.Vector(*spec.get('target',[0,0,30]))
                location=center+unreal.Vector(*spec.get('camera',[530,-70,50]))
                rotation=unreal.MathLibrary.find_look_at_rotation(location,center)
                self.camera_transform=unreal.Transform(location=location,rotation=rotation)
                self.camera.set_editor_property('field_of_view',spec.get('fov',43))
                unreal.GameplayStatics.get_player_controller(world,0).set_control_rotation(rotation)
                self.changed=time.monotonic();self.phase='settle'
            if self.camera_transform:self.camera.set_world_transform(self.camera_transform,False,True)
            if self.phase=='settle' and time.monotonic()-self.changed>1.0:
                path=OUT/'Screenshots'/CONFIG['name']/('%02d.png'%self.index);path.parent.mkdir(parents=True,exist_ok=True)
                self.task=unreal.AutomationLibrary.take_high_res_screenshot(1600,1000,str(path))
                self.report['captures'].append({'file':str(path),'spec':self.specs[self.index]})
                self.changed=time.monotonic();self.phase='captured';self.save();return
            if self.phase=='captured' and time.monotonic()-self.changed>1.0:
                self.index+=1
                if self.index==len(self.specs):self.end()
                else:self.phase='pose'
        except Exception:
            self.report['failures'].append(traceback.format_exc());self.end()
        finally:self.busy=False
comparison=Comparison()
