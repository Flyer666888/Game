"""Actual main-map PIE with the native VR mode and no XR device; no saved map changes."""
from pathlib import Path
import time
import unreal
P = Path(unreal.Paths.project_dir()).resolve()
source = P / 'Scripts/Editor/Level01PolishV01/runtime_first_level.py'
code = source.read_text(encoding='utf-8-sig')
assert code.count('first_level_probe = FirstLevelProbe()') == 1
code = code.replace('first_level_probe = FirstLevelProbe()', '')
context = {'__name__':'gdd28_vr_probe', '__file__':str(source)}
exec(compile(code,str(source),'exec'), context)
context['O'] = P / 'Docs/Gameplay/GDDSession28/VRRuntime'

class GDD28VRRoute(context['FirstLevelProbe']):
    def begin(self):
        assert self.editor.get_game_world() is None
        assert self.level.load_level(context['MAP'])
        self.ws = self.editor.get_editor_world().get_world_settings()
        self.original_mode = self.ws.get_editor_property('default_game_mode')
        self.ws.set_editor_property('default_game_mode', unreal.load_class(None, '/Script/experiment.NLVRGameMode'))
        self.vr_started = None
        super().begin()

    def bootstrap(self):
        self.world = self.editor.get_game_world()
        if not self.world:
            return
        self.pawn = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        if not self.pawn:
            return
        assert isinstance(self.pawn, unreal.NLVRPlayerCharacter)
        self.director = unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLLevelEncounterDirector)[0]
        assert str(self.director.get_editor_property('level_id')) == self.test_level
        assert not self.pawn.is_ready_for_level_encounter()
        assert self.director.get_active_encounter() is None
        assert str(self.director.get_active_stage_id()) == 'None'
        assert len(unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLEnemyCharacter)) == 0
        if self.vr_started is None:
            self.vr_started = time.monotonic()
        if time.monotonic() - self.vr_started < 6:
            return
        self.report['checks'] = {
            'saved_main_map_uses_native_vr_pawn_under_mode_override':True,
            'untracked_vr_player_not_ready':True,
            'no_encounter_or_enemy_spawned_for_six_seconds_without_devices':True,
        }
        self.report['scope'] = ['Real saved main map in PIE, temporary VR GameMode and unique test LevelId.',
                                'No HMD (-nohmd). This validates startup routing and fail-closed readiness, not physical PICO input.',
                                'No combat simulation and no map/save-profile overwrite.']
        self.finish()

    def cleanup(self):
        if hasattr(self, 'ws') and self.valid(self.ws):
            self.ws.set_editor_property('default_game_mode', self.original_mode)
        super().cleanup()

gdd28_vr = GDD28VRRoute()
