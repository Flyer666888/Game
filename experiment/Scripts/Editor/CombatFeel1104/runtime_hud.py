"""Actual VR pawn HUD preview in PIE without hardware. Checkpoint writes disabled."""
import hashlib, json, time, traceback
from pathlib import Path
import unreal
P = Path(unreal.Paths.project_dir()).resolve()
O = P / 'Docs/Gameplay/CombatFeel1104'
MAP = '/Game/ReversedScale/Maps/L_CombatLabVR'

class HUDProbe:
    def __init__(self):
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.phase = 'start'; self.busy = False; self.started = time.monotonic()
        self.saved = []; self.tasks = []; self.pawn = None
        self.mapfile = P/'Content/ReversedScale/Maps/L_CombatLabVR.umap'
        self.before = hashlib.sha256(self.mapfile.read_bytes()).hexdigest()
        self.report = dict(state='starting', failures=[], actual_hmd_acceptance=False,
            scope='Native VR pawn HUD with health 72/guard 46 resource fixture. Desktop rendering of the headset texture; physical HMD not connected.')
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
    def save(self):
        (O/'HUDRuntime.json').write_text(json.dumps(self.report,indent=2),encoding='utf-8')
    def tick(self, delta):
        if self.busy: return
        self.busy = True
        try:
            assert time.monotonic()-self.started < 100
            if self.phase == 'start':
                assert self.editor.get_game_world() is None
                assert self.level.load_level(MAP)
                for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
                    if isinstance(a,unreal.NLEncounterController):
                        self.saved.append((a,a.enable_checkpoints))
                        a.enable_checkpoints = False
                assert self.saved
                self.level.editor_request_begin_play(); self.phase = 'wait'
            elif self.phase == 'wait':
                world = self.editor.get_game_world()
                if not world: return
                self.pawn = unreal.GameplayStatics.get_player_pawn(world,0)
                if not self.pawn: return
                assert isinstance(self.pawn,unreal.NLVRPlayerCharacter)
                self.pawn.vitals.restore_resource_preset(72,46)
                self.pawn.get_component_by_class(unreal.CharacterMovementComponent).disable_movement()
                self.zero = time.monotonic(); self.phase = 'capture'
            elif self.phase == 'capture' and time.monotonic()-self.zero>2:
                self.report['components'] = [c.get_name() for c in self.pawn.get_components_by_class(unreal.ActorComponent)]
                self.report['health'] = self.pawn.vitals.get_health()
                self.report['guard_at_capture'] = self.pawn.guard.get_guard()
                self.tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1280,900,str(O/'HeadsetHUD.png')))
                self.zero = time.monotonic(); self.phase = 'finish'
            elif self.phase == 'finish' and time.monotonic()-self.zero>2:
                self.pawn = None
                self.level.editor_request_end_play(); self.phase = 'ending'
            elif self.phase == 'ending' and self.editor.get_game_world() is None:
                for actor, value in self.saved: actor.enable_checkpoints=value
                assert hashlib.sha256(self.mapfile.read_bytes()).hexdigest() == self.before
                self.report['state'] = 'passed' if not self.report['failures'] else 'failed'
                self.save(); unreal.unregister_slate_post_tick_callback(self.handle)
        except Exception:
            self.report['failures'].append(traceback.format_exc()); self.report['state']='failed'
            self.level.editor_request_end_play(); self.phase='ending'; self.save()
        finally: self.busy=False

hud_probe = HUDProbe()
