"""Read and photograph initial Ready presentation; never start an encounter.

Use a disposable -game -nohmd session on the VR or Guard Captain lab. No input,
damage, controller emulation, checkpoint writes or actor spawning is requested.
"""
import json
import time
import traceback
from pathlib import Path
import unreal


class ReadyPresentation:
    def __init__(self):
        self.start = time.monotonic()
        self.handle = None
        self.busy = False
        self.stage = 'wait'
        self.shot = None
        self.shot_signature = None
        self.world = None
        self.report = {'date': '2026-10-16', 'success': False,
                       'tests_added_or_run': False, 'agent_gameplay_inputs': False,
                       'scope': 'Initial Ready presentation only; no combat start or inputs.'}
        self.docs = Path(unreal.Paths.project_dir()).resolve() / 'Docs/AI'
        self.report_path = self.docs / 'EnemyReadyPresentation-Pending.json'

    @staticmethod
    def vec(value):
        return [value.x, value.y, value.z]

    @staticmethod
    def signature(path):
        return [path.stat().st_size, path.stat().st_mtime_ns] if path.exists() else None

    def finish(self, error=None):
        if self.stage == 'done':
            return
        self.stage = 'done'
        self.report.update(success=error is None, elapsed_seconds=round(time.monotonic()-self.start, 3))
        if error:
            self.report['error'] = error
            unreal.log_error(error)
        try:
            self.docs.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
            unreal.unregister_slate_post_tick_callback(self.handle)
        finally:
            unreal.SystemLibrary.execute_console_command(self.world, 'quit')

    def tick(self, delta):
        if self.busy or self.stage == 'done':
            return
        self.busy = True
        try:
            elapsed = time.monotonic() - self.start
            if elapsed > 100:
                self.finish('Initial presentation capture timed out.')
                return
            if self.stage == 'wait' and elapsed >= 20:
                for name, label in [('L_CombatLabVR', 'VREnemyReady'),
                                    ('L_CombatLabGuardCaptain', 'GuardCaptainReady')]:
                    self.world = unreal.find_object(None, '/Game/ReversedScale/Maps/' + name + '.' + name)
                    if self.world:
                        break
                if not self.world:
                    return
                player = unreal.GameplayStatics.get_player_pawn(self.world, 0)
                if not player:
                    return
                encounter = player.get_encounter_controller()
                if not encounter:
                    return
                self.report_path = self.docs / (label + '-2026-10-16.json')
                camera = player.get_editor_property('player_camera')
                previews = list(unreal.GameplayStatics.get_all_actors_with_tag(self.world, 'NL_ReadyEnemyPreview'))
                enemies = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLEnemyCharacter))
                if encounter.get_state() != unreal.NLEncounterState.READY or encounter.get_alive_count() != 0 or enemies:
                    raise RuntimeError('This capture is only for an idle Ready presentation; combat is active.')
                if not previews:
                    raise RuntimeError('No waiting enemies are visible in the initial Ready presentation.')
                preview_rows = []
                for actor in previews:
                    mesh = actor.get_component_by_class(unreal.SkeletalMeshComponent)
                    preview_rows.append({
                        'name': actor.get_name(), 'class': actor.get_class().get_path_name(),
                        'position_cm': self.vec(actor.get_actor_location()),
                        'tags': [str(tag) for tag in actor.tags],
                        'mesh': mesh.get_editor_property('skeletal_mesh_asset').get_path_name() if mesh else None,
                        'mesh_position_cm': self.vec(mesh.get_world_location()) if mesh else None,
                        'collision': str(mesh.get_collision_enabled()) if mesh else None,
                        'hidden': bool(actor.get_editor_property('hidden')),
                    })
                self.report.update({
                    'map': name, 'pawn_class': player.get_class().get_path_name(),
                    'state': str(encounter.get_state()),
                    'ready_wave_index': encounter.get_entry_wave_index(),
                    'planned': encounter.get_planned_count(), 'spawned': encounter.get_spawned_count(),
                    'alive': encounter.get_alive_count(), 'defeated': encounter.get_defeated_count(),
                    'combat_enemy_actor_count': len(enemies), 'ready_previews': preview_rows,
                    'player_position_cm': self.vec(player.get_actor_location()),
                    'camera_position_cm': self.vec(camera.get_world_location()),
                    'camera_rotation': str(camera.get_world_rotation()),
                    'health': player.get_editor_property('vitals').get_health(),
                    'guard': player.get_editor_property('guard').get_guard(),
                    'melee_damage': player.get_editor_property('blade').get_editor_property('attack_definition').get_editor_property('damage'),
                })
                self.shot = self.docs / (label + '.png')
                self.shot_signature = self.signature(self.shot)
                self.report['screenshot'] = str(self.shot)
                unreal.SystemLibrary.execute_console_command(self.world,
                    'HighResShot 1600x900 filename="' + str(self.shot) + '"')
                self.stage = 'screenshot'
                self.shot_start = time.monotonic()
            elif self.stage == 'screenshot':
                signature = self.signature(self.shot)
                if signature and signature != self.shot_signature and time.monotonic()-self.shot_start > 2:
                    player = unreal.GameplayStatics.get_player_pawn(self.world, 0)
                    encounter = player.get_encounter_controller() if player else None
                    if not encounter or encounter.get_state() != unreal.NLEncounterState.READY or encounter.get_alive_count() != 0:
                        raise RuntimeError('The scene left Ready before its screenshot was saved.')
                    self.report['screenshot_signature'] = signature
                    self.finish()
                elif time.monotonic()-self.shot_start > 20:
                    self.finish('No fresh screenshot produced.')
        except Exception:
            self.finish(traceback.format_exc())
        finally:
            self.busy = False


_ready_presentation = ReadyPresentation()
_ready_presentation.handle = unreal.register_slate_post_tick_callback(_ready_presentation.tick)
unreal.log('READY_PRESENTATION_CAPTURE_REGISTERED')
