"""Actual UE arm/hand close-ups at explicit poses; temporary PIE only."""
import json,time,traceback
from pathlib import Path
import unreal
OUT=Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v04')
CONFIG=json.loads((OUT/'HandDetailSpec.json').read_text(encoding='utf-8'))
def apply_grip(enemy,variant):
    if variant=='candidate':data=json.loads((OUT/'CandidateGrip.json').read_text(encoding='utf-8'))
    else:data=json.loads((OUT/'GripDefaults.json').read_text(encoding='utf-8'))[0]
    transform=unreal.Transform(location=unreal.Vector(*data['translation']),scale=unreal.Vector(*data['scale']))
    transform.rotation=unreal.Quat(*data['quaternion'])
    enemy.set_editor_property('sword_grip_transform',transform)
    enemy.get_editor_property('sword').set_relative_transform(transform,False,True)
class HandDetails:
    def __init__(self):
        self.editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.start=time.monotonic();self.phase='start';self.busy=False;self.index=0
        self.enemy=self.mesh=self.camera=self.task=None;self.changed=0
        self.old_recompute=unreal.SystemLibrary.get_console_variable_int_value('r.SkinCache.RecomputeTangents')
        self.report={'state':'starting','captures':[],'failures':[],'scope':'Actual saved mesh/animation rendered in PIE; no asset or map save.'}
        self.handle=unreal.register_slate_post_tick_callback(self.tick)
    def save(self):
        (OUT/(CONFIG.get('name','HandDetailPreview')+'.json')).write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
    def end(self):
        unreal.SystemLibrary.execute_console_command(self.editor.get_game_world(),'viewmode lit')
        unreal.SystemLibrary.execute_console_command(self.editor.get_game_world(),'r.SkinCache.RecomputeTangents '+str(self.old_recompute))
        self.enemy=self.mesh=self.camera=self.task=None;self.phase='ending';self.level.editor_request_end_play();self.save()
    def tick(self,delta):
        if self.busy:return
        self.busy=True
        try:
            if self.phase=='ending':
                if self.editor.get_game_world() is None:
                    self.report['state']='failed' if self.report['failures'] else 'passed';self.save();unreal.unregister_slate_post_tick_callback(self.handle)
                return
            assert time.monotonic()-self.start<180,'Hand detail deadline'
            if self.phase=='start':
                assert self.editor.get_game_world() is None
                self.level.editor_request_begin_play();self.phase='wait';return
            world=self.editor.get_game_world()
            if not world:return
            pawn=unreal.GameplayStatics.get_player_pawn(world,0)
            if not pawn:return
            if self.phase=='wait':
                enemies=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.NLEnemyCharacter)
                if not enemies:return
                self.enemy=sorted(enemies,key=lambda a:a.get_name())[0]
                for enemy in enemies:
                    enemy.set_combat_enabled(False);enemy.set_actor_tick_enabled(False)
                    enemy.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
                    if enemy!=self.enemy:enemy.set_actor_hidden_in_game(True)
                self.enemy.set_actor_rotation(unreal.Rotator(yaw=0),True)
                self.mesh=self.enemy.get_component_by_class(unreal.SkeletalMeshComponent)
                self.mesh.set_morph_target('EnemyGrip_R',1)
                pawn.set_actor_tick_enabled(False)
                for c in pawn.get_components_by_class(unreal.PrimitiveComponent):
                    if c.get_name() in ('RightHand','HeldWeapon','RightSleeve'):c.set_hidden_in_game(True)
                self.camera=pawn.get_editor_property('player_camera')
                unreal.SystemLibrary.execute_console_command(world,'showhud')
                unreal.SystemLibrary.execute_console_command(world,'t.IdleWhenNotForeground 0')
                self.phase='pose';self.report['state']='previewing'
            spec=CONFIG['samples'][self.index]
            if self.phase=='pose':
                asset=unreal.load_asset(spec['clip']);assert asset
                if spec.get('mesh'):
                    model=unreal.load_asset(spec['mesh']);assert model
                    self.mesh.set_skeletal_mesh_asset(model)
                if spec.get('grip_variant'):apply_grip(self.enemy,spec['grip_variant'])
                self.mesh.set_morph_target('EnemyGrip_R',spec.get('grip_weight',1))
                unreal.SystemLibrary.execute_console_command(world,'viewmode '+spec.get('view_mode','lit'))
                unreal.SystemLibrary.execute_console_command(world,'r.SkinCache.RecomputeTangents '+str(spec.get('recompute_tangents',self.old_recompute)))
                self.mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
                self.mesh.set_animation(asset);self.mesh.set_position(spec['time'],False);self.mesh.stop()
                self.camera.set_editor_property('field_of_view',spec.get('fov',34))
                self.changed=time.monotonic();self.phase='settle'
            bones=spec.get('focus_bones',['upperarm_r','hand_r'])
            center=unreal.Vector()
            for bone in bones:center=center+self.mesh.get_socket_location(bone)
            center=center/len(bones)+unreal.Vector(*spec.get('aim_offset',[0,0,0]))
            location=center+unreal.Vector(*spec.get('camera',[150,80,30]))
            rotation=unreal.MathLibrary.find_look_at_rotation(location,center)
            unreal.GameplayStatics.get_player_controller(world,0).set_control_rotation(rotation)
            self.camera.set_world_transform(unreal.Transform(location=location,rotation=rotation),False,True)
            if self.phase=='settle' and time.monotonic()-self.changed>1.2:
                path=OUT/'Screenshots'/CONFIG.get('folder','HandDetails')/('%02d_%s.png'%(self.index,spec['label']))
                path.parent.mkdir(parents=True,exist_ok=True)
                self.task=unreal.AutomationLibrary.take_high_res_screenshot(1600,1000,str(path))
                skel=self.mesh.get_editor_property('skeletal_mesh_asset')
                morph_names=[m.get_name() for m in skel.get_editor_property('morph_targets')]
                instance=self.mesh.get_anim_instance()
                self.report['captures'].append({'file':str(path),'spec':spec,'mesh':skel.get_path_name(),
                    'morph_overrides':{n:self.mesh.get_morph_target(n) for n in morph_names},
                    'animation_curves':{n:instance.get_curve_value(n) for n in morph_names},
                    'grip_morph_name':str(self.enemy.get_editor_property('grip_morph_name')),
                    'grip_morph_weight':self.enemy.get_editor_property('grip_morph_weight'),
                    'sword_relative':{p:str(self.enemy.get_editor_property('sword').get_editor_property(p))
                        for p in ('relative_location','relative_rotation','relative_scale3d')}})
                self.changed=time.monotonic();self.phase='captured';self.save();return
            if self.phase=='captured' and time.monotonic()-self.changed>1.0:
                self.index+=1
                if self.index==len(CONFIG['samples']):self.end()
                else:self.phase='pose'
        except Exception:
            self.report['failures'].append(traceback.format_exc());self.end()
        finally:self.busy=False
hand_details=HandDetails()
