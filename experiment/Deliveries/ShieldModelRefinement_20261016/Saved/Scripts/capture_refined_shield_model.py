"""Capture the equipped shield and its two surfaces in a disposable desktop Ready session.

Launch explicitly on L_CombatLabMixed with -game -nohmd. This script changes
presentation only, restores every change, and exits without saving any asset/map.
"""
import hashlib
import json
import time
import traceback
from pathlib import Path

import unreal


class _RefinedShieldModelCapture:
    WORLD_PATH = '/Game/ReversedScale/Maps/L_CombatLabMixed.L_CombatLabMixed'
    STARTUP_WAIT = 18.0
    SETTLE_SECONDS = 3.0
    SCREENSHOT_TIMEOUT = 15.0
    TOTAL_TIMEOUT = 120.0

    def __init__(self):
        self.begin = time.monotonic()
        self.stage = 'startup'
        self.stage_begin = self.begin
        self.busy = False
        self.finished = False
        self.handle = None
        self.world = None
        self.player = None
        self.guard = None
        self.original_visual = None
        self.binding_captured = False
        self.face = None
        self.face_transform = None
        self.hud = None
        self.hud_visible = None
        self.components = {}
        self.visibility = {}
        self.pending_file = None
        self.pending_signature = None
        self.project = Path(unreal.Paths.project_dir())
        self.docs = self.project / 'Docs/AI'
        self.report_path = self.docs / 'ShieldModelPresentation-2026-10-16.json'
        self.report = {
            'date': '2026-10-16', 'status': 'WaitingForInitialPresentation', 'success': False,
            'map': self.WORLD_PATH, 'views': [],
            'no_agent_gameplay_inputs': True, 'tests_added_or_run': False,
            'assets_or_maps_saved': False,
            'scope': 'Desktop Ready art only. Equipped/back views preserve the held transform; '
                     'front temporarily rotates only the shield mesh for presentation. '
                     'No guard activation, controller simulation, collision edits or encounter start.',
        }

    @staticmethod
    def transform(value):
        return {
            'location_cm': [value.translation.x, value.translation.y, value.translation.z],
            'quaternion_xyzw': [value.rotation.x, value.rotation.y, value.rotation.z, value.rotation.w],
            'scale': [value.scale3d.x, value.scale3d.y, value.scale3d.z],
        }

    @staticmethod
    def path(obj):
        return obj.get_path_name() if obj else None

    @staticmethod
    def file_signature(path):
        if not path.exists():
            return None
        stat = path.stat()
        return [stat.st_size, stat.st_mtime_ns]

    @staticmethod
    def visible_flags(component):
        # IsVisible() combines bVisible and bHiddenInGame; it cannot restore the
        # two original flags separately. Read the stored properties instead.
        return {'visible': bool(component.get_editor_property('visible')),
                'hidden_in_game': bool(component.get_editor_property('hidden_in_game'))}

    def component_record(self, component, skeletal=False):
        mesh = component.get_editor_property('skeletal_mesh_asset' if skeletal else 'static_mesh')
        return {
            'mesh': self.path(mesh),
            'materials': [self.path(component.get_material(i)) for i in range(component.get_num_materials())],
            'relative_transform': self.transform(component.get_relative_transform()),
            'world_transform': self.transform(component.get_world_transform()),
            'visibility': self.visible_flags(component),
        }

    def resource_record(self):
        encounter = self.player.get_encounter_controller()
        return {
            'encounter_state': str(encounter.get_state()),
            'alive_enemies': encounter.get_alive_count(),
            'health': self.player.get_editor_property('vitals').get_health(),
            'guard': self.guard.get_guard(),
            'guard_active': self.guard.is_guard_active(),
            'guard_collision': str(self.components['guard_collision'].get_collision_enabled()),
            'melee_damage': self.player.get_editor_property('blade').get_editor_property(
                'attack_definition').get_editor_property('damage'),
        }

    def advance(self, stage):
        self.stage = stage
        self.stage_begin = time.monotonic()

    def show(self, name, visible):
        # No recursive propagation: only these explicitly recorded components change.
        component = self.components[name]
        component.set_visibility(visible, False)
        component.set_hidden_in_game(not visible, False)

    def prepare(self):
        for name in ('mirror_pivot', 'mirror_face', 'left_hand', 'left_sleeve',
                     'right_hand', 'right_sleeve', 'held_weapon', 'guard_collision'):
            component = self.player.get_editor_property(name)
            if not component:
                raise RuntimeError('Required component missing: ' + name)
            self.components[name] = component
            self.visibility[name] = self.visible_flags(component)
        self.guard = self.player.get_editor_property('guard')
        self.original_visual = self.guard.get_editor_property('guard_visual')
        self.binding_captured = True
        self.face = self.components['mirror_face']
        self.face_transform = self.face.get_relative_transform()
        controller = unreal.GameplayStatics.get_player_controller(self.world, 0)
        self.hud = controller.get_hud() if controller else None
        if self.hud:
            self.hud_visible = bool(self.hud.get_editor_property('bShowHUD'))

        self.report['pawn_class'] = self.player.get_class().get_path_name()
        self.report['shield'] = self.component_record(self.face)
        self.report['left_hand'] = self.component_record(self.components['left_hand'], True)
        self.report['weapon_a'] = self.component_record(self.components['held_weapon'])
        self.report['original_component_visibility'] = self.visibility.copy()
        self.report['original_guard_visual'] = self.path(self.original_visual)
        self.report['original_hud_visible'] = self.hud_visible
        self.report['initial_state'] = self.resource_record()
        mesh_path = self.report['shield']['mesh']
        if not mesh_path or not mesh_path.startswith('/Game/'):
            raise RuntimeError('Held shield is not a saved project mesh: ' + str(mesh_path))
        package = mesh_path.split('.', 1)[0][len('/Game/'):]
        mesh_file = self.project / 'Content' / (package + '.uasset')
        self.report['mesh_asset_file'] = str(mesh_file)
        self.report['mesh_asset_sha256'] = hashlib.sha256(mesh_file.read_bytes()).hexdigest()

        # The guard keeps its own collision/resource updates; detach only its visual pointer.
        self.guard.set_editor_property('guard_visual', None)
        for name in ('mirror_pivot', 'mirror_face', 'left_hand', 'left_sleeve'):
            self.show(name, True)
        self.show('guard_collision', False)
        self.advance('equipped_settle')

    def request_image(self, filename, next_stage, kind):
        output = self.docs / filename
        self.pending_file = output
        self.pending_signature = self.file_signature(output)
        view = {
            'file': str(output), 'kind': kind, 'state': self.resource_record(),
            'shield_relative_transform': self.transform(self.face.get_relative_transform()),
            'shield_world_transform': self.transform(self.face.get_world_transform()),
            'left_grip_relative_transform': self.transform(self.components['left_hand'].get_relative_transform()),
            'camera_transform': self.transform(self.player.get_editor_property('player_camera').get_world_transform()),
            'actual_held_transform': kind != 'front_art_presentation',
        }
        self.report['views'].append(view)
        # Advance before issuing the screenshot; engine commands may pump Slate callbacks.
        self.advance(next_stage)
        unreal.SystemLibrary.execute_console_command(self.world,
            'HighResShot 1800x1100 filename="' + str(output) + '"')

    def image_ready(self):
        elapsed = time.monotonic() - self.stage_begin
        if elapsed < self.SETTLE_SECONDS:
            return False
        signature = self.file_signature(self.pending_file)
        if signature and signature != self.pending_signature and signature[0] > 8:
            with self.pending_file.open('rb') as source:
                if source.read(8) == b'\x89PNG\r\n\x1a\n':
                    self.report['views'][-1]['written_bytes'] = signature[0]
                    self.report['views'][-1]['capture_saved'] = True
                    return True
        if elapsed >= self.SCREENSHOT_TIMEOUT:
            raise RuntimeError('Screenshot did not produce a fresh PNG: ' + str(self.pending_file))
        return False

    def restore(self):
        errors = []
        if self.face and self.face_transform:
            try:
                self.face.set_relative_transform(self.face_transform, False, True)
            except Exception:
                errors.append('shield transform: ' + traceback.format_exc())
        for name, flags in self.visibility.items():
            try:
                component = self.components[name]
                component.set_visibility(flags['visible'], False)
                component.set_hidden_in_game(flags['hidden_in_game'], False)
            except Exception:
                errors.append(name + ' visibility: ' + traceback.format_exc())
        if self.hud and self.hud_visible is not None:
            try:
                self.hud.set_editor_property('bShowHUD', self.hud_visible)
            except Exception:
                errors.append('HUD: ' + traceback.format_exc())
        if self.guard and self.binding_captured:
            try:
                self.guard.set_editor_property('guard_visual', self.original_visual)
            except Exception:
                errors.append('guard visual binding: ' + traceback.format_exc())
        if not errors and self.face:
            self.report['restored_shield_relative_transform'] = self.transform(self.face.get_relative_transform())
            self.report['restored_component_visibility'] = {
                name: self.visible_flags(component) for name, component in self.components.items()}
            self.report['restored_guard_visual'] = self.path(self.guard.get_editor_property('guard_visual'))
            expected_transform = self.transform(self.face_transform)
            actual_transform = self.report['restored_shield_relative_transform']
            if any(abs(a - b) > 0.000001 for key in expected_transform
                   for a, b in zip(expected_transform[key], actual_transform[key])):
                errors.append('Shield relative transform did not return to its original value')
            if self.report['restored_component_visibility'] != self.visibility:
                errors.append('Component visibility did not return to its original values')
            if self.report['restored_guard_visual'] != self.path(self.original_visual):
                errors.append('Guard visual binding did not return to its original object')
            if self.hud and bool(self.hud.get_editor_property('bShowHUD')) != self.hud_visible:
                errors.append('HUD visibility did not return to its original value')
        self.report['restore_errors'] = errors
        self.report['presentation_restored'] = not errors
        return errors

    def finish(self, success, reason=None):
        if self.finished:
            return
        self.finished = True
        self.report['status'] = 'Captured' if success else 'Failed'
        self.report['failure'] = reason
        self.report['elapsed_seconds'] = round(time.monotonic() - self.begin, 3)
        try:
            if self.handle is not None:
                unreal.unregister_slate_post_tick_callback(self.handle)
        finally:
            try:
                if self.restore():
                    self.report['status'] = 'Failed'
                    self.report['failure'] = 'Presentation restoration incomplete; see restore_errors'
                if self.player and self.guard and self.components:
                    self.report['final_state'] = self.resource_record()
            except Exception:
                self.report['status'] = 'Failed'
                self.report['failure'] = 'Final restoration/report error: ' + traceback.format_exc()
            finally:
                try:
                    self.report['success'] = (self.report['status'] == 'Captured'
                        and self.report.get('presentation_restored', False)
                        and len(self.report['views']) == 3
                        and all(view.get('capture_saved', False) for view in self.report['views']))
                    if self.report['status'] == 'Captured' and not self.report['success']:
                        self.report['status'] = 'Failed'
                        self.report['failure'] = 'Three fresh screenshots and complete restoration were not confirmed'
                    self.docs.mkdir(parents=True, exist_ok=True)
                    self.report_path.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
                    unreal.log('REFINED_SHIELD_MODEL_CAPTURE_' + self.report['status'].upper())
                except Exception:
                    unreal.log_error(traceback.format_exc())
                finally:
                    # This entry point is solely for the task-owned disposable -game process.
                    unreal.SystemLibrary.execute_console_command(self.world, 'quit')

    def tick(self, delta):
        if self.finished or self.busy:
            return
        self.busy = True
        try:
            now = time.monotonic()
            if now - self.begin >= self.TOTAL_TIMEOUT:
                raise RuntimeError('120-second art capture deadline exceeded at stage ' + self.stage)
            if not self.world:
                self.world = unreal.find_object(None, self.WORLD_PATH)
            if not self.world:
                return
            if not self.player:
                self.player = unreal.GameplayStatics.get_player_pawn(self.world, 0)
            if not self.player:
                return
            if self.stage == 'startup' and now - self.begin < self.STARTUP_WAIT:
                return
            if self.player.get_class().get_path_name() != '/Script/experiment.NLDesktopPlayerCharacter':
                raise RuntimeError('Art capture requires the desktop Mixed pawn; do not run on VR or PIE')
            encounter = self.player.get_encounter_controller()
            if not encounter or encounter.get_state() != unreal.NLEncounterState.READY or encounter.get_alive_count() != 0:
                raise RuntimeError('Scene left the initial Ready state or contains live enemies; capture aborted')
            guard = self.player.get_editor_property('guard')
            if guard.is_guard_active():
                raise RuntimeError('Guard input became active; art capture aborted without changing gameplay')
            elapsed = now - self.stage_begin
            if self.stage == 'startup':
                if now - self.begin >= self.STARTUP_WAIT:
                    self.prepare()
            elif self.stage == 'equipped_settle' and elapsed >= self.SETTLE_SECONDS:
                self.request_image('ShieldModel_Equipped.png', 'equipped_written', 'actual_equipped_sword_and_shield')
            elif self.stage == 'equipped_written' and self.image_ready():
                for name in ('right_hand', 'right_sleeve', 'held_weapon'):
                    self.show(name, False)
                if self.hud:
                    self.hud.set_editor_property('bShowHUD', False)
                self.advance('back_settle')
            elif self.stage == 'back_settle' and elapsed >= self.SETTLE_SECONDS:
                self.request_image('ShieldModel_Back.png', 'back_written', 'actual_held_back_detail')
            elif self.stage == 'back_written' and self.image_ready():
                original = self.face_transform
                front = unreal.Transform(location=original.translation + unreal.Vector(28.0, 0.0, 16.0),
                                         rotation=unreal.Rotator(yaw=180.0), scale=original.scale3d)
                self.face.set_relative_transform(front, False, True)
                for name in ('left_hand', 'left_sleeve'):
                    self.show(name, False)
                self.advance('front_settle')
            elif self.stage == 'front_settle' and elapsed >= self.SETTLE_SECONDS:
                self.request_image('ShieldModel_Front.png', 'front_written', 'front_art_presentation')
            elif self.stage == 'front_written' and self.image_ready():
                self.finish(True)
        except Exception:
            self.finish(False, traceback.format_exc())
        finally:
            self.busy = False


_shield_model_capture = _RefinedShieldModelCapture()
_shield_model_capture.handle = unreal.register_slate_post_tick_callback(_shield_model_capture.tick)
unreal.log('REFINED_SHIELD_MODEL_ART_CAPTURE_REGISTERED')
