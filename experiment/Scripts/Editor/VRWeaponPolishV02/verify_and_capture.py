"""Actual equipped VR asset chain under explicit synthetic grip poses; no HMD acceptance claim."""
import hashlib, json, math, time, traceback
from pathlib import Path
import unreal
P = Path(unreal.Paths.project_dir()).resolve()
OUT = P / 'Docs/Gameplay/VRWeaponPolish_v02'
SHOT = OUT / 'Screenshots'
SHOT.mkdir(parents=True, exist_ok=True)
MAP = '/Game/ReversedScale/Maps/L_CombatLabVR'
NEW = '/Game/ReversedScale/Weapons/SelectedSwordA_DetailV01/SM_PlayerSword_A_DetailV01'
OLD = '/Game/ReversedScale/Weapons/SelectedSwordA/SM_PlayerSword_A'
def xyz(v): return [float(v.x), float(v.y), float(v.z)]
def valid(obj):
    try: return obj is not None and unreal.SystemLibrary.is_valid(obj)
    except (TypeError, RuntimeError): return False

class GripProbe:
    def __init__(self):
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.started = time.monotonic()
        self.phase = 'start'
        self.busy = False
        self.index = 0
        self.saved_encounters = []
        self.tasks = []
        self.map_file = P / 'Content/ReversedScale/Maps/L_CombatLabVR.umap'
        self.before_hash = hashlib.sha256(self.map_file.read_bytes()).hexdigest()
        self.report = {'state':'starting','failures':[], 'poses':[], 'captures':[],
            'scope':'Actual native VR pawn and saved mesh/hand/animation in PIE, supplied OpenXR grip poses; no physical PICO input or combat. Checkpoints disabled only in the unsaved test world.',
            'actual_hmd_acceptance':False}
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.save()
    def save(self):
        (OUT/'RuntimeGripReport.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
    def finish(self):
        self.phase = 'ending'
        self.pawn = self.hand = self.weapon = self.controller = self.camera = None
        self.level.editor_request_end_play()
        self.save()
    def begin(self):
        assert self.editor.get_game_world() is None
        if not self.editor.get_editor_world().get_path_name().startswith(MAP):
            assert self.level.load_level(MAP)
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        for a in actors:
            if isinstance(a, unreal.NLEncounterController):
                self.saved_encounters.append((a, a.get_editor_property('enable_checkpoints')))
                a.set_editor_property('enable_checkpoints', False)
        assert self.saved_encounters, 'VR map encounter must be explicitly isolated'
        self.level.editor_request_begin_play()
        self.phase = 'bootstrap'
    def setup(self, world):
        self.pawn = unreal.GameplayStatics.get_player_pawn(world,0)
        if not self.pawn: return False
        assert isinstance(self.pawn,unreal.NLVRPlayerCharacter)
        for e in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.NLEncounterController):
            assert not e.get_editor_property('enable_checkpoints')
            assert e.get_alive_count() == 0
        self.pawn.set_actor_tick_enabled(False)
        self.pawn.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
        self.pawn.set_actor_rotation(unreal.Rotator(),True)
        self.controller = self.pawn.get_editor_property('right_controller')
        self.controller.set_component_tick_enabled(False)
        self.pawn.get_editor_property('left_controller').set_component_tick_enabled(False)
        self.hand = self.pawn.get_editor_property('right_hand')
        self.weapon = self.pawn.get_editor_property('held_weapon')
        self.blade = self.pawn.get_editor_property('blade')
        self.camera = self.pawn.get_editor_property('player_camera')
        self.camera.set_editor_property('lock_to_hmd',False)
        self.camera.set_editor_property('use_pawn_control_rotation',False)
        self.camera.set_editor_property('field_of_view',85.)
        self.new_mesh = unreal.load_asset(NEW)
        self.old_mesh = unreal.load_asset(OLD)
        assert self.new_mesh and self.old_mesh
        assert self.weapon.get_editor_property('static_mesh') == self.new_mesh, 'BeginPlay must equip the saved detailed asset'
        self.report['equipped_mesh'] = self.new_mesh.get_path_name()
        self.report['lod0_triangles'] = self.new_mesh.get_num_triangles(0)
        self.report['actual_materials'] = [self.weapon.get_material(i).get_path_name() for i in range(7)]
        self.report['mesh_sha256'] = hashlib.sha256((P/'Content/ReversedScale/Weapons/SelectedSwordA_DetailV01/SM_PlayerSword_A_DetailV01.uasset').read_bytes()).hexdigest()
        self.report['hand_mesh'] = self.hand.get_editor_property('skeletal_mesh_asset').get_path_name()
        self.report['motion_source'] = str(self.controller.get_editor_property('motion_source'))
        assert self.report['motion_source'] == 'RightGrip'
        self.new_grip = self.hand.get_relative_transform()
        self.report['weapon_socket_transform'] = str(self.weapon.get_relative_transform())
        for c in self.pawn.get_components_by_class(unreal.PrimitiveComponent):
            c.set_hidden_in_game(c not in (self.hand,self.weapon),False)
            if c in (self.hand,self.weapon): c.set_visibility(True,False)
        self.eye = self.pawn.get_actor_location()+unreal.Vector(0,0,70)
        self.grip_location = self.eye+unreal.Vector(65,22,-32)
        self.camera.set_world_transform(unreal.Transform(location=self.eye,rotation=unreal.Rotator()),False,True)
        unreal.GameplayStatics.get_player_controller(world,0).set_control_rotation(unreal.Rotator())
        unreal.SystemLibrary.execute_console_command(world,'showhud')
        unreal.SystemLibrary.execute_console_command(world,'r.SetNearClipPlane 2')
        self.pose_specs = [(90,0,0),(90,130,0),(90,0,75),(0,0,0),(0,90,0),(-90,0,0),(31,-43,68)]
        self.phase = 'pose'
        return True
    def set_pose(self):
        pitch,yaw,roll = self.pose_specs[self.index]
        self.controller.set_world_transform(unreal.Transform(location=self.grip_location,rotation=unreal.Rotator(pitch=pitch,yaw=yaw,roll=roll)),False,True)
        self.changed = time.monotonic()
        self.phase = 'measure'
    def measure(self):
        transform = self.weapon.get_world_transform()
        points = [unreal.MathLibrary.transform_location(transform,self.blade.get_editor_property(n))
                  for n in ('blade_root_local','blade_mid_local','blade_tip_local')]
        a,b = points[0],points[2]
        d = b-a
        length = math.sqrt(d.x*d.x+d.y*d.y+d.z*d.z)
        axis = d/length
        f = self.controller.get_forward_vector()
        dot = axis.x*f.x+axis.y*f.y+axis.z*f.z
        row = {'rotation_pitch_yaw_roll':self.pose_specs[self.index],'tip_axis_world':xyz(axis),
            'grip_axis_world':xyz(f),'dot':dot,'blade_length_cm':length,'blade_points_world':list(map(xyz,points))}
        self.report['poses'].append(row)
        assert dot > .999, row
        assert abs(length-56.52)<.03, row
        if self.index == 0: assert axis.z > .999, row
        if self.index == 5: assert axis.z < -.999, row
        self.index += 1
        if self.index < len(self.pose_specs): self.phase = 'pose'
        else:
            self.index = 0
            self.phase = 'capture_setup'
    def capture_setup(self):
        self.controller.set_world_transform(unreal.Transform(location=self.grip_location,rotation=unreal.Rotator(pitch=90)),False,True)
        self.hand.set_relative_transform(self.new_grip,False,True)
        self.weapon.set_static_mesh(self.new_mesh)
        self.weapon.set_editor_property('override_materials',[])
        self.camera.set_editor_property('field_of_view',85.)
        self.camera.set_world_transform(unreal.Transform(location=self.eye,rotation=unreal.Rotator()),False,True)
        self.changed = time.monotonic()
        self.phase = 'capture_settle'
    def capture(self,world):
        labels = ['Equipped_Upright','Forte_Closeup','Blade_Oblique']
        if self.index in (1,2):
            center = unreal.MathLibrary.transform_location(self.weapon.get_world_transform(),unreal.Vector(0,0,13 if self.index == 1 else 31))
            location = center+unreal.Vector(-62,-68,3) if self.index == 1 else center+unreal.Vector(-95,-68,7)
            rotation = unreal.MathLibrary.find_look_at_rotation(location,center)
            self.camera.set_editor_property('field_of_view',32. if self.index == 1 else 60.)
            self.camera.set_world_transform(unreal.Transform(location=location,rotation=rotation),False,True)
            unreal.GameplayStatics.get_player_controller(world,0).set_control_rotation(rotation)
        filename = SHOT/(labels[self.index]+'.png')
        task = unreal.AutomationLibrary.take_high_res_screenshot(1600,1100,str(filename),delay=.3)
        self.tasks.append(task)
        self.report['captures'].append({'label':labels[self.index],'file':str(filename),'synthetic_pose':True})
        self.changed = time.monotonic()
        self.phase = 'capture_wait'
        self.save()
    def tick(self,delta):
        if self.busy: return
        self.busy = True
        try:
            if self.phase == 'ending':
                if self.editor.get_game_world() is not None: return
                for actor,value in self.saved_encounters:
                    if valid(actor): actor.set_editor_property('enable_checkpoints',value)
                after = hashlib.sha256(self.map_file.read_bytes()).hexdigest()
                self.report['map_unchanged'] = after == self.before_hash
                self.report['checkpoint_settings_restored'] = all(valid(a) and a.get_editor_property('enable_checkpoints')==v for a,v in self.saved_encounters)
                assert self.report['map_unchanged'] and self.report['checkpoint_settings_restored']
                self.report['state'] = 'failed' if self.report['failures'] else 'passed'
                self.save()
                unreal.unregister_slate_post_tick_callback(self.handle)
                return
            assert time.monotonic()-self.started < 240,'Runtime grip capture timeout'
            if self.phase == 'start': self.begin();return
            world = self.editor.get_game_world()
            if not world:return
            if self.phase == 'bootstrap': self.setup(world);return
            if self.phase == 'pose': self.set_pose();return
            if self.phase == 'measure' and time.monotonic()-self.changed>.4:self.measure();return
            if self.phase == 'capture_setup':self.capture_setup();return
            if self.phase == 'capture_settle' and time.monotonic()-self.changed>1.5:self.capture(world);return
            if self.phase == 'capture_wait' and time.monotonic()-self.changed>2:
                assert Path(self.report['captures'][-1]['file']).is_file(),'Screenshot missing'
                self.index += 1
                if self.index == 3:self.finish()
                else:self.phase = 'capture_setup'
        except Exception:
            self.report['failures'].append(traceback.format_exc())
            if self.phase == 'ending':
                self.report['state']='cleanup_failed';self.save()
                unreal.unregister_slate_post_tick_callback(self.handle)
            else:self.finish()
        finally:self.busy=False
probe = GripProbe()
