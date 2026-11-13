"""Capture the saved main map through its existing UE evidence cameras.

Execute this script in the normal editor after the tree patch and final save.
It captures 1600x900 martial-court, alchemy and optional overview images using
Slate ticks, creates no actors, saves no packages and restores the viewport.
Inspect EnvironmentScreenshots/CaptureReport.json before dependent work.
"""
import hashlib
import json
import struct
import time
import traceback
from pathlib import Path

import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
SESSION = PROJECT / 'Docs/Gameplay/Optimization1111'
CONFIG_PATH = SESSION / 'EnvironmentCaptureConfig.json'
CONFIG = json.loads(CONFIG_PATH.read_text(encoding='utf-8-sig')) if CONFIG_PATH.exists() else {}
OUTPUT = SESSION / ('EnvironmentBeforeScreenshots' if CONFIG.get('before', False) else 'EnvironmentScreenshots')
MAP = '/Game/ReversedScale/Maps/L_NilinGameplayV01'
MAP_FILE = PROJECT / 'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
CAMERA_SPECS = (
    ('MartialCourt_TreeArchitecture', 'NL1105_Art_CAM_MartialCourt'),
    ('Alchemy_TreeArchitecture', 'NL1105_Art_CAM_Alchemy'),
    ('Overview', 'NL1105_Art_CAM_Overview'),
)


def map_hash():
    return hashlib.sha256(MAP_FILE.read_bytes()).hexdigest()


def png_size(path):
    with path.open('rb') as stream:
        header = stream.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR', str(path)
    return struct.unpack('>II', header[16:24])


class EnvironmentCapture:
    def __init__(self, include_overview=True):
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self.specs = list(CAMERA_SPECS if include_overview else CAMERA_SPECS[:2])
        self.started = time.monotonic()
        self.original_hash = map_hash()
        self.handle = None
        self.busy = False
        self.finished = False
        self.phase = 'prepare'
        self.last = 0.0
        self.pending = None
        self.pending_since = 0.0
        self.pending_camera = None
        self.pending_name = None
        self.cameras = []
        self.tasks = []
        self.results = []
        self.old_viewport = None
        self.old_screen_percentage = None
        self.old_motion_blur = None
        self.initial_actor_names = None
        self.original_camera_transforms = {}
        OUTPUT.mkdir(parents=True, exist_ok=True)
        self.write_report('starting')

    def write_report(self, state, error=None):
        current_hash = map_hash()
        report = {
            'state': state, 'map': MAP,
            'source': 'Actual saved-map Unreal Engine renderer using existing GDD1105 CameraActors',
            'resolution': [1600, 900], 'captures': self.results,
            'requested': [name for name, _ in self.specs],
            'map_sha256_before': self.original_hash, 'map_sha256_after': current_hash,
            'saved_map_unchanged': current_hash == self.original_hash,
            'temporary_actors_created': 0, 'temporary_actors_remaining': 0,
            'map_save_called': False, 'elapsed_seconds': time.monotonic() - self.started,
            'error': error,
        }
        (OUTPUT / 'CaptureReport.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    def finish(self, error=None):
        if self.finished:
            return
        self.finished = True
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        try:
            if self.old_screen_percentage is not None:
                unreal.SystemLibrary.execute_console_command(self.editor.get_editor_world(),
                    f'r.ScreenPercentage {self.old_screen_percentage}')
            if self.old_motion_blur is not None:
                unreal.SystemLibrary.execute_console_command(self.editor.get_editor_world(),
                    f'r.MotionBlurQuality {self.old_motion_blur}')
            if self.old_viewport is not None:
                self.editor.set_level_viewport_camera_info(*self.old_viewport)
            if self.initial_actor_names is not None:
                current = {a.get_name() for a in self.actors.get_all_level_actors()}
                assert current == self.initial_actor_names, 'Level actors changed during capture'
            for camera in self.cameras:
                assert camera.get_actor_transform() == self.original_camera_transforms[camera.get_name()], \
                    'An authored camera transform changed'
            assert map_hash() == self.original_hash, 'Saved map changed during capture'
            assert len(self.results) == len(self.specs), 'Incomplete screenshot set'
        except Exception:
            error = (error or '') + '\n' + traceback.format_exc()
        self.write_report('passed' if error is None else 'failed', error)
        if error is None:
            unreal.log(f'OPT1111_ENVIRONMENT_CAPTURE_PASSED {len(self.results)} images; map unchanged')
        else:
            unreal.log_error('OPT1111_ENVIRONMENT_CAPTURE_FAILED ' + error)

    def prepare(self):
        assert self.editor.get_game_world() is None, 'End PIE before environment capture'
        assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Save the final map before capture'
        if not self.editor.get_editor_world().get_path_name().startswith(MAP + '.'):
            assert self.level.load_level(MAP)
        assert map_hash() == self.original_hash
        all_actors = self.actors.get_all_level_actors()
        self.initial_actor_names = {a.get_name() for a in all_actors}
        for _, label in self.specs:
            found = [a for a in all_actors if isinstance(a, unreal.CameraActor)
                     and a.actor_has_tag('NL.GDD1105.Art') and a.get_actor_label() == label]
            assert len(found) == 1, f'Expected exactly one saved evidence camera: {label}'
            self.cameras.append(found[0])
            self.original_camera_transforms[found[0].get_name()] = found[0].get_actor_transform()
        self.old_viewport = self.editor.get_level_viewport_camera_info()
        self.old_screen_percentage = unreal.SystemLibrary.get_console_variable_float_value('r.ScreenPercentage')
        self.old_motion_blur = unreal.SystemLibrary.get_console_variable_int_value('r.MotionBlurQuality')
        unreal.SystemLibrary.execute_console_command(self.editor.get_editor_world(), 'r.ScreenPercentage 100')
        unreal.SystemLibrary.execute_console_command(self.editor.get_editor_world(), 'r.MotionBlurQuality 0')
        self.phase = 'warmup'
        self.last = time.monotonic()
        self.write_report('warming')

    def schedule_next(self):
        if len(self.results) == len(self.specs):
            self.finish()
            return
        index = len(self.results)
        name, _ = self.specs[index]
        camera = self.cameras[index]
        pending = OUTPUT / (name + '.png')
        # Preserve earlier evidence and prevent a stale PNG from satisfying this run.
        if pending.exists():
            archive = OUTPUT / 'Previous' / time.strftime('%Y%m%d_%H%M%S')
            archive.mkdir(parents=True, exist_ok=True)
            pending.replace(archive / pending.name)
        self.editor.set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
        self.pending = pending
        self.pending_camera = camera
        self.pending_name = name
        self.pending_since = time.time()
        task = unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, str(pending), camera=camera,
                                                                delay=2.0, force_game_view=True)
        self.tasks.append(task)
        self.last = time.monotonic()
        self.phase = 'capture'
        self.write_report('capturing')

    def tick(self, delta):
        if self.finished or self.busy:
            return
        self.busy = True
        try:
            assert self.editor.get_game_world() is None, 'PIE started during capture'
            assert time.monotonic() - self.started < 240, 'Environment capture timeout'
            if self.phase == 'prepare':
                self.prepare()
            elif self.phase == 'warmup' and time.monotonic() - self.last > 18:
                self.schedule_next()
            elif self.phase == 'between' and time.monotonic() - self.last > 4:
                self.schedule_next()
            elif self.phase == 'capture' and time.monotonic() - self.last > 6:
                if self.pending.exists() and self.pending.stat().st_size > 10000 \
                        and self.pending.stat().st_mtime >= self.pending_since - .5:
                    width, height = png_size(self.pending)
                    assert (width, height) == (1600, 900), (width, height)
                    component = self.pending_camera.get_component_by_class(unreal.CameraComponent)
                    p, r = self.pending_camera.get_actor_location(), self.pending_camera.get_actor_rotation()
                    self.results.append({'name': self.pending_name, 'file': str(self.pending),
                        'bytes': self.pending.stat().st_size, 'width': width, 'height': height,
                        'camera': self.pending_camera.get_actor_label(), 'position_cm': [p.x, p.y, p.z],
                        'rotation_degrees': [r.pitch, r.yaw, r.roll], 'fov': component.field_of_view})
                    self.pending = None
                    self.phase = 'between'
                    self.last = time.monotonic()
                    self.write_report('captured')
                elif time.monotonic() - self.last > 50:
                    raise RuntimeError('Screenshot did not complete: ' + str(self.pending))
        except Exception:
            self.finish(traceback.format_exc())
        finally:
            self.busy = False

    def start(self):
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        return self


if __name__ == '__main__':
    CAPTURE = EnvironmentCapture(include_overview=True).start()
