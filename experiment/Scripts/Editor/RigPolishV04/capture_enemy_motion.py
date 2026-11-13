"""Observe real authored enemies walking/attacking, then a real health-driven death.
Capture only changes PIE presentation; never save the map or alter encounter data.
"""
import unreal,json,time,math,traceback
from pathlib import Path
OUT=Path(r'D:\game design\experiment\Docs\Gameplay\RigPolish_v04')
LABEL=(OUT/'CaptureLabel.txt').read_text(encoding='utf-8-sig').strip()
assert LABEL in ('Before','After')
class Probe:
    def __init__(self):
        self.editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.start=time.monotonic();self.phase='start';self.busy=False;self.handle=None
        self.enemy=None;self.camera=None;self.zero=None;self.last=None;self.frames=[];self.captures=[];self.index=0;self.task=None;self.killed=False;self.hit=False
        self.times=[.5,2,5,8,10,12,14,16,18,20,22,24,25.15,25.6,26.2,27,28]
        self.report={'label':LABEL,'state':'starting','failures':[],'scope':'Real first-stage AI with a fixed player target. Player actor tick is disabled for follow-camera presentation. Health protection keeps the target alive. Synthetic resolver contacts with the existing melee definition trigger hit at 21s and death at 25s; this is not a manual gameplay test.'}
        self.handle=unreal.register_slate_post_tick_callback(self.tick)
    def save(self):
        self.report['frames']=self.frames;self.report['captures']=self.captures
        (OUT/(LABEL+'Motion.json')).write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
    def end(self):
        self.enemy=self.camera=self.task=None
        self.phase='ending';self.level.editor_request_end_play();self.save()
    def contact(self,world,pawn):
        resolver=next(obj for obj in unreal.ObjectIterator(unreal.NLCombatResolverSubsystem) if unreal.SystemLibrary.is_valid(obj) and obj.get_outer()==world)
        definition=unreal.load_asset('/Game/ReversedScale/Combat/DA_YueyaoMelee')
        contact=unreal.NLCombatContact()
        contact.set_editor_property('attack_instance_id',unreal.GuidLibrary.new_guid())
        contact.set_editor_property('source_runtime_id',pawn.get_component_by_class(unreal.NLCombatIdentityComponent).ensure_runtime_id())
        contact.set_editor_property('target_runtime_id',self.enemy.get_component_by_class(unreal.NLCombatIdentityComponent).ensure_runtime_id())
        contact.set_editor_property('projectile_generation',-1)
        contact.set_editor_property('contact_time_seconds',unreal.GameplayStatics.get_time_seconds(world))
        contact.set_editor_property('attack_definition_id',definition.get_editor_property('stable_id'))
        contact.set_editor_property('hit_position',self.enemy.get_actor_location())
        result=resolver.resolve_contact(pawn,self.enemy,contact,definition)
        assert result.get_editor_property('outcome')==unreal.NLCombatOutcome.HIT,str(result.get_editor_property('outcome'))
    def tick(self,delta):
        if self.busy:return
        self.busy=True
        try:
            if self.phase=='ending':
                if self.editor.get_game_world() is None:
                    self.report['state']='passed' if not self.report['failures'] else 'failed'
                    self.save();unreal.unregister_slate_post_tick_callback(self.handle)
                return
            assert time.monotonic()-self.start<140,'Motion observation deadline'
            if self.phase=='start':
                assert self.editor.get_game_world() is None
                self.level.editor_request_begin_play();self.phase='wait';return
            world=self.editor.get_game_world()
            if not world:return
            pawn=unreal.GameplayStatics.get_player_pawn(world,0)
            if not pawn:return
            vitals=pawn.get_editor_property('vitals')
            if vitals.get_health()<70:vitals.restore_resource_preset(100,100)
            if not self.enemy:
                enemies=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.NLEnemyCharacter)
                if not enemies:return
                self.enemy=sorted(enemies,key=lambda a:a.get_name())[0]
                self.zero=unreal.GameplayStatics.get_time_seconds(world)
                self.camera=pawn.get_editor_property('player_camera')
                pawn.set_actor_tick_enabled(False)
                self.camera.set_editor_property('field_of_view',45)
                for component in pawn.get_components_by_class(unreal.PrimitiveComponent):
                    if component.get_name() in ('RightHand','HeldWeapon','RightSleeve'):
                        component.set_hidden_in_game(True)
                unreal.SystemLibrary.execute_console_command(world,'showhud')
                unreal.SystemLibrary.execute_console_command(world,'t.IdleWhenNotForeground 0')
                unreal.SystemLibrary.execute_console_command(world,'Slate.bAllowThrottling 0')
                self.report['state']='observing';self.phase='observe'
            now=unreal.GameplayStatics.get_time_seconds(world)-self.zero
            if not unreal.SystemLibrary.is_valid(self.enemy):
                assert self.killed,'Enemy unexpectedly vanished';self.end();return
            mesh=self.enemy.get_component_by_class(unreal.SkeletalMeshComponent);brain=self.enemy.get_enemy_brain();inst=mesh.get_anim_instance()
            asset=inst.get_animation_asset() if inst else None
            location=self.enemy.get_actor_location()
            center=location+unreal.Vector(0,0,0)
            camera_location=center+unreal.Vector(420,-450,145)
            rotation=unreal.MathLibrary.find_look_at_rotation(camera_location,center)
            unreal.GameplayStatics.get_player_controller(world,0).set_control_rotation(rotation)
            self.camera.set_world_transform(unreal.Transform(location=camera_location,rotation=rotation),False,True)
            positions={};rotations={}
            for bone in ('pelvis','spine_03','head','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r','foot_l','foot_r'):
                t=mesh.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_COMPONENT)
                positions[bone]=[t.translation.x,t.translation.y,t.translation.z]
                rotations[bone]=[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
            row={'t':now,'state':str(brain.get_state()),'asset':asset.get_name() if asset else None,'instance':inst.get_class().get_name() if inst else None,
                 'mesh_asset':mesh.get_editor_property('skeletal_mesh_asset').get_path_name(),
                 'speed':self.enemy.get_velocity().length(),'mesh_z':mesh.get_world_location().z,'actor_z':location.z,'positions':positions,'rotations':rotations,
                 'actor_yaw':self.enemy.get_actor_rotation().yaw,'player_health':vitals.get_health(),'attack_window':brain.is_attack_window_active(),
                 'blade_state':str(self.enemy.get_editor_property('blade').get_swing_state())}
            sword=self.enemy.get_editor_property('sword');blade=self.enemy.get_editor_property('blade')
            row['animation_time']=mesh.get_position();row['play_rate']=mesh.get_play_rate()
            row['enemy_location']=[location.x,location.y,location.z]
            player_location=pawn.get_actor_location()
            row['player_location']=[player_location.x,player_location.y,player_location.z]
            row['target_distance_cm']=(location-player_location).length()
            row['blade_points_world']={}
            for name in ('blade_root_local','blade_mid_local','blade_tip_local'):
                point=unreal.MathLibrary.transform_location(sword.get_world_transform(),blade.get_editor_property(name))
                row['blade_points_world'][name]=[point.x,point.y,point.z]
            self.frames.append(row)
            if self.index<len(self.times) and now>=self.times[self.index]:
                path=OUT/'Screenshots'/LABEL/('%02d.png'%self.index);path.parent.mkdir(parents=True,exist_ok=True)
                self.task=unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(path))
                self.captures.append({'file':str(path),'time':now,'state':row['state'],'asset':row['asset']});self.index+=1
                self.save()
            if now>=21 and not self.hit:
                self.hit=True;self.contact(world,pawn)
            if now>=25 and not self.killed:
                self.killed=True
                for attempt in range(10):
                    if self.enemy.get_editor_property('vitals').is_dead():break
                    self.contact(world,pawn)
                assert self.enemy.get_editor_property('vitals').is_dead(),'Test contacts did not defeat enemy'
            if now>29:self.end()
        except Exception:
            self.report['failures'].append(traceback.format_exc());self.end()
        finally:self.busy=False
probe=Probe()
